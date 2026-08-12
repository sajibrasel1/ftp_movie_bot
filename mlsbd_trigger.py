#!/usr/bin/env python3
"""
MLSBD Movie Bot - cPanel Trigger Script (Production-Ready)
==========================================================
Lightweight crawler that:
- Scrapes the homepage of MLSBD.co for latest movie/series posts
- Resolves Savelinks.me redirect pages to extract GDFlix links
- Checks database for duplicates (by GDFlix URL)
- Triggers GitHub Actions workflow (process_mlsbd_movie.yml) for pending movies

Perfect for cPanel shared hosting (runs without Selenium, using requests only).

Author: AI Assistant
Version: 1.0
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
GITHUB_WORKFLOW_FILE = "process_mlsbd_movie.yml"

# Site configuration
MLSBD_BASE_URL = "https://mlsbd.co"

# Processing limits
MAX_MOVIES_PER_RUN = 1  # Process 1 movie at a time to avoid race conditions
REQUEST_TIMEOUT = 15

# Logging
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "mlsbd_trigger.log"

# =====================================================
# LOGGING SETUP
# =====================================================

# Safe StreamHandler that encodes to sys.stdout.encoding with 'replace' handler
# to prevent UnicodeEncodeError in non-UTF-8 console environments (like Windows cmd)
class SafeStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            encoding = getattr(stream, 'encoding', 'ascii') or 'ascii'
            safe_msg = msg.encode(encoding, 'replace').decode(encoding)
            stream.write(safe_msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        SafeStreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# User-Agent header to emulate real browsers and bypass basic blocks
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

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

def check_movie_exists(cursor, gdflix_url):
    """Check if GDFlix URL already exists in database"""
    try:
        cursor.execute(
            "SELECT id, status FROM mlsbd_movies WHERE gdflix_url = %s",
            (gdflix_url,)
        )
        return cursor.fetchone()
    except Exception as e:
        logger.error(f"Error checking movie existence: {e}")
        return None

def insert_movie(cursor, movie_data):
    """Insert new movie into database"""
    try:
        cursor.execute(
            """
            INSERT INTO mlsbd_movies 
                (movie_title, mlsbd_url, savelinks_url, gdflix_url, 
                 quality, year, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'pending')
            """,
            (
                movie_data["title"],
                movie_data["mlsbd_url"],
                movie_data["savelinks_url"],
                movie_data["gdflix_url"],
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

def get_pending_movies(cursor, limit=1):
    """Get pending movies ready for processing"""
    try:
        cursor.execute(
            """
            SELECT id, movie_title, gdflix_url 
            FROM mlsbd_movies 
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
                UPDATE mlsbd_movies 
                SET status = %s, github_run_id = %s, processing_started_at = NOW()
                WHERE id = %s
                """,
                (status, github_run_id, movie_id)
            )
        elif status == "failed":
            cursor.execute(
                """
                UPDATE mlsbd_movies 
                SET status = %s, error_message = %s, retry_count = retry_count + 1, 
                    last_retry_at = NOW()
                WHERE id = %s
                """,
                (status, error_msg, movie_id)
            )
        else:
            cursor.execute(
                "UPDATE mlsbd_movies SET status = %s WHERE id = %s",
                (status, movie_id)
            )
    except Exception as e:
        logger.error(f"Error updating movie status: {e}")

# =====================================================
# MLSBD SCRAPING & RESOLVING FUNCTIONS
# =====================================================

def parse_quality(text):
    """Extract movie quality from text - ONLY 720p HD"""
    text_upper = text.upper()
    
    # শুধু 720p accept করুন, অন্য সব skip
    if '720P' in text_upper:
        return '720p HD'
    
    # অন্য qualities return None (will be skipped)
    return None

def parse_year(text):
    """Extract year from text"""
    match = re.search(r'\((19|20)\d{2}\)', text)
    if match:
        return int(match.group().strip('()'))
    match_naked = re.search(r'\b(19|20)\d{2}\b', text)
    if match_naked:
        return int(match_naked.group())
    return None

def clean_movie_title(text):
    """Clean MLSBD title to keep user-friendly format"""
    title = unquote(text)
    # Remove text like "Download & Watch Online..."
    title = re.sub(r'Download & Watch Online.*', '', title, flags=re.IGNORECASE)
    # Remove sizes (e.g. 600MB, 1.2GB, 2.3GB)
    title = re.sub(r'\d+(?:\.\d+)?\s*(?:MB|GB)', '', title, flags=re.IGNORECASE)
    # Remove quality and format terms
    terms_to_remove = [
        r'\b(?:480p|720p|1080p|2160p|4k|uhd|fhd|sd|hd)\b',
        r'\b(?:x264|x265|hevc|h264|h265|aac|dd5\.1|dual audio|org)\b',
        r'\b(?:web-?dl|webrip|bluray|brrip|bdrip|dvdrip|hdtc|hdts)\b',
        r'\b(?:bengali|dubbed|hindi|english|tamil|telugu|malayalam|kannada|south)\b',
        r'\b(?:bongobd|zee5|chorki|hoichoi|netflix|amazon|prime|hotstar|sonyliv)\b',
        r'\b(?:utshob)\b'
    ]
    for term in terms_to_remove:
        title = re.sub(term, '', title, flags=re.IGNORECASE)
    
    # Remove year inside parentheses (e.g. (2026))
    title = re.sub(r'\((19|20)\d{2}\)', '', title)
    title = re.sub(r'\b(19|20)\d{2}\b', '', title)
    
    # Remove non-alphanumeric punctuation and special characters
    title = re.sub(r'[\u2013\u2014•|\[\]().,_\-–—]+', ' ', title)
    
    # Clean up whitespace
    title = re.sub(r'\s+', ' ', title).strip()
    return title

def resolve_savelinks(savelinks_url, referer_url):
    """
    Resolve Savelinks.me redirect page using requests.
    Returns the target GDFlix URL if found.
    """
    headers = HEADERS.copy()
    headers['Referer'] = referer_url
    
    try:
        time.sleep(0.5)  # Tiny pause to avoid hitting server too fast
        r = requests.get(savelinks_url, headers=headers, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            logger.warning(f"  ⚠️ Savelinks fetch failed: {r.status_code}")
            return None
            
        soup = BeautifulSoup(r.text, 'html.parser')
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link['href']
            if 'gdflix' in href:
                return href
                
        return None
    except Exception as e:
        logger.error(f"  ❌ Error resolving Savelinks {savelinks_url}: {e}")
        return None

def crawl_mlsbd():
    """
    Crawls MLSBD homepage, extracts new movie posts, 
    and resolves Savelinks -> GDFlix URLs.
    """
    logger.info("🎬 Starting MLSBD Crawl...")
    movies_found = []
    
    try:
        r = requests.get(MLSBD_BASE_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            logger.error(f"❌ Failed to load MLSBD homepage: {r.status_code}")
            return []
            
        soup = BeautifulSoup(r.text, 'html.parser')
        links = soup.find_all('a', href=True)
        
        exclude_patterns = [
            '/category/', '/tag/', '/page/', '/contact-us/', '/about-us/', 
            '/dmca/', '/how-to-download/', '/request/', '/login/', '/register/',
            '/author/', 'mlsbd.co/?', 'mlsbd.co/feed', 'mlsbd.co/comments', '#'
        ]
        
        seen_posts = set()
        year_regex = re.compile(r'\((19|20)\d{2}\)')
        post_links = []
        
        for link in links:
            href = link['href']
            title = link.text.strip()
            
            if href.startswith("https://mlsbd.co/") and title:
                clean_href = href.rstrip('/')
                should_exclude = any(pat in href for pat in exclude_patterns)
                
                if not should_exclude and clean_href != "https://mlsbd.co":
                    if year_regex.search(title):
                        if clean_href not in seen_posts:
                            seen_posts.add(clean_href)
                            post_links.append((title, href))
                            
        logger.info(f"🔍 Found {len(post_links)} movie posts on homepage.")
        
        # Connect to DB to check duplicate links early and reduce requests
        db_conn = get_db_connection()
        if not db_conn:
            return []
        cursor = db_conn.cursor()
        
        for raw_title, post_url in post_links[:8]:  # Scan top 8 posts to keep it fast
            logger.info(f"📰 Scraping post: {raw_title}")
            
            try:
                time.sleep(1)  # Crawl delay
                r_post = requests.get(post_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
                if r_post.status_code != 200:
                    logger.warning(f"  ⚠️ Failed to fetch post page: {r_post.status_code}")
                    continue
                    
                soup_post = BeautifulSoup(r_post.text, 'html.parser')
                post_links_found = soup_post.find_all('a', href=True)
                
                savelinks_list = []
                for link in post_links_found:
                    href = link['href']
                    text = link.text.strip()
                    if 'savelinks.me' in href:
                        savelinks_list.append((text, href))
                        
                logger.info(f"  Found {len(savelinks_list)} Savelinks URLs.")
                
                # Resolve each Savelinks URL to check for GDFlix links
                for text, sv_url in savelinks_list:
                    # Parse quality from text
                    quality = parse_quality(text)
                    
                    # Skip if not 720p
                    if quality is None:
                        continue
                    
                    year = parse_year(raw_title)
                    base_title = clean_movie_title(raw_title)
                    
                    # Form formatted title e.g. "Malik (2026) [1080p Full HD]"
                    full_title = base_title
                    if year:
                        full_title += f" ({year})"
                    full_title += f" [{quality}]"
                    
                    logger.info(f"  🔄 Resolving quality: {quality} ...")
                    
                    gdflix_url = resolve_savelinks(sv_url, post_url)
                    
                    if gdflix_url:
                        logger.info(f"    ✅ Resolved GDFlix: {gdflix_url}")
                        
                        movie_data = {
                            "title": full_title,
                            "mlsbd_url": post_url,
                            "savelinks_url": sv_url,
                            "gdflix_url": gdflix_url,
                            "quality": quality,
                            "year": year
                        }
                        
                        # Double-check database existence
                        existing = check_movie_exists(cursor, gdflix_url)
                        if not existing:
                            inserted_id = insert_movie(cursor, movie_data)
                            if inserted_id:
                                logger.info(f"    ➕ Inserted pending movie to database: ID={inserted_id}")
                                movies_found.append(movie_data)
                        else:
                            logger.info(f"    ⏭️ GDFlix URL already exists in database (status: {existing[1]})")
                    else:
                        logger.warning("    ❌ No GDFlix URL found for this Savelinks redirect.")
                        
            except Exception as e:
                logger.error(f"  ❌ Error scraping post page {post_url}: {e}")
                
        db_conn.commit()
        db_conn.close()
        
    except Exception as e:
        logger.error(f"❌ Error scraping MLSBD homepage: {e}")
        
    return movies_found

# =====================================================
# GITHUB ACTIONS TRIGGER
# =====================================================

def trigger_github_action(movie_id, movie_title, movie_url):
    """Trigger GitHub Actions process_mlsbd_movie workflow"""
    if not GITHUB_TOKEN:
        logger.error("❌ GITHUB_TOKEN environment variable not set!")
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
            logger.info(f"🚀 Successfully triggered GitHub Actions workflow for: {movie_title}")
            return True
        else:
            logger.error(f"❌ GitHub API dispatch failed ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Error triggering GitHub Actions: {e}")
        return False

# =====================================================
# MAIN ROUTINE
# =====================================================

def main():
    logger.info("=" * 80)
    logger.info("🎬 MLSBD CPANEL TRIGGER STARTING")
    logger.info("=" * 80)
    
    db_conn = None
    try:
        # Step 1: Connect to DB and check for pending movies first
        db_conn = get_db_connection()
        if not db_conn:
            logger.error("❌ Database connection failed. Exiting.")
            return
            
        cursor = db_conn.cursor()
        
        logger.info("🔍 Checking for pending/failed movies in database...")
        pending = get_pending_movies(cursor, limit=MAX_MOVIES_PER_RUN)
        
        if pending:
            logger.info(f"✅ Found {len(pending)} pending movie(s). Skipping crawl and processing immediately.")
            for movie_id, movie_title, gdflix_url in pending:
                logger.info(f"🚀 Triggering process for: {movie_title} (ID: {movie_id})")
                
                success = trigger_github_action(movie_id, movie_title, gdflix_url)
                if success:
                    update_movie_status(cursor, movie_id, "processing", github_run_id="triggered")
                    db_conn.commit()
                else:
                    update_movie_status(cursor, movie_id, "failed", error_msg="Failed to trigger GitHub Action dispatch")
                    db_conn.commit()
                    
            logger.info("🎬 Run finished.")
            return
            
        # Step 2: No pending movies, run crawler
        logger.info("ℹ️ No pending movies. Crawling MLSBD homepage...")
        new_movies = crawl_mlsbd()
        logger.info(f"📊 Crawl completed. Found and inserted {len(new_movies)} new movies.")
        
        # Step 3: Trigger for newly added movies
        if new_movies:
            # Re-fetch pending to get their IDs
            pending = get_pending_movies(cursor, limit=MAX_MOVIES_PER_RUN)
            for movie_id, movie_title, gdflix_url in pending:
                logger.info(f"🚀 Triggering process for: {movie_title} (ID: {movie_id})")
                
                success = trigger_github_action(movie_id, movie_title, gdflix_url)
                if success:
                    update_movie_status(cursor, movie_id, "processing", github_run_id="triggered")
                    db_conn.commit()
                else:
                    update_movie_status(cursor, movie_id, "failed", error_msg="Failed to trigger GitHub Action dispatch")
                    db_conn.commit()
                    
    except Exception as e:
        logger.exception(f"❌ Fatal error in main: {e}")
    finally:
        if db_conn:
            db_conn.close()
            
    logger.info("=" * 80)
    logger.info("🎬 MLSBD CPANEL TRIGGER FINISHED")
    logger.info("=" * 80)

if __name__ == "__main__":
    main()
