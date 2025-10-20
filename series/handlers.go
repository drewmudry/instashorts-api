package series

import (
	"net/http"

	"github.com/drewmudry/instashorts-api/models"
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

type Handler struct {
	DB *gorm.DB
}

func NewHandler(db *gorm.DB) *Handler {
	return &Handler{DB: db}
}

type CreateSeriesRequest struct {
	Title       string `json:"title" binding:"required"`
	Description string `json:"description"`
	PostsPerDay int    `json:"posts_per_day" binding:"required,min=1,max=3"`
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
