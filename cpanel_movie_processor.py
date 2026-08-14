#!/usr/bin/env python3
"""
cPanel Direct Movie Processor
=============================
Processes pending movies and posts directly to Telegram
NO GitHub Actions - Everything runs on cPanel

Flow:
1. Get pending movies from database
2. Download poster image
3. Auto-detect and assign categories
4. Post to Telegram with website link
5. Mark as completed

Author: AI Assistant
Version: 2.1 (With Auto Categories)
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import mysql.connector
import requests
from telethon import TelegramClient, Button
from telethon.sessions import StringSession

# Import category detector
from category_detector import CategoryDetector

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

# Telegram credentials
TELEGRAM_API_ID = int(os.environ.get("TELEGRAM_API_ID", "28186143"))
TELEGRAM_API_HASH = os.environ.get("TELEGRAM_API_HASH", "6073c3149388bbc06e818add0be1622d")
TELEGRAM_SESSION = os.environ.get("TELEGRAM_SESSION", (
    "1BVtsOJ0Bu1pxJKbdngNZprbcKPoGy5JsesQEEz6Wq_KgdkeQmkcH8Lto7vokIX"
    "Jomxjy8k9uoXIBDZvr01VwNTbrZKJOjo9gMVHanqyeA-kEFWrS4QNi_S_miWc3F"
    "L9Pk7F-Rr1N28jZEbu8yGx8qN774KT1J4DtA5QWkvt4_52UlU6InRiAhyBXUB_S"
    "Ogn5Xw06xHeKDjDxrQI5A-SfwD6Yl_NA5GIeOZz4KtLc333wa_nKEXbZ2_97m0Q"
    "3CpdsgmKS9KWaXmBqCu0s97y1nqXxHaqWh5oDBJ6048QmHedO7JMr-64W83yu4D"
    "DLcOBIds19nki4tngGdFBCVyMb1KlavbW-rqU="
))
TELEGRAM_BOT_TOKEN = "8294665841:AAGA0fldnAJj0dazXQsa9p67HARnqACwW0E"
TELEGRAM_CHANNEL = "https://t.me/newmoviesarena4u"
TELEGRAM_CHAT_ID = "@newmoviesarena4u"  # Channel username

# Movie website URL
MOVIE_SITE_URL = "https://movies.techandclick.site"

# Logging
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "cpanel_movie_processor.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Temp directory for posters
TEMP_DIR = BASE_DIR / "temp_posters"
TEMP_DIR.mkdir(exist_ok=True)

# =====================================================
# DATABASE FUNCTIONS
# =====================================================

def get_db_connection():
    """Create database connection"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        conn.autocommit = False
        return conn
    except mysql.connector.Error as e:
        logger.error(f"Database connection failed: {e}")
        sys.exit(1)


def get_pending_movies(cursor, limit=5):
    """Get pending movies ready for Telegram posting"""
    cursor.execute(
        """
        SELECT id, movie_title, slug, poster_url, quality,
               movie_size_readable, year, download_links, mlsbd_url,
               available_qualities
        FROM mlsbd_movies 
        WHERE status = 'pending'
        AND poster_url IS NOT NULL
        AND slug IS NOT NULL
        AND (telegram_message_ids IS NULL OR telegram_message_ids = '')
        ORDER BY created_at ASC
        LIMIT %s
        """,
        (limit,)
    )
    return cursor.fetchall()


def mark_movie_as_processing(cursor, movie_id):
    """Mark movie as processing"""
    cursor.execute(
        "UPDATE mlsbd_movies SET status = 'processing', processing_started_at = NOW() WHERE id = %s",
        (movie_id,)
    )


def mark_movie_as_completed(cursor, movie_id, telegram_message_id):
    """Mark movie as posted to Telegram (keep pending status, just record message id)"""
    cursor.execute(
        """
        UPDATE mlsbd_movies 
        SET telegram_message_ids = %s,
            telegram_channel_id = %s,
            processing_completed_at = NOW()
        WHERE id = %s
        """,
        (json.dumps([telegram_message_id]), str(TELEGRAM_CHAT_ID), movie_id)
    )


def assign_categories_to_movie(cursor, movie_id, movie_title):
    """
    Auto-detect and assign categories to movie
    
    Args:
        cursor: Database cursor
        movie_id: Movie ID
        movie_title: Movie title for detection
        
    Returns:
        list: Category slugs assigned
    """
    try:
        detector = CategoryDetector()
        
        # Detect categories from title
        category_slugs = detector.get_category_slugs(movie_title)
        detected_info = detector.detect_from_title(movie_title)
        primary_lang = detector.get_primary_language(movie_title)
        primary_genre = detector.get_primary_genre(movie_title)
        
        if not category_slugs:
            logger.warning(f"No categories detected for: {movie_title}")
            return []
        
        # Update movie with detected info
        cursor.execute(
            """
            UPDATE mlsbd_movies
            SET detected_categories = %s,
                language = %s,
                genre = %s
            WHERE id = %s
            """,
            (json.dumps(detected_info), primary_lang, primary_genre, movie_id)
        )
        
        # Get category IDs from slugs
        placeholders = ','.join(['%s'] * len(category_slugs))
        cursor.execute(
            f"""
            SELECT id, category_slug
            FROM movie_categories
            WHERE category_slug IN ({placeholders})
            AND is_active = 1
            """,
            category_slugs
        )
        
        categories = cursor.fetchall()
        
        if not categories:
            logger.warning(f"No matching categories in database for: {', '.join(category_slugs)}")
            return []
        
        # Link movie to categories
        assigned_slugs = []
        for cat_id, cat_slug in categories:
            try:
                cursor.execute(
                    """
                    INSERT IGNORE INTO movie_category_links (movie_id, category_id)
                    VALUES (%s, %s)
                    """,
                    (movie_id, cat_id)
                )
                assigned_slugs.append(cat_slug)
            except mysql.connector.IntegrityError:
                pass  # Already exists
        
        logger.info(f"✅ Assigned categories: {', '.join(assigned_slugs)}")
        return assigned_slugs
        
    except Exception as e:
        logger.error(f"❌ Failed to assign categories: {e}")
        return []


def mark_movie_as_failed(cursor, movie_id, error_message):
    """Mark movie as failed"""
    cursor.execute(
        """
        UPDATE mlsbd_movies 
        SET status = 'failed',
            error_message = %s,
            retry_count = retry_count + 1,
            last_retry_at = NOW()
        WHERE id = %s
        """,
        (error_message[:1000], movie_id)
    )


# =====================================================
# POSTER DOWNLOAD
# =====================================================

def download_poster(poster_url, movie_id):
    """Download poster image from URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(poster_url, headers=headers, timeout=30, stream=True)
        response.raise_for_status()
        
        # Determine file extension
        content_type = response.headers.get('Content-Type', '')
        if 'jpeg' in content_type or 'jpg' in content_type:
            ext = '.jpg'
        elif 'png' in content_type:
            ext = '.png'
        elif 'webp' in content_type:
            ext = '.webp'
        else:
            ext = '.jpg'  # Default
        
        # Save to temp file
        poster_path = TEMP_DIR / f"poster_{movie_id}{ext}"
        
        with open(poster_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"✅ Poster downloaded: {poster_path}")
        return poster_path
        
    except Exception as e:
        logger.error(f"❌ Failed to download poster: {e}")
        return None


# =====================================================
# TELEGRAM POSTING
# =====================================================

async def post_movie_to_telegram(client, movie, poster_path):
    """Post movie to Telegram with poster and website link"""
    try:
        movie_id, movie_title, slug, poster_url, quality, size, year, download_links, mlsbd_url, available_qualities = movie

        # Build movie page URL
        movie_url = f"{MOVIE_SITE_URL}/movie.php?slug={slug}"

        # Parse available qualities
        qualities_str = ''
        if available_qualities:
            try:
                qs = json.loads(available_qualities)
                if isinstance(qs, list) and qs:
                    qualities_str = ' | '.join(qs)
            except Exception:
                pass
        if not qualities_str and quality:
            qualities_str = quality

        # Build caption
        caption_lines = [
            f"🎬 **{movie_title}**",
            "",
        ]
        if year:
            caption_lines.append(f"📅 {year}")
        if qualities_str:
            caption_lines.append(f"🎞 {qualities_str}")
        if size:
            caption_lines.append(f"💾 {size}")

        caption_lines += [
            "",
            "👇 Watch & Download",
        ]
        caption = '\n'.join(caption_lines)

        # Inline button
        buttons = [[Button.url("🎬 Watch Now & Download", movie_url)]]

        # Send with poster or text-only
        if poster_path and poster_path.exists():
            message = await client.send_file(
                TELEGRAM_CHAT_ID,
                file=str(poster_path),
                caption=caption,
                buttons=buttons,
                parse_mode='md'
            )
        else:
            message = await client.send_message(
                TELEGRAM_CHAT_ID,
                caption,
                buttons=buttons,
                parse_mode='md'
            )

        logger.info(f"✅ Posted to Telegram: {movie_title} (msg_id={message.id})")
        return message.id

    except Exception as e:
        logger.error(f"❌ Failed to post to Telegram: {e}")
        return None


# =====================================================
# MAIN PROCESSING
# =====================================================

async def process_movies():
    """Main processing function"""
    logger.info("=" * 80)
    logger.info("🎬 CPANEL MOVIE PROCESSOR STARTED")
    logger.info("=" * 80)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get pending movies
        movies = get_pending_movies(cursor, limit=5)
        
        if not movies:
            logger.info("✅ No pending movies. All caught up!")
            return
        
        logger.info(f"📋 Found {len(movies)} pending movies")
        
        # Initialize Telegram client
        client = TelegramClient(
            StringSession(TELEGRAM_SESSION) if TELEGRAM_SESSION else "cpanel_processor",
            TELEGRAM_API_ID,
            TELEGRAM_API_HASH
        )
        
        await client.start()
        logger.info("✅ Connected to Telegram")
        
        # Process each movie
        success_count = 0
        failed_count = 0
        
        for movie in movies:
            movie_id = movie[0]
            movie_title = movie[1]
            poster_url = movie[3]
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing: {movie_title}")
            logger.info(f"Movie ID: {movie_id}")
            
            try:
                # Mark as processing
                mark_movie_as_processing(cursor, movie_id)
                conn.commit()
                
                # Auto-assign categories
                logger.info("🏷️  Detecting and assigning categories...")
                assigned_categories = assign_categories_to_movie(cursor, movie_id, movie_title)
                conn.commit()
                
                # Download poster
                poster_path = None
                if poster_url:
                    poster_path = download_poster(poster_url, movie_id)
                
                # Post to Telegram
                message_id = await post_movie_to_telegram(client, movie, poster_path)
                
                if message_id:
                    # Mark as completed
                    mark_movie_as_completed(cursor, movie_id, message_id)
                    conn.commit()
                    success_count += 1
                    logger.info(f"✅ Movie {movie_id} completed successfully")
                    
                    # Cleanup poster
                    if poster_path and poster_path.exists():
                        poster_path.unlink()
                else:
                    raise Exception("Failed to post to Telegram")
                
                # Wait between posts
                await asyncio.sleep(3)
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ Failed to process movie {movie_id}: {error_msg}")
                
                # Mark as failed
                mark_movie_as_failed(cursor, movie_id, error_msg)
                conn.commit()
                failed_count += 1
        
        logger.info("=" * 80)
        logger.info(f"✅ Success: {success_count}")
        logger.info(f"❌ Failed: {failed_count}")
        logger.info("=" * 80)
        
        await client.disconnect()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


# =====================================================
# ENTRY POINT
# =====================================================

if __name__ == "__main__":
    asyncio.run(process_movies())
