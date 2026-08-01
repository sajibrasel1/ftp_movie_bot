#!/usr/bin/env python3
"""
Auto Retry Failed Movies
=========================
This script automatically retries failed movies.
Runs via cron job to check for stuck/failed movies and reset them to pending.

Usage: Run via cron every 30 minutes
*/30 * * * * cd /home/techandc/movie_bot_new/ftp_movie_bot && source set_env.sh && /home/techandc/virtualenv/movie_bot_new/3.11/bin/python auto_retry_failed.py >> logs/auto_retry.log 2>&1
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import mysql.connector

# =====================================================
# CONFIGURATION
# =====================================================

DB_CONFIG = {
    "host": "localhost",
    "user": "techandc_bot",
    "password": "12345Sajibs6@",
    "database": "techandc_prompts",
}

MAX_RETRY_COUNT = 5  # Maximum 5 retries
STUCK_TIMEOUT_MINUTES = 60  # If processing for more than 60 minutes, consider it stuck

# Logging
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "auto_retry.log"

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
    """Get MySQL database connection"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        conn.autocommit = True
        return conn
    except mysql.connector.Error as e:
        logger.error(f"Database connection failed: {e}")
        return None


def reset_failed_movies(cursor):
    """Reset failed movies to pending (if retry count < max)"""
    try:
        cursor.execute(
            """
            UPDATE ftp_movies 
            SET status = 'pending', 
                error_message = NULL,
                github_run_id = NULL,
                processing_started_at = NULL
            WHERE status = 'failed' 
              AND retry_count < %s
            """,
            (MAX_RETRY_COUNT,)
        )
        
        affected_rows = cursor.rowcount
        return affected_rows
    except Exception as e:
        logger.error(f"Error resetting failed movies: {e}")
        return 0


def reset_stuck_movies(cursor):
    """Reset stuck movies (processing for too long)"""
    try:
        stuck_threshold = datetime.now() - timedelta(minutes=STUCK_TIMEOUT_MINUTES)
        
        cursor.execute(
            """
            UPDATE ftp_movies 
            SET status = 'pending', 
                error_message = 'Processing timeout - auto-reset',
                retry_count = retry_count + 1,
                github_run_id = NULL,
                processing_started_at = NULL
            WHERE status = 'processing' 
              AND processing_started_at < %s
              AND retry_count < %s
            """,
            (stuck_threshold, MAX_RETRY_COUNT)
        )
        
        affected_rows = cursor.rowcount
        return affected_rows
    except Exception as e:
        logger.error(f"Error resetting stuck movies: {e}")
        return 0


def get_status_summary(cursor):
    """Get current status summary"""
    try:
        cursor.execute(
            """
            SELECT status, COUNT(*) as count 
            FROM ftp_movies 
            GROUP BY status
            """
        )
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting status summary: {e}")
        return []


# =====================================================
# MAIN EXECUTION
# =====================================================

def main():
    """Main execution function"""
    logger.info("=" * 80)
    logger.info("🔄 AUTO RETRY FAILED MOVIES - STARTING")
    logger.info("=" * 80)
    
    db_conn = None
    
    try:
        # Connect to database
        db_conn = get_db_connection()
        if not db_conn:
            logger.error("❌ Database connection failed. Exiting.")
            return
        
        cursor = db_conn.cursor()
        
        # Get current status
        logger.info("📊 Current Status:")
        status_summary = get_status_summary(cursor)
        for status, count in status_summary:
            logger.info(f"  {status}: {count}")
        
        # Reset failed movies
        logger.info("\n🔄 Resetting failed movies...")
        failed_reset = reset_failed_movies(cursor)
        logger.info(f"✅ Reset {failed_reset} failed movies to pending")
        
        # Reset stuck movies
        logger.info("\n🔄 Checking for stuck processing movies...")
        stuck_reset = reset_stuck_movies(cursor)
        logger.info(f"✅ Reset {stuck_reset} stuck movies to pending")
        
        # Get updated status
        logger.info("\n📊 Updated Status:")
        status_summary = get_status_summary(cursor)
        for status, count in status_summary:
            logger.info(f"  {status}: {count}")
        
        logger.info("=" * 80)
        logger.info(f"✅ AUTO RETRY COMPLETED: {failed_reset + stuck_reset} movies reset")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.exception(f"❌ Fatal error: {e}")
        sys.exit(1)
        
    finally:
        if db_conn:
            db_conn.close()


if __name__ == "__main__":
    main()
