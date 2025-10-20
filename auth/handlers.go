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

	// Generate session token
	sessionToken, err := models.GenerateSessionToken()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to generate session"})
		return
	}

	// Create session in database
	session := models.Session{
		SessionToken:   sessionToken,
		UserID:         user.ID,
		UserAgent:      c.Request.UserAgent(),
		IPAddress:      c.ClientIP(),
		ExpiresAt:      time.Now().Add(7 * 24 * time.Hour), // 7 days
		LastAccessedAt: time.Now(),
	}

	if err := h.DB.Create(&session).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create session"})
		return
	}

	// Set session token in secure HttpOnly cookie
	isProduction := os.Getenv("ENV") == "production"
	c.SetSameSite(http.SameSiteLaxMode)
	c.SetCookie(
		"session_token", // name
		sessionToken,    // value
		7*24*60*60,      // maxAge in seconds (7 days)
		"/",             // path
		"",              // domain (empty means current domain)
		isProduction,    // secure (only send over HTTPS in production)
		true,            // httpOnly (not accessible via JavaScript)
	)

	// Clear the oauth_state cookie
	c.SetCookie("oauth_state", "", -1, "/", "", false, true)

	// Redirect to frontend
	frontendURL := os.Getenv("FRONTEND_URL")
	c.Redirect(http.StatusTemporaryRedirect, fmt.Sprintf("%s/dashboard", frontendURL))
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

// Logout handler deletes the session from database and clears cookie
func (h *Handler) Logout(c *gin.Context) {
	// Get session token from cookie
	sessionToken, err := c.Cookie("session_token")
	if err == nil && sessionToken != "" {
		// Delete session from database
		h.DB.Where("session_token = ?", sessionToken).Delete(&models.Session{})
	}

	// Clear session cookie
	c.SetCookie("session_token", "", -1, "/", "", false, true)

	c.JSON(http.StatusOK, gin.H{"message": "Logged out successfully"})
}

func generateStateToken() string {
	// Implement a secure random state generator
	// For now, a simple implementation:
	return fmt.Sprintf("%d", time.Now().UnixNano())
}
