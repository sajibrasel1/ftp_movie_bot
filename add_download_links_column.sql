-- =====================================================
-- Add download_links JSON column to mlsbd_movies table
-- This will store all available download links (GDFlix, MultiCloud, FilePress, etc.)
-- for fallback support
-- =====================================================

USE techandc_prompts;

-- Add download_links column after gdflix_url
ALTER TABLE mlsbd_movies 
ADD COLUMN download_links JSON DEFAULT NULL COMMENT 'All available download links (GDFlix, MultiCloud, FilePress, etc.)' 
AFTER gdflix_url;

-- Add poster_url column if not exists (for movie posters)
ALTER TABLE mlsbd_movies 
ADD COLUMN IF NOT EXISTS poster_url VARCHAR(500) DEFAULT NULL COMMENT 'Movie poster/thumbnail URL from MLSBD' 
AFTER direct_download_url;

-- Verify changes
SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'techandc_prompts'
  AND TABLE_NAME = 'mlsbd_movies'
  AND COLUMN_NAME IN ('download_links', 'poster_url')
ORDER BY ORDINAL_POSITION;

-- Show current table structure
DESCRIBE mlsbd_movies;
