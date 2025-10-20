package series

import (
	"encoding/json"
	"log"
	"net/http"
	"strconv"

	"github.com/drewmudry/instashorts-api/models"
	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
	"gorm.io/gorm"
)

type Handler struct {
	DB    *gorm.DB
	Redis *redis.Client
}

func NewHandler(db *gorm.DB, rdb *redis.Client) *Handler {
	return &Handler{DB: db, Redis: rdb}
}

type CreateSeriesRequest struct {
	Title       string `json:"title" binding:"required"`
	Description string `json:"description"`
	PostsPerDay int    `json:"posts_per_day" binding:"required,min=1,max=3"`
}

type SeriesCreatedMessage struct {
	SeriesID    uint `json:"series_id"`
	PostsPerDay int  `json:"posts_per_day"`
}

func (h *Handler) CreateSeries(c *gin.Context) {
	userID := c.GetUint("user_id")
	var req CreateSeriesRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	series := models.Series{
		UserID:      userID,
		Title:       req.Title,
		Description: req.Description,
		PostsPerDay: req.PostsPerDay,
	}

	if err := h.DB.Create(&series).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create series"})
		return
	}

	// Publish message to Redis
	message := SeriesCreatedMessage{
		SeriesID:    series.ID,
		PostsPerDay: series.PostsPerDay,
	}
	payload, err := json.Marshal(message)
	if err != nil {
		log.Printf("Error marshalling json: %v", err)
	} else {
		err := h.Redis.Publish(c.Request.Context(), "series_created", payload).Err()
		if err != nil {
			log.Printf("Error publishing to redis: %v", err)
		}
	}

	c.JSON(http.StatusOK, series)
}

func (h *Handler) GetUserSeries(c *gin.Context) {
	userID := c.GetUint("user_id")
	var series []models.Series
	if err := h.DB.Where("user_id = ?", userID).Find(&series).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve series"})
		return
	}

	c.JSON(http.StatusOK, series)
}

func (h *Handler) GetSeriesVideos(c *gin.Context) {
	seriesIDStr := c.Param("id")
	seriesID, err := strconv.ParseUint(seriesIDStr, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid series ID"})
		return
	}

	userID := c.GetUint("user_id")

	// First, verify the series belongs to the user
	var series models.Series
	if err := h.DB.First(&series, "id = ? AND user_id = ?", seriesID, userID).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			c.JSON(http.StatusNotFound, gin.H{"error": "Series not found"})
		} else {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Database error"})
		}
		return
	}

	var videos []models.Video
	if err := h.DB.Where("series_id = ?", seriesID).Find(&videos).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve videos"})
		return
	}

	c.JSON(http.StatusOK, videos)
}
