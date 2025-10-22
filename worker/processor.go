package worker

import (
	"context"
	"log"

	"github.com/drewmudry/instashorts-api/tasks"
	"github.com/go-redis/redis/v8"
	"gorm.io/gorm"
)

// TaskHandler is a function that processes a task payload.
type TaskHandler func(ctx context.Context, payload string) error

// Processor holds dependencies and registered task handlers.
type Processor struct {
	DB       *gorm.DB
	RDB      *redis.Client
	handlers map[string]TaskHandler
}

// NewProcessor creates a new worker processor.
func NewProcessor(db *gorm.DB, rdb *redis.Client) *Processor {
	return &Processor{
		DB:       db,
		RDB:      rdb,
		handlers: make(map[string]TaskHandler),
	}
}

// Register maps a queue name (task type) to a handler function.
func (p *Processor) Register(queueName string, handler TaskHandler) {
	p.handlers[queueName] = handler
	log.Printf("Registered handler for queue: %s", queueName)
}

// Enqueue is a helper to add a new task to a queue.
func (p *Processor) Enqueue(ctx context.Context, queueName string, payload interface{}) error {
	payloadStr, err := tasks.Marshal(payload)
	if err != nil {
		return err
	}
	return p.RDB.LPush(ctx, queueName, payloadStr).Err()
}

// Listen starts the worker, listening on all registered queues.
func (p *Processor) Listen(ctx context.Context, queueNames ...string) {
	log.Printf("Worker listening on %d queues: %v", len(queueNames), queueNames)

	for {
		// BRPop blocks until a task is available on any of the listed queues.
		result, err := p.RDB.BRPop(ctx, 0, queueNames...).Result()
		if err != nil {
			log.Printf("Error popping from queue: %v", err)
			continue
		}

		// result[0] is the queue name, result[1] is the payload
		queueName := result[0]
		payload := result[1]

		handler, ok := p.handlers[queueName]
		if !ok {
			log.Printf("Error: No handler registered for queue %s", queueName)
			continue
		}

		log.Printf("Received task from queue %s", queueName)

		// Run the handler
		if err := handler(ctx, payload); err != nil {
			log.Printf("Error processing task from %s: %v", queueName, err)
			// TODO: Add error handling (e.g., move to a dead-letter queue)
		}
	}
}
