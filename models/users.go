package models

import (
	"time"

	"gorm.io/gorm"
)

type User struct {
	ID uint `gorm:"primaryKey" json:"id"`

	// Google OAuth fields
	GoogleID      string `gorm:"uniqueIndex;not null" json:"google_id"`
	Email         string `gorm:"uniqueIndex;not null" json:"email"`
	EmailVerified bool   `gorm:"default:false" json:"email_verified"`

	// Profile from Google
	FullName   string `json:"full_name"`
	GivenName  string `json:"given_name"`
	FamilyName string `json:"family_name"`
	Picture    string `json:"picture"`
	Locale     string `json:"locale"`

	// Application-specific
	Username *string `gorm:"uniqueIndex" json:"username"` // Pointer so it can be null
	IsActive bool    `gorm:"default:true" json:"is_active"`

	// Stripe/Subscription fields
	StripeCustomerID       *string    `gorm:"uniqueIndex" json:"stripe_customer_id,omitempty"`
	StripeConnectAccountID *string    `gorm:"uniqueIndex" json:"stripe_connect_account_id,omitempty"`
	SubscriptionStatus     string     `gorm:"default:free" json:"subscription_status"`
	SubscriptionEndsAt     *time.Time `json:"subscription_ends_at,omitempty"`

	// Referral fields
	ReferralCode          *string `gorm:"uniqueIndex" json:"referral_code,omitempty"`
	ReferredByUserID      *uint   `json:"referred_by_user_id,omitempty"`
	ReferredByUser        *User   `gorm:"foreignKey:ReferredByUserID" json:"referred_by,omitempty"`
	ReferralEarningsCents int64   `gorm:"default:0" json:"referral_earnings_cents"`

	// Timestamps
	CreatedAt   time.Time      `json:"created_at"`
	UpdatedAt   time.Time      `json:"updated_at"`
	LastLoginAt *time.Time     `json:"last_login_at,omitempty"`
	DeletedAt   gorm.DeletedAt `gorm:"index" json:"-"`
}

// TableName overrides the table name
func (User) TableName() string {
	return "users"
}

// Helper methods
func (u *User) IsSubscribed() bool {
	if u.SubscriptionStatus != "active" && u.SubscriptionStatus != "trial" {
		return false
	}
	if u.SubscriptionEndsAt != nil && u.SubscriptionEndsAt.Before(time.Now()) {
		return false
	}
	return true
}

func (u *User) CanEarnReferrals() bool {
	// User must have Stripe Connect set up to receive payouts
	return u.StripeConnectAccountID != nil && *u.StripeConnectAccountID != ""
}

// CreateUserFromGoogle creates a new user from Google OAuth data
type GoogleUserInfo struct {
	ID            string `json:"id"`
	Email         string `json:"email"`
	VerifiedEmail bool   `json:"verified_email"`
	Name          string `json:"name"`
	GivenName     string `json:"given_name"`
	FamilyName    string `json:"family_name"`
	Picture       string `json:"picture"`
	Locale        string `json:"locale"`
}

func CreateUserFromGoogle(info GoogleUserInfo) *User {
	now := time.Now()
	return &User{
		GoogleID:      info.ID,
		Email:         info.Email,
		EmailVerified: info.VerifiedEmail,
		FullName:      info.Name,
		GivenName:     info.GivenName,
		FamilyName:    info.FamilyName,
		Picture:       info.Picture,
		Locale:        info.Locale,
		LastLoginAt:   &now,
	}
}
