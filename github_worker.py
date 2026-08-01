#!/usr/bin/env python3
"""
FTP Movie Bot - GitHub Worker Script (Optimized & Production-Ready)
===================================================================
Runs on GitHub Actions runner with massive resources.
Handles:
- Downloading movies from FTP (uses GitHub's bandwidth & disk)
- Smart file splitting if >1.9GB (FFmpeg -c copy, no quality loss)
- Reliable Telegram upload with retry logic
- Automatic cleanup (deletes all temp files)

Resources Available:
- 14 GB disk space
- 7 GB RAM
- 6-hour timeout
- Dedicated CPU cores

Author: AI Assistant
Version: 2.0 (Professional Edition)
"""

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import mysql.connector
import requests

# =====================================================
# CONFIGURATION FROM ENVIRONMENT VARIABLES
# =====================================================

MOVIE_ID = os.environ.get("MOVIE_ID")
MOVIE_TITLE = os.environ.get("MOVIE_TITLE")
MOVIE_URL = os.environ.get("MOVIE_URL")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_NAME = os.environ.get("DB_NAME")

# Processing limits
MAX_TELEGRAM_SIZE = 1_900_000_000  # 1.9 GB (try with new bot token)
MAX_FILE_SIZE_FOR_PROCESSING = 10_000_000_000  # 10 GB max

# Retry configuration
MAX_DOWNLOAD_RETRIES = None  # None = unlimited retries (will keep trying until success)
MAX_UPLOAD_RETRIES = 5  # Telegram upload retries (increased for large files)
RETRY_DELAY = 10  # Retry delay in seconds
# GitHub Actions has 6-hour timeout, so it will retry within that time
RETRY_DELAY_BASE = 5  # Base delay in seconds (will increase: 5s, 10s, 15s... up to 60s max)

# =====================================================
# LOGGING SETUP
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# =====================================================
# DATABASE FUNCTIONS
# =====================================================

def get_db_connection():
    """Get MySQL database connection"""
    if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
        logger.warning("⚠️ Database credentials not provided - database updates will be skipped")
        return None
    
    # Skip database connection if running from GitHub (can't connect to cPanel MySQL)
    if DB_HOST == "localhost":
        logger.warning("⚠️ Database host is localhost - skipping database connection (GitHub runner can't access cPanel MySQL)")
        return None
    
    try:
        return mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            connect_timeout=10,
        )
    except mysql.connector.Error as e:
        logger.warning(f"⚠️ Database connection failed: {e} - continuing without database updates")
        return None


def update_movie_status(db_conn, status, **kwargs):
    """Update movie status in database"""
    if not db_conn or not MOVIE_ID:
        return
    
    try:
        cursor = db_conn.cursor()
        
        updates = [f"status = '{status}'"]
        
        if "is_split" in kwargs:
            updates.append(f"is_split = {1 if kwargs['is_split'] else 0}")
        if "total_parts" in kwargs:
            updates.append(f"total_parts = {kwargs['total_parts']}")
        if "telegram_message_ids" in kwargs:
            msg_ids_json = json.dumps(kwargs["telegram_message_ids"])
            updates.append(f"telegram_message_ids = '{msg_ids_json}'")
        if "telegram_channel_id" in kwargs:
            updates.append(f"telegram_channel_id = '{kwargs['telegram_channel_id']}'")
        if "error_message" in kwargs:
            error_msg = kwargs["error_message"].replace("'", "''")
            updates.append(f"error_message = '{error_msg}'")
        
        if status == "completed":
            updates.append("processing_completed_at = NOW()")
        
        query = f"UPDATE ftp_movies SET {', '.join(updates)} WHERE id = {MOVIE_ID}"
        cursor.execute(query)
        db_conn.commit()
        
        logger.info(f"✅ Database updated: status={status}")
        
    except Exception as e:
        logger.error(f"❌ Failed to update database: {e}")


# =====================================================
# FILE DOWNLOAD OPERATIONS
# =====================================================

def download_file(url, output_path, max_retries=None):
    """
    Download file from URL with progress tracking, error handling, and unlimited retry logic.
    Downloads to GitHub runner (not cPanel server).
    
    Args:
        url: FTP URL to download from
        output_path: Local path to save file
        max_retries: Maximum retry attempts (None = unlimited)
    """
    logger.info(f"📥 Downloading from: {url}")
    logger.info(f"💾 Saving to: {output_path}")
    
    attempt = 0
    
    while True:
        attempt += 1
        
        # Check if we've exceeded max retries (if set)
        if max_retries is not None and attempt > max_retries:
            logger.error(f"❌ All {max_retries} download attempts failed")
            raise Exception(f"Failed to download after {max_retries} attempts")
        
        try:
            logger.info(f"🔄 Download attempt #{attempt}" + (" (unlimited retries)" if max_retries is None else f"/{max_retries}"))
            
            # Use longer timeout and connection settings
            response = requests.get(
                url, 
                stream=True, 
                timeout=(30, 300),  # (connect timeout, read timeout)
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Connection': 'keep-alive',
                }
            )
            response.raise_for_status()
            
            total_size = int(response.headers.get("content-length", 0))
            logger.info(f"📊 File size: {total_size / (1024**3):.2f} GB")
            
            if total_size > MAX_FILE_SIZE_FOR_PROCESSING:
                raise ValueError(f"File too large: {total_size / (1024**3):.2f} GB")
            
            downloaded = 0
            chunk_size = 1024 * 1024  # 1 MB chunks (smaller for stability)
            
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Log progress every 100 MB
                        if downloaded % (100 * 1024 * 1024) < chunk_size:
                            progress = (downloaded / total_size) * 100 if total_size else 0
                            logger.info(f"📥 Progress: {downloaded / (1024**3):.2f} GB / {total_size / (1024**3):.2f} GB ({progress:.1f}%)")
            
            actual_size = os.path.getsize(output_path)
            logger.info(f"✅ Download complete: {actual_size / (1024**3):.2f} GB")
            
            return actual_size
            
        except (requests.exceptions.RequestException, Exception) as e:
            logger.error(f"❌ Download attempt #{attempt} failed: {e}")
            
            # Clean up partial download
            if os.path.exists(output_path):
                os.remove(output_path)
                logger.info(f"🗑️ Removed partial download")
            
            # Calculate exponential backoff wait time (cap at 60 seconds)
            wait_time = min(attempt * 5, 60)
            logger.info(f"⏳ Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
            
            # Continue to next iteration (retry)


# =====================================================
# VIDEO PROCESSING (FFmpeg)
# =====================================================

def get_video_duration(video_path):
    """Get video duration in seconds using FFprobe"""
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        logger.info(f"⏱️ Video duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
        return duration
        
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ FFprobe failed: {e}")
        return None
    except ValueError:
        logger.error("❌ Could not parse video duration")
        return None


def split_video(input_path, file_size):
    """
    Split video into parts under MAX_TELEGRAM_SIZE using FFmpeg.
    Uses -c copy (no re-encoding, no quality loss).
    """
    logger.info(f"✂️ File size ({file_size / (1024**3):.2f} GB) exceeds Telegram limit")
    logger.info("📦 Splitting video into parts...")
    
    # Calculate number of parts needed
    num_parts = (file_size // MAX_TELEGRAM_SIZE) + 1
    logger.info(f"📊 Will split into {num_parts} parts")
    
    # Get video duration
    duration = get_video_duration(input_path)
    if not duration:
        # Fallback: estimate 1 hour per GB
        segment_time = 3600
    else:
        segment_time = int(duration / num_parts)
    
    logger.info(f"⏱️ Segment duration: {segment_time} seconds ({segment_time/60:.2f} minutes)")
    
    # Get file extension
    extension = Path(input_path).suffix
    output_pattern = f"part_%03d{extension}"
    
    # FFmpeg command (copy codecs, no re-encoding)
    cmd = [
        "ffmpeg",
        "-i", str(input_path),
        "-c", "copy",  # Copy codecs (NO quality loss)
        "-map", "0",  # Map all streams
        "-f", "segment",  # Use segment muxer
        "-segment_time", str(segment_time),
        "-reset_timestamps", "1",
        "-avoid_negative_ts", "make_zero",
        output_pattern
    ]
    
    logger.info(f"🔧 Running FFmpeg: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Find all created parts
        parts = sorted(Path(".").glob(f"part_*{extension}"))
        logger.info(f"✅ Split complete: {len(parts)} parts created")
        
        for i, part in enumerate(parts, 1):
            size = os.path.getsize(part)
            logger.info(f"  📦 Part {i}: {part.name} ({size / (1024**3):.2f} GB)")
        
        return [str(p) for p in parts]
        
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ FFmpeg split failed: {e}")
        logger.error(f"FFmpeg stderr: {e.stderr}")
        raise


# =====================================================
# TELEGRAM UPLOAD OPERATIONS
# =====================================================

def upload_to_telegram_sync(file_path, caption, bot_token, chat_id, part_number=None, total_parts=None):
    """
    Upload video file to Telegram using chunked streaming upload.
    More memory efficient and stable for large files.
    """
    if part_number:
        caption = f"📹 {caption}\n\n📦 Part {part_number}/{total_parts}"
    
    file_size = os.path.getsize(file_path)
    logger.info(f"📤 Uploading: {Path(file_path).name} ({file_size / (1024**3):.2f} GB)")
    
    # Telegram Bot API endpoint
    url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
    
    # Calculate appropriate timeout (generous for large files)
    upload_timeout = max(3600, int((file_size / (30 * 1024 * 1024)) * 60))  # 1 min per 30MB
    logger.info(f"⏱️ Upload timeout set to: {upload_timeout} seconds ({upload_timeout/60:.1f} minutes)")
    
    # Create a session with optimized settings
    session = requests.Session()
    
    # Configure retry and connection pooling
    from requests.adapters import HTTPAdapter
    from requests.packages.urllib3.util.retry import Retry
    
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"],
        backoff_factor=3,  # 3s, 6s, 12s
    )
    
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=1,
        pool_maxsize=1,
        pool_block=True,
    )
    
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    for attempt in range(1, MAX_UPLOAD_RETRIES + 1):
        try:
            logger.info(f"📤 Upload attempt {attempt}/{MAX_UPLOAD_RETRIES}")
            
            # Open file in binary mode for streaming
            with open(file_path, "rb") as video_file:
                # Prepare multipart form data
                files = {
                    'video': (Path(file_path).name, video_file, 'video/mp4')
                }
                
                data = {
                    'chat_id': chat_id,
                    'caption': caption,
                    'supports_streaming': 'true'
                }
                
                # Stream upload with progress logging
                logger.info("📡 Starting chunked upload...")
                
                response = session.post(
                    url,
                    files=files,
                    data=data,
                    timeout=(180, upload_timeout),  # 3 min connect, long read
                    headers={
                        'Connection': 'keep-alive',
                        'Accept': '*/*',
                    },
                    stream=False,
                )
                
                response.raise_for_status()
                result = response.json()
                
                if result.get('ok'):
                    message_id = result['result']['message_id']
                    logger.info(f"✅ Upload successful: Message ID {message_id}")
                    session.close()
                    return message_id
                else:
                    error_desc = result.get('description', 'Unknown error')
                    raise Exception(f"Telegram API error: {error_desc}")
            
        except requests.exceptions.SSLError as e:
            logger.error(f"❌ SSL error (attempt {attempt}/{MAX_UPLOAD_RETRIES}): {e}")
            
            if attempt < MAX_UPLOAD_RETRIES:
                wait_time = RETRY_DELAY * attempt * 3  # Triple wait: 30s, 60s, 90s, 120s, 150s
                logger.info(f"⏳ Retrying in {wait_time} seconds (resetting connection)...")
                session.close()
                time.sleep(wait_time)
                
                # Recreate session
                session = requests.Session()
                session.mount("https://", adapter)
                session.mount("http://", adapter)
            else:
                session.close()
                raise
        
        except requests.exceptions.Timeout as e:
            logger.error(f"❌ Upload timeout (attempt {attempt}/{MAX_UPLOAD_RETRIES}): {e}")
            
            if attempt < MAX_UPLOAD_RETRIES:
                wait_time = RETRY_DELAY * attempt * 2
                logger.info(f"⏳ Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                session.close()
                raise
        
        except requests.exceptions.ConnectionError as e:
            logger.error(f"❌ Connection error (attempt {attempt}/{MAX_UPLOAD_RETRIES}): {e}")
            
            if attempt < MAX_UPLOAD_RETRIES:
                wait_time = RETRY_DELAY * attempt * 2
                logger.info(f"⏳ Retrying in {wait_time} seconds...")
                session.close()
                time.sleep(wait_time)
                
                # Recreate session
                session = requests.Session()
                session.mount("https://", adapter)
                session.mount("http://", adapter)
            else:
                session.close()
                raise
        
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Request failed (attempt {attempt}/{MAX_UPLOAD_RETRIES}): {e}")
            
            if attempt < MAX_UPLOAD_RETRIES:
                wait_time = RETRY_DELAY * attempt
                logger.info(f"⏳ Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                session.close()
                raise
        
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            session.close()
            raise
    
    session.close()
    raise Exception(f"Failed to upload after {MAX_UPLOAD_RETRIES} attempts")


# =====================================================
# CLEANUP OPERATIONS
# =====================================================

def cleanup_files(*file_patterns):
    """
    Delete all temporary files matching patterns.
    Called automatically even if script fails.
    """
    logger.info("🧹 Cleaning up temporary files...")
    
    deleted_count = 0
    for pattern in file_patterns:
        for file_path in Path(".").glob(pattern):
            try:
                file_path.unlink()
                logger.info(f"  🗑️ Deleted: {file_path}")
                deleted_count += 1
            except Exception as e:
                logger.error(f"  ❌ Failed to delete {file_path}: {e}")
    
    logger.info(f"✅ Cleanup complete: {deleted_count} files deleted")


# =====================================================
# MAIN EXECUTION
# =====================================================

def main():
    """Main execution function"""
    logger.info("=" * 80)
    logger.info("🎬 FTP MOVIE BOT - GITHUB WORKER")
    logger.info("=" * 80)
    logger.info(f"Movie ID: {MOVIE_ID}")
    logger.info(f"Movie Title: {MOVIE_TITLE}")
    logger.info(f"Movie URL: {MOVIE_URL}")
    logger.info("=" * 80)
    
    db_conn = None
    file_parts = []
    input_file = None
    
    try:
        # Validate environment variables
        if not all([MOVIE_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
            raise ValueError("❌ Missing required environment variables")
        
        # Connect to database
        db_conn = get_db_connection()
        
        # Determine file extension from URL
        extension = Path(MOVIE_URL).suffix or ".mp4"
        input_file = f"movie{extension}"
        
        # Step 1: Download movie from FTP
        logger.info("📥 Step 1: Downloading movie from FTP...")
        file_size = download_file(MOVIE_URL, input_file, max_retries=MAX_DOWNLOAD_RETRIES)
        
        # Step 2: Check if splitting is needed
        if file_size <= MAX_TELEGRAM_SIZE:
            logger.info(f"✅ File size OK ({file_size / (1024**3):.2f} GB), no splitting needed")
            file_parts = [input_file]
            is_split = False
            total_parts = 1
        else:
            logger.info("✂️ Step 2: Splitting video...")
            file_parts = split_video(input_file, file_size)
            is_split = True
            total_parts = len(file_parts)
            
            # Update database with split info
            if db_conn:
                update_movie_status(db_conn, "processing", is_split=True, total_parts=total_parts)
        
        # Step 3: Upload to Telegram
        logger.info("📤 Step 3: Uploading to Telegram...")
        message_ids = []
        
        for i, part_file in enumerate(file_parts, 1):
            caption = MOVIE_TITLE if not is_split else MOVIE_TITLE
            
            message_id = upload_to_telegram_sync(
                part_file,
                caption,
                TELEGRAM_BOT_TOKEN,
                TELEGRAM_CHAT_ID,
                part_number=i if is_split else None,
                total_parts=total_parts if is_split else None
            )
            
            message_ids.append(message_id)
        
        # Step 4: Update database as completed
        logger.info("✅ Step 4: Updating database...")
        if db_conn:
            update_movie_status(
                db_conn,
                "completed",
                is_split=is_split,
                total_parts=total_parts,
                telegram_message_ids=message_ids,
                telegram_channel_id=TELEGRAM_CHAT_ID
            )
        
        logger.info("=" * 80)
        logger.info("🎉 MOVIE PROCESSING COMPLETED SUCCESSFULLY!")
        logger.info(f"📦 Uploaded {total_parts} part(s) to Telegram")
        logger.info(f"📨 Message IDs: {message_ids}")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.exception(f"❌ Fatal error: {e}")
        
        # Update database as failed
        if db_conn:
            update_movie_status(db_conn, "failed", error_message=str(e))
        
        sys.exit(1)
        
    finally:
        # CRITICAL: Always cleanup files (even on failure)
        cleanup_files("movie.*", "part_*")
        
        if db_conn:
            db_conn.close()


if __name__ == "__main__":
    main()
