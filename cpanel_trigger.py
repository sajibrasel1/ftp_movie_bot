#!/usr/bin/env python3
"""
FTP Movie Bot - cPanel Trigger Script
======================================
This lightweight script runs on your cPanel server via cron.
It scrapes ftp.ctgfun.com, checks for new movies, and triggers GitHub Actions.

Resource Usage: ~0.1% CPU, ~25MB RAM, ~2-3 seconds execution time
Perfect for shared hosting limitations.

Cron Schedule: */30 * * * * (every 30 minutes recommended)
"""

import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import mysql.connector
import requests
from bs4 import BeautifulSoup

# =====================================================
# CONFIGURATION
# =====================================================

# Database credentials (update with your actual credentials)
DB_CONFIG = {
    "host": "localhost",
    "user": "techandc_bot",
    "password": "12345Sajibs6@",
    "database": "techandc_prompts",
}

# GitHub configuration
GITHUB_USERNAME = "sajibrasel1"  # Updated with your GitHub username
GITHUB_REPO = "ftp_movie_bot"  # Updated with your repository name
# IMPORTANT: Set GITHUB_TOKEN environment variable before running
# For cPanel: export GITHUB_TOKEN="your_token_here" in ~/.bashrc
# Or pass it in cron: GITHUB_TOKEN=your_token /path/to/script.py
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")  # Token loaded from environment variable

# GitHub API endpoints
GITHUB_API_BASE = f"https://api.github.com/repos/{GITHUB_USERNAME}/{GITHUB_REPO}"
GITHUB_WORKFLOW_FILE = "process_movie.yml"

# FTP site configuration
FTP_BASE_URL = "http://ftp.ctgfun.com"
FTP_MOVIE_PATHS = [
    "/Movies/",
    "/Movies/2024/",
    "/Movies/2025/",
    "/Movies/2026/",
    "/Movies/Hollywood/",
    "/Movies/Bollywood/",
]

# Logging
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "cpanel_trigger.log"

# Limits
MAX_MOVIES_PER_RUN = 5  # Process max 5 movies per cron run
MAX_GITHUB_MINUTES_PER_MONTH = 1800  # Leave 200 minutes buffer (free tier = 2000)

# =====================================================
# LOGGING SETUP
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# =====================================================
# DATABASE FUNCTIONS
# =====================================================

def get_db_connection():
    """Get MySQL database connection"""
    return mysql.connector.connect(**DB_CONFIG)


def check_movie_exists(cursor, movie_url):
    """Check if movie already exists in database"""
    cursor.execute(
        "SELECT id, status FROM ftp_movies WHERE movie_url = %s",
        (movie_url,)
    )
    result = cursor.fetchone()
    return result


def insert_movie(cursor, movie_data):
    """Insert new movie into database"""
    try:
        cursor.execute(
            """
            INSERT INTO ftp_movies 
                (movie_title, movie_url, movie_size_bytes, movie_size_readable, 
                 file_extension, quality, year, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
            """,
            (
                movie_data["title"],
                movie_data["url"],
                movie_data["size_bytes"],
                movie_data["size_readable"],
                movie_data["extension"],
                movie_data["quality"],
                movie_data["year"],
            )
        )
        return cursor.lastrowid
    except mysql.connector.Error as e:
        if e.errno == 1062:  # Duplicate entry
            logger.warning(f"Movie already exists: {movie_data['title']}")
            return None
        raise


def get_pending_movies(cursor, limit=5):
    """Get pending movies ready for processing"""
    cursor.execute(
        """
        SELECT id, movie_title, movie_url, movie_size_bytes 
        FROM ftp_movies 
        WHERE status = 'pending' 
        ORDER BY created_at ASC 
        LIMIT %s
        """,
        (limit,)
    )
    return cursor.fetchall()


def update_movie_status(cursor, movie_id, status, github_run_id=None, error_msg=None):
    """Update movie processing status"""
    if status == "processing":
        cursor.execute(
            """
            UPDATE ftp_movies 
            SET status = %s, github_run_id = %s, processing_started_at = NOW()
            WHERE id = %s
            """,
            (status, github_run_id, movie_id)
        )
    elif status == "failed":
        cursor.execute(
            """
            UPDATE ftp_movies 
            SET status = %s, error_message = %s, retry_count = retry_count + 1, 
                last_retry_at = NOW()
            WHERE id = %s
            """,
            (status, error_msg, movie_id)
        )
    else:
        cursor.execute(
            "UPDATE ftp_movies SET status = %s WHERE id = %s",
            (status, movie_id)
        )


def check_github_quota(cursor):
    """Check if we have GitHub Actions minutes available"""
    current_month = datetime.now().strftime("%Y-%m")
    cursor.execute(
        "SELECT minutes_used, minutes_limit FROM github_actions_usage WHERE month_year = %s",
        (current_month,)
    )
    result = cursor.fetchone()
    
    if result:
        minutes_used, minutes_limit = result
        return minutes_used < MAX_GITHUB_MINUTES_PER_MONTH
    
    # First time this month, create entry
    cursor.execute(
        "INSERT INTO github_actions_usage (month_year, minutes_used, movies_processed) VALUES (%s, 0, 0)",
        (current_month,)
    )
    return True


# =====================================================
# FTP SCRAPING FUNCTIONS
# =====================================================

def parse_movie_title(filename):
    """Extract movie title, year, quality from filename"""
    # Remove extension
    name = os.path.splitext(filename)[0]
    
    # Extract year
    year_match = re.search(r"(19|20)\d{2}", name)
    year = int(year_match.group()) if year_match else None
    
    # Extract quality
    quality = None
    quality_patterns = [
        r"2160p|4K|UHD",
        r"1080p|FullHD|FHD",
        r"720p|HD",
        r"480p|SD",
        r"BluRay|BRRip|BDRip",
        r"WEB-DL|WEBRip",
        r"DVDRip|DVD",
    ]
    for pattern in quality_patterns:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            quality = match.group()
            break
    
    # Clean title (remove quality, year, etc.)
    title = re.sub(r"(19|20)\d{2}", "", name)
    title = re.sub(r"(2160p|4K|1080p|720p|480p|BluRay|WEB-DL|WEBRip|DVDRip|BRRip|BDRip)", "", title, flags=re.IGNORECASE)
    title = re.sub(r"[._-]+", " ", title)
    title = title.strip()
    
    return {
        "title": title,
        "year": year,
        "quality": quality,
    }


def parse_file_size(size_str):
    """Convert size string to bytes"""
    size_str = size_str.strip().upper()
    
    # Extract number and unit
    match = re.match(r"([\d.]+)\s*([KMGT]?B?)", size_str)
    if not match:
        return None
    
    number = float(match.group(1))
    unit = match.group(2)
    
    multipliers = {
        "B": 1,
        "KB": 1024,
        "MB": 1024**2,
        "GB": 1024**3,
        "TB": 1024**4,
    }
    
    multiplier = multipliers.get(unit, 1)
    return int(number * multiplier)


def scrape_ftp_directory(directory_url):
    """Scrape FTP directory listing for movies"""
    movies = []
    
    try:
        response = requests.get(directory_url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Parse directory listing (Apache/Nginx style)
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            
            # Get filename link
            link_tag = cells[0].find("a")
            if not link_tag:
                continue
            
            filename = link_tag.text.strip()
            
            # Skip directories and non-video files
            if filename.endswith("/") or filename == "..":
                continue
            
            extension = os.path.splitext(filename)[1].lower()
            if extension not in [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"]:
                continue
            
            # Get file size
            size_text = cells[1].text.strip() if len(cells) > 1 else "0"
            size_bytes = parse_file_size(size_text)
            
            # Skip small files (< 100MB, probably samples)
            if size_bytes and size_bytes < 100 * 1024 * 1024:
                continue
            
            # Build full URL
            file_url = directory_url.rstrip("/") + "/" + filename
            
            # Parse movie metadata
            metadata = parse_movie_title(filename)
            
            movies.append({
                "title": metadata["title"],
                "url": file_url,
                "size_bytes": size_bytes,
                "size_readable": size_text,
                "extension": extension,
                "quality": metadata["quality"],
                "year": metadata["year"],
            })
            
        logger.info(f"Found {len(movies)} movies in {directory_url}")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error scraping {directory_url}: {e}")
    
    return movies


def scrape_all_directories():
    """Scrape all configured FTP directories"""
    all_movies = []
    
    for path in FTP_MOVIE_PATHS:
        url = FTP_BASE_URL + path
        logger.info(f"Scraping {url}...")
        movies = scrape_ftp_directory(url)
        all_movies.extend(movies)
    
    logger.info(f"Total movies found: {len(all_movies)}")
    return all_movies


# =====================================================
# GITHUB ACTIONS TRIGGER
# =====================================================

def trigger_github_action(movie_id, movie_title, movie_url):
    """Trigger GitHub Action workflow via REST API"""
    url = f"{GITHUB_API_BASE}/actions/workflows/{GITHUB_WORKFLOW_FILE}/dispatches"
    
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }
    
    payload = {
        "ref": "main",  # or "master" depending on your default branch
        "inputs": {
            "movie_id": str(movie_id),
            "movie_title": movie_title,
            "movie_url": movie_url,
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 204:
            logger.info(f"✅ GitHub Action triggered for: {movie_title}")
            return True
        else:
            logger.error(f"❌ GitHub API error {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Failed to trigger GitHub Action: {e}")
        return False


# =====================================================
# MAIN EXECUTION
# =====================================================

def main():
    """Main execution function"""
    logger.info("=" * 80)
    logger.info("FTP Movie Bot - cPanel Trigger Starting")
    logger.info("=" * 80)
    
    db_conn = None
    
    try:
        # Connect to database
        db_conn = get_db_connection()
        cursor = db_conn.cursor()
        
        # Check GitHub Actions quota
        if not check_github_quota(cursor):
            logger.warning("⚠️ GitHub Actions monthly quota reached. Skipping run.")
            return
        
        # Step 1: Scrape FTP directories for new movies
        logger.info("Step 1: Scraping FTP directories...")
        scraped_movies = scrape_all_directories()
        
        # Step 2: Filter out existing movies and add new ones
        logger.info("Step 2: Checking for new movies...")
        new_movies_count = 0
        
        for movie in scraped_movies:
            existing = check_movie_exists(cursor, movie["url"])
            
            if not existing:
                movie_id = insert_movie(cursor, movie)
                if movie_id:
                    new_movies_count += 1
                    logger.info(f"➕ New movie added: {movie['title']} ({movie['size_readable']})")
        
        db_conn.commit()
        logger.info(f"✅ Added {new_movies_count} new movies to database")
        
        # Step 3: Get pending movies and trigger GitHub Actions
        logger.info("Step 3: Triggering GitHub Actions for pending movies...")
        pending_movies = get_pending_movies(cursor, limit=MAX_MOVIES_PER_RUN)
        
        if not pending_movies:
            logger.info("ℹ️ No pending movies to process")
            return
        
        logger.info(f"Found {len(pending_movies)} pending movies")
        
        for movie_id, movie_title, movie_url, movie_size in pending_movies:
            logger.info(f"Processing: {movie_title}")
            
            # Trigger GitHub Action
            success = trigger_github_action(movie_id, movie_title, movie_url)
            
            if success:
                # Update status to processing
                update_movie_status(cursor, movie_id, "processing", github_run_id="triggered")
                db_conn.commit()
                logger.info(f"✅ Triggered processing for: {movie_title}")
            else:
                # Mark as failed
                update_movie_status(cursor, movie_id, "failed", error_msg="Failed to trigger GitHub Action")
                db_conn.commit()
                logger.error(f"❌ Failed to trigger: {movie_title}")
        
        logger.info("=" * 80)
        logger.info("FTP Movie Bot - cPanel Trigger Completed Successfully")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.exception(f"❌ Fatal error in main execution: {e}")
        sys.exit(1)
        
    finally:
        if db_conn:
            db_conn.close()


if __name__ == "__main__":
    main()
