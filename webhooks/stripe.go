package webhooks

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"

	"github.com/drewmudry/instashorts-api/models"
	"github.com/gin-gonic/gin"
	"github.com/stripe/stripe-go/v76"
	"github.com/stripe/stripe-go/v76/transfer"
	"github.com/stripe/stripe-go/v76/webhook"
	"gorm.io/gorm"
)

type Handler struct {
	DB *gorm.DB
}

func NewHandler(db *gorm.DB) *Handler {
	return &Handler{DB: db}
}

// HandleStripeWebhook processes incoming Stripe webhook events
func (h *Handler) HandleStripeWebhook(c *gin.Context) {
	// Read the request body
	payload, err := io.ReadAll(c.Request.Body)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body"})
		return
	}

	// Get Stripe signature from headers
	signatureHeader := c.GetHeader("Stripe-Signature")

	// Verify webhook signature
	webhookSecret := os.Getenv("STRIPE_WEBHOOK_SECRET")
	event, err := webhook.ConstructEvent(payload, signatureHeader, webhookSecret)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid webhook signature"})
		return
	}

	// Handle specific event types
	switch event.Type {
	case "invoice.payment_succeeded":
		h.handleInvoicePaymentSucceeded(event)
	case "account.updated":
		// Optional: Handle Connect account updates
		fmt.Printf("Account updated event received\n")
	default:
		fmt.Printf("Unhandled event type: %s\n", event.Type)
	}

	// Return 200 OK to acknowledge receipt
	c.JSON(http.StatusOK, gin.H{"received": true})
}

// handleInvoicePaymentSucceeded processes successful invoice payments and creates referral transfers
func (h *Handler) handleInvoicePaymentSucceeded(event stripe.Event) {
	var invoice stripe.Invoice
	if err := json.Unmarshal(event.Data.Raw, &invoice); err != nil {
		fmt.Printf("Error parsing invoice: %v\n", err)
		return
	}

	// Get the Stripe customer ID from the invoice
	customerID := invoice.Customer.ID
	if customerID == "" {
		fmt.Printf("No customer ID in invoice\n")
		return
	}

	// Find the user by Stripe customer ID
	var user models.User
	if err := h.DB.Where("stripe_customer_id = ?", customerID).First(&user).Error; err != nil {
		fmt.Printf("User not found for customer ID %s: %v\n", customerID, err)
		return
	}

	// Check if user was referred by someone
	if user.ReferredByUserID == nil {
		fmt.Printf("User %d was not referred by anyone\n", user.ID)
		return
	}

	// Find the referrer
	var referrer models.User
	if err := h.DB.First(&referrer, *user.ReferredByUserID).Error; err != nil {
		fmt.Printf("Referrer not found for user %d: %v\n", user.ID, err)
		return
	}

	// Check if referrer is eligible for payouts
	if !referrer.CanEarnReferrals() {
		fmt.Printf("Referrer %d is not eligible for payouts (no Stripe Connect account)\n", referrer.ID)
		return
	}

	// Calculate commission (20% of the invoice total)
	const commissionRate = 0.20
	invoiceTotal := invoice.AmountPaid // Amount in cents
	commissionAmount := int64(float64(invoiceTotal) * commissionRate)

	if commissionAmount <= 0 {
		fmt.Printf("Commission amount is zero or negative\n")
		return
	}

	// Get the charge ID to link the transfer to the original payment
	var chargeID string
	if invoice.Charge != nil {
		chargeID = invoice.Charge.ID
	}

	// Create a transfer to the referrer's Connect account
	transferParams := &stripe.TransferParams{
		Amount:      stripe.Int64(commissionAmount),
		Currency:    stripe.String(string(invoice.Currency)),
		Destination: stripe.String(*referrer.StripeConnectAccountID),
		Description: stripe.String(fmt.Sprintf("Referral commission for user %d", user.ID)),
	}

	// Link to the original payment if we have a charge ID
	if chargeID != "" {
		transferParams.SourceTransaction = stripe.String(chargeID)
	}

	// Add metadata for tracking
	transferParams.Metadata = map[string]string{
		"referrer_user_id": fmt.Sprintf("%d", referrer.ID),
		"referred_user_id": fmt.Sprintf("%d", user.ID),
		"invoice_id":       invoice.ID,
		"commission_rate":  "0.20",
	}

	// Execute the transfer
	t, err := transfer.New(transferParams)
	if err != nil {
		fmt.Printf("Failed to create transfer: %v\n", err)
		return
	}

	fmt.Printf("Successfully created transfer %s for $%.2f to referrer %d\n",
		t.ID, float64(commissionAmount)/100, referrer.ID)

	// Update referrer's earnings in the database
	referrer.ReferralEarningsCents += commissionAmount
	if err := h.DB.Save(&referrer).Error; err != nil {
		fmt.Printf("Failed to update referrer earnings: %v\n", err)
		return
	}

	fmt.Printf("Updated referrer %d earnings to $%.2f\n",
		referrer.ID, float64(referrer.ReferralEarningsCents)/100)
}
