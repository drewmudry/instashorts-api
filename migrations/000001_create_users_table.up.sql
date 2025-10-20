-- Create users table for Google OAuth
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    
    -- Google OAuth fields
    google_id VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    email_verified BOOLEAN DEFAULT false,
    
    -- Profile information from Google
    full_name VARCHAR(255),
    given_name VARCHAR(255),
    family_name VARCHAR(255),
    picture TEXT, -- Google profile picture URL
    locale VARCHAR(10), -- e.g., 'en-US'
    
    -- Application-specific fields
    username VARCHAR(255) UNIQUE, -- Optional username they can set later
    is_active BOOLEAN DEFAULT true,
    
    -- Subscription/monetization fields (prep for Stripe)
    stripe_customer_id VARCHAR(255) UNIQUE,
    stripe_connect_account_id VARCHAR(255) UNIQUE, -- For receiving payouts
    subscription_status VARCHAR(50) DEFAULT 'free', -- free, trial, active, cancelled, past_due
    subscription_ends_at TIMESTAMP WITH TIME ZONE,
    
    -- Referral prep (you'll link to referral table later)
    referral_code VARCHAR(50) UNIQUE, -- Their unique referral code
    referred_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    referral_earnings_cents BIGINT DEFAULT 0, -- Track total earnings from referrals
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP WITH TIME ZONE,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for performance
CREATE INDEX idx_users_google_id ON users(google_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_referral_code ON users(referral_code);
CREATE INDEX idx_users_stripe_customer_id ON users(stripe_customer_id);
CREATE INDEX idx_users_referred_by_user_id ON users(referred_by_user_id);
CREATE INDEX idx_users_deleted_at ON users(deleted_at);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE
    ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
