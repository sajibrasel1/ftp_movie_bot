#!/usr/bin/env python3
"""
MLSBD Homepage Scraper with Full Feature Support
- Duplicate prevention (merges qualities for same movie)
- Poster scraping from movie pages
- Download links via Savelinks resolution
- Auto category assignment
- Multi-quality support with quality_variants
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
    """Extract clean base title removing quality indicators"""
    t = re.sub(r'\s*\[?(4K Ultra HD|4K|2160p|1080p Full HD|1080p|Full HD|720p HD|720p|480p|SD)\]?\s*', ' ', title, flags=re.IGNORECASE)
    t = re.sub(r'Download & Watch Online.*', '', t, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', t).strip().strip('[]').strip()

def get_existing_by_base_title(cursor, base_title):
    """Get existing movie row by base title (for merging qualities)"""
    cursor.execute(
        "SELECT id, quality, available_qualities, quality_variants "
        "FROM mlsbd_movies WHERE base_movie_title = %s LIMIT 1",
        (base_title,)
    )
    return cursor.fetchone()

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

def parse_quality(text):
    """Extract movie quality from text - ONLY 720p HD"""
    text_upper = text.upper()
    if '720P' in text_upper:
        return '720p HD'
    return None

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
    """Extract download links from MLSBD movie page via Savelinks"""
    try:
        r = requests.get(movie_url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return {}
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Find Savelinks.me URLs
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'savelinks.me' in href:
                logger.info(f"  🔗 Resolving Savelinks...")
                return resolve_savelinks(href, movie_url)
        
        return {}
    except Exception as e:
        logger.error(f"Download links fetch error: {e}")
        return {}

def assign_categories(cursor, movie_id, title, quality=''):
    """Auto-detect and assign categories to a movie"""
    t = f"{title} {quality}".lower()
    slug_map = {
        'bengali-movies':  re.search(r'\b(bengali|bangla|hoichoi|chorki|bongodb|iscreen|fridaay|klikk|utshob|cinematic|bongo)\b', t),
        'hindi-movies':    re.search(r'\b(hindi|bollywood)\b', t),
        'english-movies':  re.search(r'\b(english|hollywood)\b', t),
        'tamil-movies':    re.search(r'\b(tamil|kollywood)\b', t),
        'telugu-movies':   re.search(r'\b(telugu|tollywood)\b', t),
        'dual-audio':      re.search(r'\bdual\s*audio\b', t),
        'web-series':      re.search(r'\b(s\d{2}e\d{2}|season\s*\d+|web\s*series|netflix|amazon|hoichoi|hotstar|zee5|sonyliv)\b', t),
        '4k-ultra-hd':     re.search(r'\b(4k|2160p)\b', t),
        '1080p-full-hd':   re.search(r'\b1080p?\b', t),
        '720p-hd':         re.search(r'\b720p?\b', t),
        '480p':            re.search(r'\b480p?\b', t),
    }
    for slug, match in slug_map.items():
        if match:
            try:
                cursor.execute("SELECT id FROM movie_categories WHERE category_slug=%s LIMIT 1", (slug,))
                row = cursor.fetchone()
                if row:
                    cat_id = row[0]
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
        quality    = movie_data.get("quality", "720p HD")
        dl         = movie_data.get("download_links", {}) or {}
        dl_json    = json.dumps(dl) if dl else None

        existing = get_existing_by_base_title(cursor, base_title)

        if existing:
            # ── MERGE quality into existing row ──
            movie_id = existing[0]
            try:
                avail = json.loads(existing[2] or '[]')
            except Exception:
                avail = []
            if quality not in avail:
                avail.append(quality)

            try:
                qv = json.loads(existing[3] or '{}')
            except Exception:
                qv = {}
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
            logger.info(f"  🔄 Merged quality [{quality}] into existing movie")
            return movie_id

        else:
            # ── INSERT new movie ──
            slug = generate_slug(base_title)
            slug = ensure_unique_slug(cursor, slug)

            qv = {quality: {'size': 'Unknown', 'download_links': dl,
                            'mlsbd_url': movie_data.get('mlsbd_url', '')}}

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
                    quality,
                    movie_data.get("year"),
                    json.dumps([quality]),
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
    logger.info("🎬 MLSBD HOMEPAGE SCRAPER (Full Features)")
    logger.info("=" * 70)
    
    db_conn = get_db_connection()
    if not db_conn:
        return
    
    cursor = db_conn.cursor()
    
    try:
        r = requests.get(MLSBD_BASE_URL, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        links = soup.find_all('a', href=True)
        year_regex = re.compile(r'\((19|20)\d{2}\)')
        
        seen = set()
        new_count = 0
        updated_count = 0
        
        for link in links[:20]:  # Process top 20 links from homepage
            href = link['href']
            title_text = link.text.strip()
            
            if href.startswith("https://mlsbd.co/") and year_regex.search(title_text):
                if '/category/' not in href and '/tag/' not in href and '/reviews/' not in href:
                    clean_href = href.rstrip('/')
                    
                    if clean_href not in seen and clean_href != "https://mlsbd.co":
                        seen.add(clean_href)
                        
                        clean = clean_title(title_text)
                        year = parse_year(title_text)
                        quality = parse_quality(title_text) or "720p HD"
                        
                        logger.info(f"\n{'─'*50}")
                        logger.info(f"📰 Processing: {clean} [{quality}]")
                        
                        # Check if already exists
                        base_title = get_base_title(clean)
                        existing = get_existing_by_base_title(cursor, base_title)
                        
                        # Fetch poster
                        poster_url = fetch_poster_from_movie_page(clean_href)
                        if poster_url:
                            logger.info(f"  🖼️ Poster found")
                        
                        # Fetch download links
                        download_links = fetch_download_links_from_page(clean_href)
                        if download_links:
                            logger.info(f"  📦 Download links: {', '.join(download_links.keys())}")
                        
                        movie_data = {
                            'title': f"{clean} ({year})" if year else clean,
                            'mlsbd_url': clean_href,
                            'poster_url': poster_url,
                            'download_links': download_links,
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
                            
                            # Assign categories
                            assign_categories(cursor, movie_id, movie_data['title'], quality)
                        
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
