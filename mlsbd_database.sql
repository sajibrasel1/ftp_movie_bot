-- =====================================================
-- MLSBD Movie Bot - Database Schema
-- =====================================================
-- This table tracks movies crawled from mlsbd.co
-- Prevents duplicate processing and tracks status
-- =====================================================

CREATE TABLE IF NOT EXISTS mlsbd_movies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    
    -- Movie identification
    movie_title VARCHAR(500) NOT NULL,
    mlsbd_url VARCHAR(500) NOT NULL,            -- The MLSBD post page URL (e.g. https://mlsbd.co/malik-2026-bengali-utshob/)
    savelinks_url VARCHAR(500) DEFAULT NULL,    -- Savelinks URL (e.g. https://savelinks.me/view/ymVLRRyi)
    gdflix_url VARCHAR(500) DEFAULT NULL,        -- Resolved GDFlix URL (e.g. https://gdflix.dev/file/NlfPCAUax8tAokO)
    direct_download_url TEXT DEFAULT NULL,       -- Direct googleusercontent link
    
    -- File information
    movie_size_bytes BIGINT DEFAULT NULL,
    movie_size_readable VARCHAR(50) DEFAULT NULL,
    file_extension VARCHAR(20) DEFAULT NULL,
    quality VARCHAR(50) DEFAULT NULL,            -- e.g., 1080p, 720p, 480p, 4K
    year INT DEFAULT NULL,
    
    -- Processing status
    status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending',
    github_run_id VARCHAR(100) DEFAULT NULL,
    
    -- Split information (if file was split)
    is_split BOOLEAN DEFAULT FALSE,
    total_parts INT DEFAULT 1,
    
    -- Telegram delivery
    telegram_message_ids JSON DEFAULT NULL,      -- Array of message IDs in Telegram
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
    INDEX idx_mlsbd_url (mlsbd_url(255)),
    UNIQUE KEY unique_gdflix_url (gdflix_url(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
