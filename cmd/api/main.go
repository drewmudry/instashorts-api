// main.go
package main

import (
	"log"
	"os"

	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"

	"github.com/drewmudry/instashorts-api/auth"
	"github.com/drewmudry/instashorts-api/referrals"
	"github.com/drewmudry/instashorts-api/series"
	stripehandlers "github.com/drewmudry/instashorts-api/stripe"
	"github.com/drewmudry/instashorts-api/webhooks"
)

type Server struct {
	DB     *gorm.DB
	Router *gin.Engine
}

func NewServer() (*Server, error) {
	// Load .env file
	if err := godotenv.Load(); err != nil {
		log.Println("No .env file found")
	}

	// Get database URL from environment
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		dsn = "postgres://postgres:postgres@localhost:5432/instashorts?sslmode=disable"
	}

	// Connect to database with GORM
	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Info), // Set to logger.Silent in production
	})
	if err != nil {
		return nil, err
	}

	// Get underlying SQL database to configure connection pool
	sqlDB, err := db.DB()
	if err != nil {
		return nil, err
	}

	// Configure connection pool
	sqlDB.SetMaxOpenConns(25)
	sqlDB.SetMaxIdleConns(5)

	// Test the connection
	if err := sqlDB.Ping(); err != nil {
		return nil, err
	}

	log.Println("Database connected successfully")

	// Create Gin router with CORS middleware
	router := gin.Default()

	// Add database to context middleware
	router.Use(func(c *gin.Context) {
		c.Set("db", db)
		c.Next()
	})

	// Add CORS middleware for your frontend
	router.Use(func(c *gin.Context) {
		c.Writer.Header().Set("Access-Control-Allow-Origin", os.Getenv("FRONTEND_URL"))
		c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Content-Length, Accept-Encoding, X-CSRF-Token, Authorization, accept, origin, Cache-Control, X-Requested-With")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS, GET, PUT, DELETE")

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}

		c.Next()
	})

	server := &Server{
		DB:     db,
		Router: router,
	}

	// Setup routes
	server.setupRoutes()

	return server, nil
}

func (s *Server) setupRoutes() {
	// Health check (no auth required)
	s.Router.GET("/health", func(c *gin.Context) {
		// Check database connection
		sqlDB, err := s.DB.DB()
		if err != nil {
			c.JSON(500, gin.H{"status": "unhealthy", "error": err.Error()})
			return
		}

		if err := sqlDB.Ping(); err != nil {
			c.JSON(500, gin.H{"status": "unhealthy", "error": err.Error()})
			return
		}

		c.JSON(200, gin.H{
			"status":   "healthy",
			"database": "connected",
		})
	})

	// Create handlers
	authHandler := auth.NewHandler(s.DB)
	referralHandler := referrals.NewHandler(s.DB)
	stripeHandler := stripehandlers.NewHandler(s.DB)
	webhookHandler := webhooks.NewHandler(s.DB)
	seriesHandler := series.NewHandler(s.DB)

	// Public routes
	// Root route - no auth needed
	s.Router.GET("/", func(c *gin.Context) {
		c.JSON(200, gin.H{"message": "Instashorts API v1"})
	})

	// Webhook routes (public - no auth, but signature verified in handler)
	webhookRoutes := s.Router.Group("/webhooks")
	{
		webhookRoutes.POST("/stripe", webhookHandler.HandleStripeWebhook)
	}

	// Auth routes (public - no auth middleware)
	authRoutes := s.Router.Group("/auth")
	{
		authRoutes.GET("/google", authHandler.InitiateGoogleLogin)
		authRoutes.GET("/google/callback", authHandler.GoogleCallback)
		authRoutes.POST("/logout", authHandler.Logout)

		// Protected auth route - requires auth middleware
		authRoutes.GET("/me", auth.AuthMiddleware(), authHandler.GetCurrentUser)
	}

	// Protected routes that require authentication
	protected := s.Router.Group("")
	protected.Use(auth.AuthMiddleware())
	{
		// Referral endpoints
		referralRoutes := protected.Group("/referrals")
		{
			referralRoutes.POST("/code", referralHandler.SetReferralCode)
			referralRoutes.GET("/stats", referralHandler.GetReferralStats)
		}

		// Stripe Connect endpoints
		stripeRoutes := protected.Group("/stripe")
		{
			stripeRoutes.POST("/connect-onboarding", stripeHandler.CreateConnectOnboardingLink)
			stripeRoutes.GET("/connect-status", stripeHandler.GetConnectAccountStatus)
		}

		// Series routes
		seriesRoutes := protected.Group("/series")
		{
			seriesRoutes.POST("", seriesHandler.CreateSeries)
			seriesRoutes.GET("", seriesHandler.GetUserSeries)
			seriesRoutes.GET("/:id/videos", seriesHandler.GetSeriesVideos)
		}

		// Example protected route
		protected.GET("/protected", func(c *gin.Context) {
			userID := c.GetUint("user_id")
			email := c.GetString("email")
			c.JSON(200, gin.H{
				"message": "This is a protected route",
				"user_id": userID,
				"email":   email,
			})
		})

		// Add more protected routes here as needed
		// protected.GET("/videos", videoHandler.GetUserVideos)
		// protected.POST("/videos", videoHandler.CreateVideo)
	}
}

func (s *Server) Run() error {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("🚀 Server starting on port %s", port)
	return s.Router.Run(":" + port)
}

func main() {
	server, err := NewServer()
	if err != nil {
		log.Fatal("Failed to create server:", err)
	}

	if err := server.Run(); err != nil {
		log.Fatal("Failed to run server:", err)
	}
}
