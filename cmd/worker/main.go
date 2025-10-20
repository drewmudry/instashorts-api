package main

import (
	"context"
	"encoding/json"
	"log"
	"os"

	"github.com/go-redis/redis/v8"
	"github.com/joho/godotenv"
	"github.com/robfig/cron/v3"
)

type SeriesCreatedMessage struct {
	SeriesID    uint `json:"series_id"`
	PostsPerDay int  `json:"posts_per_day"`
}

func main() {
	// Load .env file
	if err := godotenv.Load(); err != nil {
		log.Println("No .env file found")
	}

	redisURL := os.Getenv("REDIS_URL")
	if redisURL == "" {
		redisURL = "localhost:6379"
	}

	rdb := redis.NewClient(&redis.Options{
		Addr: redisURL,
	})

	ctx := context.Background()

	// Create a new cron scheduler
	c := cron.New()
	c.Start()
	defer c.Stop()

	pubsub := rdb.Subscribe(ctx, "series_created")
	defer pubsub.Close()

	ch := pubsub.Channel()

	log.Println("Worker started, waiting for messages...")

	for msg := range ch {
		var message SeriesCreatedMessage
		if err := json.Unmarshal([]byte(msg.Payload), &message); err != nil {
			log.Printf("Error unmarshalling message: %v", err)
			continue
		}

		log.Printf("Received message for series %d with %d posts per day", message.SeriesID, message.PostsPerDay)

		// Schedule a new cron job for this series
		_, err := c.AddFunc("@every 1m", func() {
			for i := 0; i < message.PostsPerDay; i++ {
				log.Printf("Logging for series ID: %d", message.SeriesID)
			}
		})
		if err != nil {
			log.Printf("Error scheduling cron job: %v", err)
		}
	}
}
