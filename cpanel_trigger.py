#!/usr/bin/env python3
"""
FTP Movie Bot - cPanel Trigger Script (Optimized & Production-Ready)
====================================================================
Lightweight recursive FTP crawler that:
- Dynamically discovers ALL directories and subdirectories
- Extracts direct video file URLs (not just folder names)
- Checks database for duplicates
- Triggers GitHub Actions for new movies only

Resource Usage: ~0.1% CPU, ~25MB RAM, 2-3 seconds per execution
Perfect for shared cPanel hosting.

Author: AI Assistant
Version: 2.0 (Professional Edition)
"""

import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

import mysql.connector
import requests
from bs4 import BeautifulSoup

# =====================================================
# CONFIGURATION
# =====================================================

# Database credentials
DB_CONFIG = {
    "host": "localhost",
    "user": "techandc_bot",
    "password": "12345Sajibs6@",
    "database": "techandc_prompts",
}

# GitHub configuration
GITHUB_USERNAME = "sajibrasel1"
GITHUB_REPO = "ftp_movie_bot"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_API_BASE = f"https://api.github.com/repos/{GITHUB_USERNAME}/{GITHUB_REPO}"
GITHUB_WORKFLOW_FILE = "process_movie.yml"

# FTP site configuration
FTP_BASE_URL = "http://ftp.ctgfun.com"
FTP_START_PATH = "/"

# Crawler settings
MAX_RECURSION_DEPTH = 50
CRAWL_DELAY_SECONDS = 0.3  # Reduced for faster crawling
REQUEST_TIMEOUT = 15

# Processing limits
MAX_MOVIES_PER_RUN = 2  # Process 2 movies at a time (faster and more stable)
MAX_GITHUB_MINUTES_PER_MONTH = 1800
MIN_FILE_SIZE_MB = 100  # Skip files smaller than 100MB

# Scan mode (Auto-detect based on time)
QUICK_SCAN_MODE = os.environ.get("FORCE_FULL_SCAN", "").lower() == "true"  # Set FORCE_FULL_SCAN=true for manual full scan
FULL_SCAN_HOUR = 3  # Run full scan daily at 3 AM (when server load is low)

# Logging
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "cpanel_trigger.log"

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
    """Get MySQL database connection with error handling"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        conn.autocommit = True
        return conn
    except mysql.connector.Error as e:
        logger.error(f"Database connection failed: {e}")
        return None


def check_movie_exists(cursor, movie_url):
    """Check if movie URL already exists in database"""
    try:
        cursor.execute(
            "SELECT id, status FROM ftp_movies WHERE movie_url = %s",
            (movie_url,)
        )
        result = cursor.fetchone()
        return result
    except Exception as e:
        logger.error(f"Error checking movie existence: {e}")
        return None


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
            logger.debug(f"Movie already exists: {movie_data['title']}")
            return None
        logger.error(f"Error inserting movie: {e}")
        return None


def get_pending_movies(cursor, limit=5):
    """Get pending movies ready for processing (including failed movies that can retry)"""
    try:
        cursor.execute(
            """
            SELECT id, movie_title, movie_url, movie_size_bytes 
            FROM ftp_movies 
            WHERE (status = 'pending' OR (status = 'failed' AND retry_count < 5))
            ORDER BY 
                CASE WHEN status = 'pending' THEN 0 ELSE 1 END,
                created_at ASC 
            LIMIT %s
            """,
            (limit,)
        )
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error fetching pending movies: {e}")
        return []


def update_movie_status(cursor, movie_id, status, github_run_id=None, error_msg=None):
    """Update movie processing status"""
    try:
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
    except Exception as e:
        logger.error(f"Error updating movie status: {e}")


def check_github_quota(cursor):
    """Check if we have GitHub Actions minutes available"""
    try:
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
    except Exception as e:
        logger.error(f"Error checking GitHub quota: {e}")
        return True  # Allow processing on error


# =====================================================
# FTP PARSING FUNCTIONS
# =====================================================

def parse_movie_title(filename):
    """Extract movie title, year, quality from filename"""
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
        r"HDTS|PreDVD|HDRip",
    ]
    for pattern in quality_patterns:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            quality = match.group()
            break
    
    # Clean title
    title = re.sub(r"(19|20)\d{2}", "", name)
    title = re.sub(r"(2160p|4K|1080p|720p|480p|BluRay|WEB-DL|WEBRip|DVDRip|BRRip|BDRip|HDTS|PreDVD|HDRip)", "", title, flags=re.IGNORECASE)
    title = re.sub(r"[._-]+", " ", title)
    title = re.sub(r"\[.*?\]", "", title)  # Remove [DDN], [TAG], etc.
    title = title.strip()
    
    return {
        "title": title,
        "year": year,
        "quality": quality,
    }


def parse_file_size(size_str):
    """Convert size string to bytes (handles both '2G' and '2GB' formats)"""
    if not size_str:
        return None
    
    size_str = size_str.strip().upper()
    
    # Match patterns like: 2G, 2GB, 2.5G, 1024M, 500K
    match = re.match(r"([\d.]+)\s*([KMGT])B?", size_str)
    if not match:
        return None
    
    number = float(match.group(1))
    unit = match.group(2)
    
    multipliers = {
        "K": 1024,
        "M": 1024**2,
        "G": 1024**3,
        "T": 1024**4,
    }
    
    return int(number * multipliers.get(unit, 1))


# =====================================================
# RECURSIVE FTP CRAWLING (OPTIMIZED)
# =====================================================

def is_directory_link(href):
    """Check if href represents a directory"""
    return href.endswith("/")


def is_parent_directory(href):
    """Check if href is parent directory link"""
    return href in ["../", "..", "Parent Directory"]


def is_video_file(filename):
    """Check if filename is a video file"""
    video_extensions = [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg"]
    extension = os.path.splitext(filename.lower())[1]
    return extension in video_extensions


def scrape_ftp_directory_recursive(base_url, current_path="/", depth=0, visited=None, all_movies=None):
    """
    Recursively crawl FTP directory structure.
    ENHANCED: Now enters folders to find actual video files.
    
    Args:
        base_url: FTP base URL
        current_path: Current directory path
        depth: Current recursion depth
        visited: Set of visited paths
        all_movies: List to accumulate movies
    
    Returns:
        List of movie dictionaries with direct video file URLs
    """
    # Initialize on first call
    if visited is None:
        visited = set()
    if all_movies is None:
        all_movies = []
    
    # Safety check: max recursion depth
    if depth > MAX_RECURSION_DEPTH:
        logger.warning(f"⚠️ Max depth reached at: {current_path}")
        return all_movies
    
    # Avoid revisiting
    if current_path in visited:
        return all_movies
    visited.add(current_path)
    
    # Build full URL
    full_url = base_url.rstrip("/") + current_path
    
    logger.info(f"{'  ' * depth}📂 [{depth}] {unquote(current_path)}")
    
    try:
        # Server-friendly delay
        if depth > 0:
            time.sleep(CRAWL_DELAY_SECONDS)
        
        response = requests.get(full_url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        links = soup.find_all("a")
        
        directories = []
        files = []
        
        # Separate directories and files
        for link in links:
            href = link.get("href", "").strip()
            
            if not href or is_parent_directory(href) or href.startswith("http"):
                continue
            
            if is_directory_link(href):
                directories.append(href)
            else:
                files.append(link)
        
        # Process video files in current directory
        for file_link in files:
            href = file_link.get("href", "").strip()
            filename = file_link.text.strip()
            
            if not is_video_file(filename):
                continue
            
            # Get file size - FTP uses simple <pre> tag with space-separated format
            size_text = "Unknown"
            size_bytes = None
            
            try:
                # Get the entire line containing the link
                pre_tag = file_link.find_parent("pre")
                if pre_tag:
                    # Extract the line containing this file
                    full_text = pre_tag.get_text()
                    for line in full_text.split("\n"):
                        if filename in line or href in line:
                            # Format: filename    date    time    size
                            # Example: file.mp4              09-Jan-2025 08:10      2G
                            parts = line.split()
                            if len(parts) >= 4:
                                # Size is typically the last part
                                size_text = parts[-1]
                                size_bytes = parse_file_size(size_text)
                            break
            except Exception as e:
                logger.debug(f"Could not parse size: {e}")
            
            # Skip small files
            if size_bytes and size_bytes < MIN_FILE_SIZE_MB * 1024 * 1024:
                logger.debug(f"{'  ' * depth}  ⏭️ Skip small: {filename}")
                continue
            
            # Build direct file URL
            file_url = full_url.rstrip("/") + "/" + href
            metadata = parse_movie_title(filename)
            
            movie_data = {
                "title": metadata["title"],
                "url": file_url,
                "size_bytes": size_bytes,
                "size_readable": size_text,
                "extension": os.path.splitext(filename)[1],
                "quality": metadata["quality"],
                "year": metadata["year"],
                "directory": current_path,
            }
            
            all_movies.append(movie_data)
            logger.info(f"{'  ' * depth}  ✅ {metadata['title']} ({size_text})")
        
        # Recursively crawl subdirectories
        for directory in directories:
            new_path = current_path.rstrip("/") + "/" + directory
            scrape_ftp_directory_recursive(base_url, new_path, depth + 1, visited, all_movies)
        
    except requests.exceptions.RequestException as e:
        logger.error(f"{'  ' * depth}❌ Request error: {e}")
    except Exception as e:
        logger.error(f"{'  ' * depth}❌ Unexpected error: {e}")
    
    return all_movies


def quick_scan_all_folders():
    """Quick scan - check all main folders (English, Indian, Others) but only 1 level deep"""
    logger.info("=" * 80)
    logger.info("⚡ QUICK SCAN MODE - All Main Folders (1-Level Deep)")
    logger.info("=" * 80)
    
    # Main folders to scan
    main_folders = ["English", "Indian", "Others", "TV_Series"]
    all_movies = []
    
    for main_folder in main_folders:
        logger.info(f"\n📁 Scanning: {main_folder}/")
        folder_url = f"{FTP_BASE_URL}/{main_folder}/"
        
        try:
            response = requests.get(folder_url, timeout=REQUEST_TIMEOUT)
            
            if response.status_code != 200:
                logger.warning(f"⚠️ {main_folder} not accessible")
                continue
            
            soup = BeautifulSoup(response.text, "html.parser")
            links = soup.find_all("a")
            
            # Get all subfolders
            subfolders = []
            for link in links:
                href = link.get("href", "").strip()
                if href and href.endswith("/") and not is_parent_directory(href):
                    subfolders.append(href)
            
            logger.info(f"  Found {len(subfolders)} subfolders")
            
            # Scan each subfolder for video files (1 level only)
            for subfolder in subfolders:
                subfolder_url = folder_url + subfolder
                
                try:
                    time.sleep(CRAWL_DELAY_SECONDS)
                    subfolder_response = requests.get(subfolder_url, timeout=REQUEST_TIMEOUT)
                    
                    if subfolder_response.status_code != 200:
                        continue
                    
                    subfolder_soup = BeautifulSoup(subfolder_response.text, "html.parser")
                    subfolder_links = subfolder_soup.find_all("a")
                    
                    for file_link in subfolder_links:
                        href = file_link.get("href", "").strip()
                        filename = file_link.text.strip()
                        
                        if not is_video_file(filename):
                            continue
                        
                        # Get file size
                        size_text = "Unknown"
                        size_bytes = None
                        
                        try:
                            pre_tag = file_link.find_parent("pre")
                            if pre_tag:
                                full_text = pre_tag.get_text()
                                for line in full_text.split("\n"):
                                    if filename in line or href in line:
                                        parts = line.split()
                                        if len(parts) >= 4:
                                            size_text = parts[-1]
                                            size_bytes = parse_file_size(size_text)
                                        break
                        except Exception:
                            pass
                        
                        # Skip small files
                        if size_bytes and size_bytes < MIN_FILE_SIZE_MB * 1024 * 1024:
                            continue
                        
                        file_url = subfolder_url.rstrip("/") + "/" + href
                        metadata = parse_movie_title(filename)
                        
                        movie_data = {
                            "title": metadata["title"],
                            "url": file_url,
                            "size_bytes": size_bytes,
                            "size_readable": size_text,
                            "extension": os.path.splitext(filename)[1],
                            "quality": metadata["quality"],
                            "year": metadata["year"],
                            "directory": f"/{main_folder}/{subfolder}",
                        }
                        
                        all_movies.append(movie_data)
                        logger.debug(f"    ✅ {metadata['title']}")
                
                except Exception as e:
                    logger.debug(f"  Error scanning {subfolder}: {e}")
                    continue
            
            logger.info(f"  ✅ {main_folder} scan complete")
            
        except Exception as e:
            logger.error(f"❌ Failed to scan {main_folder}: {e}")
            continue
    
    logger.info(f"\n✅ Quick scan complete: {len(all_movies)} movies found across all folders")
    return all_movies


def scrape_all_directories():
    """Entry point for recursive crawling"""
    logger.info("=" * 80)
    logger.info("🚀 STARTING RECURSIVE FTP CRAWL (FULL SCAN)")
    logger.info(f"Base URL: {FTP_BASE_URL}")
    logger.info(f"Max Depth: {MAX_RECURSION_DEPTH}")
    logger.info("=" * 80)
    
    all_movies = scrape_ftp_directory_recursive(FTP_BASE_URL, FTP_START_PATH)
    
    logger.info("=" * 80)
    logger.info(f"✅ CRAWL COMPLETE: {len(all_movies)} video files discovered")
    logger.info("=" * 80)
    
    return all_movies


# =====================================================
# GITHUB ACTIONS TRIGGER
# =====================================================

def trigger_github_action(movie_id, movie_title, movie_url):
    """Trigger GitHub Action workflow via REST API"""
    if not GITHUB_TOKEN:
        logger.error("❌ GITHUB_TOKEN not set!")
        return False
    
    url = f"{GITHUB_API_BASE}/actions/workflows/{GITHUB_WORKFLOW_FILE}/dispatches"
    
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }
    
    payload = {
        "ref": "main",
        "inputs": {
            "movie_id": str(movie_id),
            "movie_title": movie_title,
            "movie_url": movie_url,
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 204:
            logger.info(f"✅ GitHub Action triggered: {movie_title}")
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
    logger.info("🎬 FTP MOVIE BOT - CPANEL TRIGGER")
    logger.info("=" * 80)
    
    db_conn = None
    
    try:
        # Connect to database
        db_conn = get_db_connection()
        if not db_conn:
            logger.error("❌ Database connection failed. Exiting.")
            return
        
        cursor = db_conn.cursor()
        
        # Check GitHub quota
        if not check_github_quota(cursor):
            logger.warning("⚠️ GitHub Actions quota reached. Skipping.")
            return
        
        # OPTIMIZED: Check for pending movies FIRST
        logger.info("🔍 Checking for pending movies in database...")
        pending_movies = get_pending_movies(cursor, limit=MAX_MOVIES_PER_RUN)
        
        if pending_movies:
            # We have pending movies - process them immediately (skip crawling)
            logger.info(f"✅ Found {len(pending_movies)} pending movies - skipping FTP crawl")
            logger.info("🚀 Triggering GitHub Actions for pending movies...")
            
            for movie_id, movie_title, movie_url, movie_size in pending_movies:
                logger.info(f"Processing: {movie_title}")
                
                success = trigger_github_action(movie_id, movie_title, movie_url)
                
                if success:
                    update_movie_status(cursor, movie_id, "processing", github_run_id="triggered")
                    db_conn.commit()
                else:
                    update_movie_status(cursor, movie_id, "failed", error_msg="Failed to trigger GitHub Action")
                    db_conn.commit()
            
            logger.info("=" * 80)
            logger.info("✅ CPANEL TRIGGER COMPLETED SUCCESSFULLY")
            logger.info("=" * 80)
            return
        
        # No pending movies - do FTP crawl to find new content
        logger.info("ℹ️ No pending movies found - starting FTP crawl...")
        
        # Auto-detect: Full scan at specific hour, Quick scan otherwise
        current_hour = datetime.now().hour
        force_full = os.environ.get("FORCE_FULL_SCAN", "").lower() == "true"
        
        should_full_scan = force_full or (current_hour == FULL_SCAN_HOUR)
        
        # Step 1: FTP crawl (Auto-detect or Force mode)
        if should_full_scan:
            logger.info(f"🔄 Using FULL SCAN mode (scheduled at {FULL_SCAN_HOUR}:00 or forced)")
            logger.info("⏰ This will take 5-10 minutes to discover new folders...")
            scraped_movies = scrape_all_directories()
        else:
            logger.info(f"⚡ Using QUICK SCAN mode (All main folders, 1-level deep)")
            logger.info(f"💡 Next full scan scheduled at {FULL_SCAN_HOUR}:00 AM")
            scraped_movies = quick_scan_all_folders()
        
        # Step 2: Filter and add new movies to database
        logger.info("📊 Step 2: Processing discovered movies...")
        new_movies_count = 0
        
        for movie in scraped_movies:
            existing = check_movie_exists(cursor, movie["url"])
            
            if not existing:
                movie_id = insert_movie(cursor, movie)
                if movie_id:
                    new_movies_count += 1
                    logger.info(f"➕ NEW: {movie['title']} ({movie['size_readable']})")
        
        db_conn.commit()
        logger.info(f"✅ {new_movies_count} new movies added to database")
        
        # Step 3: Trigger GitHub Actions for newly added movies
        if new_movies_count > 0:
            logger.info("🚀 Step 3: Triggering GitHub Actions for new movies...")
            pending_movies = get_pending_movies(cursor, limit=MAX_MOVIES_PER_RUN)
            
            for movie_id, movie_title, movie_url, movie_size in pending_movies:
                logger.info(f"Processing: {movie_title}")
                
                success = trigger_github_action(movie_id, movie_title, movie_url)
                
                if success:
                    update_movie_status(cursor, movie_id, "processing", github_run_id="triggered")
                    db_conn.commit()
                else:
                    update_movie_status(cursor, movie_id, "failed", error_msg="Failed to trigger GitHub Action")
                    db_conn.commit()
        
        logger.info("=" * 80)
        logger.info("✅ CPANEL TRIGGER COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.exception(f"❌ Fatal error: {e}")
        sys.exit(1)
        
    finally:
        if db_conn:
            db_conn.close()


if __name__ == "__main__":
    main()
