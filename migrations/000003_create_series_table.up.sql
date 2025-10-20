CREATE TABLE IF NOT EXISTS series (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    posts_per_day INT NOT NULL DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_series_user_id ON series(user_id);
CREATE TRIGGER update_series_updated_at BEFORE UPDATE
    ON series FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();