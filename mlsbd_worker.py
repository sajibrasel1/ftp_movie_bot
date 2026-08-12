#!/usr/bin/env python3
"""
MLSBD Movie Bot - GitHub Actions Worker Script (Production-Ready)
=================================================================
Runs on GitHub Actions to:
1. Bypass GDFlix URL using Selenium in headless mode to get direct Google User Content download link.
2. Update database (mlsbd_movies table) with the resolved direct URL.
3. Download the movie from direct link with HTTP Range resume support.
4. Split the movie using FFmpeg if size > 1.9 GB.
5. Upload to Telegram channel using Telethon Bot Mode.
6. Update status in cPanel DB using the update_status.php API.

Author: AI Assistant
Version: 1.0
"""

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from contextlib import contextmanager

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Selenium imports for GDFlix bypass
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# =====================================================
# CONFIGURATION
# =====================================================

MOVIE_ID = os.environ.get("MOVIE_ID")
MOVIE_TITLE = os.environ.get("MOVIE_TITLE")
MOVIE_URL = os.environ.get("MOVIE_URL")  # GDFlix URL passed as input

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
DB_API_URL = os.environ.get("DB_API_URL")
DB_API_KEY = os.environ.get("DB_API_KEY")

MAX_TELEGRAM_SIZE = 1_900_000_000  # 1.9 GB for Telethon (2GB with safety margin)
MAX_FILE_SIZE_FOR_PROCESSING = 20_000_000_000  # 20 GB max
MAX_DOWNLOAD_RETRIES = None  # Unlimited retries for stable download
FFMPEG_SPLIT_SAFETY_FACTOR = 0.90  # 90% of max size

# =====================================================
# LOGGING
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
    handlers=[SafeStreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# =====================================================
# SELENIUM GDFLIX BYPASS FUNCTION
# =====================================================

def get_chrome_driver():
    """Setup and return Selenium ChromeDriver in headless mode"""
    logger.info("🔧 Initializing Headless Chrome Driver...")
    options = Options()
    options.add_argument("--headless=new")  # Use modern headless mode
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    # Override navigator.webdriver to undefined to bypass basic detection
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    
    return driver

def wait_for_cloudflare(driver, timeout=25):
    """Wait for Cloudflare challenge to clear"""
    logger.info("[*] Waiting for Cloudflare check to clear...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        title = driver.title
        if "Just a moment" not in title and "Cloudflare" not in title and title.strip() != "":
            logger.info(f"[+] Cloudflare cleared! Page Title: {title}")
            return True
        time.sleep(1)
    logger.warning(f"[-] Cloudflare did not clear. Current title: {driver.title}")
    return False

def bypass_gdflix_to_direct_link(driver, gdflix_url):
    """
    Bypasses GDFlix redirect using Selenium and resolves
    the direct googleusercontent download link.
    """
    logger.info(f"[*] Navigating to GDFlix page: {gdflix_url} ...")
    driver.get(gdflix_url)
    
    wait_for_cloudflare(driver)
    time.sleep(5)  # Wait for page scripts to run
    
    logger.info("[*] Locating download buttons/links...")
    links = driver.find_elements(By.TAG_NAME, "a")
    
    instant_dl_url = None
    for link in links:
        try:
            href = link.get_attribute("href")
            text = link.text.strip()
            if href and ("Instant DL" in text or "instant" in href or "busycdn" in href):
                instant_dl_url = href
                break
        except Exception:
            continue
            
    if not instant_dl_url:
        logger.error("[-] Instant DL link not found on GDFlix page.")
        return None
        
    logger.info(f"[+] Found Instant DL link: {instant_dl_url}")
    logger.info("[*] Navigating to Instant DL page to resolve Google Drive link...")
    driver.get(instant_dl_url)
    
    wait_for_cloudflare(driver)
    time.sleep(5)  # Allow time for final redirects
    
    current_url = driver.current_url
    logger.info(f"[+] Current URL: {current_url}")
    
    # Locate final googleusercontent download link
    links = driver.find_elements(By.TAG_NAME, "a")
    direct_link = None
    for link in links:
        try:
            href = link.get_attribute("href")
            if href and "googleusercontent.com" in href:
                direct_link = href
                break
        except Exception:
            continue
            
    if not direct_link and "googleusercontent.com" in current_url:
        direct_link = current_url
        
    return direct_link

# =====================================================
# DATABASE API FUNCTIONS
# =====================================================

def update_movie_status(status, **kwargs):
    """Update movie status in mlsbd_movies table via API"""
    if not MOVIE_ID or not DB_API_URL or not DB_API_KEY:
        logger.warning("⚠️ Database API credentials or MOVIE_ID missing - skipping DB update")
        return
        
    try:
        payload = {
            "movie_id": int(MOVIE_ID),
            "action": "update_status",
            "status": status,
            "table": "mlsbd_movies"  # Target MLSBD table
        }
        
        # Add optional fields
        for key in ["is_split", "total_parts", "telegram_message_ids", "telegram_channel_id", "error_message", "direct_download_url"]:
            if key in kwargs:
                if key == "telegram_message_ids":
                    payload[key] = kwargs[key]
                elif key == "is_split":
                    payload[key] = 1 if kwargs[key] else 0
                else:
                    payload[key] = str(kwargs[key])
                    
        api_url_with_key = f"{DB_API_URL}?api_key={DB_API_KEY}"
        response = requests.post(api_url_with_key, json=payload, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"✅ Database updated via API: status={status}")
        else:
            logger.error(f"❌ API error {response.status_code}: {response.text}")
            
    except Exception as e:
        logger.error(f"❌ Failed to update DB status via API: {e}")

def save_message_id_immediately(message_id):
    """Save message ID immediately via API to enable resumable uploads"""
    if not MOVIE_ID or not DB_API_URL or not DB_API_KEY:
        return
        
    try:
        payload = {
            "movie_id": int(MOVIE_ID),
            "action": "save_message_id",
            "message_id": int(message_id),
            "table": "mlsbd_movies"
        }
        api_url_with_key = f"{DB_API_URL}?api_key={DB_API_KEY}"
        response = requests.post(api_url_with_key, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"💾 Saved message ID {message_id} via API (total parts: {result.get('total_parts', '?')})")
        else:
            logger.error(f"❌ API save message error {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"❌ Failed to save message ID via API: {e}")

def get_uploaded_message_ids_api():
    """Get already uploaded message IDs from database via API"""
    if not MOVIE_ID or not DB_API_URL or not DB_API_KEY:
        return []
        
    try:
        payload = {
            "movie_id": int(MOVIE_ID),
            "action": "get_uploaded_parts",
            "table": "mlsbd_movies"
        }
        api_url_with_key = f"{DB_API_URL}?api_key={DB_API_KEY}"
        response = requests.post(api_url_with_key, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            message_ids = result.get("message_ids", [])
            logger.info(f"📋 Found {len(message_ids)} already uploaded parts via API")
            return message_ids
    except Exception as e:
        logger.error(f"❌ Failed to get uploaded message IDs via API: {e}")
        
    return []

# =====================================================
# DOWNLOAD & RESUME OPERATIONS
# =====================================================

def check_resume_support(url):
    """Check if server supports HTTP Range requests for resumable downloads"""
    try:
        response = requests.head(
            url,
            timeout=30,
            headers={'User-Agent': 'Mozilla/5.0'},
            allow_redirects=True
        )
        accept_ranges = response.headers.get('Accept-Ranges', '').lower()
        supports_resume = accept_ranges == 'bytes'
        total_size = int(response.headers.get('Content-Length', 0))
        
        if supports_resume:
            logger.info("✅ Server supports resumable downloads")
        else:
            logger.warning("⚠️ Server does NOT support resumable downloads")
            
        response.close()
        return supports_resume, total_size
    except Exception as e:
        logger.warning(f"⚠️ Could not check resume support: {e}")
        return False, 0

def format_speed(bytes_per_second):
    return f"{bytes_per_second / (1024 * 1024):.2f} MB/s"

def format_eta(seconds):
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds / 60)}m {int(seconds % 60)}s"
    else:
        return f"{int(seconds / 3600)}h {int((seconds % 3600) / 60)}m"

def download_file(url, output_path, max_retries=None):
    logger.info(f"📥 Downloading from resolved URL: {url[:100]}...")
    logger.info(f"💾 Saving to: {output_path}")
    
    supports_resume, expected_total_size = check_resume_support(url)
    
    existing_size = 0
    if os.path.exists(output_path):
        existing_size = os.path.getsize(output_path)
        if existing_size > 0:
            logger.info(f"🔄 Found partial download: {existing_size / (1024**3):.2f} GB already downloaded")
            if not supports_resume:
                logger.warning("⚠️ Server doesn't support resume - deleting partial file and restarting")
                os.remove(output_path)
                existing_size = 0
                
    attempt = 0
    session_start = time.time()
    
    while True:
        attempt += 1
        if max_retries is not None and attempt > max_retries:
            raise Exception(f"Failed to download after {max_retries} attempts")
            
        logger.info(f"🔄 Download attempt #{attempt}")
        if os.path.exists(output_path):
            existing_size = os.path.getsize(output_path)
        else:
            existing_size = 0
            
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Connection': 'keep-alive',
            }
            
            if existing_size > 0 and supports_resume:
                headers['Range'] = f'bytes={existing_size}-'
                
            response = requests.get(
                url,
                stream=True,
                timeout=(60, 600),
                headers=headers,
                allow_redirects=True
            )
            
            if existing_size > 0 and supports_resume:
                if response.status_code == 206:
                    logger.info("✅ Server accepted resume request (HTTP 206 Partial Content)")
                elif response.status_code == 200:
                    logger.warning("⚠️ Server ignored Range header. Restarting download.")
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
                try:
                    total_size = int(content_range.split('/')[-1])
                except:
                    total_size = expected_total_size
            else:
                total_size = int(response.headers.get('Content-Length', 0))
                
            if total_size == 0:
                total_size = expected_total_size
                
            logger.info(f"📊 Total file size: {total_size / (1024**3):.2f} GB")
            if total_size > MAX_FILE_SIZE_FOR_PROCESSING:
                raise ValueError(f"File too large: {total_size / (1024**3):.2f} GB")
                
            file_mode = "ab" if existing_size > 0 else "wb"
            
            with open(output_path, file_mode) as f:
                downloaded_this_session = 0
                chunk_size = 8 * 1024 * 1024
                last_log_time = time.time()
                
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded_this_session += len(chunk)
                        
                        current_time = time.time()
                        if current_time - last_log_time >= 10:  # Log every 10 seconds
                            current_size = existing_size + downloaded_this_session
                            elapsed = current_time - session_start
                            speed = downloaded_this_session / elapsed if elapsed > 0 else 0
                            progress = (current_size / total_size) * 100 if total_size else 0
                            remaining_bytes = total_size - current_size
                            eta = remaining_bytes / speed if speed > 0 else 0
                            
                            logger.info(
                                f"📥 Downloaded: {current_size / (1024**3):.2f} GB | "
                                f"Progress: {progress:.1f}% | "
                                f"Speed: {format_speed(speed)} | "
                                f"ETA: {format_eta(eta)}"
                            )
                            last_log_time = current_time
                            
            actual_size = os.path.getsize(output_path)
            if total_size and abs(actual_size - total_size) > 1024 * 1024:  # 1MB margin
                logger.warning(f"⚠️ Size mismatch! Expected {total_size} bytes, got {actual_size} bytes. Retrying...")
                continue
                
            logger.info(f"✅ Download complete! File size: {actual_size / (1024**3):.2f} GB")
            return actual_size
            
        except Exception as e:
            logger.warning(f"⚠️ Download attempt failed: {e}")
            time.sleep(10)  # Wait before retry

# =====================================================
# VIDEO SPLITTING WITH FFMPEG
# =====================================================

def split_video(input_path, file_size):
    """Split video using FFmpeg -c copy (no re-encoding)"""
    logger.info("✂️ Splitting video into 1.9GB parts...")
    
    # Calculate target time segment based on bitrate estimation
    # segment_time = (target_size_in_bits) / (bitrate_in_bits_per_sec)
    # A safer method is segmenting by size if FFmpeg supports it, or estimate segment length in seconds
    
    # Let's get video duration first
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", input_path
        ]
        duration = float(subprocess.check_output(cmd).decode().strip())
        logger.info(f"🎬 Video duration: {duration:.2f} seconds")
    except Exception as e:
        logger.warning(f"⚠️ Could not read duration via ffprobe: {e}. Defaulting duration to 2 hours.")
        duration = 7200
        
    avg_bitrate = (file_size * 8) / duration  # bits per second
    target_part_size = MAX_TELEGRAM_SIZE * FFMPEG_SPLIT_SAFETY_FACTOR
    segment_time = target_part_size * 8 / avg_bitrate  # seconds
    
    logger.info(f"📊 Estimated segment time: {segment_time:.1f} seconds")
    
    # Use FFmpeg segment filter to split
    extension = Path(input_path).suffix
    output_pattern = f"part_%03d{extension}"
    
    ffmpeg_cmd = [
        "ffmpeg", "-y", "-i", input_path, "-c", "copy",
        "-f", "segment", "-segment_time", str(int(segment_time)),
        "-reset_timestamps", "1", output_pattern
    ]
    
    logger.info(f"🔧 Running FFmpeg: {' '.join(ffmpeg_cmd)}")
    start_time = time.time()
    
    res = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        logger.error(f"❌ FFmpeg error: {res.stderr.decode()}")
        raise Exception("FFmpeg splitting failed")
        
    elapsed = time.time() - start_time
    logger.info(f"✅ Splitting completed in {elapsed:.1f} seconds.")
    
    # Retrieve generated parts
    parts = sorted([str(p) for p in Path(".").glob(f"part_*{extension}")])
    logger.info(f"📦 Generated parts: {parts}")
    return parts

# =====================================================
# TELEGRAM UPLOAD WITH TELETHON
# =====================================================

def format_movie_caption(title, is_split=False, part_number=None, total_parts=None):
    caption = title
    if is_split and part_number and total_parts:
        caption += f"\n\n📦 Part {part_number}/{total_parts}"
    return caption

def upload_with_bot_token(file_path, caption, channel_id, bot_token):
    from telethon import TelegramClient
    from telethon.tl.types import DocumentAttributeVideo
    
    logger.info("Using Telethon with Bot Token (2GB support)")
    
    api_id = os.environ.get("TELEGRAM_API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH")
    
    if not api_id or not api_hash:
        raise ValueError("TELEGRAM_API_ID and TELEGRAM_API_HASH required for Telethon")
        
    async def do_upload():
        client = TelegramClient('bot_session', int(api_id), api_hash)
        try:
            await client.start(bot_token=bot_token)
            logger.info("Connected to Telegram via Telethon (Bot Mode)")
            
            file_size = os.path.getsize(file_path)
            last_progress_time = [time.time()]
            
            def progress_callback(current, total):
                now = time.time()
                if now - last_progress_time[0] >= 10:
                    percent = (current / total) * 100
                    speed = current / (now - last_progress_time[0]) if (now - last_progress_time[0]) > 0 else 0
                    logger.info(
                        f"Upload Progress: {current / (1024**3):.2f} GB / {total / (1024**3):.2f} GB "
                        f"({percent:.1f}%) | Speed: {format_speed(speed)}"
                    )
                    last_progress_time[0] = now
                    
            start_time = time.time()
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
            
            elapsed = time.time() - start_time
            speed = file_size / elapsed if elapsed > 0 else 0
            logger.info(f"Telethon upload successful! Message ID: {message.id} | Speed: {format_speed(speed)}")
            return message.id
            
        finally:
            await client.disconnect()
            
    return asyncio.run(do_upload())

# =====================================================
# CLEANUP
# =====================================================

def safe_cleanup(exclude_files=None):
    logger.info("🧹 Starting cleanup of temporary files...")
    exclude_files = exclude_files or []
    exclude_set = {str(Path(f).resolve()) for f in exclude_files}
    
    # Clean file patterns
    for pattern in ["movie.*", "part_*.*"]:
        for file_path in Path(".").glob(pattern):
            resolved = str(file_path.resolve())
            if resolved not in exclude_set:
                try:
                    os.remove(file_path)
                    logger.info(f"  🗑️ Deleted: {file_path.name}")
                except Exception as e:
                    logger.warning(f"  ⚠️ Could not delete {file_path.name}: {e}")

# =====================================================
# MAIN RUNNER
# =====================================================

def main():
    logger.info("=" * 80)
    logger.info("🎬 MLSBD WORKER ACTIVATED")
    logger.info(f"Movie ID: {MOVIE_ID}")
    logger.info(f"Movie Title: {MOVIE_TITLE}")
    logger.info(f"GDFlix URL: {MOVIE_URL}")
    logger.info("=" * 80)
    
    if not all([MOVIE_ID, MOVIE_TITLE, MOVIE_URL]):
        logger.error("❌ Missing required env variables!")
        sys.exit(1)
        
    # Step 0: Resolve Savelinks/GDFlix using Selenium (only if not resuming)
    already_uploaded_ids = get_uploaded_message_ids_api()
    parts_already_uploaded = len(already_uploaded_ids)
    
    direct_download_url = None
    
    # Check if we need to resolve the direct URL
    if parts_already_uploaded == 0:
        logger.info("🌐 Step 0: Resolving GDFlix Cloudflare bypass via Selenium...")
        driver = None
        try:
            driver = get_chrome_driver()
            direct_download_url = bypass_gdflix_to_direct_link(driver, MOVIE_URL)
            if not direct_download_url:
                raise ValueError("Bypass resolved to empty download link")
                
            logger.info(f"✅ GDFlix Bypassed! Resolved link: {direct_download_url[:100]}...")
            
            # Save the resolved link to DB
            update_movie_status("processing", direct_download_url=direct_download_url)
            
        except Exception as e:
            logger.exception(f"❌ Failed to bypass GDFlix: {e}")
            update_movie_status("failed", error_message=f"GDFlix bypass failed: {str(e)}")
            sys.exit(1)
        finally:
            if driver:
                driver.quit()
                logger.info("[-] Chrome browser closed.")
                
    # Run download/split/upload pipeline
    parts_to_keep = []
    try:
        # Determine file extension
        # GDFlix usually points to a Google Drive file, we default to MKV or try to detect from title
        extension = ".mkv"
        if ".mp4" in MOVIE_TITLE.lower():
            extension = ".mp4"
            
        input_file = f"movie{extension}"
        
        if parts_already_uploaded == 0:
            logger.info("📥 Step 1: Downloading movie from direct link...")
            file_size = download_file(direct_download_url, input_file, max_retries=MAX_DOWNLOAD_RETRIES)
            
            # Step 2: Split
            if file_size <= MAX_TELEGRAM_SIZE:
                logger.info("✅ File is small enough, no splitting needed.")
                file_parts = [input_file]
                is_split = False
                total_parts = 1
            else:
                file_parts = split_video(input_file, file_size)
                is_split = True
                total_parts = len(file_parts)
                
                # Delete original
                if os.path.exists(input_file):
                    os.remove(input_file)
                    
                # Update DB
                update_movie_status("processing", is_split=True, total_parts=total_parts)
        else:
            # Resuming
            logger.info("🔄 Resuming process from existing parts")
            file_parts = sorted([str(p) for p in Path(".").glob(f"part_*{extension}")])
            
            if not file_parts:
                # If we don't have parts, we need to fetch the resolved direct URL to re-download
                # We can update DB back to pending or fetch it
                # For simplicity, we fail and let the retry mechanism handle it by restarting
                raise FileNotFoundError("Part files not found locally for resume, restarting process")
                
            is_split = True
            total_parts = len(file_parts)
            logger.info(f"✅ Found {total_parts} local parts to resume.")
            
        # Step 3: Upload
        logger.info("📤 Step 3: Uploading to Telegram channel...")
        message_ids = already_uploaded_ids.copy()
        
        parts_to_upload = file_parts[parts_already_uploaded:]
        parts_to_keep = parts_to_upload.copy()
        
        for i, part_file in enumerate(parts_to_upload, start=parts_already_uploaded + 1):
            caption = format_movie_caption(
                MOVIE_TITLE,
                is_split=is_split,
                part_number=i if is_split else None,
                total_parts=total_parts if is_split else None
            )
            
            logger.info(f"📤 Uploading part {i}/{total_parts}...")
            
            message_id = upload_with_bot_token(
                part_file,
                caption,
                TELEGRAM_CHAT_ID,
                TELEGRAM_BOT_TOKEN
            )
            
            message_ids.append(message_id)
            save_message_id_immediately(message_id)
            
            # Clean part file
            try:
                os.remove(part_file)
                if part_file in parts_to_keep:
                    parts_to_keep.remove(part_file)
            except Exception as e:
                logger.warning(f"⚠️ Could not delete uploaded part file {part_file}: {e}")
                
        # Step 4: Complete
        logger.info("✅ Step 4: Updating status to completed...")
        update_movie_status(
            "completed",
            is_split=is_split,
            total_parts=total_parts,
            telegram_message_ids=message_ids,
            telegram_channel_id=TELEGRAM_CHAT_ID
        )
        logger.info("🎉 SUCCESS! Processing completed successfully.")
        
    except Exception as e:
        logger.exception(f"❌ Fatal error in processing pipeline: {e}")
        update_movie_status("failed", error_message=str(e))
        sys.exit(1)
    finally:
        safe_cleanup(exclude_files=parts_to_keep)

if __name__ == "__main__":
    main()
