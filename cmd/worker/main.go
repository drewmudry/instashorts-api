package main

import (
	"context"
	"encoding/json"
	"log"
	"time"

	"github.com/drewmudry/instashorts-api/internal/platform"
	"github.com/drewmudry/instashorts-api/models"
	"github.com/go-redis/redis/v8"
	"gorm.io/gorm"
)

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

func main() {
	// Use the shared initializers
	db := platform.NewDBConnection()
	rdb := platform.NewRedisClient()
	ctx := context.Background()

	// Start a goroutine to listen for video tasks and process them
	go listenForVideoTasks(ctx, db, rdb)

	log.Println("Worker started, waiting for queue tasks...")
	// Keep the main thread alive
	select {}
}

// listenForVideoTasks uses a Redis List as a queue to process tasks.
// This is safe to run on multiple worker instances.
func listenForVideoTasks(ctx context.Context, db *gorm.DB, rdb *redis.Client) {
	log.Println("Processor listening for video tasks on the queue...")

	for { // Loop indefinitely
		// BRPop is a blocking command that waits for a task and atomically pops it.
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
			time.Sleep(1 * time.Second)
			log.Printf("Error marshalling render task for video %d: %v", video.ID, err)
			db.Model(&video).Update("status", "failed_script")
			continue
		}

		// Push the next task to the next queue
		err = rdb.LPush(ctx, videoRenderingQueue, payload).Err()
		if err != nil {
			time.Sleep(1 * time.Second)
			log.Printf("Error pushing to render queue for video %d: %v", video.ID, err)
			db.Model(&video).Update("status", "failed_script")
			continue
		}
		time.Sleep(1 * time.Second)
		log.Printf("Script complete for video %d. Queued for rendering.", video.ID)
		db.Model(&video).Update("status", "pending_render")

		// Another worker function would be listening on `videoRenderingQueue`
		// to complete the next step.
		time.Sleep(1 * time.Second)
		db.Model(&video).Update("status", "complete")
	}
}
