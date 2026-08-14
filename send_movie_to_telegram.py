#!/usr/bin/env python3
"""
Send Movie to Telegram with Website Link
=========================================
Sends movie poster + "Watch Now" button to Telegram group
Links to movies.techandclick.site instead of direct downloads
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import mysql.connector
from telethon import TelegramClient, Button
from telethon.sessions import StringSession

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

# Telegram credentials (from environment or hardcode)
API_ID = int(os.environ.get("TELEGRAM_API_ID", "YOUR_API_ID"))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "YOUR_API_HASH")
SESSION_STRING = os.environ.get("TELEGRAM_SESSION", "")

# Target Telegram group/channel
TELEGRAM_CHAT_ID = -1003916118619  # Your group ID

# Movie website URL
MOVIE_SITE_URL = "https://movies.techandclick.site"

# Logging
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "telegram_movie_sender.log"

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


def get_completed_movies_to_post(cursor, limit=10):
    """Get completed movies that haven't been posted to Telegram yet"""
    cursor.execute(
        """
        SELECT id, movie_title, slug, poster_url, quality, 
               movie_size_readable, year, download_links
        FROM mlsbd_movies 
        WHERE status = 'completed' 
        AND (telegram_message_ids IS NULL OR telegram_message_ids = '')
        AND poster_url IS NOT NULL
        AND slug IS NOT NULL
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (limit,)
    )
    return cursor.fetchall()


def mark_movie_as_posted(cursor, movie_id, message_id):
    """Mark movie as posted to Telegram"""
    cursor.execute(
        """
        UPDATE mlsbd_movies 
        SET telegram_message_ids = %s,
            telegram_channel_id = %s
        WHERE id = %s
        """,
        (json.dumps([message_id]), str(TELEGRAM_CHAT_ID), movie_id)
    )


# =====================================================
# TELEGRAM FUNCTIONS
# =====================================================

async def send_movie_to_telegram(client, movie):
    """
    Send movie poster with Watch Now button to Telegram
    
    Args:
        client: Telethon client
        movie: Movie dict from database
        
    Returns:
        int: Message ID if successful, None otherwise
    """
    try:
        movie_id = movie[0]
        movie_title = movie[1]
        slug = movie[2]
        poster_url = movie[3]
        quality = movie[4]
        size = movie[5]
        year = movie[6]
        
        # Build movie URL
        movie_url = f"{MOVIE_SITE_URL}/{slug}"
        
        # Build caption
        caption = f"🎬 **{movie_title}**\n\n"
        
        if quality:
            caption += f"📺 Quality: **{quality}**\n"
        if year:
            caption += f"📅 Year: **{year}**\n"
        if size:
            caption += f"💾 Size: **{size}**\n"
        
        caption += f"\n🔗 Watch & Download:\n👇 Click the button below"
        
        # Create inline button
        buttons = [
            [Button.url("🎬 Watch Now", movie_url)]
        ]
        
        # Send photo with caption and button
        message = await client.send_file(
            TELEGRAM_CHAT_ID,
            file=poster_url,
            caption=caption,
            buttons=buttons,
            parse_mode='md'
        )
        
        logger.info(f"✅ Posted movie ID {movie_id}: {movie_title}")
        logger.info(f"   URL: {movie_url}")
        logger.info(f"   Message ID: {message.id}")
        
        return message.id
        
    except Exception as e:
        logger.error(f"❌ Failed to send movie ID {movie_id}: {e}")
        return None


async def main():
    """Main function"""
    logger.info("=" * 80)
    logger.info("🎬 TELEGRAM MOVIE SENDER STARTED")
    logger.info("=" * 80)
    
    # Database connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get movies to post
        movies = get_completed_movies_to_post(cursor, limit=10)
        
        if not movies:
            logger.info("No movies to post. All caught up!")
            return
        
        logger.info(f"Found {len(movies)} movies to post")
        
        # Initialize Telegram client
        client = TelegramClient(
            StringSession(SESSION_STRING) if SESSION_STRING else "movie_sender",
            API_ID,
            API_HASH
        )
        
        await client.start()
        logger.info("✅ Connected to Telegram")
        
        # Send each movie
        sent_count = 0
        failed_count = 0
        
        for movie in movies:
            movie_id = movie[0]
            
            # Send to Telegram
            message_id = await send_movie_to_telegram(client, movie)
            
            if message_id:
                # Mark as posted in database
                mark_movie_as_posted(cursor, movie_id, message_id)
                conn.commit()
                sent_count += 1
                
                # Wait a bit between messages to avoid rate limits
                await asyncio.sleep(2)
            else:
                failed_count += 1
        
        logger.info("=" * 80)
        logger.info(f"✅ Sent: {sent_count}")
        logger.info(f"❌ Failed: {failed_count}")
        logger.info("=" * 80)
        
        await client.disconnect()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    asyncio.run(main())
