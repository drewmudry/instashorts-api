package main

import (
	"context"
	"encoding/json"
	"log"

	"github.com/drewmudry/instashorts-api/internal/platform" // <-- IMPORT
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

	// Start a goroutine to listen for video tasks and process them
	go listenForVideoTasks(ctx, db, rdb)

	log.Println("Worker started, waiting for messages...")
	// Keep the main thread alive
	select {}
}

// listenForNewSeries subscribes to `series_created` and adds cron jobs
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

		// Create a local copy of the message for the closure
		// to avoid race conditions in the loop.
		m := message

		// Schedule a new cron job for this series.
		// "@daily" runs once a day at midnight. You can change this,
		// e.g., "@every 24h" or more specific cron specs.
		_, err := c.AddFunc("@every 1m", func() {
			log.Printf("Running daily job for series %d: queuing %d videos", m.SeriesID, m.PostsPerDay)

			// This job's only role is to QUEUE the tasks.
			// The other worker will process them.
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

				err = rdb.Publish(ctx, videoProcessingQueue, payload).Err()
				if err != nil {
					log.Printf("Error publishing daily task to %s: %v", videoProcessingQueue, err)
				}
			}
		})
		if err != nil {
			log.Printf("Error scheduling cron job for series %d: %v", message.SeriesID, err)
		}
	}
}

// listenForVideoTasks subscribes to `video_processing_queue` and does the work
func listenForVideoTasks(ctx context.Context, db *gorm.DB, rdb *redis.Client) {
	pubsub := rdb.Subscribe(ctx, videoProcessingQueue)
	defer pubsub.Close()
	ch := pubsub.Channel()

	log.Println("Processor listening for video tasks...")

	for msg := range ch {
		var task VideoProcessingTask
		if err := json.Unmarshal([]byte(msg.Payload), &task); err != nil {
			log.Printf("Error unmarshalling %s message: %v", videoProcessingQueue, err)
			continue
		}

		log.Printf("Received task to process video %d", task.VideoID)

		// --- THIS IS YOUR VIDEO WORKFLOW ---
		// 1. Fetch the video record
		var video models.Video
		if err := db.First(&video, task.VideoID).Error; err != nil {
			log.Printf("Video %d not found: %v", task.VideoID, err)
			continue
		}

		// 2. Mark as processing
		db.Model(&video).Update("status", "processing")
		log.Printf("Processing video %d...", video.ID)

		// 3. TODO: Add your actual video generation logic here
		// (e.g., call OpenAI, generate script, render video)
		// time.Sleep(30 * time.Second) // Simulate long-running task

		// 4. Mark as completed (or failed)
		// For now, we'll just mark it "completed"
		db.Model(&video).Update("status", "completed")
		log.Printf("Completed processing video %d", video.ID)
	}
}
