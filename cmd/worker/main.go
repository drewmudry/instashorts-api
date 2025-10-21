package main

import (
	"context"
	"encoding/json"
	"log"
	"time"

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

// Example task for a chained pipeline
type VideoRenderTask struct {
	VideoID uint `json:"video_id"`
}

const videoProcessingQueue = "video_processing_queue"
const videoRenderingQueue = "video_rendering_queue" // Example for chaining
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

// listenForNewSeries subscribes to `series_created` and adds cron jobs.
// This uses Pub/Sub, so you should only run one instance of the worker service
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
		_, err := c.AddFunc("@daily", func() {
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

				// CORRECT: Use LPUSH to add the task to the queue
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

// listenForVideoTasks uses a Redis List as a queue to process tasks.
// This is safe to run on multiple worker instances.
func listenForVideoTasks(ctx context.Context, db *gorm.DB, rdb *redis.Client) {
	log.Println("Processor listening for video tasks on the queue...")

	for { // Loop indefinitely
		// CORRECT: BRPop is a blocking command that waits for a task and atomically pops it.
		// This ensures only one worker receives any given task.
		result, err := rdb.BRPop(ctx, 0, videoProcessingQueue).Result()
		if err != nil {
			log.Printf("Error popping from queue %s: %v", videoProcessingQueue, err)
			time.Sleep(1 * time.Second)
			continue
		}

		taskPayload := result[1]

		var task VideoProcessingTask
		if err := json.Unmarshal([]byte(taskPayload), &task); err != nil {
			log.Printf("Error unmarshalling %s message: %v", videoProcessingQueue, err)
			continue
		}

		log.Printf("Received task to process video %d", task.VideoID)

		var video models.Video
		if err := db.First(&video, task.VideoID).Error; err != nil {
			log.Printf("Video %d not found: %v", task.VideoID, err)
			continue
		}

		db.Model(&video).Update("status", "processing_script")
		log.Printf("Generating script for video %d...", video.ID)

		// --- EXAMPLE OF A PIPELINE ---
		// 1. TODO: Add your script generation logic here.
		// time.Sleep(10 * time.Second) // Simulate work

		// 2. After script is done, chain to the next step by publishing a new task.
		renderTask := VideoRenderTask{VideoID: video.ID}
		payload, err := json.Marshal(renderTask)
		if err != nil {
			log.Printf("Error marshalling render task for video %d: %v", video.ID, err)
			db.Model(&video).Update("status", "failed_script")
			continue
		}

		// Push the next task to the next queue
		err = rdb.LPush(ctx, videoRenderingQueue, payload).Err()
		if err != nil {
			log.Printf("Error pushing to render queue for video %d: %v", video.ID, err)
			db.Model(&video).Update("status", "failed_script")
			continue
		}

		log.Printf("Script complete for video %d. Queued for rendering.", video.ID)
		db.Model(&video).Update("status", "pending_render")

		// Another worker function would be listening on `videoRenderingQueue`
		// to complete the next step.
	}
}
