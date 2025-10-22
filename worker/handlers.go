// drewmudry/instashorts-api/worker/handlers.go
package worker

import (
	"context"
	"encoding/json"
	"log"
	"time"

	"github.com/drewmudry/instashorts-api/models"
	"github.com/drewmudry/instashorts-api/processing"
	"github.com/drewmudry/instashorts-api/tasks"
)

// HandleTitleGeneration processes tasks from the QueueVideoTitle.
func (p *Processor) HandleTitleGeneration(ctx context.Context, payload string) error {
	var task tasks.TitleTaskPayload
	if err := json.Unmarshal([]byte(payload), &task); err != nil {
		return err
	}

	log.Printf("Processing title for video %d", task.VideoID)
	var video models.Video
	if err := p.DB.First(&video, task.VideoID).Error; err != nil {
		return err
	}

	var series models.Series
	if err := p.DB.First(&series, video.SeriesID).Error; err != nil {
		return err
	}

	// Update status
	p.DB.Model(&video).Update("status", "processing_title")

	// Get existing titles
	var existingVideos []models.Video
	p.DB.Where("series_id = ? AND id != ?", video.SeriesID, video.ID).Find(&existingVideos)
	var existingTitles []string
	for _, v := range existingVideos {
		if v.Title != "" {
			existingTitles = append(existingTitles, v.Title)
		}
	}

	// Call business logic
	title, err := processing.GenerateTitle(ctx, series, existingTitles)
	if err != nil {
		p.DB.Model(&video).Update("status", "failed_title")
		return err
	}

	// Save result
	if err := p.DB.Model(&video).Update("title", title).Error; err != nil {
		return err
	}
	log.Printf("Generated title for video %d: %s", video.ID, title)

	// ---
	// Chain to the next step
	// ---
	nextTask := tasks.ScriptTaskPayload{VideoID: video.ID}
	if err := p.Enqueue(ctx, tasks.QueueVideoScript, nextTask); err != nil {
		p.DB.Model(&video).Update("status", "failed_queue_script")
		return err
	}

	log.Printf("Queued video %d for script generation", video.ID)
	p.DB.Model(&video).Update("status", "pending_script")
	return nil
}

// HandleScriptGeneration processes tasks from the QueueVideoScript.
func (p *Processor) HandleScriptGeneration(ctx context.Context, payload string) error {
	var task tasks.ScriptTaskPayload
	if err := json.Unmarshal([]byte(payload), &task); err != nil {
		return err
	}

	log.Printf("Processing script for video %d", task.VideoID)
	var video models.Video
	if err := p.DB.First(&video, task.VideoID).Error; err != nil {
		return err
	}

	var series models.Series
	if err := p.DB.First(&series, video.SeriesID).Error; err != nil {
		return err
	}

	// Update status
	p.DB.Model(&video).Update("status", "processing_script")

	// Call business logic (placeholder)
	script, err := processing.GenerateScript(ctx, video, series)
	if err != nil {
		p.DB.Model(&video).Update("status", "failed_script")
		return err
	}

	// TODO: Save the script to the database
	log.Printf("Generated script for video %d: %s...", video.ID, script[:20])

	// ---
	// Chain to the next step
	// ---
	nextTask := tasks.RenderTaskPayload{VideoID: video.ID}
	if err := p.Enqueue(ctx, tasks.QueueVideoRender, nextTask); err != nil {
		p.DB.Model(&video).Update("status", "failed_queue_render")
		return err
	}

	log.Printf("Queued video %d for rendering", video.ID)
	p.DB.Model(&video).Update("status", "pending_render")
	return nil
}

// HandleRenderVideo processes tasks from the QueueVideoRender.
func (p *Processor) HandleRenderVideo(ctx context.Context, payload string) error {
	var task tasks.RenderTaskPayload
	if err := json.Unmarshal([]byte(payload), &task); err != nil {
		return err
	}

	var video models.Video
	if err := p.DB.First(&video, task.VideoID).Error; err != nil {
		return err
	}

	log.Printf("Rendering video %d (%s)...", task.VideoID, video.Title)
	p.DB.Model(&video).Update("status", "rendering")

	// TODO: Add your actual rendering logic here.

	// Simulate work
	time.Sleep(10 * time.Second)

	// This is the final step
	p.DB.Model(&video).Update("status", "complete")
	log.Printf("Completed video %d", task.VideoID)

	return nil
}
