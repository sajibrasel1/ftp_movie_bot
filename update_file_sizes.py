#!/usr/bin/env python3
"""
Update file sizes for existing movies in database
Fetches actual sizes from FTP and updates the database
"""

import logging
import re
import sys
from pathlib import Path

import mysql.connector
import requests
from bs4 import BeautifulSoup

# Database credentials
DB_CONFIG = {
    "host": "localhost",
    "user": "techandc_bot",
    "password": "12345Sajibs6@",
    "database": "techandc_prompts",
}

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def parse_file_size(size_str):
    """Convert size string to bytes"""
    if not size_str:
        return None
    
    size_str = size_str.strip().upper()
    match = re.match(r"([\d.]+)\s*([KMGT])B?", size_str)
    if not match:
        return None
    
    number = float(match.group(1))
    unit = match.group(2)
    
    multipliers = {
        "K": 1024,
        "M": 1024**2,
        "G": 1024**3,
        "T": 1024**4,
    }
    
    return int(number * multipliers.get(unit, 1))


def get_file_size_from_ftp(movie_url):
    """Fetch file size from FTP directory listing"""
    try:
        # Get the directory URL (remove filename)
        directory_url = movie_url.rsplit("/", 1)[0] + "/"
        filename = movie_url.rsplit("/", 1)[1]
        
        response = requests.get(directory_url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        pre_tag = soup.find("pre")
        
        if not pre_tag:
            return None, None
        
        full_text = pre_tag.get_text()
        
        for line in full_text.split("\n"):
            if filename in line:
                parts = line.split()
                if len(parts) >= 4:
                    size_text = parts[-1]
                    size_bytes = parse_file_size(size_text)
                    return size_bytes, size_text
        
        return None, None
        
    except Exception as e:
        logger.debug(f"Error fetching size: {e}")
        return None, None


def main():
    """Update sizes for movies with NULL or 0 bytes"""
    logger.info("=" * 80)
    logger.info("🔧 UPDATING FILE SIZES IN DATABASE")
    logger.info("=" * 80)
    
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Get movies with NULL or unknown sizes
        cursor.execute(
            """
            SELECT id, movie_title, movie_url, movie_size_readable 
            FROM ftp_movies 
            WHERE movie_size_bytes IS NULL OR movie_size_bytes = 0
            LIMIT 100
            """
        )
        
        movies = cursor.fetchall()
        
        if not movies:
            logger.info("✅ All movies already have file sizes")
            return
        
        logger.info(f"Found {len(movies)} movies with unknown sizes")
        logger.info("Fetching sizes from FTP...")
        
        updated_count = 0
        
        for movie_id, title, url, old_size in movies:
            logger.info(f"Processing: {title}")
            
            size_bytes, size_text = get_file_size_from_ftp(url)
            
            if size_bytes:
                cursor.execute(
                    """
                    UPDATE ftp_movies 
                    SET movie_size_bytes = %s, movie_size_readable = %s 
                    WHERE id = %s
                    """,
                    (size_bytes, size_text, movie_id)
                )
                conn.commit()
                updated_count += 1
                logger.info(f"  ✅ Updated: {size_text} ({size_bytes / 1024**3:.2f} GB)")
            else:
                logger.warning(f"  ⚠️ Could not fetch size")
        
        logger.info("=" * 80)
        logger.info(f"✅ Updated {updated_count} movie sizes")
        logger.info("=" * 80)
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.exception(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
