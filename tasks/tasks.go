package tasks

import "encoding/json"

// ---
// QUEUE DEFINITIONS
// ---
// We define all queue names as constants here.
const (
	// QueueVideoTitle is the first step: Generate a title.
	QueueVideoTitle = "q_video_title"

	// QueueSceneGeneration is the new second step: Generate scenes and prompts. (NEW)
	QueueSceneGeneration = "q_scene_generation"

	// QueueVideoScript is the old second/new third step: Generate a script.
	QueueVideoScript = "q_video_script"

	// QueueVideoRender is the third/new fourth step: Render the video.
	QueueVideoRender = "q_video_render"
)

// ---
// TASK PAYLOADS
// ---
// These are the structs that will be JSON-marshalled and sent to Redis.

// TitleTaskPayload is the payload for QueueVideoTitle
type TitleTaskPayload struct {
	VideoID uint `json:"video_id"`
}

// SceneTaskPayload is the payload for QueueSceneGeneration (NEW)
type SceneTaskPayload struct {
	VideoID uint `json:"video_id"`
}

// ScriptTaskPayload is the payload for QueueVideoScript
type ScriptTaskPayload struct {
	VideoID uint `json:"video_id"`
}

// RenderTaskPayload is the payload for QueueVideoRender (DISABLED)
type RenderTaskPayload struct {
	VideoID uint `json:"video_id"`
}

// VideoRenderTaskPayload is an alias for RenderTaskPayload
type VideoRenderTaskPayload = RenderTaskPayload

// ---
// HELPER FUNCTIONS
// ---

// Marshal creates a JSON payload for a task.
func Marshal(payload interface{}) (string, error) {
	b, err := json.Marshal(payload)
	if err != nil {
		return "", err
	}
	return string(b), nil
}
