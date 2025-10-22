// drewmudry/instashorts-api/series/handlers.go
package series

import (
	"encoding/json"
	"log"
	"net/http"
	"strconv"

	"github.com/drewmudry/instashorts-api/models"
	"github.com/drewmudry/instashorts-api/tasks"
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

const seriesCreatedChannel = "series_created"

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
		IsActive:    true, //
	}

	if err := h.DB.Create(&series).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create series"})
		return
	}

	for i := 0; i < series.PostsPerDay; i++ {
		// 1. Create the 'pending' video record in the database
		video := models.Video{
			SeriesID: series.ID,
			Status:   "pending",
		}
		if err := h.DB.Create(&video).Error; err != nil {
			log.Printf("Error creating pending video record: %v", err)
			continue // Don't fail the whole request
		}

		// 2. Publish a task for the worker to process this specific video
		//    USING THE NEW TASK DEFINITION
		task := tasks.TitleTaskPayload{VideoID: video.ID} // <-- USE NEW PAYLOAD
		payload, err := json.Marshal(task)
		if err != nil {
			log.Printf("Error marshalling video task: %v", err)
			continue
		}

		//    USING THE NEW QUEUE NAME
		err = h.Redis.LPush(c.Request.Context(), tasks.QueueVideoTitle, payload).Err() // <-- USE NEW QUEUE
		if err != nil {
			log.Printf("Error publishing to %s: %v", tasks.QueueVideoTitle, err)
		} else {
			log.Printf("Queued initial video %d for series %d", video.ID, series.ID)
		}
	}

	// Publish message to Redis for the *daily scheduler*
	message := SeriesCreatedMessage{
		SeriesID:    series.ID,
		PostsPerDay: series.PostsPerDay,
	}
	payload, err := json.Marshal(message)
	if err != nil {
		log.Printf("Error marshalling json: %v", err)
	} else {
		err := h.Redis.Publish(c.Request.Context(), seriesCreatedChannel, payload).Err()
		if err != nil {
			log.Printf("Error publishing to %s: %v", seriesCreatedChannel, err)
		}
	}

	c.JSON(http.StatusOK, series)
}

// ... (GetUserSeries and GetSeriesVideos remain unchanged) ...
func (h *Handler) GetUserSeries(c *gin.Context) {
	userID := c.GetUint("user_id")
	var series []models.Series

	if err := h.DB.Where("user_id = ?", userID).Find(&series).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve series"})
		return
	}

	// Populate video count for each series
	for i := range series {
		var count int64
		h.DB.Model(&models.Video{}).Where("series_id = ?", series[i].ID).Count(&count)
		series[i].VideoCount = int(count)
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
	// This query will now automatically pull `title` and `script`
	if err := h.DB.Where("series_id = ?", seriesID).Find(&videos).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to retrieve videos"})
		return
	}

	// This JSON response will now contain `title` and `script`
	c.JSON(http.StatusOK, videos)
}
