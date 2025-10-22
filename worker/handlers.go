package worker

import (
	"context"
	"encoding/json"
	"log"
	"time"

	"github.com/drewmudry/instashorts-api/models"
	"github.com/drewmudry/instashorts-api/processing"
	"github.com/drewmudry/instashorts-api/tasks"
	"gorm.io/gorm" // Import gorm for transaction logic in HandleSceneGeneration
)

// HandleTitleGeneration processes tasks from the QueueVideoTitle.
func (p *Processor) HandleTitleGeneration(ctx context.Context, payload string) error {
	// ... (Load task, video, series, existingTitles - NO CHANGE)
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
	title, err := processing.GenerateTitle(ctx, series, existingTitles) //
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
	// Chain to the NEW next step: Scene Generation
	// ---
	nextTask := tasks.SceneTaskPayload{VideoID: video.ID}
	if err := p.Enqueue(ctx, tasks.QueueSceneGeneration, nextTask); err != nil {
		p.DB.Model(&video).Update("status", "failed_queue_scenes")
		return err
	}

	log.Printf("Queued video %d for scene generation", video.ID)
	p.DB.Model(&video).Update("status", "pending_scenes") // <-- NEW STATUS
	return nil
}

// HandleSceneGeneration processes tasks from the QueueSceneGeneration. (NEW HANDLER)
func (p *Processor) HandleSceneGeneration(ctx context.Context, payload string) error {
	var task tasks.SceneTaskPayload
	if err := json.Unmarshal([]byte(payload), &task); err != nil {
		return err
	}

	log.Printf("Processing scenes for video %d", task.VideoID)
	var video models.Video
	if err := p.DB.First(&video, task.VideoID).Error; err != nil {
		return err
	}

	if video.Title == "" {
		p.DB.Model(&video).Update("status", "failed_scenes_no_title")
		return nil // Should not happen in normal flow, but prevent crash
	}

	var series models.Series
	if err := p.DB.First(&series, video.SeriesID).Error; err != nil {
		return err
	}

	// Update status
	p.DB.Model(&video).Update("status", "processing_scenes")

	// Call business logic to generate scenes and prompts
	scenes, err := processing.GenerateScenes(ctx, series, video.Title)
	if err != nil {
		p.DB.Model(&video).Update("status", "failed_scenes")
		return err
	}

	// Save scenes to database in a single transaction
	err = p.DB.Transaction(func(tx *gorm.DB) error {
		for _, scene := range scenes {
			scene.VideoID = video.ID
			if err := tx.Create(&scene).Error; err != nil {
				return err
			}
		}
		return nil
	})
	if err != nil {
		p.DB.Model(&video).Update("status", "failed_save_scenes")
		return err
	}

	log.Printf("Generated %d scenes and prompts for video %d", len(scenes), video.ID)

	// ---
	// Chain to the next step: Script Generation
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
	// Preload scenes for the script generator to use
	if err := p.DB.Preload("Scenes").First(&video, task.VideoID).Error; err != nil {
		return err
	}

	var series models.Series
	if err := p.DB.First(&series, video.SeriesID).Error; err != nil {
		return err
	}

	// Update status
	p.DB.Model(&video).Update("status", "processing_script")

	// Call business logic (placeholder) - NOW IT SHOULD USE SCENES/TITLE
	script, err := processing.GenerateScript(ctx, video, series) //
	if err != nil {
		p.DB.Model(&video).Update("status", "failed_script")
		return err
	}

	// Save the script to the database
	if err := p.DB.Model(&video).Update("script", script).Error; err != nil {
		return err
	}
	log.Printf("Generated script for video %d: %s...", video.ID, script[:20]) //

	// ---
	// RENDERING DISABLED: Mark video as complete after script generation
	// ---
	// nextTask := tasks.VideoRenderTaskPayload{VideoID: video.ID}
	// if err := p.Enqueue(ctx, tasks.QueueVideoRender, nextTask); err != nil {
	// 	p.DB.Model(&video).Update("status", "failed_queue_render")
	// 	return err
	// }
	// log.Printf("Queued video %d for rendering", video.ID)
	// p.DB.Model(&video).Update("status", "pending_render")

	// Mark as complete since rendering is disabled
	p.DB.Model(&video).Update("status", "complete")
	log.Printf("Video %d processing complete (rendering disabled)", video.ID)
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
