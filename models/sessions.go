package models

import (
	"crypto/rand"
	"encoding/base64"
	"time"

	"gorm.io/gorm"
)

type Session struct {
	ID           uint   `gorm:"primaryKey" json:"id"`
	SessionToken string `gorm:"uniqueIndex;not null" json:"session_token"`
	UserID       uint   `gorm:"not null;index" json:"user_id"`
	User         User   `gorm:"foreignKey:UserID" json:"-"`

	// Security metadata
	UserAgent string `json:"user_agent,omitempty"`
	IPAddress string `json:"ip_address,omitempty"`

	// Lifecycle
	ExpiresAt      time.Time `gorm:"not null;index" json:"expires_at"`
	LastAccessedAt time.Time `json:"last_accessed_at"`
	CreatedAt      time.Time `json:"created_at"`
}

// TableName overrides the table name
func (Session) TableName() string {
	return "sessions"
}

// GenerateSessionToken creates a cryptographically secure random session token
func GenerateSessionToken() (string, error) {
	b := make([]byte, 32) // 32 bytes = 256 bits
	_, err := rand.Read(b)
	if err != nil {
		return "", err
	}
	return base64.URLEncoding.EncodeToString(b), nil
}

// IsExpired checks if the session has expired
func (s *Session) IsExpired() bool {
	return time.Now().After(s.ExpiresAt)
}

// UpdateLastAccessed updates the last accessed timestamp
func (s *Session) UpdateLastAccessed(db *gorm.DB) error {
	s.LastAccessedAt = time.Now()
	return db.Model(s).Update("last_accessed_at", s.LastAccessedAt).Error
}
