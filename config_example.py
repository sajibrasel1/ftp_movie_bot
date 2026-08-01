"""
Configuration Template
======================
Copy this file to 'config_local.py' and update with your actual credentials.
Then import from config_local.py instead of hardcoding in main scripts.

IMPORTANT: 'config_local.py' is in .gitignore and will never be committed.
"""

# =====================================================
# DATABASE CONFIGURATION
# =====================================================
DATABASE = {
    "host": "localhost",
    "user": "your_db_user",
    "password": "your_db_password",
    "database": "your_db_name",
}

# =====================================================
# GITHUB CONFIGURATION
# =====================================================
GITHUB = {
    "username": "YOUR_GITHUB_USERNAME",
    "repository": "movie-bot",
    "token": "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "workflow_file": "process_movie.yml",
}

# =====================================================
# TELEGRAM CONFIGURATION
# =====================================================
TELEGRAM = {
    "bot_token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
    "chat_id": "-1001234567890",
}

# =====================================================
# FTP CONFIGURATION
# =====================================================
FTP = {
    "base_url": "http://ftp.ctgfun.com",
    "movie_paths": [
        "/Movies/",
        "/Movies/2024/",
        "/Movies/2025/",
        "/Movies/2026/",
        "/Movies/Hollywood/",
        "/Movies/Bollywood/",
    ],
}

# =====================================================
# PROCESSING LIMITS
# =====================================================
LIMITS = {
    "max_movies_per_run": 5,
    "max_telegram_size_gb": 1.9,
    "max_file_size_gb": 10,
    "max_github_minutes_per_month": 1800,
}

# =====================================================
# LOGGING
# =====================================================
LOGGING = {
    "level": "INFO",
    "log_dir": "logs",
    "cpanel_trigger_log": "cpanel_trigger.log",
}
