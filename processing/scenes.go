package processing

import (
	"context"
	"encoding/json"
	"fmt"
	"os"

	"github.com/drewmudry/instashorts-api/models"
	"github.com/openai/openai-go/v3"
	"github.com/openai/openai-go/v3/option"
)

// --- Scene Generation Structs and Logic ---

// SceneBreakdown is the structured output for the first LLM call (scene descriptions)
type SceneBreakdown struct {
	Scenes []SceneDescription `json:"scenes" jsonschema_description:"A list of distinct visual scenes that will make up the video. Aim for 3-5 scenes."`
}

// SceneDescription represents a single scene's details
type SceneDescription struct {
	Description string  `json:"description" jsonschema_description:"A detailed, visual description of the scene's action and setting, without camera details."`
	Duration    float32 `json:"duration" jsonschema_description:"The approximate duration of this scene in seconds (e.g., 2.5). Sum of durations should be around 15-30 seconds."`
}

// PromptGeneration is the structured output for the second LLM call (video prompt)
type PromptGeneration struct {
	Prompt string `json:"prompt" jsonschema_description:"The high-quality text-to-video generation prompt for this scene."`
}

// GenerateSchema is defined in processing/title.go and reused here
var sceneBreakdownSchema = GenerateSchema[SceneBreakdown]()
var promptGenerationSchema = GenerateSchema[PromptGeneration]()

// GenerateScenes generates scene breakdowns for a video title and then creates high-quality
// video generation prompts for each scene.
func GenerateScenes(ctx context.Context, series models.Series, videoTitle string) ([]models.VideoScene, error) {
	apiKey := os.Getenv("OPENAI_API_KEY")
	if apiKey == "" {
		return nil, fmt.Errorf("OPENAI_API_KEY environment variable not set")
	}

	client := openai.NewClient(option.WithAPIKey(apiKey))

	// 1. Scene Breakdown Generation (First LLM Call: Description & Duration)
	// ---------------------------------------------
	breakdownPrompt := fmt.Sprintf(`You are a visual storyteller creating a short vertical video (InstaShorts) for a series titled "%s" with the description "%s".
The video's title is: "%s".
Based on the title, create a visual breakdown of 3 to 5 distinct scenes.
For each scene, provide a detailed description of the setting and action, and an approximate duration in seconds.
The total duration of all scenes should be between 15 and 30 seconds.`,
		series.Title, series.Description, videoTitle)

	breakdownResponse, err := getStructuredResponse[SceneBreakdown](ctx, client, breakdownPrompt, sceneBreakdownSchema)
	if err != nil {
		return nil, fmt.Errorf("failed to generate scene breakdown: %w", err)
	}

	if len(breakdownResponse.Scenes) == 0 {
		return nil, fmt.Errorf("LLM returned no scenes")
	}

	var videoScenes []models.VideoScene

	// Define consistent style and color grading based on the series
	globalStylePrompt := fmt.Sprintf("A %s themed video with a %s color grading, cinematic, 4k, hyperrealistic", series.Title, "vibrant cyberpunk") // Example Style

	// 2. Prompt Generation for Each Scene (Second LLM Call: Detailed Prompt)
	// -------------------------------------------------------------
	for i, sceneDesc := range breakdownResponse.Scenes {

		// Build the high-quality prompt for the current scene
		promptBase := fmt.Sprintf(`Generate a single, hyper-detailed, high-quality text-to-video prompt for a modern AI video model.
The video is part of a series titled "%s" with the overall theme/style: "%s".
The specific scene description is: "%s".
The generated prompt must maintain consistent styling and color grading with the overall theme.
The prompt must be a single, continuous text block and MUST include specific camera movements (e.g., Dolly Zoom, Tracking Shot, Wide Angle, Close-up, Pan-right, Tilt-down) and subject actions.
Do NOT use commas in the generated prompt, only spaces.`,
			series.Title, globalStylePrompt, sceneDesc.Description)

		promptResponse, err := getStructuredResponse[PromptGeneration](ctx, client, promptBase, promptGenerationSchema)
		if err != nil {
			return nil, fmt.Errorf("failed to generate prompt for scene %d: %w", i+1, err)
		}

		videoScenes = append(videoScenes, models.VideoScene{
			SceneNumber: i + 1,
			Description: sceneDesc.Description,
			Prompt:      promptResponse.Prompt,
			Duration:    sceneDesc.Duration,
		})
	}

	return videoScenes, nil
}

// getStructuredResponse is a helper function to call the OpenAI API with JSON schema enforcement
func getStructuredResponse[T any](ctx context.Context, client openai.Client, prompt string, schema interface{}) (*T, error) {
	schemaParam := openai.ResponseFormatJSONSchemaJSONSchemaParam{
		Name:        "structured_response",
		Description: openai.String("Structured data response"),
		Schema:      schema,
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
		return nil, fmt.Errorf("OpenAI API error: %w", err)
	}

	if len(chatCompletion.Choices) == 0 {
		return nil, fmt.Errorf("no response from OpenAI")
	}

	rawResponse := chatCompletion.Choices[0].Message.Content

	var structuredResponse T
	if err := json.Unmarshal([]byte(rawResponse), &structuredResponse); err != nil {
		return nil, fmt.Errorf("failed to parse OpenAI JSON response: %w\nRaw content: %s", err, rawResponse)
	}

	return &structuredResponse, nil
}
