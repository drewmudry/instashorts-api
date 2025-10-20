package stripe

import (
	"fmt"
	"net/http"
	"os"

	"github.com/drewmudry/instashorts-api/models"
	"github.com/gin-gonic/gin"
	"github.com/stripe/stripe-go/v76"
	"github.com/stripe/stripe-go/v76/account"
	"github.com/stripe/stripe-go/v76/accountlink"
	"gorm.io/gorm"
)

type Handler struct {
	DB *gorm.DB
}

func NewHandler(db *gorm.DB) *Handler {
	// Set Stripe API key from environment
	stripe.Key = os.Getenv("STRIPE_SECRET_KEY")
	return &Handler{DB: db}
}

// CreateConnectOnboardingLink creates or retrieves a Stripe Connect account and generates an onboarding link
func (h *Handler) CreateConnectOnboardingLink(c *gin.Context) {
	userID := c.GetUint("user_id")

	// Get user from database
	var user models.User
	if err := h.DB.First(&user, userID).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "User not found"})
		return
	}

	var stripeAccountID string

	// Check if user already has a Stripe Connect account
	if user.StripeConnectAccountID != nil && *user.StripeConnectAccountID != "" {
		stripeAccountID = *user.StripeConnectAccountID
	} else {
		// Create a new Stripe Express account
		params := &stripe.AccountParams{
			Type: stripe.String(string(stripe.AccountTypeExpress)),
			Capabilities: &stripe.AccountCapabilitiesParams{
				Transfers: &stripe.AccountCapabilitiesTransfersParams{
					Requested: stripe.Bool(true),
				},
			},
		}

		// Add user's email if available
		if user.Email != "" {
			params.Email = stripe.String(user.Email)
		}

		acct, err := account.New(params)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create Stripe account"})
			return
		}

		stripeAccountID = acct.ID

		// Save the Stripe Connect account ID to the user
		user.StripeConnectAccountID = &stripeAccountID
		if err := h.DB.Save(&user).Error; err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to save Stripe account ID"})
			return
		}
	}

	// Generate Account Link for onboarding
	frontendURL := os.Getenv("FRONTEND_URL")
	params := &stripe.AccountLinkParams{
		Account:    stripe.String(stripeAccountID),
		RefreshURL: stripe.String(fmt.Sprintf("%s/dashboard/referrals/connect", frontendURL)),
		ReturnURL:  stripe.String(fmt.Sprintf("%s/dashboard/referrals/success", frontendURL)),
		Type:       stripe.String("account_onboarding"),
	}

	link, err := accountlink.New(params)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create onboarding link"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"onboarding_url": link.URL,
		"account_id":     stripeAccountID,
	})
}

// GetConnectAccountStatus checks the status of a user's Stripe Connect account
func (h *Handler) GetConnectAccountStatus(c *gin.Context) {
	userID := c.GetUint("user_id")

	var user models.User
	if err := h.DB.First(&user, userID).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "User not found"})
		return
	}

	if user.StripeConnectAccountID == nil || *user.StripeConnectAccountID == "" {
		c.JSON(http.StatusOK, gin.H{
			"connected":           false,
			"onboarding_complete": false,
		})
		return
	}

	// Retrieve account from Stripe to check status
	acct, err := account.GetByID(*user.StripeConnectAccountID, nil)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve account status"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"connected":           true,
		"onboarding_complete": acct.ChargesEnabled && acct.PayoutsEnabled,
		"charges_enabled":     acct.ChargesEnabled,
		"payouts_enabled":     acct.PayoutsEnabled,
		"details_submitted":   acct.DetailsSubmitted,
	})
}
