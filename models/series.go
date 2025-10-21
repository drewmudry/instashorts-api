package models

import (
	"time"
)

type Series struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	UserID      uint      `gorm:"not null;index" json:"user_id"`
	User        User      `gorm:"foreignKey:UserID" json:"-"`
	Title       string    `gorm:"not null" json:"title"`
	Description string    `json:"description"`
	PostsPerDay int       `gorm:"not null;default:1" json:"posts_per_day"`
	IsActive    bool      `gorm:"default:true" json:"is_active"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`

	// Video count (computed field, not persisted)
	VideoCount int `gorm:"-" json:"video_count"`
}

func (Series) TableName() string {
	return "series"
}
