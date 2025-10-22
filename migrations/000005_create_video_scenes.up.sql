CREATE TABLE IF NOT EXISTS video_scenes (
    id BIGSERIAL PRIMARY KEY,
    video_id BIGINT NOT NULL REFERENCES seriesVideos(id) ON DELETE CASCADE,
    scene_number INT NOT NULL,
    description TEXT NOT NULL,
    prompt TEXT,
    duration REAL DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(video_id, scene_number)
);
CREATE INDEX idx_video_scenes_video_id ON video_scenes(video_id);