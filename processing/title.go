package processing

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strings"

	"github.com/drewmudry/instashorts-api/models"
	"github.com/invopop/jsonschema"
	"github.com/openai/openai-go/v3"
	"github.com/openai/openai-go/v3/option"
)

// TitleResponse represents the JSON response from OpenAI
type TitleResponse struct {
	Title string `json:"title" jsonschema_description:"A unique, engaging title for the video"`
}

// GenerateSchema generates a JSON schema for structured outputs
func GenerateSchema[T any]() interface{} {
	reflector := &jsonschema.Reflector{
		AllowAdditionalProperties: false,
		DoNotReference:            true,
	}
	var v T
	schema := reflector.Reflect(v)
	return schema
}

// titleResponseSchema is the cached schema
var titleResponseSchema = GenerateSchema[TitleResponse]()

// GenerateTitle calls OpenAI to generate a unique title for a video
func GenerateTitle(ctx context.Context, series models.Series, existingTitles []string) (string, error) {
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

	rawResponse := chatCompletion.Choices[0].Message.Content
	log.Printf("OpenAI Response: %s", rawResponse)

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
