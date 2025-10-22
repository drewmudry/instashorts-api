package processing

import (
	"context"

	"github.com/drewmudry/instashorts-api/models"
)

// GenerateScript is a placeholder for your script generation logic.
// It fulfills the function call from the worker handler.
func GenerateScript(ctx context.Context, video models.Video, series models.Series) (string, error) {

	// TODO: Add your real script generation logic here (e.g., another OpenAI call)

	// Return the placeholder script as requested
	script := "this is the video script"

	return script, nil
}
