-- Add 'source' column to ftp_movies table to track where movie came from
-- Run this SQL on your database

USE techandc_prompts;

-- Add source column if it doesn't exist
ALTER TABLE ftp_movies 
ADD COLUMN IF NOT EXISTS source VARCHAR(100) DEFAULT 'ftp.ctgfun.com' 
AFTER status;

-- Create index for faster source-based queries
CREATE INDEX IF NOT EXISTS idx_source ON ftp_movies(source);

-- Update existing movies to have default source
UPDATE ftp_movies 
SET source = 'ftp.ctgfun.com' 
WHERE source IS NULL;

SELECT 'Source column added successfully!' AS status;
