-- Drop trigger and function
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
DROP FUNCTION IF EXISTS update_updated_at_column();

-- Drop indexes
DROP INDEX IF EXISTS idx_users_google_id;
DROP INDEX IF EXISTS idx_users_email;
DROP INDEX IF EXISTS idx_users_referral_code;
DROP INDEX IF EXISTS idx_users_stripe_customer_id;
DROP INDEX IF EXISTS idx_users_referred_by_user_id;

-- Drop table
DROP TABLE IF EXISTS users;