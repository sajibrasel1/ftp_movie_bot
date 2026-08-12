-- MLSBD Configuration Table
-- This table stores dynamic configuration like domain, scraping settings, etc.

CREATE TABLE IF NOT EXISTS `mlsbd_config` (
  `config_key` VARCHAR(100) PRIMARY KEY,
  `config_value` TEXT NOT NULL,
  `description` VARCHAR(255) DEFAULT NULL,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insert default configuration
INSERT INTO `mlsbd_config` (`config_key`, `config_value`, `description`) VALUES
('base_url', 'https://mlsbd.co', 'Current MLSBD domain (change when domain changes)'),
('scraper_enabled', '1', 'Enable/disable scraper (1=enabled, 0=disabled)'),
('max_movies_per_run', '5', 'Maximum movies to scrape per cron run'),
('quality_filter', '720p HD', 'Quality to scrape (720p HD, 1080p Full HD, etc.)'),
('scraper_delay', '2', 'Delay in seconds between page requests'),
('last_scrape_time', '', 'Last successful scrape timestamp')
ON DUPLICATE KEY UPDATE 
  `config_value` = VALUES(`config_value`),
  `description` = VALUES(`description`);
