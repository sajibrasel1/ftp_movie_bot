#!/usr/bin/env python3
"""
Poster Backfill Script for MLSBD Movies
Fetches missing posters for existing movies in database
"""
import logging, re, sys, time
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

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"poster_backfill_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

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

def fetch_poster_from_movie_page(movie_url):
    """Fetch poster URL from MLSBD movie detail page"""
    try:
        r = requests.get(movie_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            logger.warning(f"HTTP {r.status_code} for {movie_url}")
            return None
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Try multiple selectors for poster image
        # 1. WordPress post thumbnail
        img = soup.select_one('img.wp-post-image')
        if img and img.get('src'):
            return img['src']
        
        # 2. Featured image in article
        img = soup.select_one('article img, .entry-content img, .post-thumbnail img')
        if img:
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if src and 'logo' not in src.lower():
                return src
        
        # 3. Open Graph image (meta tag)
        og_img = soup.select_one('meta[property="og:image"]')
        if og_img and og_img.get('content'):
            return og_img['content']
        
        # 4. Twitter image meta tag
        twitter_img = soup.select_one('meta[name="twitter:image"]')
        if twitter_img and twitter_img.get('content'):
            return twitter_img['content']
        
        # 5. Any img with movie-related class
        for img in soup.select('img'):
            classes = ' '.join(img.get('class', []))
            if any(keyword in classes.lower() for keyword in ['poster', 'thumbnail', 'featured']):
                src = img.get('src') or img.get('data-src')
                if src:
                    return src
        
        return None
    except Exception as e:
        logger.error(f"Poster fetch error for {movie_url}: {e}")
        return None

def update_poster(cursor, movie_id, poster_url):
    """Update poster_url for a movie"""
    try:
        cursor.execute("""
            UPDATE mlsbd_movies
            SET poster_url = %s
            WHERE id = %s
        """, (poster_url, movie_id))
        return True
    except Exception as e:
        logger.error(f"Update error for movie {movie_id}: {e}")
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Backfill missing posters for MLSBD movies')
    parser.add_argument('--limit', type=int, default=50, help='Max movies to process (default: 50)')
    parser.add_argument('--batch', type=int, default=10, help='Batch size between delays (default: 10)')
    parser.add_argument('--delay', type=float, default=2, help='Delay between requests in seconds (default: 2)')
    parser.add_argument('--all', action='store_true', help='Process ALL movies without poster (ignores --limit)')
    
    args = parser.parse_args()
    
    logger.info("🎨 Starting poster backfill process...")
    logger.info(f"⚙️ Settings: limit={args.limit if not args.all else 'ALL'}, batch={args.batch}, delay={args.delay}s")
    
    db_conn = get_db_connection()
    if not db_conn:
        logger.error("❌ Failed to connect to database")
        return
    
    cursor = db_conn.cursor(dictionary=True)
    
    try:
        # Get movies without posters
        query = """
            SELECT id, movie_title, mlsbd_url
            FROM mlsbd_movies
            WHERE (poster_url IS NULL OR poster_url = '')
              AND mlsbd_url IS NOT NULL
              AND mlsbd_url != ''
            ORDER BY created_at DESC
        """
        
        if not args.all:
            query += f" LIMIT {args.limit}"
        
        cursor.execute(query)
        movies = cursor.fetchall()
        
        total_movies = len(movies)
        logger.info(f"📋 Found {total_movies} movies without posters")
        
        if total_movies == 0:
            logger.info("✅ All movies already have posters!")
            return
        
        success_count = 0
        failed_count = 0
        
        for idx, movie in enumerate(movies, 1):
            movie_id = movie['id']
            title = movie['movie_title']
            mlsbd_url = movie['mlsbd_url']
            
            logger.info(f"[{idx}/{total_movies}] 📥 Fetching poster: {title}")
            logger.info(f"  URL: {mlsbd_url}")
            
            poster_url = fetch_poster_from_movie_page(mlsbd_url)
            
            if poster_url:
                if update_poster(cursor, movie_id, poster_url):
                    success_count += 1
                    logger.info(f"  ✅ Success! Poster: {poster_url[:60]}...")
                else:
                    failed_count += 1
                    logger.warning(f"  ⚠️ Failed to update database")
            else:
                failed_count += 1
                logger.warning(f"  ❌ No poster found")
            
            # Delay between requests (batch-aware)
            if idx < total_movies and idx % args.batch == 0:
                logger.info(f"⏸️ Batch complete. Sleeping {args.delay}s...")
                time.sleep(args.delay)
            else:
                time.sleep(0.5)  # Short delay between individual requests
        
        logger.info("=" * 60)
        logger.info(f"🎉 Backfill complete!")
        logger.info(f"  ✅ Success: {success_count}")
        logger.info(f"  ❌ Failed: {failed_count}")
        logger.info(f"  📊 Total processed: {total_movies}")
        logger.info(f"  📈 Success rate: {(success_count/total_movies*100):.1f}%")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        db_conn.close()

if __name__ == "__main__":
    main()
