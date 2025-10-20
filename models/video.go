package models

import (
	"time"
)

type Video struct {
	ID        uint      `gorm:"primaryKey" json:"id"`
	SeriesID  uint      `gorm:"not null;index" json:"series_id"`
	Series    Series    `gorm:"foreignKey:SeriesID" json:"-"`
	Status    string    `gorm:"default:'pending'" json:"status"`
	CreatedAt time.Time `json:"created_at"`
}

func (Video) TableName() string {
	return "videos"
}
