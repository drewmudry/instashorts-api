package models

import (
	"time"
)

type Video struct {
	ID        uint      `gorm:"primaryKey" json:"id"`
	SeriesID  uint      `gorm:"not null;index" json:"series_id"`
	Title     string    `gorm:"size:255" json:"title"`
	Script    string    `gorm:"type:text" json:"script,omitempty"`
	Status    string    `gorm:"default:'pending'" json:"status"`
	CreatedAt time.Time `json:"created_at"`
}

func (Video) TableName() string {
	return "seriesvideos"
}
