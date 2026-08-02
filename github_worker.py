#!/usr/bin/env python3
"""
FTP Movie Bot - GitHub Worker Script (Production-Ready v3.1)
=============================================================
Runs on GitHub Actions with self-hosted Telegram Bot API Server.

TELEGRAM API OPTIONS:
--------------------
1. Self-Hosted Bot API (Current): Supports up to 2GB files
   - Setup: https://github.com/tdlib/telegram-bot-api
   - Set TELEGRAM_API_URL=http://your-server:8081
   - Requires API_ID and API_HASH from https://my.telegram.org

2. Official Bot API: Limited to 50MB files
   - URL: https://api.telegram.org (default)
   - No setup needed, but files must be split

3. Telethon/Pyrogram (Alternative): Direct MTProto, supports 2GB+
   - No Bot API server needed
   - Requires API_ID, API_HASH, and session file
   - Example: 
     from telethon import TelegramClient
     client = TelegramClient('session', api_id, api_hash)
     await client.send_file(channel_id, 'video.mp4')
"""

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from contextlib import contextmanager

import mysql.connector
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.exceptions import IncompleteRead

# =====================================================
# CONFIGURATION
# =====================================================

MOVIE_ID = os.environ.get("MOVIE_ID")
MOVIE_TITLE = os.environ.get("MOVIE_TITLE")
MOVIE_URL = os.environ.get("MOVIE_URL")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
TELEGRAM_API_URL = os.environ.get("TELEGRAM_API_URL", "https://api.telegram.org")

# Telethon credentials (optional, for direct MTProto uploads)
TELEGRAM_API_ID = os.environ.get("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.environ.get("TELEGRAM_API_HASH")
TELEGRAM_PHONE_NUMBER = os.environ.get("TELEGRAM_PHONE_NUMBER")
USE_TELETHON = os.environ.get("USE_TELETHON", "false").lower() == "true"

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_NAME = os.environ.get("DB_NAME")

MAX_TELEGRAM_SIZE = 1_900_000_000  # 1.9 GB for self-hosted API (2GB with safety margin)
MAX_FILE_SIZE_FOR_PROCESSING = 10_000_000_000  # 10 GB max
PART_SIZE_HARD_LIMIT = 2_000_000_000  # 2 GB absolute maximum
PART_SIZE_VERIFICATION_MARGIN = 50_000_000  # 50 MB safety

MAX_DOWNLOAD_RETRIES = None  # Unlimited
MAX_UPLOAD_RETRIES = 15
INITIAL_RETRY_DELAY = 5
MAX_RETRY_DELAY = 300
EXPONENTIAL_BACKOFF_MULTIPLIER = 2

FFMPEG_SPLIT_SAFETY_FACTOR = 0.90  # 90% of max size

# =====================================================
# LOGGING
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# =====================================================
# HELPER FUNCTIONS
# =====================================================

def calculate_exponential_backoff(attempt, initial_delay=INITIAL_RETRY_DELAY, max_delay=MAX_RETRY_DELAY):
    """Calculate exponential backoff with jitter"""
    import random
    delay = min(initial_delay * (EXPONENTIAL_BACKOFF_MULTIPLIER ** (attempt - 1)), max_delay)
    jitter = random.uniform(0, delay * 0.1)
    return delay + jitter


def format_speed(bytes_per_second):
    """Format speed in MB/s"""
    return f"{bytes_per_second / (1024 * 1024):.2f} MB/s"


def format_eta(seconds):
    """Format ETA"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds / 60)}m {int(seconds % 60)}s"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"


# =====================================================
# SESSION CREATION (MUST BE BEFORE CONTEXT MANAGERS)
# =====================================================

def create_upload_session():
    """Create requests session for uploads"""
    session = requests.Session()
    
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"],
        backoff_factor=2,
        raise_on_status=False
    )
    
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=1,
        pool_maxsize=1,
        pool_block=True
    )
    
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    return session


# =====================================================
# CONTEXT MANAGERS
# =====================================================

@contextmanager
def safe_session():
    """Context manager for HTTP session"""
    session = None
    try:
        session = create_upload_session()
        yield session
    finally:
        if session:
            try:
                session.close()
            except Exception as e:
                logger.debug(f"Error closing session: {e}")


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
    """Update movie status with transaction safety and parameterized queries"""
    if not db_conn or not MOVIE_ID:
        return
    
    cursor = None
    try:
        # Validate MOVIE_ID is numeric to prevent injection
        try:
            movie_id_int = int(MOVIE_ID)
        except (ValueError, TypeError):
            logger.error(f"❌ Invalid MOVIE_ID: {MOVIE_ID}")
            return
        
        cursor = db_conn.cursor()
        db_conn.start_transaction()
        
        updates = ["status = %s"]
        params = [status]
        
        if "is_split" in kwargs:
            updates.append("is_split = %s")
            params.append(1 if kwargs['is_split'] else 0)
        if "total_parts" in kwargs:
            updates.append("total_parts = %s")
            params.append(kwargs['total_parts'])
        if "telegram_message_ids" in kwargs:
            updates.append("telegram_message_ids = %s")
            params.append(json.dumps(kwargs["telegram_message_ids"]))
        if "telegram_channel_id" in kwargs:
            updates.append("telegram_channel_id = %s")
            params.append(str(kwargs["telegram_channel_id"]))
        if "error_message" in kwargs:
            updates.append("error_message = %s")
            params.append(str(kwargs["error_message"])[:500])
        
        if status == "completed":
            updates.append("processing_completed_at = NOW()")
        elif status == "processing":
            updates.append("processing_started_at = NOW()")
        
        query = f"UPDATE ftp_movies SET {', '.join(updates)} WHERE id = %s"
        params.append(movie_id_int)
        
        cursor.execute(query, params)
        db_conn.commit()
        
        logger.info(f"✅ Database updated: status={status}")
        
    except Exception as e:
        logger.error(f"❌ Failed to update database: {e}")
        if db_conn:
            try:
                db_conn.rollback()
            except:
                pass
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass


def get_uploaded_message_ids(db_conn):
    """Get already uploaded message IDs with parameterized query"""
    if not db_conn or not MOVIE_ID:
        return []
    
    cursor = None
    try:
        # Validate MOVIE_ID
        try:
            movie_id_int = int(MOVIE_ID)
        except (ValueError, TypeError):
            logger.error(f"❌ Invalid MOVIE_ID: {MOVIE_ID}")
            return []
        
        cursor = db_conn.cursor()
        query = "SELECT telegram_message_ids FROM ftp_movies WHERE id = %s"
        cursor.execute(query, (movie_id_int,))
        result = cursor.fetchone()
        
        if result and result[0]:
            message_ids = json.loads(result[0])
            logger.info(f"📋 Found {len(message_ids)} already uploaded parts")
            return message_ids
        
        return []
        
    except Exception as e:
        logger.error(f"❌ Failed to get uploaded message IDs: {e}")
        return []
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass


def save_message_id_immediately(db_conn, message_id):
    """Save message ID with parameterized query"""
    if not db_conn or not MOVIE_ID:
        return
    
    cursor = None
    try:
        # Validate MOVIE_ID
        try:
            movie_id_int = int(MOVIE_ID)
        except (ValueError, TypeError):
            logger.error(f"❌ Invalid MOVIE_ID: {MOVIE_ID}")
            return
        
        db_conn.start_transaction()
        cursor = db_conn.cursor()
        
        # Get current message IDs
        query = "SELECT telegram_message_ids FROM ftp_movies WHERE id = %s"
        cursor.execute(query, (movie_id_int,))
        result = cursor.fetchone()
        
        current_ids = []
        if result and result[0]:
            current_ids = json.loads(result[0])
        
        # Check for duplicate before appending
        if message_id not in current_ids:
            current_ids.append(message_id)
        
            update_query = "UPDATE ftp_movies SET telegram_message_ids = %s WHERE id = %s"
            cursor.execute(update_query, (json.dumps(current_ids), movie_id_int))
            db_conn.commit()
            
            logger.info(f"💾 Saved message ID {message_id} (total: {len(current_ids)})")
        else:
            logger.warning(f"⚠️ Message ID {message_id} already exists, skipping")
            db_conn.commit()
        
    except Exception as e:
        logger.error(f"❌ Failed to save message ID: {e}")
        if db_conn:
            try:
                db_conn.rollback()
            except:
                pass
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass


# =====================================================
# FILE DOWNLOAD OPERATIONS
# =====================================================

def check_resume_support(url):
    """
    Check if server supports HTTP Range requests (resumable downloads).
    Returns: (supports_resume: bool, total_size: int)
    """
    try:
        response = requests.head(
            url,
            timeout=30,
            headers={'User-Agent': 'Mozilla/5.0'},
            allow_redirects=True
        )
        
        # Check for Accept-Ranges header
        accept_ranges = response.headers.get('Accept-Ranges', '').lower()
        supports_resume = accept_ranges == 'bytes'
        
        # Get total file size
        total_size = int(response.headers.get('Content-Length', 0))
        
        if supports_resume:
            logger.info(f"✅ Server supports resumable downloads (Accept-Ranges: bytes)")
        else:
            logger.warning(f"⚠️ Server does NOT support resumable downloads (Accept-Ranges: {accept_ranges or 'none'})")
        
        response.close()
        return supports_resume, total_size
        
    except Exception as e:
        logger.warning(f"⚠️ Could not check resume support: {e}")
        return False, 0


def download_file(url, output_path, max_retries=None):
    logger.info(f"📥 Downloading from: {url}")
    logger.info(f"💾 Saving to: {output_path}")
    
    supports_resume, expected_total_size = check_resume_support(url)
    
    existing_size = 0
    if os.path.exists(output_path):
        existing_size = os.path.getsize(output_path)
        if existing_size > 0:
            logger.info(f"🔄 Found partial download: {existing_size / (1024**3):.2f} GB already downloaded")
            if not supports_resume:
                logger.warning(f"⚠️ Server doesn't support resume - deleting partial file and restarting")
                os.remove(output_path)
                existing_size = 0
    
    attempt = 0
    download_start_time = time.time()
    
    while True:
        attempt += 1
        
        if max_retries is not None and attempt > max_retries:
            raise Exception(f"Failed to download after {max_retries} attempts")
        
        retry_info = " (unlimited)" if max_retries is None else f"/{max_retries}"
        logger.info(f"🔄 Download attempt #{attempt}{retry_info}")
        
        if os.path.exists(output_path):
            existing_size = os.path.getsize(output_path)
        else:
            existing_size = 0
        
        if existing_size > 0:
            logger.info(f"📊 Resuming from byte: {existing_size:,} ({existing_size / (1024**3):.2f} GB)")
        
        file_handle = None
        response = None
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Connection': 'keep-alive',
            }
            
            if existing_size > 0 and supports_resume:
                headers['Range'] = f'bytes={existing_size}-'
                logger.info(f"📡 Requesting: Range: bytes={existing_size}-")
            
            response = requests.get(
                url,
                stream=True,
                timeout=(60, 600),
                headers=headers,
                allow_redirects=True
            )
            
            if existing_size > 0 and supports_resume:
                if response.status_code == 206:
                    logger.info(f"✅ Server accepted resume request (HTTP 206 Partial Content)")
                    content_range = response.headers.get('Content-Range', '')
                    if content_range:
                        logger.info(f"📊 Content-Range: {content_range}")
                elif response.status_code == 200:
                    logger.warning(f"⚠️ Server returned HTTP 200 (ignoring Range header)")
                    logger.warning(f"⚠️ Deleting partial file and restarting from zero")
                    response.close()
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    existing_size = 0
                    supports_resume = False
                    continue
                else:
                    response.raise_for_status()
            else:
                response.raise_for_status()
            
            if response.status_code == 206:
                content_range = response.headers.get('Content-Range', '')
                if content_range:
                    try:
                        total_size = int(content_range.split('/')[-1])
                    except:
                        total_size = expected_total_size
                else:
                    total_size = expected_total_size
            else:
                total_size = int(response.headers.get('Content-Length', 0))
            
            if total_size == 0:
                total_size = expected_total_size
            
            logger.info(f"📊 Total file size: {total_size / (1024**3):.2f} GB")
            
            if total_size > MAX_FILE_SIZE_FOR_PROCESSING:
                raise ValueError(f"File too large: {total_size / (1024**3):.2f} GB")
            
            file_mode = "ab" if existing_size > 0 else "wb"
            file_handle = open(output_path, file_mode)
            
            downloaded_this_session = 0
            chunk_size = 8 * 1024 * 1024
            last_log_time = time.time()
            session_start = time.time()
            
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    file_handle.write(chunk)
                    downloaded_this_session += len(chunk)
                    
                    current_time = time.time()
                    if current_time - last_log_time >= 5:
                        current_size = existing_size + downloaded_this_session
                        elapsed = current_time - session_start
                        speed = downloaded_this_session / elapsed if elapsed > 0 else 0
                        progress = (current_size / total_size) * 100 if total_size else 0
                        remaining_bytes = total_size - current_size
                        eta = remaining_bytes / speed if speed > 0 else 0
                        
                        logger.info(
                            f"📥 Downloaded: {current_size / (1024**3):.2f} GB | "
                            f"Existing: {existing_size / (1024**3):.2f} GB | "
                            f"This session: {downloaded_this_session / (1024**3):.2f} GB | "
                            f"Progress: {progress:.1f}% | "
                            f"Speed: {format_speed(speed)} | "
                            f"ETA: {format_eta(eta)}"
                        )
                        last_log_time = current_time
            
            file_handle.close()
            file_handle = None
            
            actual_size = os.path.getsize(output_path)
            
            if total_size > 0 and actual_size != total_size:
                logger.warning(f"⚠️ File size mismatch: {actual_size} bytes != {total_size} bytes expected")
                logger.warning(f"⚠️ Keeping partial file for resume. Will retry...")
                raise Exception(f"Download incomplete: got {actual_size} bytes, expected {total_size} bytes")
            
            total_time = time.time() - download_start_time
            avg_speed = actual_size / total_time if total_time > 0 else 0
            
            logger.info(f"✅ Download complete: {actual_size / (1024**3):.2f} GB in {format_eta(total_time)}")
            logger.info(f"✅ Integrity verified: {actual_size} bytes matches expected size")
            logger.info(f"📊 Average speed: {format_speed(avg_speed)}")
            
            return actual_size
            
        except (requests.exceptions.ConnectionError, 
                requests.exceptions.ChunkedEncodingError,
                IncompleteRead) as e:
            logger.error(f"❌ Connection dropped (attempt #{attempt}): {type(e).__name__}: {e}")
            if file_handle:
                try:
                    file_handle.close()
                    logger.info(f"💾 Partial file saved for resume")
                except:
                    pass
            
            if os.path.exists(output_path):
                partial_size = os.path.getsize(output_path)
                logger.info(f"📊 Partial download saved: {partial_size / (1024**3):.2f} GB")
            
            wait_time = calculate_exponential_backoff(attempt)
            logger.info(f"⏳ Retrying in {wait_time:.1f}s (will resume from last byte)...")
            time.sleep(wait_time)
            
        except requests.exceptions.Timeout as e:
            logger.error(f"❌ Timeout (attempt #{attempt}): {e}")
            if file_handle:
                try:
                    file_handle.close()
                    logger.info(f"💾 Partial file saved for resume")
                except:
                    pass
            
            wait_time = calculate_exponential_backoff(attempt)
            logger.info(f"⏳ Retrying in {wait_time:.1f}s...")
            time.sleep(wait_time)
            
        except Exception as e:
            logger.error(f"❌ Download attempt #{attempt} failed: {type(e).__name__}: {e}")
            if file_handle:
                try:
                    file_handle.close()
                except:
                    pass
            
            if isinstance(e, ValueError):
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                        logger.info(f"🗑️ Deleted partial file due to validation error")
                    except:
                        pass
                raise
            
            wait_time = calculate_exponential_backoff(attempt)
            logger.info(f"⏳ Retrying in {wait_time:.1f}s...")
            time.sleep(wait_time)
        
        finally:
            if response:
                try:
                    response.close()
                except:
                    pass


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
    Split video into parts under MAX_TELEGRAM_SIZE using FFmpeg (-c copy, no re-encoding).
    Uses conservative splitting to ensure NO part ever exceeds the limit due to keyframe boundaries.
    Automatically verifies each part size and re-splits if needed.
    
    Args:
        input_path: Path to input video file
        file_size: Size of input file in bytes
    
    Returns:
        list: List of created part file paths
    """
    logger.info(f"✂️ File size ({file_size / (1024**3):.2f} GB) exceeds Telegram limit")
    logger.info(f"📦 Maximum part size: {MAX_TELEGRAM_SIZE / (1024**3):.2f} GB")
    logger.info(f"🔒 Hard limit (never exceed): {PART_SIZE_HARD_LIMIT / (1024**3):.2f} GB")
    
    # Calculate number of parts needed with SAFETY FACTOR to account for keyframe boundaries
    # FFmpeg with -c copy may create slightly larger parts due to keyframe alignment
    target_part_size = int(MAX_TELEGRAM_SIZE * FFMPEG_SPLIT_SAFETY_FACTOR)
    num_parts = int((file_size / target_part_size) + 1)
    
    logger.info(f"📊 Target part size: {target_part_size / (1024**3):.2f} GB (90% of max)")
    logger.info(f"📊 Will split into approximately {num_parts} parts")
    
    # Get video duration for time-based splitting
    duration = get_video_duration(input_path)
    if not duration:
        logger.warning("⚠️ Could not get video duration, using file size estimation")
        # Estimate: 1 hour per GB (fallback)
        duration = (file_size / (1024**3)) * 3600
    
    # Calculate segment duration
    segment_time = int(duration / num_parts)
    logger.info(f"⏱️ Segment duration: {segment_time} seconds ({segment_time/60:.2f} minutes)")
    logger.info(f"⏱️ Total video duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
    
    # Get file extension
    extension = Path(input_path).suffix or ".mp4"
    output_pattern = f"part_%03d{extension}"
    
    # FFmpeg command (copy codecs - NO re-encoding, NO quality loss)
    # Note: -break_non_keyframes 1 allows breaking at non-keyframes if needed to respect size limit
    cmd = [
        "ffmpeg",
        "-i", str(input_path),
        "-c", "copy",  # Copy all codecs (video, audio, subtitles)
        "-map", "0",  # Map all streams
        "-f", "segment",  # Use segment muxer
        "-segment_time", str(segment_time),
        "-reset_timestamps", "1",  # Reset timestamps for each segment
        "-avoid_negative_ts", "make_zero",  # Avoid negative timestamps
        "-break_non_keyframes", "1",  # Allow breaking at non-keyframes if needed
        output_pattern
    ]
    
    logger.info(f"🔧 Running FFmpeg: {' '.join(cmd)}")
    
    max_split_attempts = 3  # Maximum number of re-split attempts
    
    for split_attempt in range(1, max_split_attempts + 1):
        try:
            logger.info(f"✂️ Split attempt {split_attempt}/{max_split_attempts}")
            
            # Run FFmpeg with progress monitoring
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=3600  # 1 hour timeout for splitting
            )
            
            if process.stderr:
                logger.debug(f"FFmpeg stderr: {process.stderr[-500:]}")  # Log last 500 chars
            
            # Find all created parts
            parts = sorted(Path(".").glob(f"part_*{extension}"))
            
            if not parts:
                raise Exception("FFmpeg did not create any output files")
            
            logger.info(f"✅ Split complete: {len(parts)} parts created")
            
            # Verify each part size
            oversized_parts = []
            all_parts_ok = True
            
            for i, part in enumerate(parts, 1):
                size = os.path.getsize(part)
                size_gb = size / (1024**3)
                logger.info(f"  📦 Part {i}/{len(parts)}: {part.name} ({size_gb:.2f} GB)")
                
                # Check against HARD LIMIT (absolute maximum)
                if size > PART_SIZE_HARD_LIMIT:
                    logger.error(f"  ❌ Part {i} EXCEEDS HARD LIMIT: {size_gb:.2f} GB > {PART_SIZE_HARD_LIMIT / (1024**3):.2f} GB")
                    oversized_parts.append((part, size))
                    all_parts_ok = False
                # Check against preferred limit
                elif size > MAX_TELEGRAM_SIZE:
                    logger.warning(f"  ⚠️ Part {i} exceeds preferred limit: {size_gb:.2f} GB > {MAX_TELEGRAM_SIZE / (1024**3):.2f} GB")
                    logger.warning(f"  ⚠️ But within hard limit, will attempt upload")
                elif size > (MAX_TELEGRAM_SIZE - PART_SIZE_VERIFICATION_MARGIN):
                    logger.warning(f"  ⚠️ Part {i} is close to limit: {size_gb:.2f} GB")
            
            # If any parts exceed HARD LIMIT, we need to re-split
            if oversized_parts:
                logger.error(f"❌ {len(oversized_parts)} parts exceed HARD LIMIT")
                
                if split_attempt < max_split_attempts:
                    logger.info(f"🔄 Re-splitting with more segments (attempt {split_attempt + 1}/{max_split_attempts})...")
                    
                    # Clean up current parts
                    for part in parts:
                        try:
                            part.unlink()
                        except:
                            pass
                    
                    # Increase number of parts by 50%
                    num_parts = int(num_parts * 1.5) + 1
                    new_segment_time = int(duration / num_parts)
                    logger.info(f"📊 New split: {num_parts} parts, {new_segment_time}s per segment")
                    
                    # Update FFmpeg command
                    cmd[cmd.index("-segment_time") + 1] = str(new_segment_time)
                    
                    # Try again (continue loop)
                    continue
                else:
                    # Max attempts reached, cannot split safely
                    raise Exception(f"Cannot split video into parts under {PART_SIZE_HARD_LIMIT / (1024**3):.2f} GB after {max_split_attempts} attempts")
            
            # All parts within acceptable limits
            logger.info(f"✅ All {len(parts)} parts verified successfully")
            return [str(p) for p in parts]
            
        except subprocess.TimeoutExpired:
            logger.error("❌ FFmpeg splitting timed out after 1 hour")
            raise
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ FFmpeg split failed with exit code {e.returncode}")
            logger.error(f"FFmpeg stderr: {e.stderr}")
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error during splitting: {e}")
            raise
    
    # Should never reach here
    raise Exception(f"Failed to split video after {max_split_attempts} attempts")


# =====================================================
# TELEGRAM UPLOAD OPERATIONS
# =====================================================

class StreamingFileReader:
    """File reader that streams file in chunks without loading entire file to RAM"""
    
    def __init__(self, file_path, chunk_size=8 * 1024 * 1024):
        self.file_path = file_path
        self.chunk_size = chunk_size
        self.file_size = os.path.getsize(file_path)
        self.bytes_read = 0
        self.file = None
        self.start_time = time.time()
        self.last_log_time = time.time()
    
    def __enter__(self):
        self.file = open(self.file_path, 'rb')
        return self
    
    def __exit__(self, *args):
        if self.file:
            self.file.close()
    
    def __iter__(self):
        return self
    
    def __next__(self):
        chunk = self.file.read(self.chunk_size)
        if not chunk:
            raise StopIteration
        
        self.bytes_read += len(chunk)
        
        # Log progress every 10 seconds
        current_time = time.time()
        if current_time - self.last_log_time >= 10:
            progress = (self.bytes_read / self.file_size) * 100
            elapsed = current_time - self.start_time
            speed = self.bytes_read / elapsed if elapsed > 0 else 0
            remaining_bytes = self.file_size - self.bytes_read
            eta = remaining_bytes / speed if speed > 0 else 0
            
            logger.info(
                f"📤 Progress: {self.bytes_read / (1024**3):.2f} GB / {self.file_size / (1024**3):.2f} GB "
                f"({progress:.1f}%) | Speed: {format_speed(speed)} | ETA: {format_eta(eta)}"
            )
            self.last_log_time = current_time
        
        return chunk
    
    def read(self, size=-1):
        """
        Compatibility method for requests library.
        IMPORTANT: Must NOT load entire file when size=-1 (defeats streaming purpose).
        """
        if size == -1 or size is None:
            # Return empty bytes to prevent loading entire file to RAM
            # This is called by requests library for final read check
            return b''
        return self.file.read(size)


def upload_with_telethon_sync(file_path, caption, channel_id):
    """Upload large files using Telethon (supports 2GB without self-hosted API)"""
    import asyncio
    from telethon import TelegramClient
    from telethon.tl.types import DocumentAttributeVideo
    
    logger.info("📤 Using Telethon for upload (supports 2GB natively)")
    
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        raise ValueError("TELEGRAM_API_ID and TELEGRAM_API_HASH required for Telethon")
    
    async def do_upload():
        client = TelegramClient('telegram_session', int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
        
        try:
            # Start client (will use existing session or create new one)
            await client.start(phone=lambda: TELEGRAM_PHONE_NUMBER)
            logger.info("✅ Connected to Telegram via Telethon")
            
            file_size = os.path.getsize(file_path)
            last_progress_time = [time.time()]
            
            def progress_callback(current, total):
                now = time.time()
                if now - last_progress_time[0] >= 10:  # Log every 10 seconds
                    percent = (current / total) * 100
                    speed = current / (now - last_progress_time[0]) if (now - last_progress_time[0]) > 0 else 0
                    logger.info(
                        f"📤 Progress: {current / (1024**3):.2f} GB / {total / (1024**3):.2f} GB "
                        f"({percent:.1f}%) | Speed: {format_speed(speed)}"
                    )
                    last_progress_time[0] = now
            
            # Upload video
            logger.info("📤 Starting Telethon upload...")
            message = await client.send_file(
                int(channel_id),
                file_path,
                caption=caption[:1024],
                supports_streaming=True,
                progress_callback=progress_callback,
                attributes=[
                    DocumentAttributeVideo(
                        duration=0,
                        w=1920,
                        h=1080,
                        supports_streaming=True
                    )
                ]
            )
            
            logger.info(f"✅ Telethon upload successful!")
            logger.info(f"📨 Message ID: {message.id}")
            
            return message.id
            
        finally:
            await client.disconnect()
    
    # Run async function in sync context
    return asyncio.run(do_upload())


def upload_to_telegram_sync(file_path, caption, bot_token, chat_id, part_number=None, total_parts=None):
    """Upload video with retry logic and streaming"""
    
    # Check if we should use Telethon instead
    file_size = os.path.getsize(file_path)
    is_official_api = TELEGRAM_API_URL == "https://api.telegram.org"
    
    if USE_TELETHON or (is_official_api and file_size > 50_000_000):
        # Use Telethon for files > 50MB on official API
        logger.info("🔄 Switching to Telethon for large file upload")
        caption_with_part = f"📹 {caption}\n\n📦 Part {part_number}/{total_parts}" if part_number and total_parts else caption
        return upload_with_telethon_sync(file_path, caption_with_part, chat_id)
    
    # Otherwise use Bot API
    if part_number and total_parts:
        caption = f"📹 {caption}\n\n📦 Part {part_number}/{total_parts}"
    
    file_size = os.path.getsize(file_path)
    file_size_gb = file_size / (1024**3)
    
    logger.info(f"📤 Uploading part {part_number or 1}/{total_parts or 1}: {Path(file_path).name} ({file_size_gb:.2f} GB)")
    
    if file_size > PART_SIZE_HARD_LIMIT:
        raise ValueError(f"File too large: {file_size_gb:.2f} GB (exceeds hard limit)")
    elif file_size > MAX_TELEGRAM_SIZE:
        logger.warning(f"⚠️ File {file_size_gb:.2f} GB exceeds preferred limit but within hard limit")
    
    url = f"{TELEGRAM_API_URL.rstrip('/')}/bot{bot_token}/sendVideo"
    
    # Increased timeout for large files (1.9 GB can take hours on slow connections)
    base_timeout = 10800  # 3 hours base timeout for large files
    size_based_timeout = int((file_size / (100 * 1024 * 1024)) * 300)  # +5 min per 100MB
    upload_timeout = base_timeout + size_based_timeout
    
    logger.info(f"⏱️ Upload timeout: {upload_timeout}s ({format_eta(upload_timeout)})")
    
    for attempt in range(1, MAX_UPLOAD_RETRIES + 1):
        upload_start = time.time()
        session = None
        response = None
        
        try:
            logger.info(f"📤 Upload attempt {attempt}/{MAX_UPLOAD_RETRIES}")
            
            session = create_upload_session()
            
            data = {
                'chat_id': chat_id,
                'caption': caption[:1024],
                'supports_streaming': True
            }
            
            # Use standard file open for official Telegram API (simpler and more reliable)
            with open(file_path, 'rb') as video_file:
                files = {
                    'video': (Path(file_path).name, video_file, 'video/mp4')
                }
                
                response = session.post(
                    url,
                    files=files,
                    data=data,
                    timeout=(180, upload_timeout),
                    headers={
                        'Connection': 'keep-alive',
                        'Accept': '*/*',
                    },
                    stream=False
                )
            
            duration = time.time() - upload_start
            avg_speed = file_size / duration if duration > 0 else 0
            
            response.raise_for_status()
            result = response.json()
            
            if result.get('ok'):
                message_id = result['result']['message_id']
                logger.info(f"✅ Upload successful in {format_eta(duration)}")
                logger.info(f"📊 Average speed: {format_speed(avg_speed)}")
                logger.info(f"📨 Message ID: {message_id}")
                
                return message_id
            else:
                error_desc = result.get('description', 'Unknown error')
                raise Exception(f"Telegram API error: {error_desc}")
        
        except requests.exceptions.SSLError as e:
            logger.error(f"❌ SSL error (attempt {attempt}/{MAX_UPLOAD_RETRIES}): {e}")
            
        except requests.exceptions.ConnectionError as e:
            logger.error(f"❌ Connection error (attempt {attempt}/{MAX_UPLOAD_RETRIES}): {e}")
            
        except requests.exceptions.Timeout:
            duration = time.time() - upload_start
            logger.error(f"❌ Timeout after {format_eta(duration)} (attempt {attempt}/{MAX_UPLOAD_RETRIES})")
            
        except requests.exceptions.ChunkedEncodingError as e:
            logger.error(f"❌ ChunkedEncoding error (attempt {attempt}/{MAX_UPLOAD_RETRIES}): {e}")
            
        except requests.exceptions.RequestException as e:
            # Log response body for debugging
            error_details = ""
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_json = e.response.json()
                    error_details = f" | API error: {error_json.get('description', 'No description')}"
                except:
                    error_details = f" | Response: {e.response.text[:200]}"
            logger.error(f"❌ {type(e).__name__} (attempt {attempt}/{MAX_UPLOAD_RETRIES}): {e}{error_details}")
            
        except (BrokenPipeError, ConnectionResetError) as e:
            logger.error(f"❌ {type(e).__name__} (attempt {attempt}/{MAX_UPLOAD_RETRIES})")
            
        except Exception as e:
            logger.error(f"❌ Unexpected {type(e).__name__} (attempt {attempt}/{MAX_UPLOAD_RETRIES}): {e}")
            if attempt >= MAX_UPLOAD_RETRIES:
                raise
        
        finally:
            # CRITICAL: Always close response and session to prevent memory leaks
            if response:
                try:
                    response.close()
                except:
                    pass
            if session:
                try:
                    session.close()
                except:
                    pass
        
        # Retry logic
        if attempt < MAX_UPLOAD_RETRIES:
            wait_time = calculate_exponential_backoff(attempt)
            logger.info(f"⏳ Waiting {wait_time:.1f}s before retry...")
            time.sleep(wait_time)
        else:
            raise Exception(f"Failed to upload {file_path} after {MAX_UPLOAD_RETRIES} attempts")
    
    raise Exception(f"Upload failed unexpectedly")


# =====================================================
# CLEANUP OPERATIONS
# =====================================================

def cleanup_files(*file_patterns, exclude_files=None):
    """
    Delete all temporary files matching patterns.
    Called automatically even if script fails.
    
    Args:
        *file_patterns: Glob patterns to match files for deletion
        exclude_files: List of files to exclude from deletion (still needed for upload)
    """
    logger.info("🧹 Cleaning up temporary files...")
    
    exclude_files = exclude_files or []
    exclude_set = {str(Path(f).resolve()) for f in exclude_files}
    
    deleted_count = 0
    skipped_count = 0
    
    for pattern in file_patterns:
        for file_path in Path(".").glob(pattern):
            resolved_path = str(file_path.resolve())
            
            # Skip files that are excluded (still needed)
            if resolved_path in exclude_set:
                logger.info(f"  ⏭️ Skipped (still needed): {file_path}")
                skipped_count += 1
                continue
            
            try:
                file_path.unlink()
                logger.info(f"  🗑️ Deleted: {file_path}")
                deleted_count += 1
            except Exception as e:
                logger.error(f"  ❌ Failed to delete {file_path}: {e}")
    
    logger.info(f"✅ Cleanup complete: {deleted_count} files deleted, {skipped_count} files skipped")


def safe_cleanup_all_temp_files(exclude_files=None):
    """
    Safe cleanup that deletes temporary files after processing.
    
    Args:
        exclude_files: List of files to exclude from deletion (still needed for upload/resume)
    """
    logger.info("🧹 Final cleanup: removing temporary files...")
    
    exclude_files = exclude_files or []
    exclude_set = {str(Path(f).resolve()) for f in exclude_files}
    
    patterns = ["movie.*", "part_*"]
    deleted_count = 0
    skipped_count = 0
    
    for pattern in patterns:
        for file_path in Path(".").glob(pattern):
            resolved_path = str(file_path.resolve())
            
            # Skip files that are excluded (still needed)
            if resolved_path in exclude_set:
                logger.info(f"  ⏭️ Skipped (still needed): {file_path}")
                skipped_count += 1
                continue
            
            try:
                file_path.unlink()
                logger.info(f"  🗑️ Deleted: {file_path}")
                deleted_count += 1
            except Exception as e:
                logger.error(f"  ❌ Failed to delete {file_path}: {e}")
    
    logger.info(f"✅ Final cleanup complete: {deleted_count} files deleted, {skipped_count} files skipped")


# =====================================================
# MAIN EXECUTION
# =====================================================

def main():
    """
    Main execution function with resume-from-failed-part capability.
    Ensures proper resource management and cleanup in all scenarios.
    """
    logger.info("=" * 80)
    logger.info("🎬 FTP MOVIE BOT - GITHUB WORKER v3.0 (Production)")
    logger.info("=" * 80)
    logger.info(f"Movie ID: {MOVIE_ID}")
    logger.info(f"Movie Title: {MOVIE_TITLE}")
    logger.info(f"Movie URL: {MOVIE_URL}")
    if TELEGRAM_API_URL != "https://api.telegram.org":
        logger.info(f"Using custom Telegram Bot API: {TELEGRAM_API_URL}")
    else:
        logger.info(f"Using official Telegram Bot API")
    logger.info("=" * 80)
    
    db_conn = None
    file_parts = []
    input_file = None
    parts_to_keep = []  # Parts that still need uploading (don't delete)
    
    try:
        # Validate environment variables
        if not all([MOVIE_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
            raise ValueError("❌ Missing required environment variables")
        
        # Connect to database
        db_conn = get_db_connection()
        
        # Check if this movie already has parts uploaded (resume capability)
        already_uploaded_ids = get_uploaded_message_ids(db_conn) if db_conn else []
        parts_already_uploaded = len(already_uploaded_ids)
        
        if parts_already_uploaded > 0:
            logger.info(f"🔄 RESUME MODE: {parts_already_uploaded} parts already uploaded")
            logger.info(f"📋 Existing message IDs: {already_uploaded_ids}")
        
        # Determine file extension from URL
        extension = Path(MOVIE_URL).suffix.lower() or ".mp4"
        
        # Validate extension (MP4 and MKV are safe for FFmpeg -c copy)
        if extension not in ['.mp4', '.mkv', '.avi', '.mov']:
            logger.warning(f"⚠️ Uncommon extension: {extension} - FFmpeg -c copy may have issues")
        
        input_file = f"movie{extension}"
        
        # Step 1: Download movie from FTP (only if not already split and cached)
        if parts_already_uploaded == 0:
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
                
                # Clean up original file after successful split (save disk space)
                if os.path.exists(input_file):
                    try:
                        os.remove(input_file)
                        logger.info(f"🗑️ Removed original file (split completed): {input_file}")
                    except Exception as e:
                        logger.warning(f"⚠️ Could not remove original file: {e}")
                
                # Update database with split info
                if db_conn:
                    update_movie_status(db_conn, "processing", is_split=True, total_parts=total_parts)
        else:
            # Resume mode: parts already exist (from previous run or cached)
            logger.info("🔄 Step 1 & 2: Skipped (resuming from existing parts)")
            
            # Find existing part files
            file_parts = sorted([str(p) for p in Path(".").glob(f"part_*{extension}")])
            
            if not file_parts:
                # Parts don't exist locally, need to re-download and re-split
                logger.warning("⚠️ Part files not found locally, will re-download and re-split")
                file_size = download_file(MOVIE_URL, input_file, max_retries=MAX_DOWNLOAD_RETRIES)
                
                if file_size <= MAX_TELEGRAM_SIZE:
                    file_parts = [input_file]
                    is_split = False
                    total_parts = 1
                else:
                    file_parts = split_video(input_file, file_size)
                    is_split = True
                    total_parts = len(file_parts)
                    
                    # Clean up original after split
                    if os.path.exists(input_file):
                        try:
                            os.remove(input_file)
                            logger.info(f"🗑️ Removed original file: {input_file}")
                        except:
                            pass
            else:
                is_split = True
                total_parts = len(file_parts)
                logger.info(f"✅ Found {total_parts} existing parts locally")
        
        # Step 3: Upload to Telegram (with resume capability)
        logger.info("📤 Step 3: Uploading to Telegram...")
        message_ids = already_uploaded_ids.copy()  # Start with already uploaded IDs
        
        # Determine which parts still need uploading
        parts_to_upload = file_parts[parts_already_uploaded:]
        parts_to_keep = parts_to_upload.copy()  # Don't delete these until uploaded
        
        if not parts_to_upload:
            logger.info("✅ All parts already uploaded!")
        else:
            logger.info(f"📦 Uploading remaining {len(parts_to_upload)} parts (starting from part {parts_already_uploaded + 1}/{total_parts})")
        
        # Upload each part
        for i, part_file in enumerate(parts_to_upload, start=parts_already_uploaded + 1):
            caption = MOVIE_TITLE if not is_split else MOVIE_TITLE
            
            logger.info(f"\n{'=' * 60}")
            logger.info(f"📤 Starting upload: Part {i}/{total_parts}")
            logger.info(f"📂 File: {part_file}")
            logger.info(f"{'=' * 60}\n")
            
            try:
                message_id = upload_to_telegram_sync(
                    part_file,
                    caption,
                    TELEGRAM_BOT_TOKEN,
                    TELEGRAM_CHAT_ID,
                    part_number=i if is_split else None,
                    total_parts=total_parts if is_split else None
                )
                
                message_ids.append(message_id)
                
                # CRITICAL: Save message ID immediately after successful upload
                # This enables resume if next part fails
                if db_conn:
                    save_message_id_immediately(db_conn, message_id)
                    logger.info(f"💾 Progress saved: {i}/{total_parts} parts uploaded")
                
                # Part uploaded successfully, can now delete it (save disk space)
                try:
                    os.remove(part_file)
                    logger.info(f"🗑️ Removed uploaded part: {part_file}")
                    # Remove from parts_to_keep
                    if part_file in parts_to_keep:
                        parts_to_keep.remove(part_file)
                except Exception as e:
                    logger.warning(f"⚠️ Could not remove uploaded part: {e}")
                
            except Exception as e:
                logger.error(f"❌ Failed to upload part {i}/{total_parts}: {e}")
                # Don't delete this part - it's still needed for retry
                raise
        
        # Step 4: Update database as completed
        logger.info("\n" + "=" * 60)
        logger.info("✅ Step 4: Marking as completed...")
        logger.info("=" * 60)
        
        if db_conn:
            update_movie_status(
                db_conn,
                "completed",
                is_split=is_split,
                total_parts=total_parts,
                telegram_message_ids=message_ids,
                telegram_channel_id=TELEGRAM_CHAT_ID
            )
        
        logger.info("\n" + "=" * 80)
        logger.info("🎉 MOVIE PROCESSING COMPLETED SUCCESSFULLY!")
        logger.info(f"📦 Uploaded {total_parts} part(s) to Telegram")
        logger.info(f"📨 Message IDs: {message_ids}")
        logger.info("=" * 80 + "\n")
        
    except Exception as e:
        logger.exception(f"\n❌ Fatal error: {e}\n")
        
        # Update database as failed
        if db_conn:
            update_movie_status(db_conn, "failed", error_message=str(e))
        
        sys.exit(1)
        
    finally:
        # CRITICAL: Always cleanup files (even on failure)
        # Pass parts_to_keep to prevent deleting files still needed for resume
        logger.info("\n" + "=" * 60)
        logger.info("🧹 Starting cleanup...")
        logger.info("=" * 60)
        
        safe_cleanup_all_temp_files(exclude_files=parts_to_keep)
        
        # Close database connection
        if db_conn:
            try:
                db_conn.close()
                logger.info("✅ Database connection closed")
            except Exception as e:
                logger.warning(f"⚠️ Error closing database: {e}")


if __name__ == "__main__":
    main()
