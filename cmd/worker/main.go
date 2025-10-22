package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	"github.com/drewmudry/instashorts-api/internal/platform"
	"github.com/drewmudry/instashorts-api/models"
	"github.com/go-redis/redis/v8"
	"github.com/invopop/jsonschema"
	"github.com/openai/openai-go/v3"
	"github.com/openai/openai-go/v3/option"
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

// TitleResponse represents the JSON response from OpenAI
type TitleResponse struct {
	Title string `json:"title" jsonschema_description:"A unique, engaging title for the video"`
}

// GenerateSchema generates a JSON schema for structured outputs
func GenerateSchema[T any]() interface{} {
	// Structured Outputs uses a subset of JSON schema
	// These flags are necessary to comply with the subset
	reflector := &jsonschema.Reflector{
		AllowAdditionalProperties: false,
		DoNotReference:            true,
	}
	var v T
	schema := reflector.Reflect(v)
	return schema
}

// Generate the JSON schema at initialization time
var titleResponseSchema = GenerateSchema[TitleResponse]()

// generateVideoTitle calls OpenAI to generate a unique title for a video
func generateVideoTitle(ctx context.Context, series models.Series, existingTitles []string) (string, error) {
	apiKey := os.Getenv("OPENAI_API_KEY")
	if apiKey == "" {
		return "", fmt.Errorf("OPENAI_API_KEY environment variable not set")
	}

	client := openai.NewClient(
		option.WithAPIKey(apiKey),
	)

	// Build the prompt
	prompt := fmt.Sprintf(`You are creating a title for a new video in a series.

Series Title: %s
Series Description: %s

The following titles have already been used in this series:
%s

Generate a unique, engaging title for the next video in this series. The title should:
- Be relevant to the series theme
- Be different from all existing titles
- Be catchy and engaging
- Be under 100 characters

Respond in JSON format with this structure:
{
  "title": "your generated title here"
}`, series.Title, series.Description, formatExistingTitles(existingTitles))

	schemaParam := openai.ResponseFormatJSONSchemaJSONSchemaParam{
		Name:        "video_title",
		Description: openai.String("A unique title for a video in a series"),
		Schema:      titleResponseSchema,
		Strict:      openai.Bool(true),
	}

	chatCompletion, err := client.Chat.Completions.New(ctx, openai.ChatCompletionNewParams{
		Messages: []openai.ChatCompletionMessageParamUnion{
			openai.UserMessage(prompt),
		},
		Model: openai.ChatModelGPT4oMini,
		ResponseFormat: openai.ChatCompletionNewParamsResponseFormatUnion{
			OfJSONSchema: &openai.ResponseFormatJSONSchemaParam{
				JSONSchema: schemaParam,
			},
		},
	})

	if err != nil {
		return "", fmt.Errorf("OpenAI API error: %w", err)
	}

	if len(chatCompletion.Choices) == 0 {
		return "", fmt.Errorf("no response from OpenAI")
	}

	// Print the raw LLM response for debugging
	rawResponse := chatCompletion.Choices[0].Message.Content
	log.Printf("OpenAI Response: %s", rawResponse)
	log.Printf("OpenAI Finish Reason: %s", chatCompletion.Choices[0].FinishReason)

	if rawResponse == "" {
		return "", fmt.Errorf("OpenAI returned empty response. Finish reason: %s", chatCompletion.Choices[0].FinishReason)
	}

	// Parse the JSON response
	var titleResp TitleResponse
	if err := json.Unmarshal([]byte(rawResponse), &titleResp); err != nil {
		return "", fmt.Errorf("failed to parse OpenAI JSON response: %w", err)
	}

	title := strings.TrimSpace(titleResp.Title)
	if title == "" {
		return "", fmt.Errorf("OpenAI returned empty title")
	}

	return title, nil
}

// formatExistingTitles formats the list of existing titles for the prompt
func formatExistingTitles(titles []string) string {
	if len(titles) == 0 {
		return "- None (this is the first video)"
	}
	var formatted []string
	for _, title := range titles {
		if title != "" {
			formatted = append(formatted, fmt.Sprintf("- %s", title))
		}
	}
	if len(formatted) == 0 {
		return "- None (this is the first video)"
	}
	return strings.Join(formatted, "\n")
}

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

		// Fetch the parent series
		var series models.Series
		if err := db.First(&series, video.SeriesID).Error; err != nil {
			log.Printf("Series %d not found for video %d: %v", video.SeriesID, video.ID, err)
			db.Model(&video).Update("status", "failed")
			continue
		}

		// Query all existing videos in the series (excluding current video) to get their titles
		var existingVideos []models.Video
		if err := db.Where("series_id = ? AND id != ?", video.SeriesID, video.ID).Find(&existingVideos).Error; err != nil {
			log.Printf("Error querying existing videos for series %d: %v", video.SeriesID, err)
			db.Model(&video).Update("status", "failed")
			continue
		}

		// Extract titles from existing videos
		var existingTitles []string
		for _, v := range existingVideos {
			if v.Title != "" {
				existingTitles = append(existingTitles, v.Title)
			}
		}

		// Generate title using OpenAI
		log.Printf("Generating title for video %d using OpenAI...", video.ID)
		title, err := generateVideoTitle(ctx, series, existingTitles)
		if err != nil {
			log.Printf("Error generating title for video %d: %v", video.ID, err)
			db.Model(&video).Update("status", "failed")
			continue
		}

		// Update video with the generated title
		if err := db.Model(&video).Update("title", title).Error; err != nil {
			log.Printf("Error updating title for video %d: %v", video.ID, err)
			db.Model(&video).Update("status", "failed")
			continue
		}
		log.Printf("Generated title for video %d: %s", video.ID, title)

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
