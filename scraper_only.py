#!/usr/bin/env python3
"""
MLSBD Homepage Scraper with Multi-Page & Multi-Quality Support
- Scrapes pages 1-3 of MLSBD homepage
- Supports all qualities: 480p, 720p, 1080p, 4K
- Duplicate prevention with base_movie_title matching
- Auto poster fetching and download links resolution
"""
import json, logging, re, sys, time
from datetime import datetime
from pathlib import Path
import mysql.connector
import requests
from bs4 import BeautifulSoup

DB_CONFIG = {
    "host": "localhost",
    "user": "techandc_bot",
    "password": "12345Sajibs6@",
    "database": "techandc_prompts",
}

MLSBD_BASE_URL = "https://mlsbd.co"
MAX_PAGES = 3  # Scrape pages 1-3

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"scraper_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        conn.autocommit = True
        return conn
    except Exception as e:
        logger.error(f"DB error: {e}")
        return None

def get_base_title(title):
    """Extract clean base title removing quality indicators and pipes"""
    t = re.sub(r'\s*\[?(4K Ultra HD|4K|2160p|1080p Full HD|1080p|Full HD|720p HD|720p|480p|SD)\]?\s*', ' ', title, flags=re.IGNORECASE)
    t = re.sub(r'Download & Watch Online.*', '', t, flags=re.IGNORECASE)
    # Remove pipes and extra spaces
    t = re.sub(r'\|+', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    return t.strip().strip('[]').strip()

def get_existing_by_base_title(cursor, base_title):
    """Get existing movie row by base title (for merging qualities)"""
    cursor.execute(
        "SELECT id, quality, available_qualities, quality_variants "
        "FROM mlsbd_movies WHERE base_movie_title = %s LIMIT 1",
        (base_title,)
    )
    return cursor.fetchone()

def parse_quality(text):
    """Extract movie quality from text - supports all qualities"""
    text_upper = text.upper()
    
    # Priority order: 4K > 1080p > 720p > 480p
    if '4K' in text_upper or '2160P' in text_upper:
        return '4K Ultra HD'
    elif '1080P' in text_upper:
        return '1080p Full HD'
    elif '720P' in text_upper:
        return '720p HD'
    elif '480P' in text_upper:
        return '480p'
    
    # Default fallback
    return '720p HD'

def resolve_savelinks(savelinks_url, referer_url):
    """Resolve Savelinks.me redirect page to extract download links"""
    headers = HEADERS.copy()
    headers['Referer'] = referer_url
    
    try:
        time.sleep(0.5)
        r = requests.get(savelinks_url, headers=headers, timeout=15)
        if r.status_code != 200:
            return {}
            
        soup = BeautifulSoup(r.text, 'html.parser')
        links = soup.find_all('a', href=True)
        
        download_links = {}
        for link in links:
            href = link['href']
            if 'gdflix' in href.lower():
                download_links['gdflix'] = href
            elif 'multicloud' in href.lower():
                download_links['multicloud'] = href
            elif 'filepress' in href.lower():
                download_links['filepress'] = href
            elif 'hubcloud' in href.lower():
                download_links['hubcloud'] = href
                
        return download_links
    except Exception as e:
        logger.error(f"Savelinks resolution error: {e}")
        return {}

def fetch_download_links_from_page(movie_url):
    """Extract ALL quality-specific download links from MLSBD movie page"""
    try:
        r = requests.get(movie_url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return {}, {}
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Collect ALL savelinks URLs with their surrounding text/context
        savelinks_urls = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'savelinks.me' in href:
                # Get surrounding text to detect quality
                link_text = a.get_text(strip=True)
                # Check parent elements for quality context
                parent_text = ''
                parent = a.parent
                for _ in range(3):
                    if parent:
                        parent_text = parent.get_text(strip=True)
                        parent = parent.parent
                context = f"{link_text} {parent_text}"
                savelinks_urls.append((href, context))
        
        if not savelinks_urls:
            return {}, {}
        
        logger.info(f"  🔗 Found {len(savelinks_urls)} Savelinks URLs")
        
        # Map qualities to savelinks
        quality_map = {
            '4K Ultra HD': [],
            '1080p Full HD': [],
            '720p HD': [],
            '480p': [],
        }
        unmapped = []
        
        for url, context in savelinks_urls:
            ctx_upper = context.upper()
            if '4K' in ctx_upper or '2160P' in ctx_upper:
                quality_map['4K Ultra HD'].append(url)
            elif '1080P' in ctx_upper:
                quality_map['1080p Full HD'].append(url)
            elif '720P' in ctx_upper:
                quality_map['720p HD'].append(url)
            elif '480P' in ctx_upper:
                quality_map['480p'].append(url)
            else:
                unmapped.append(url)
        
        # If context-based mapping failed, distribute by order
        # MLSBD usually orders: 480p, 720p, 1080p, 4K
        if all(len(v) == 0 for v in quality_map.values()) and unmapped:
            order = ['480p', '720p HD', '1080p Full HD', '4K Ultra HD']
            for i, url in enumerate(unmapped):
                if i < len(order):
                    quality_map[order[i]].append(url)
        
        # Resolve each quality's savelinks
        quality_downloads = {}
        for quality, urls in quality_map.items():
            if urls:
                logger.info(f"  🔄 Resolving {quality}...")
                links = resolve_savelinks(urls[0], movie_url)
                if links:
                    quality_downloads[quality] = links
                    logger.info(f"  📦 {quality}: {', '.join(links.keys())}")
                time.sleep(1)
        
        # Also return best quality links as flat dict (for backward compat)
        best_links = {}
        for q in ['4K Ultra HD', '1080p Full HD', '720p HD', '480p']:
            if q in quality_downloads:
                best_links = quality_downloads[q]
                break
        
        return best_links, quality_downloads
        
    except Exception as e:
        logger.error(f"Download links fetch error: {e}")
        return {}, {}

def fetch_poster_from_movie_page(movie_url):
    """Fetch poster URL from MLSBD movie detail page"""
    try:
        r = requests.get(movie_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Try multiple selectors
        img = soup.select_one('img.wp-post-image')
        if img and img.get('src'):
            return img['src']
        
        img = soup.select_one('article img, .entry-content img, .post-thumbnail img')
        if img:
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if src and 'logo' not in src.lower():
                return src
        
        og_img = soup.select_one('meta[property="og:image"]')
        if og_img and og_img.get('content'):
            return og_img['content']
        
        return None
    except Exception as e:
        logger.error(f"Poster fetch error: {e}")
        return None

def generate_slug(title):
    """Generate URL-friendly slug"""
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s-]+', '-', slug)
    return slug.strip('-')[:200]

def ensure_unique_slug(cursor, slug):
    """Ensure slug is unique by appending number if needed"""
    original_slug = slug
    counter = 1
    while True:
        cursor.execute("SELECT id FROM mlsbd_movies WHERE slug = %s", (slug,))
        if not cursor.fetchone():
            return slug
        slug = f"{original_slug}-{counter}"
        counter += 1

def insert_movie(cursor, movie_data):
    """
    Smart upsert: merge ALL qualities into existing movie if same base title exists.
    Never creates duplicate rows for the same movie.
    """
    try:
        base_title = get_base_title(movie_data["title"])
        quality    = movie_data.get("quality", "720p HD")
        dl         = movie_data.get("download_links", {}) or {}
        dl_json    = json.dumps(dl) if dl else None
        # quality_downloads = dict of {quality: {links}} for ALL qualities
        quality_downloads = movie_data.get("quality_downloads", {}) or {}

        existing = get_existing_by_base_title(cursor, base_title)

        if existing:
            # ── MERGE qualities into existing row ──
            movie_id = existing[0]
            try:
                avail = json.loads(existing[2] or '[]')
            except Exception:
                avail = []
            try:
                qv = json.loads(existing[3] or '{}')
            except Exception:
                qv = {}

            # Merge all detected qualities
            if quality_downloads:
                for q, links in quality_downloads.items():
                    if q not in avail:
                        avail.append(q)
                    qv[q] = {
                        'size': 'Unknown',
                        'download_links': links,
                        'mlsbd_url': movie_data.get('mlsbd_url', ''),
                    }
            else:
                # Fallback: just single quality
                if quality not in avail:
                    avail.append(quality)
                qv[quality] = {
                    'size': 'Unknown',
                    'download_links': dl,
                    'mlsbd_url': movie_data.get('mlsbd_url', ''),
                }

            QP = {'4K Ultra HD': 4, '1080p Full HD': 3, '720p HD': 2, '480p': 1}
            best_quality = max(avail, key=lambda q: QP.get(q, 0))

            cursor.execute("""
                UPDATE mlsbd_movies
                SET available_qualities = %s,
                    quality_variants    = %s,
                    quality             = %s,
                    poster_url          = COALESCE(poster_url, %s),
                    updated_at          = NOW()
                WHERE id = %s
            """, (json.dumps(avail), json.dumps(qv), best_quality, movie_data.get('poster_url'), movie_id))
            logger.info(f"  🔄 Merged {len(avail)} qualities into existing movie")
            return movie_id

        else:
            # ── INSERT new movie ──
            slug = generate_slug(base_title)
            slug = ensure_unique_slug(cursor, slug)

            # Build quality_variants from all detected qualities
            if quality_downloads:
                qv = {}
                avail = []
                for q, links in quality_downloads.items():
                    avail.append(q)
                    qv[q] = {'size': 'Unknown', 'download_links': links,
                             'mlsbd_url': movie_data.get('mlsbd_url', '')}
                QP = {'4K Ultra HD': 4, '1080p Full HD': 3, '720p HD': 2, '480p': 1}
                best_quality = max(avail, key=lambda q: QP.get(q, 0))
            else:
                avail = [quality]
                qv = {quality: {'size': 'Unknown', 'download_links': dl,
                                'mlsbd_url': movie_data.get('mlsbd_url', '')}}
                best_quality = quality

            cursor.execute(
                """
                INSERT INTO mlsbd_movies
                    (movie_title, slug, mlsbd_url, download_links, poster_url, 
                     quality, year, status, available_qualities, quality_variants, base_movie_title)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'completed', %s, %s, %s)
                """,
                (
                    base_title,
                    slug,
                    movie_data["mlsbd_url"],
                    dl_json,
                    movie_data.get("poster_url"),
                    best_quality,
                    movie_data.get("year"),
                    json.dumps(avail),
                    json.dumps(qv),
                    base_title,
                )
            )
            return cursor.lastrowid

    except Exception as e:
        logger.error(f"Error inserting/updating movie: {e}")
        return None

def clean_title(text):
    """Clean movie title"""
    title = re.sub(r'Download & Watch Online.*', '', text, flags=re.IGNORECASE)
    title = re.sub(r'\d+(?:\.\d+)?\s*(?:MB|GB)', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\b(480p|720p|1080p|x264|web-?dl|bluray)\b', '', title, flags=re.IGNORECASE)
    title = re.sub(r'[\[\]().,_\-–—]+', ' ', title)
    return re.sub(r'\s+', ' ', title).strip()

def parse_year(text):
    """Extract year from title"""
    match = re.search(r'\((19|20)\d{2}\)', text)
    return int(match.group().strip('()')) if match else None

def main():
    logger.info("=" * 70)
    logger.info(f"🎬 MLSBD HOMEPAGE SCRAPER (Pages 1-{MAX_PAGES})")
    logger.info("=" * 70)
    
    db_conn = get_db_connection()
    if not db_conn:
        return
    
    cursor = db_conn.cursor()
    all_posts = []
    
    try:
        # Scrape multiple pages
        for page_num in range(1, MAX_PAGES + 1):
            if page_num == 1:
                page_url = MLSBD_BASE_URL
            else:
                page_url = f"{MLSBD_BASE_URL}/page/{page_num}/"
            
            logger.info(f"\n📄 Scraping page {page_num}: {page_url}")
            
            r = requests.get(page_url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                logger.warning(f"⚠️ Page {page_num} returned status {r.status_code}")
                continue
            
            soup = BeautifulSoup(r.text, 'html.parser')
            links = soup.find_all('a', href=True)
            year_regex = re.compile(r'\((19|20)\d{2}\)')
            
            seen = set()
            page_posts = 0
            
            for link in links:
                href = link['href']
                title_text = link.text.strip()
                
                if href.startswith("https://mlsbd.co/") and year_regex.search(title_text):
                    if '/category/' not in href and '/tag/' not in href and '/reviews/' not in href:
                        clean_href = href.rstrip('/')
                        
                        if clean_href not in seen and clean_href != "https://mlsbd.co":
                            seen.add(clean_href)
                            all_posts.append((title_text, clean_href))
                            page_posts += 1
            
            logger.info(f"  ✅ Found {page_posts} movie posts on page {page_num}")
            time.sleep(1)  # Delay between pages
        
        logger.info(f"\n🔍 Total {len(all_posts)} unique movie posts found across {MAX_PAGES} pages")
        
        new_count = 0
        updated_count = 0
        
        for raw_title, post_url in all_posts[:30]:  # Process top 30 to keep it reasonable
            clean = clean_title(raw_title)
            year = parse_year(raw_title)
            quality = parse_quality(raw_title)
            
            base_title = get_base_title(clean)
            existing = get_existing_by_base_title(cursor, base_title)
            
            logger.info(f"\n{'─'*50}")
            logger.info(f"📰 Processing: {clean} [{quality}]")
            
            # Fetch poster
            poster_url = fetch_poster_from_movie_page(post_url)
            if poster_url:
                logger.info(f"  🖼️ Poster found")
            
            # Fetch download links - ALL qualities
            download_links, quality_downloads = fetch_download_links_from_page(post_url)
            if quality_downloads:
                logger.info(f"  📦 Quality downloads: {list(quality_downloads.keys())}")
            elif download_links:
                logger.info(f"  📦 Download links: {', '.join(download_links.keys())}")
            
            movie_data = {
                'title': f"{clean} ({year})" if year else clean,
                'mlsbd_url': post_url,
                'poster_url': poster_url,
                'download_links': download_links,
                'quality_downloads': quality_downloads,
                'quality': quality,
                'year': year,
            }
            
            movie_id = insert_movie(cursor, movie_data)
            if movie_id:
                if existing:
                    updated_count += 1
                    logger.info(f"  ✅ Updated existing movie (ID: {movie_id})")
                else:
                    new_count += 1
                    logger.info(f"  ✅ Added new movie (ID: {movie_id})")
            
            time.sleep(2)  # Delay to respect server
        
        logger.info("\n" + "=" * 70)
        logger.info(f"🎉 Scraping complete!")
        logger.info(f"  ➕ New movies: {new_count}")
        logger.info(f"  🔄 Updated movies: {updated_count}")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        db_conn.close()

if __name__ == "__main__":
    main()
