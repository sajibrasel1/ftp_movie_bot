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

# Import slug generator
from slug_generator import generate_slug, ensure_unique_slug

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

# Site configuration (will be loaded from database)
MLSBD_BASE_URL = "https://mlsbd.co"  # Fallback default

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

def get_config_value(cursor, key, default=None):
    """Fetch configuration value from mlsbd_config table"""
    try:
        cursor.execute(
            "SELECT config_value FROM mlsbd_config WHERE config_key = %s",
            (key,)
        )
        result = cursor.fetchone()
        return result[0] if result else default
    except Exception as e:
        logger.warning(f"Error fetching config '{key}': {e}. Using default: {default}")
        return default

def load_mlsbd_config(cursor):
    """Load MLSBD configuration from database"""
    global MLSBD_BASE_URL, MAX_MOVIES_PER_RUN
    
    # Fetch base URL from database
    base_url = get_config_value(cursor, 'base_url', MLSBD_BASE_URL)
    if base_url:
        MLSBD_BASE_URL = base_url.rstrip('/')
        logger.info(f"📡 Loaded MLSBD domain from database: {MLSBD_BASE_URL}")
    
    # Fetch max movies per run
    max_movies = get_config_value(cursor, 'max_movies_per_run', str(MAX_MOVIES_PER_RUN))
    try:
        MAX_MOVIES_PER_RUN = int(max_movies)
        logger.info(f"⚙️ Max movies per run: {MAX_MOVIES_PER_RUN}")
    except ValueError:
        logger.warning(f"Invalid max_movies_per_run value: {max_movies}")


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

def get_base_title(title):
    """Extract clean base title removing quality indicators"""
    import re
    t = re.sub(r'\s*\[?(4K Ultra HD|4K|2160p|1080p Full HD|1080p|Full HD|720p HD|720p|480p|SD)\]?\s*', ' ', title, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', t).strip().strip('[]').strip()

def get_existing_by_base_title(cursor, base_title):
    """Get existing movie row by base title (for merging qualities)"""
    cursor.execute(
        "SELECT id, quality, available_qualities, quality_variants "
        "FROM mlsbd_movies WHERE base_movie_title = %s LIMIT 1",
        (base_title,)
    )
    return cursor.fetchone()

def assign_categories(cursor, movie_id, title, quality=''):
    """Auto-detect and assign categories to a movie"""
    import re as _re
    t = f"{title} {quality}".lower()
    slug_map = {
        'bengali-movies':  _re.search(r'\b(bengali|bangla|hoichoi|chorki|bongodb|iscreen|fridaay|klikk|utshob|cinematic|bongo)\b', t),
        'hindi-movies':    _re.search(r'\b(hindi|bollywood)\b', t),
        'english-movies':  _re.search(r'\b(english|hollywood)\b', t),
        'tamil-movies':    _re.search(r'\b(tamil|kollywood)\b', t),
        'telugu-movies':   _re.search(r'\b(telugu|tollywood)\b', t),
        'dual-audio':      _re.search(r'\bdual\s*audio\b', t),
        'web-series':      _re.search(r'\b(s\d{2}e\d{2}|season\s*\d+|web\s*series|netflix|amazon|hoichoi|hotstar|zee5|sonyliv)\b', t),
        '4k-ultra-hd':     _re.search(r'\b(4k|2160p)\b', t),
        '1080p-full-hd':   _re.search(r'\b1080p?\b', t),
        '720p-hd':         _re.search(r'\b720p?\b', t),
        '480p':            _re.search(r'\b480p?\b', t),
        'action':          _re.search(r'\baction\b', t),
        'comedy':          _re.search(r'\bcomedy\b', t),
        'drama':           _re.search(r'\bdrama\b', t),
    }
    for slug, match in slug_map.items():
        if match:
            try:
                cursor.execute(
                    "SELECT id FROM movie_categories WHERE category_slug=%s LIMIT 1", (slug,))
                row = cursor.fetchone()
                if row:
                    cat_id = row['id'] if isinstance(row, dict) else row[0]
                    cursor.execute(
                        "INSERT IGNORE INTO movie_category_links (movie_id, category_id) VALUES (%s, %s)",
                        (movie_id, cat_id))
            except Exception:
                pass


def insert_movie(cursor, movie_data):
    """
    Smart upsert: merge quality into existing movie if same base title exists.
    Never creates duplicate rows for the same movie.
    """
    try:
        base_title = get_base_title(movie_data["title"])
        quality    = movie_data["quality"]
        dl         = movie_data.get("download_links", {}) or {}
        dl_json    = json.dumps(dl) if dl else None

        existing = get_existing_by_base_title(cursor, base_title)

        if existing:
            # ── MERGE quality into existing row ──
            movie_id = existing['id']
            try:
                avail = json.loads(existing['available_qualities'] or '[]')
            except Exception:
                avail = []
            if quality not in avail:
                avail.append(quality)

            try:
                qv = json.loads(existing['quality_variants'] or '{}')
            except Exception:
                qv = {}
            qv[quality] = {
                'size': 'Unknown',
                'download_links': dl,
                'mlsbd_url': movie_data.get('mlsbd_url', ''),
                'savelinks_url': movie_data.get('savelinks_url', ''),
            }

            QP = {'4K Ultra HD': 4, '1080p Full HD': 3, '720p HD': 2, '480p': 1}
            best_quality = max(avail, key=lambda q: QP.get(q, 0))

            cursor.execute("""
                UPDATE mlsbd_movies
                SET available_qualities = %s,
                    quality_variants    = %s,
                    quality             = %s,
                    updated_at          = NOW()
                WHERE id = %s
            """, (json.dumps(avail), json.dumps(qv), best_quality, movie_id))
            logger.debug(f"Merged quality [{quality}] into: {base_title}")
            return movie_id

        else:
            # ── INSERT new movie ──
            slug = generate_slug(base_title)
            slug = ensure_unique_slug(cursor, slug)

            qv = {quality: {'size': 'Unknown', 'download_links': dl,
                            'mlsbd_url': movie_data.get('mlsbd_url', ''),
                            'savelinks_url': movie_data.get('savelinks_url', '')}}

            cursor.execute(
                """
                INSERT INTO mlsbd_movies
                    (movie_title, slug, mlsbd_url, savelinks_url, gdflix_url,
                     download_links, poster_url, quality, year, status,
                     available_qualities, quality_variants, base_movie_title)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s)
                """,
                (
                    base_title,
                    slug,
                    movie_data["mlsbd_url"],
                    movie_data["savelinks_url"],
                    movie_data.get("gdflix_url"),
                    dl_json,
                    movie_data.get("poster_url"),
                    quality,
                    movie_data["year"],
                    json.dumps([quality]),
                    json.dumps(qv),
                    base_title,
                )
            )
            return cursor.lastrowid

    except mysql.connector.Error as e:
        if e.errno == 1062:
            logger.debug(f"Duplicate slug, skipping: {movie_data['title']}")
            return None
        logger.error(f"Error inserting movie: {e}")
        return None

def get_pending_movies(cursor, limit=1):
    """Get pending movies ready for processing"""
    try:
        cursor.execute(
            """
            SELECT id, movie_title, gdflix_url, download_links, poster_url
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
    Returns dict of all available download links (GDFlix, MultiCloud, FilePress, etc.)
    """
    headers = HEADERS.copy()
    headers['Referer'] = referer_url
    
    try:
        time.sleep(0.5)  # Tiny pause to avoid hitting server too fast
        r = requests.get(savelinks_url, headers=headers, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            logger.warning(f"  ⚠️ Savelinks fetch failed: {r.status_code}")
            return {}
            
        soup = BeautifulSoup(r.text, 'html.parser')
        links = soup.find_all('a', href=True)
        
        # Collect all download links
        download_links = {}
        
        for link in links:
            href = link['href']
            
            # Identify link types
            if 'gdflix' in href.lower():
                download_links['gdflix'] = href
            elif 'multicloud' in href.lower():
                download_links['multicloud'] = href
            elif 'filepress' in href.lower():
                download_links['filepress'] = href
            elif 'hubcloud' in href.lower():
                download_links['hubcloud'] = href
            elif 'instant.io' in href.lower():
                download_links['instant'] = href
                
        if download_links:
            logger.info(f"  📦 Found {len(download_links)} download sources: {', '.join(download_links.keys())}")
        else:
            logger.warning("  ⚠️ No download links found in Savelinks page")
                
        return download_links
    except Exception as e:
        logger.error(f"  ❌ Error resolving Savelinks {savelinks_url}: {e}")
        return {}

def extract_poster_from_page(soup, post_url):
    """
    Extract movie poster/featured image from MLSBD post page.
    Returns poster URL or None.
    """
    try:
        # Try multiple selectors for poster image
        poster_selectors = [
            'meta[property="og:image"]',  # Open Graph image (most reliable)
            'meta[name="twitter:image"]',  # Twitter card image
            'img.wp-post-image',          # WordPress featured image
            'img.attachment-post-thumbnail',
            '.post-thumbnail img',
            '.entry-content img:first-of-type',  # First image in content
            'article img:first-of-type',
            '.movie-poster img',
            '.featured-image img',
        ]
        
        for selector in poster_selectors:
            poster_tag = soup.select_one(selector)
            if poster_tag:
                poster_url = poster_tag.get('content') or poster_tag.get('src') or poster_tag.get('data-src')
                if poster_url:
                    # Skip placeholder/logo images
                    skip_patterns = ['mlsbdshop.png', 'logo.png', 'placeholder', 'default.jpg']
                    if any(pattern in poster_url.lower() for pattern in skip_patterns):
                        continue
                    
                    # Make URL absolute if relative
                    if poster_url.startswith('//'):
                        poster_url = 'https:' + poster_url
                    elif poster_url.startswith('/'):
                        from urllib.parse import urljoin
                        poster_url = urljoin(post_url, poster_url)
                    
                    logger.info(f"  🖼️ Found poster: {poster_url[:80]}...")
                    return poster_url
        
        logger.warning("  ⚠️ No unique poster found on page (only placeholders)")
        return None
        
    except Exception as e:
        logger.error(f"  ❌ Error extracting poster: {e}")
        return None

def crawl_mlsbd():
    """
    Crawls MLSBD homepage, extracts new movie posts, 
    and resolves Savelinks -> GDFlix URLs.
    Automatically detects and updates domain if current one fails.
    """
    global MLSBD_BASE_URL  # Declare at the top of function
    
    logger.info("🎬 Starting MLSBD Crawl...")
    movies_found = []
    
    try:
        # Try to access MLSBD with current domain
        r = requests.get(MLSBD_BASE_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        
        # Check if request failed
        if r.status_code != 200:
            logger.warning(f"⚠️ Current domain {MLSBD_BASE_URL} returned status {r.status_code}")
            logger.info("🔍 Attempting auto-detection of new MLSBD domain...")
            
            # Import and run auto-detection
            try:
                from auto_detect_mlsbd_domain import auto_detect_and_update
                new_domain = auto_detect_and_update()
                
                if new_domain:
                    MLSBD_BASE_URL = new_domain
                    logger.info(f"✅ Switched to new domain: {MLSBD_BASE_URL}")
                    
                    # Retry with new domain
                    r = requests.get(MLSBD_BASE_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
                    if r.status_code != 200:
                        logger.error(f"❌ New domain also failed: {r.status_code}")
                        return []
                else:
                    logger.error("❌ Auto-detection failed. Cannot proceed.")
                    return []
                    
            except Exception as e:
                logger.error(f"❌ Auto-detection error: {e}")
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
                
                # Extract poster from page
                poster_url = extract_poster_from_page(soup_post, post_url)
                
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
                    
                    download_links = resolve_savelinks(sv_url, post_url)
                    
                    if download_links:
                        # Get GDFlix URL for backward compatibility
                        gdflix_url = download_links.get('gdflix')
                        
                        logger.info(f"    ✅ Resolved {len(download_links)} download sources")
                        
                        movie_data = {
                            "title": full_title,
                            "mlsbd_url": post_url,
                            "savelinks_url": sv_url,
                            "gdflix_url": gdflix_url,
                            "download_links": download_links,
                            "poster_url": poster_url,
                            "quality": quality,
                            "year": year
                        }
                        
                        # Double-check database existence (check using GDFlix if available, else first available link)
                        check_url = gdflix_url if gdflix_url else next(iter(download_links.values()))
                        existing = check_movie_exists(cursor, check_url)
                        if not existing:
                            inserted_id = insert_movie(cursor, movie_data)
                            if inserted_id:
                                logger.info(f"    ➕ Inserted pending movie to database: ID={inserted_id}")
                                assign_categories(cursor, inserted_id,
                                                  movie_data.get('title', ''),
                                                  movie_data.get('quality', ''))
                                movies_found.append(movie_data)
                        else:
                            logger.info(f"    ⏭️ Download URL already exists in database (status: {existing[1]})")
                    else:
                        logger.warning("    ❌ No download links found for this Savelinks redirect.")
                        
            except Exception as e:
                logger.error(f"  ❌ Error scraping post page {post_url}: {e}")
                
        db_conn.commit()
        db_conn.close()
        
    except requests.exceptions.RequestException as req_err:
        # Network error or timeout - likely domain issue
        logger.warning(f"⚠️ Network error accessing {MLSBD_BASE_URL}: {req_err}")
        logger.info("🔍 Attempting auto-detection of new MLSBD domain...")
        
        try:
            from auto_detect_mlsbd_domain import auto_detect_and_update
            new_domain = auto_detect_and_update()
            
            if new_domain:
                MLSBD_BASE_URL = new_domain
                logger.info(f"✅ Switched to new domain: {MLSBD_BASE_URL}")
                
                # Retry crawl with new domain (recursive call, one time only)
                logger.info("🔄 Retrying crawl with new domain...")
                return crawl_mlsbd()
            else:
                logger.error("❌ Auto-detection failed. Cannot proceed.")
                return []
                
        except Exception as e:
            logger.error(f"❌ Auto-detection error: {e}")
            return []
    
    except Exception as e:
        logger.error(f"❌ Error scraping MLSBD homepage: {e}")
        return []
        
    return movies_found

# =====================================================
# GITHUB ACTIONS TRIGGER
# =====================================================

def trigger_github_action(movie_id, movie_title, movie_url, download_links=None, poster_url=None):
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
    
    # Convert download_links dict to JSON string for GitHub Actions input
    download_links_str = json.dumps(download_links) if download_links else ""
    
    payload = {
        "ref": "main",
        "inputs": {
            "movie_id": str(movie_id),
            "movie_title": movie_title,
            "movie_url": movie_url,
            "download_links": download_links_str,
            "poster_url": poster_url or "",
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
        # Step 1: Connect to DB and load configuration
        db_conn = get_db_connection()
        if not db_conn:
            logger.error("❌ Database connection failed. Exiting.")
            return
            
        cursor = db_conn.cursor()
        
        # Load MLSBD domain and settings from database
        load_mlsbd_config(cursor)
        
        logger.info("🔍 Checking for pending/failed movies in database...")
        pending = get_pending_movies(cursor, limit=MAX_MOVIES_PER_RUN)
        
        if pending:
            logger.info(f"✅ Found {len(pending)} pending movie(s). Skipping crawl and processing immediately.")
            for movie_id, movie_title, gdflix_url, download_links_json, poster_url in pending:
                logger.info(f"🚀 Triggering process for: {movie_title} (ID: {movie_id})")
                
                # Parse download_links from JSON
                download_links = json.loads(download_links_json) if download_links_json else {}
                
                # Use GDFlix URL as movie_url for backward compatibility
                movie_url = gdflix_url if gdflix_url else (download_links.get('gdflix') or next(iter(download_links.values()), ''))
                
                success = trigger_github_action(movie_id, movie_title, movie_url, download_links, poster_url)
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
            for movie_id, movie_title, gdflix_url, poster_url in pending:
                logger.info(f"🚀 Triggering process for: {movie_title} (ID: {movie_id})")
                
                success = trigger_github_action(movie_id, movie_title, gdflix_url, poster_url)
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
