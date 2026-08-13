#!/usr/bin/env python3
"""
Auto-Retry Failed Movies
Automatically resets failed movies to pending for retry
Run this via cron every hour or as needed
"""

import os
import sys
import logging
import pymysql
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('logs/auto_retry.log'),
        logging.StreamHandler()
    ]
)

# Database config (load from .env or hardcode)
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_USER = os.environ.get('DB_USER', 'techandc_bot')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '12345Sajibs6@')
DB_NAME = os.environ.get('DB_NAME', 'techandc_prompts')
DB_TABLE = 'mlsbd_movies'

# Retry config
MAX_AUTO_RETRIES = 3  # Maximum automatic retries
RETRY_DELAY_HOURS = 2  # Wait 2 hours before auto-retry


def get_db_connection():
    """Get database connection"""
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )


def auto_retry_failed():
    """
    Find failed movies that:
    - Have retry_count < MAX_AUTO_RETRIES
    - Failed more than RETRY_DELAY_HOURS ago
    Reset them to pending
    """
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Calculate cutoff time
        cutoff_time = datetime.now() - timedelta(hours=RETRY_DELAY_HOURS)
        
        # Find eligible failed movies
        query = f"""
            SELECT id, movie_title, retry_count, updated_at, error_message
            FROM {DB_TABLE}
            WHERE status = 'failed'
            AND (retry_count IS NULL OR retry_count < %s)
            AND updated_at < %s
            ORDER BY id ASC
        """
        
        cursor.execute(query, (MAX_AUTO_RETRIES, cutoff_time))
        failed_movies = cursor.fetchall()
        
        if not failed_movies:
            logging.info("✅ No failed movies eligible for auto-retry")
            return
        
        logging.info(f"🔍 Found {len(failed_movies)} failed movies eligible for retry")
        
        # Reset each movie to pending
        reset_count = 0
        for movie in failed_movies:
            movie_id = movie['id']
            movie_title = movie['movie_title']
            retry_count = movie['retry_count'] or 0
            error_msg = movie['error_message']
            
            logging.info(f"🔄 Resetting Movie #{movie_id}: {movie_title}")
            logging.info(f"   Previous retries: {retry_count}, Error: {error_msg}")
            
            # Update to pending with incremented retry_count
            update_query = f"""
                UPDATE {DB_TABLE}
                SET status = 'pending',
                    error_message = NULL,
                    retry_count = %s,
                    updated_at = NOW()
                WHERE id = %s
            """
            
            cursor.execute(update_query, (retry_count + 1, movie_id))
            conn.commit()
            reset_count += 1
            
            logging.info(f"✅ Movie #{movie_id} reset to pending (retry #{retry_count + 1})")
        
        logging.info(f"✅ Auto-retry complete: {reset_count} movies reset to pending")
        logging.info(f"📋 These movies will be picked up by the next crawl/trigger")
        
    except Exception as e:
        logging.error(f"❌ Error during auto-retry: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    logging.info("="*80)
    logging.info("🔄 AUTO-RETRY FAILED MOVIES STARTING")
    logging.info("="*80)
    
    try:
        auto_retry_failed()
    except Exception as e:
        logging.error(f"❌ Fatal error: {e}")
        sys.exit(1)
    
    logging.info("🎬 Auto-retry script finished")
