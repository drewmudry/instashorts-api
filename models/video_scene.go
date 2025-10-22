package models

import "time"

type VideoScene struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	VideoID     uint      `gorm:"not null;index" json:"video_id"`
	SceneNumber int       `gorm:"not null" json:"scene_number"`
	Description string    `gorm:"type:text;not null" json:"description"`
	Prompt      string    `gorm:"type:text" json:"prompt"`
	Duration    float32   `json:"duration"`
	CreatedAt   time.Time `json:"created_at"`
}

func (VideoScene) TableName() string {
	return "video_scenes"
}
