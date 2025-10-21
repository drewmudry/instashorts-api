package main

import (
	"context"
	"encoding/json"
	"log"

	"github.com/drewmudry/instashorts-api/internal/platform"
	"github.com/drewmudry/instashorts-api/models"
	"github.com/go-redis/redis/v8"
	"github.com/robfig/cron/v3"
	"gorm.io/gorm"
)

// Message for scheduling daily jobs
type SeriesCreatedMessage struct {
	SeriesID    uint `json:"series_id"`
	PostsPerDay int  `json:"posts_per_day"`
}

// Task for processing a single video
type VideoProcessingTask struct {
	VideoID uint `json:"video_id"`
}

const videoProcessingQueue = "video_processing_queue"
const seriesCreatedChannel = "series_created"

func main() {
	// Use the shared initializers
	db := platform.NewDBConnection()
	rdb := platform.NewRedisClient()
	ctx := context.Background()

	// Create a new cron scheduler
	c := cron.New()
	c.Start()
	defer c.Stop()

	// Start a goroutine to listen for new series and schedule them
	go listenForNewSeries(ctx, db, rdb, c)

	log.Println("Scheduler started, waiting for messages...")
	// Keep the main thread alive
	select {}
}

// listenForNewSeries subscribes to `series_created` and adds cron jobs.
// This uses Pub/Sub, so you should only run one instance of this service
// to avoid scheduling duplicate cron jobs.
func listenForNewSeries(ctx context.Context, db *gorm.DB, rdb *redis.Client, c *cron.Cron) {
	pubsub := rdb.Subscribe(ctx, seriesCreatedChannel)
	defer pubsub.Close()
	ch := pubsub.Channel()

	log.Println("Scheduler listening for new series...")

	for msg := range ch {
		var message SeriesCreatedMessage
		if err := json.Unmarshal([]byte(msg.Payload), &message); err != nil {
			log.Printf("Error unmarshalling %s message: %v", seriesCreatedChannel, err)
			continue
		}

		log.Printf("Received new series %d, scheduling %d posts per day", message.SeriesID, message.PostsPerDay)

		m := message

		// Schedule a new cron job for this series to run daily at midnight.
		_, err := c.AddFunc("@every 1m", func() {
			log.Printf("Running daily job for series %d: queuing %d videos", m.SeriesID, m.PostsPerDay)

			for i := 0; i < m.PostsPerDay; i++ {
				video := models.Video{
					SeriesID: m.SeriesID,
					Status:   "pending",
				}
				if err := db.Create(&video).Error; err != nil {
					log.Printf("Error creating daily pending video record: %v", err)
					continue
				}

				task := VideoProcessingTask{VideoID: video.ID}
				payload, err := json.Marshal(task)
				if err != nil {
					log.Printf("Error marshalling daily video task: %v", err)
					continue
				}

				// Use LPUSH to add the task to the queue
				err = rdb.LPush(ctx, videoProcessingQueue, payload).Err()
				if err != nil {
					log.Printf("Error pushing daily task to queue %s: %v", videoProcessingQueue, err)
				}
			}
		})
		if err != nil {
			log.Printf("Error scheduling cron job for series %d: %v", message.SeriesID, err)
		}
	}
}
