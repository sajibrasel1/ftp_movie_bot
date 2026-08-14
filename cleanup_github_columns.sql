-- =====================================================
-- Cleanup GitHub Actions Related Columns
-- Remove unnecessary columns from database
-- =====================================================

USE techandc_prompts;

-- Remove github_run_id column (no longer needed)
ALTER TABLE mlsbd_movies DROP COLUMN IF EXISTS github_run_id;

-- Remove split-related columns (we don't split files anymore)
ALTER TABLE mlsbd_movies DROP COLUMN IF EXISTS is_split;
ALTER TABLE mlsbd_movies DROP COLUMN IF EXISTS total_parts;
ALTER TABLE mlsbd_movies DROP COLUMN IF EXISTS direct_download_url;

-- Remove file info (we only store poster, not movie file)
ALTER TABLE mlsbd_movies DROP COLUMN IF EXISTS file_extension;
ALTER TABLE mlsbd_movies DROP COLUMN IF EXISTS movie_size_bytes;

-- Keep these columns:
-- movie_size_readable (from MLSBD page)
-- poster_url
-- download_links (JSON)
-- All other essential columns

-- Show updated structure
DESCRIBE mlsbd_movies;

SELECT 'GitHub-related columns removed successfully!' AS Status;
