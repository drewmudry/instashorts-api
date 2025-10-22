package main

import (
	"context"
	"log"

	"github.com/drewmudry/instashorts-api/internal/platform"
	"github.com/drewmudry/instashorts-api/tasks"
	"github.com/drewmudry/instashorts-api/worker"
)

func main() {
	// Use the shared initializers
	db := platform.NewDBConnection()
	rdb := platform.NewRedisClient()
	ctx := context.Background()

	// Create the new processor
	proc := worker.NewProcessor(db, rdb)

	// Register all task handlers
	proc.Register(tasks.QueueVideoTitle, proc.HandleTitleGeneration)
	proc.Register(tasks.QueueSceneGeneration, proc.HandleSceneGeneration)
	proc.Register(tasks.QueueVideoScript, proc.HandleScriptGeneration)
	// proc.Register(tasks.QueueVideoRender, proc.HandleRenderVideo) // DISABLED: rendering has issues

	log.Println("Worker started, waiting for queue tasks...")

	// Start listening. This is a blocking call.
	proc.Listen(ctx,
		tasks.QueueVideoTitle,
		tasks.QueueSceneGeneration,
		tasks.QueueVideoScript,
		// tasks.QueueVideoRender, // DISABLED: rendering has issues
	)
}
