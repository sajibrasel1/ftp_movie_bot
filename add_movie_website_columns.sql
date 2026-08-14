-- =====================================================
-- Add columns for movie website (movies.techandclick.site)
-- =====================================================

USE techandc_prompts;

-- Add slug for SEO-friendly URLs (auto-generated from movie_title)
ALTER TABLE mlsbd_movies 
ADD COLUMN slug VARCHAR(500) DEFAULT NULL COMMENT 'SEO-friendly URL slug (e.g., malik-2026-bengali)' 
AFTER movie_title;

-- Add unique index on slug
ALTER TABLE mlsbd_movies 
ADD UNIQUE KEY unique_slug (slug(255));

-- Add view_count for tracking popularity
ALTER TABLE mlsbd_movies 
ADD COLUMN view_count INT DEFAULT 0 COMMENT 'Number of times movie page was viewed' 
AFTER telegram_channel_id;

-- Add is_featured flag for homepage featured movies
ALTER TABLE mlsbd_movies 
ADD COLUMN is_featured BOOLEAN DEFAULT FALSE COMMENT 'Show on homepage as featured movie' 
AFTER view_count;

-- Verify changes
SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'techandc_prompts'
  AND TABLE_NAME = 'mlsbd_movies'
  AND COLUMN_NAME IN ('slug', 'view_count', 'is_featured')
ORDER BY ORDINAL_POSITION;

-- Show updated table structure
DESCRIBE mlsbd_movies;
