-- =====================================================
-- FTP Movie Bot - Database Schema
-- =====================================================
-- This table tracks movies from ftp.ctgfun.com
-- Prevents duplicate processing and tracks status
-- =====================================================

CREATE TABLE IF NOT EXISTS ftp_movies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    
    -- Movie identification
    movie_title VARCHAR(500) NOT NULL,
    movie_url TEXT NOT NULL,
    movie_size_bytes BIGINT DEFAULT NULL,
    movie_size_readable VARCHAR(50) DEFAULT NULL,
    
    -- Processing status
    status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending',
    github_run_id VARCHAR(100) DEFAULT NULL,
    
    -- File information
    file_extension VARCHAR(20) DEFAULT NULL,
    quality VARCHAR(50) DEFAULT NULL,  -- e.g., 1080p, 720p, BluRay
    year INT DEFAULT NULL,
    
    -- Split information (if file was split)
    is_split BOOLEAN DEFAULT FALSE,
    total_parts INT DEFAULT 1,
    part_urls JSON DEFAULT NULL,  -- Array of Telegram message IDs
    
    -- Telegram delivery
    telegram_message_ids JSON DEFAULT NULL,  -- Array of message IDs
    telegram_channel_id VARCHAR(100) DEFAULT NULL,
    
    -- Error tracking
    error_message TEXT DEFAULT NULL,
    retry_count INT DEFAULT 0,
    last_retry_at DATETIME DEFAULT NULL,
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    processing_started_at DATETIME DEFAULT NULL,
    processing_completed_at DATETIME DEFAULT NULL,
    
    -- Indexes for performance
    INDEX idx_status (status),
    INDEX idx_created_at (created_at),
    INDEX idx_movie_url (movie_url(255)),
    UNIQUE KEY unique_movie_url (movie_url(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================
-- Processing Log Table (Optional - for debugging)
-- =====================================================
CREATE TABLE IF NOT EXISTS ftp_movie_processing_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    movie_id INT NOT NULL,
    log_level ENUM('info', 'warning', 'error') DEFAULT 'info',
    log_message TEXT NOT NULL,
    additional_data JSON DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (movie_id) REFERENCES ftp_movies(id) ON DELETE CASCADE,
    INDEX idx_movie_id (movie_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================
-- GitHub Actions Quota Tracking (Optional)
-- =====================================================
CREATE TABLE IF NOT EXISTS github_actions_usage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    month_year VARCHAR(7) NOT NULL,  -- Format: 2026-01
    minutes_used INT DEFAULT 0,
    movies_processed INT DEFAULT 0,
    minutes_limit INT DEFAULT 2000,  -- Free tier limit
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY unique_month (month_year)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================
-- Sample Data (for testing)
-- =====================================================
-- INSERT INTO ftp_movies (movie_title, movie_url, movie_size_bytes, movie_size_readable, status)
-- VALUES 
--     ('Test Movie 2024', 'http://ftp.ctgfun.com/Movies/Test_Movie_2024.mp4', 3500000000, '3.5 GB', 'pending'),
--     ('Sample Film 1080p', 'http://ftp.ctgfun.com/Movies/Sample_Film_1080p.mkv', 2800000000, '2.8 GB', 'pending');

-- =====================================================
-- Useful Queries
-- =====================================================

-- Get all pending movies (ready to process)
-- SELECT * FROM ftp_movies WHERE status = 'pending' ORDER BY created_at ASC LIMIT 10;

-- Get currently processing movies
-- SELECT * FROM ftp_movies WHERE status = 'processing' ORDER BY processing_started_at DESC;

-- Get failed movies that need retry
-- SELECT * FROM ftp_movies WHERE status = 'failed' AND retry_count < 3 ORDER BY last_retry_at ASC;

-- Get today's completed movies
-- SELECT * FROM ftp_movies WHERE status = 'completed' AND DATE(processing_completed_at) = CURDATE();

-- Get monthly statistics
-- SELECT 
--     DATE_FORMAT(created_at, '%Y-%m') as month,
--     COUNT(*) as total_movies,
--     SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
--     SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
--     ROUND(SUM(movie_size_bytes) / 1024 / 1024 / 1024, 2) as total_gb
-- FROM ftp_movies
-- GROUP BY month
-- ORDER BY month DESC;

-- Clean up old failed entries (older than 7 days)
-- DELETE FROM ftp_movies WHERE status = 'failed' AND created_at < DATE_SUB(NOW(), INTERVAL 7 DAY);
