// drewmudry/instashorts-api/cmd/scheduler/main.go
package main

import (
	"context"
	"encoding/json"
	"log"

	"github.com/drewmudry/instashorts-api/internal/platform"
	"github.com/drewmudry/instashorts-api/models"
	"github.com/drewmudry/instashorts-api/tasks"
	"github.com/go-redis/redis/v8"
	"github.com/robfig/cron/v3"
	"gorm.io/gorm"
)

// Message for scheduling daily jobs
type SeriesCreatedMessage struct {
	SeriesID    uint `json:"series_id"`
	PostsPerDay int  `json:"posts_per_day"`
}

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

		// Schedule a new cron job for this series
		// (NOTE: Your "@every 3m" is for testing, change to "@daily" or similar for prod)
		_, err := c.AddFunc("@every 3m", func() {
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

				task := tasks.TitleTaskPayload{VideoID: video.ID}
				payload, err := json.Marshal(task)
				if err != nil {
					log.Printf("Error marshalling daily video task: %v", err)
					continue
				}

				err = rdb.LPush(ctx, tasks.QueueVideoTitle, payload).Err()
				if err != nil {
					log.Printf("Error pushing daily task to queue %s: %v", tasks.QueueVideoTitle, err)
				}
			}
		})
		if err != nil {
			log.Printf("Error scheduling cron job for series %d: %v", message.SeriesID, err)
		}
	}
}
