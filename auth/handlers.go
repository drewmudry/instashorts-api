package auth

import (
	"fmt"
	"net/http"
	"os"
	"time"

	"github.com/drewmudry/instashorts-api/models"
	"github.com/gin-gonic/gin"
	"golang.org/x/oauth2"
	"gorm.io/gorm"
)

type Handler struct {
	DB          *gorm.DB
	GoogleOAuth *GoogleOAuth
}

func NewHandler(db *gorm.DB) *Handler {
	return &Handler{
		DB:          db,
		GoogleOAuth: NewGoogleOAuth(),
	}
}

// InitiateGoogleLogin starts the OAuth flow
func (h *Handler) InitiateGoogleLogin(c *gin.Context) {
	// Generate state token for CSRF protection
	state := generateStateToken()

	// Store state in session or cache (implement based on your needs)
	c.SetCookie("oauth_state", state, 3600, "/", "", false, true)

	// Generate the OAuth URL
	url := h.GoogleOAuth.Config.AuthCodeURL(state, oauth2.AccessTypeOffline)

	// Redirect directly to Google OAuth
	c.Redirect(http.StatusTemporaryRedirect, url)
}

// GoogleCallback handles the OAuth callback
func (h *Handler) GoogleCallback(c *gin.Context) {
	// Verify state token
	state := c.Query("state")
	storedState, _ := c.Cookie("oauth_state")

	if state != storedState {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid state token"})
		return
	}

	// Get authorization code
	code := c.Query("code")
	if code == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "No authorization code"})
		return
	}

	// Exchange code for user info
	googleUser, err := h.GoogleOAuth.GetUserInfo(code)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to get user info"})
		return
	}

	// Find or create user
	var user models.User
	result := h.DB.Where("google_id = ?", googleUser.ID).First(&user)

	if result.Error == gorm.ErrRecordNotFound {
		// Create new user

		user = models.User{
			GoogleID:      googleUser.ID,
			Email:         googleUser.Email,
			EmailVerified: googleUser.VerifiedEmail,
			FullName:      googleUser.Name,
			GivenName:     googleUser.GivenName,
			FamilyName:    googleUser.FamilyName,
			Picture:       googleUser.Picture,
			Locale:        googleUser.Locale,
		}

		if err := h.DB.Create(&user).Error; err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create user"})
			return
		}
	} else if result.Error != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Database error"})
		return
	}

	// Update last login
	now := time.Now()
	user.LastLoginAt = &now
	h.DB.Save(&user)

	// Generate JWT
	token, err := GenerateJWT(user.ID, user.Email)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to generate token"})
		return
	}

	// Redirect to frontend with token
	frontendURL := os.Getenv("FRONTEND_URL")
	c.Redirect(http.StatusTemporaryRedirect, fmt.Sprintf("%s/auth/callback?token=%s", frontendURL, token))
}

// GetCurrentUser returns the authenticated user's info
func (h *Handler) GetCurrentUser(c *gin.Context) {
	userID := c.GetUint("user_id")

	var user models.User
	if err := h.DB.First(&user, userID).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "User not found"})
		return
	}

	c.JSON(http.StatusOK, user)
}

// Logout handler (mainly for clearing cookies if you use them)
func (h *Handler) Logout(c *gin.Context) {
	c.SetCookie("oauth_state", "", -1, "/", "", false, true)
	c.JSON(http.StatusOK, gin.H{"message": "Logged out successfully"})
}

func generateStateToken() string {
	// Implement a secure random state generator
	// For now, a simple implementation:
	return fmt.Sprintf("%d", time.Now().UnixNano())
}
