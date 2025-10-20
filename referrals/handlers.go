package referrals

import (
	"net/http"
	"regexp"
	"strings"

	"github.com/drewmudry/instashorts-api/models"
	"github.com/gin-gonic/gin"
	"github.com/stripe/stripe-go/v76/account"
	"gorm.io/gorm"
)

type Handler struct {
	DB *gorm.DB
}

func NewHandler(db *gorm.DB) *Handler {
	return &Handler{DB: db}
}

type SetReferralCodeRequest struct {
	ReferralCode string `json:"referral_code" binding:"required"`
}

// SetReferralCode allows users to set their unique referral code
func (h *Handler) SetReferralCode(c *gin.Context) {
	// Get authenticated user ID from context
	userID := c.GetUint("user_id")

	var req SetReferralCodeRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	// Validate referral code format
	// Only allow alphanumeric characters and underscores, 3-20 characters
	req.ReferralCode = strings.ToLower(strings.TrimSpace(req.ReferralCode))
	matched, _ := regexp.MatchString("^[a-z0-9_]{3,20}$", req.ReferralCode)
	if !matched {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Referral code must be 3-20 characters and contain only letters, numbers, and underscores",
		})
		return
	}

	// Check if code is already in use
	var existingUser models.User
	if err := h.DB.Where("referral_code = ?", req.ReferralCode).First(&existingUser).Error; err == nil {
		c.JSON(http.StatusConflict, gin.H{"error": "This referral code is already taken"})
		return
	} else if err != gorm.ErrRecordNotFound {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Database error"})
		return
	}

	// Update user's referral code
	var user models.User
	if err := h.DB.First(&user, userID).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "User not found"})
		return
	}

	// Check if user has Stripe Connect account set up
	if user.StripeConnectAccountID == nil || *user.StripeConnectAccountID == "" {
		c.JSON(http.StatusForbidden, gin.H{
			"error":   "Stripe Connect account required",
			"message": "You must connect your Stripe account before setting up a referral code. This ensures you can receive commission payments.",
		})
		return
	}

	// Verify the Stripe account is fully onboarded (payouts enabled)
	acct, err := account.GetByID(*user.StripeConnectAccountID, nil)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to verify Stripe account status"})
		return
	}

	if !acct.PayoutsEnabled {
		c.JSON(http.StatusForbidden, gin.H{
			"error":   "Stripe Connect onboarding incomplete",
			"message": "Please complete your Stripe Connect onboarding to enable payouts before setting up a referral code.",
		})
		return
	}

	user.ReferralCode = &req.ReferralCode
	if err := h.DB.Save(&user).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to update referral code"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message":       "Referral code set successfully",
		"referral_code": req.ReferralCode,
	})
}

// GetReferralStats returns referral statistics for the authenticated user
func (h *Handler) GetReferralStats(c *gin.Context) {
	userID := c.GetUint("user_id")

	var user models.User
	if err := h.DB.First(&user, userID).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "User not found"})
		return
	}

	// Count referred users
	var referredCount int64
	h.DB.Model(&models.User{}).Where("referred_by_user_id = ?", userID).Count(&referredCount)

	c.JSON(http.StatusOK, gin.H{
		"referral_code":           user.ReferralCode,
		"referred_users_count":    referredCount,
		"referral_earnings_cents": user.ReferralEarningsCents,
		"can_earn_referrals":      user.CanEarnReferrals(),
	})
}
