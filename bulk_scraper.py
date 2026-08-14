#!/usr/bin/env python3
"""
MLSBD Bulk Scraper
==================
One-time bulk scraper to collect 500-1000 movies from MLSBD.
Scrapes multiple pages (not just homepage).

Usage:
    python3 bulk_scraper.py                  # Scrape pages 1-50
    python3 bulk_scraper.py --pages 100      # Scrape pages 1-100
    python3 bulk_scraper.py --start 10       # Start from page 10
    python3 bulk_scraper.py --dry-run        # Test without inserting

After this, use mlsbd_trigger.py for homepage-only new content.
"""

import argparse
import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urljoin

import mysql.connector
import requests
from bs4 import BeautifulSoup

# Import from same folder
from slug_generator import generate_slug, ensure_unique_slug

# =====================================================
# CONFIGURATION
# =====================================================

DB_CONFIG = {
    "host": "localhost",
    "user": "techandc_bot",
    "password": "12345Sajibs6@",
    "database": "techandc_prompts",
}

MLSBD_BASE_URL = "https://mlsbd.co"  # Current working domain
REQUEST_TIMEOUT = 15
CRAWL_DELAY = 1.5  # seconds between requests

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# Accept ALL qualities (not just 720p)
QUALITY_MAP = {
    '4k': '4K Ultra HD',
    '2160p': '4K Ultra HD',
    '1080p': '1080p Full HD',
    '720p': '720p HD',
    '480p': '480p',
    '360p': '360p',
}

# Logging
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "bulk_scraper.log"

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
# DATABASE
# =====================================================

def get_db():
    conn = mysql.connector.connect(**DB_CONFIG)
    conn.autocommit = True
    return conn

def movie_exists(cursor, savelinks_url):
    """Check if this exact savelinks URL already in DB"""
    cursor.execute(
        "SELECT id FROM mlsbd_movies WHERE savelinks_url = %s OR mlsbd_url = %s",
        (savelinks_url, savelinks_url)
    )
    return cursor.fetchone() is not None

def get_existing_by_base_title(cursor, base_title):
    """Get existing movie row by base title (for merging qualities)"""
    cursor.execute(
        "SELECT id, quality, available_qualities, quality_variants, download_links "
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
                    "SELECT id FROM movie_categories WHERE category_slug=%s LIMIT 1",
                    (slug,)
                )
                row = cursor.fetchone()
                if row:
                    cat_id = row['id'] if isinstance(row, dict) else row[0]
                    cursor.execute(
                        "INSERT IGNORE INTO movie_category_links (movie_id, category_id) VALUES (%s, %s)",
                        (movie_id, cat_id)
                    )
            except Exception:
                pass
    """
    Smart insert: if same base_movie_title exists, merge the new quality into it.
    Otherwise insert a new row. Never creates duplicate movies.
    """
    if dry_run:
        logger.info(f"  [DRY RUN] Would upsert: {data['title']}")
        return 999

    base_title = data.get('base_title', data['title'])
    quality    = data['quality']
    dl         = data.get('download_links', {})

    try:
        existing = get_existing_by_base_title(cursor, base_title)

        if existing:
            # ── MERGE: add this quality into existing row ──
            movie_id = existing['id']

            # Parse existing available_qualities
            try:
                avail = json.loads(existing['available_qualities'] or '[]')
            except Exception:
                avail = []
            if quality not in avail:
                avail.append(quality)

            # Parse existing quality_variants
            try:
                qv = json.loads(existing['quality_variants'] or '{}')
            except Exception:
                qv = {}
            qv[quality] = {
                'size': data.get('movie_size_readable', 'Unknown'),
                'download_links': dl,
                'mlsbd_url': data.get('mlsbd_url', ''),
                'savelinks_url': data.get('savelinks_url', ''),
            }

            # Priority order for main quality field
            QP = {'4K Ultra HD': 4, '1080p Full HD': 3, '720p HD': 2, '480p': 1}
            best_quality = max(avail, key=lambda q: QP.get(q, 0))

            cursor.execute("""
                UPDATE mlsbd_movies
                SET available_qualities = %s,
                    quality_variants    = %s,
                    quality             = %s,
                    updated_at          = NOW()
                WHERE id = %s
            """, (
                json.dumps(avail),
                json.dumps(qv),
                best_quality,
                movie_id,
            ))
            logger.info(f"  🔀 Merged quality [{quality}] into existing: {base_title}")
            return movie_id  # return existing id (not a new insert)

        else:
            # ── INSERT: new movie ──
            slug = generate_slug(base_title)
            slug = ensure_unique_slug(cursor, slug)

            qv = {
                quality: {
                    'size': data.get('movie_size_readable', 'Unknown'),
                    'download_links': dl,
                    'mlsbd_url': data.get('mlsbd_url', ''),
                    'savelinks_url': data.get('savelinks_url', ''),
                }
            }

            cursor.execute("""
                INSERT INTO mlsbd_movies
                    (movie_title, slug, mlsbd_url, savelinks_url, gdflix_url,
                     download_links, poster_url, quality, year, status,
                     available_qualities, quality_variants, base_movie_title)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s)
            """, (
                base_title,
                slug,
                data.get('mlsbd_url', ''),
                data.get('savelinks_url', ''),
                data.get('gdflix_url', ''),
                json.dumps(dl),
                data.get('poster_url', ''),
                quality,
                data.get('year'),
                json.dumps([quality]),
                json.dumps(qv),
                base_title,
            ))
            return cursor.lastrowid

    except mysql.connector.Error as e:
        if e.errno == 1062:
            return None  # slug conflict — skip silently
        logger.error(f"  DB error: {e}")
        return None

# =====================================================
# SCRAPING HELPERS
# =====================================================

def parse_quality(text):
    """Extract quality from link text"""
    text_upper = text.upper()
    for key, val in {
        '4K': '4K Ultra HD', '2160P': '4K Ultra HD',
        '1080P': '1080p Full HD',
        '720P': '720p HD',
        '480P': '480p',
    }.items():
        if key in text_upper:
            return val
    return None

def parse_year(text):
    """Extract year from title"""
    match = re.search(r'\((19|20)\d{2}\)', text)
    if match:
        return int(match.group().strip('()'))
    match = re.search(r'\b(19|20)\d{2}\b', text)
    if match:
        return int(match.group())
    return None

def clean_title(text):
    """Clean movie title - remove quality/format terms"""
    title = unquote(text)
    title = re.sub(r'Download & Watch Online.*', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\d+(?:\.\d+)?\s*(?:MB|GB)', '', title, flags=re.IGNORECASE)

    terms = [
        r'\b(?:480p|720p|1080p|2160p|4k|uhd|fhd|sd|hd)\b',
        r'\b(?:x264|x265|hevc|h264|h265|aac|dd5\.1|dual audio|org)\b',
        r'\b(?:web-?dl|webrip|bluray|brrip|bdrip|dvdrip|hdtc|hdts)\b',
    ]
    for term in terms:
        title = re.sub(term, '', title, flags=re.IGNORECASE)

    title = re.sub(r'\((19|20)\d{2}\)', '', title)
    title = re.sub(r'[\u2013\u2014•|\[\]().,_\-–—]+', ' ', title)
    title = re.sub(r'\s+', ' ', title).strip()
    return title

def get_poster(soup, post_url):
    """Extract poster image URL - skip generic/placeholder images"""
    SKIP_IMAGES = ['mlsbdshop.png', 'logo', 'placeholder', 'default', 'banner', 'noimage']

    # Try all image sources in priority order
    candidates = []

    # 1. og:image meta tag
    og = soup.select_one('meta[property="og:image"]')
    if og and og.get('content'):
        candidates.append(og['content'])

    # 2. twitter:image
    tw = soup.select_one('meta[name="twitter:image"]')
    if tw and tw.get('content'):
        candidates.append(tw['content'])

    # 3. All images in post content
    for img in soup.select('.entry-content img, .post-content img, article img'):
        src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
        if src:
            candidates.append(src)

    # 4. wp-post-image
    wp_img = soup.select_one('img.wp-post-image')
    if wp_img:
        src = wp_img.get('src') or wp_img.get('data-src')
        if src:
            candidates.append(src)

    # Return first non-generic image
    for url in candidates:
        url = url.strip()
        if not url:
            continue
        if any(skip in url.lower() for skip in SKIP_IMAGES):
            continue
        if url.startswith('//'):
            url = 'https:' + url
        elif url.startswith('/'):
            url = urljoin(post_url, url)
        if url.startswith('http'):
            return url

    return None

def resolve_savelinks(sv_url, referer):
    """Resolve savelinks.me to get download links"""
    headers = HEADERS.copy()
    headers['Referer'] = referer
    try:
        time.sleep(0.5)
        r = requests.get(sv_url, headers=headers, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            return {}

        soup = BeautifulSoup(r.text, 'html.parser')
        links = {}
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'gdflix' in href.lower():
                links['gdflix'] = href
            elif 'hubcloud' in href.lower():
                links['hubcloud'] = href
            elif 'filepress' in href.lower():
                links['filepress'] = href
            elif 'multicloud' in href.lower():
                links['multicloud'] = href

        return links
    except Exception as e:
        logger.debug(f"Savelinks error: {e}")
        return {}

# =====================================================
# PAGE SCRAPING
# =====================================================

def get_post_links_from_page(page_num):
    """Get all movie post links from a paginated page"""
    if page_num == 1:
        url = MLSBD_BASE_URL
    else:
        url = f"{MLSBD_BASE_URL}/page/{page_num}/"

    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if r.status_code == 404:
            logger.info(f"Page {page_num}: 404 - No more pages")
            return None  # Signal: stop scraping
        if r.status_code != 200:
            logger.warning(f"Page {page_num}: Status {r.status_code}")
            return []

        soup = BeautifulSoup(r.text, 'html.parser')
        links = soup.find_all('a', href=True)

        exclude = ['/category/', '/tag/', '/page/', '/contact', '/about',
                   '/dmca/', '/request/', '/login/', '/author/', '#']
        year_regex = re.compile(r'\((19|20)\d{2}\)')

        posts = []
        seen = set()
        domain = MLSBD_BASE_URL.rstrip('/')

        for link in links:
            href = link['href'].rstrip('/')
            title = link.text.strip()

            if href.startswith(domain) and title:
                if any(ex in href for ex in exclude):
                    continue
                if href == domain:
                    continue
                if year_regex.search(title) and href not in seen:
                    seen.add(href)
                    posts.append((title, href))

        logger.info(f"Page {page_num}: Found {len(posts)} movie posts")
        return posts

    except Exception as e:
        logger.error(f"Page {page_num} error: {e}")
        return []

def is_web_series(title):
    """Check if post is a web series (has episode pattern)"""
    return bool(re.search(r'\bS\d{2}E\d{2}\b|\bSeason\s*\d+\b|\bEpisode\s*\d+\b|\bS\d+E\d+\b', title, re.IGNORECASE))

def get_episode_number(text):
    """Extract episode number from text for sorting"""
    match = re.search(r'E(\d+)', text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 0

def scrape_post(raw_title, post_url, cursor, dry_run=False):
    """Scrape a single movie post and insert all qualities"""
    inserted = 0

    try:
        time.sleep(CRAWL_DELAY)
        r = requests.get(post_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            return 0

        soup = BeautifulSoup(r.text, 'html.parser')
        poster_url = get_poster(soup, post_url)
        base_title = clean_title(raw_title)
        year = parse_year(raw_title)
        series = is_web_series(raw_title)

        # Find all savelinks
        all_savelinks = []
        for a in soup.find_all('a', href=True):
            if 'savelinks.me' in a['href']:
                link_text = a.text.strip()
                # Skip "Watch Online" duplicates
                if 'watch online' in link_text.lower():
                    continue
                all_savelinks.append((link_text, a['href']))

        if not all_savelinks:
            logger.debug(f"  No savelinks found: {raw_title}")
            return 0

        if series:
            # Web Series: MLSBD stores ALL episodes on one page
            # Title has the LATEST episode (e.g., S03E70, S01E47)
            # We only want savelinks for THAT specific episode
            # Each episode has exactly 2-4 download links (one per quality)
            # Strategy: count total qualities in title, take only that many unique links

            # Count qualities mentioned in title
            quality_count = sum(1 for q in ['480p', '720p', '1080p', '4k', '2160p']
                                if q.lower() in raw_title.lower())
            if quality_count == 0:
                quality_count = 2  # fallback: at least 720p + 1080p

            # Deduplicate by URL first
            seen_urls = set()
            unique_links = []
            for link_text, sv_url in all_savelinks:
                if sv_url not in seen_urls:
                    seen_urls.add(sv_url)
                    unique_links.append((link_text, sv_url))

            # Take only the FIRST `quality_count` links = latest episode
            savelinks = unique_links[:quality_count]
            logger.info(f"  Web Series: {len(all_savelinks)} total links → taking first {len(savelinks)} (latest episode)")
        else:
            # Regular movie: deduplicate by URL
            seen_urls = set()
            savelinks = []
            for link_text, sv_url in all_savelinks:
                if sv_url not in seen_urls:
                    seen_urls.add(sv_url)
                    savelinks.append((link_text, sv_url))

        for link_text, sv_url in savelinks:
            quality = parse_quality(link_text)
            if not quality:
                quality = parse_quality(raw_title)
            if not quality:
                quality = '720p HD'

            # Skip if exact savelinks URL already in DB
            if movie_exists(cursor, sv_url):
                logger.debug(f"  Already exists (url): {sv_url}")
                continue

            # Build full title
            full_title = base_title
            if year:
                full_title += f" ({year})"
            full_title += f" [{quality}]"

            # Resolve download links
            download_links = resolve_savelinks(sv_url, post_url)
            gdflix_url = download_links.get('gdflix', '')

            movie_data = {
                'title': full_title,
                'base_title': base_title,
                'mlsbd_url': post_url,
                'savelinks_url': sv_url,
                'gdflix_url': gdflix_url,
                'download_links': download_links,
                'poster_url': poster_url,
                'quality': quality,
                'year': year,
            }

            movie_id = insert_movie(cursor, movie_data, dry_run)
            if movie_id:
                logger.info(f"  ✅ Inserted [{quality}]: {full_title}")
                assign_categories(cursor, movie_id, base_title, quality)
                inserted += 1

    except Exception as e:
        logger.error(f"  Error scraping {post_url}: {e}")

    return inserted

# =====================================================
# MAIN
# =====================================================

def main():
    parser = argparse.ArgumentParser(description='MLSBD Bulk Scraper')
    parser.add_argument('--pages', type=int, default=50, help='Max pages to scrape (default: 50)')
    parser.add_argument('--start', type=int, default=1, help='Start from page number (default: 1)')
    parser.add_argument('--dry-run', action='store_true', help='Test without inserting to DB')
    parser.add_argument('--delay', type=float, default=1.5, help='Delay between requests in seconds')
    args = parser.parse_args()

    global CRAWL_DELAY
    CRAWL_DELAY = args.delay

    logger.info("=" * 70)
    logger.info("🎬 MLSBD BULK SCRAPER STARTING")
    logger.info(f"   Pages: {args.start} to {args.start + args.pages - 1}")
    logger.info(f"   Dry run: {args.dry_run}")
    logger.info(f"   Domain: {MLSBD_BASE_URL}")
    logger.info("=" * 70)

    db = get_db()
    cursor = db.cursor()

    total_inserted = 0
    total_posts = 0
    empty_pages = 0

    for page_num in range(args.start, args.start + args.pages):
        logger.info(f"\n📄 Scraping page {page_num}...")
        posts = get_post_links_from_page(page_num)

        if posts is None:  # 404 - no more pages
            logger.info("✅ Reached last page. Stopping.")
            break

        if not posts:
            empty_pages += 1
            if empty_pages >= 3:
                logger.info("✅ 3 empty pages in a row. Stopping.")
                break
            continue

        empty_pages = 0
        total_posts += len(posts)

        for raw_title, post_url in posts:
            logger.info(f"📽️  {raw_title}")
            count = scrape_post(raw_title, post_url, cursor, args.dry_run)
            total_inserted += count

        logger.info(f"📊 Page {page_num} done. Total inserted so far: {total_inserted}")
        time.sleep(CRAWL_DELAY)

    logger.info("\n" + "=" * 70)
    logger.info("🎬 BULK SCRAPER COMPLETE")
    logger.info(f"   Total posts scanned : {total_posts}")
    logger.info(f"   Total movies inserted: {total_inserted}")
    logger.info("=" * 70)

    db.close()

if __name__ == "__main__":
    main()
