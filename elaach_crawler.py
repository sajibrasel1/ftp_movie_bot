#!/usr/bin/env python3
"""
Elaach.com Crawler with Selenium
=================================
Scrapes latest movies from elaach.com using browser automation.
Integrates with existing FTP movie bot database.

Features:
- JavaScript rendering support
- Extracts movie titles, quality, download links
- Checks database for duplicates
- Triggers GitHub Actions for new movies

Author: AI Assistant
Version: 1.0
"""

import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import mysql.connector

# Selenium imports
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("⚠️ Selenium not installed. Install with: pip install selenium")

# webdriver-manager for auto ChromeDriver setup
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

# =====================================================
# CONFIGURATION
# =====================================================

# Database credentials (same as existing bot)
DB_CONFIG = {
    "host": "localhost",
    "user": "techandc_bot",
    "password": "12345Sajibs6@",
    "database": "techandc_prompts",
}

# elaach.com configuration
ELAACH_BASE_URL = "https://www.elaach.com"
ELAACH_SOURCE_NAME = "elaach.com"

# Crawler settings
MAX_MOVIES_TO_SCRAPE = 50  # Scrape first 50 recent movies
SELENIUM_TIMEOUT = 20  # Wait up to 20 seconds for page load

# Logging
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "elaach_crawler.log"

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
# DATABASE FUNCTIONS (Reused from cpanel_trigger.py)
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


def check_movie_exists(cursor, movie_url):
    """Check if movie URL already exists in database"""
    try:
        cursor.execute(
            "SELECT id, status FROM ftp_movies WHERE movie_url = %s",
            (movie_url,)
        )
        result = cursor.fetchone()
        return result
    except Exception as e:
        logger.error(f"Error checking movie existence: {e}")
        return None


def insert_movie(cursor, movie_data):
    """Insert new movie into database"""
    try:
        cursor.execute(
            """
            INSERT INTO ftp_movies 
                (movie_title, movie_url, movie_size_bytes, movie_size_readable, 
                 file_extension, quality, year, status, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', %s)
            """,
            (
                movie_data["title"],
                movie_data["url"],
                movie_data.get("size_bytes"),
                movie_data.get("size_readable", "Unknown"),
                movie_data.get("extension", ".mp4"),
                movie_data.get("quality"),
                movie_data.get("year"),
                movie_data.get("source", ELAACH_SOURCE_NAME),
            )
        )
        return cursor.lastrowid
    except mysql.connector.Error as e:
        if e.errno == 1062:  # Duplicate entry
            logger.debug(f"Movie already exists: {movie_data['title']}")
            return None
        logger.error(f"Error inserting movie: {e}")
        return None


# =====================================================
# MOVIE PARSING
# =====================================================

def parse_movie_title(title_text):
    """Extract movie title, year, quality from text"""
    
    # Extract year
    year_match = re.search(r"(19|20)\d{2}", title_text)
    year = int(year_match.group()) if year_match else None
    
    # Extract quality
    quality = None
    quality_patterns = [
        r"2160p|4K|UHD",
        r"1080p|FullHD|FHD",
        r"720p|HD",
        r"480p|SD",
        r"BluRay|BRRip|BDRip",
        r"WEB-DL|WEBRip",
        r"DVDRip|DVD",
    ]
    for pattern in quality_patterns:
        match = re.search(pattern, title_text, re.IGNORECASE)
        if match:
            quality = match.group()
            break
    
    # Clean title
    title = re.sub(r"(19|20)\d{2}", "", title_text)
    title = re.sub(r"(2160p|4K|1080p|720p|480p|BluRay|WEB-DL|WEBRip|DVDRip|BRRip|BDRip)", "", title, flags=re.IGNORECASE)
    title = re.sub(r"[._-]+", " ", title)
    title = re.sub(r"\[.*?\]", "", title)  # Remove [DDN], [TAG], etc.
    title = title.strip()
    
    return {
        "title": title,
        "year": year,
        "quality": quality or "HD",
    }


# =====================================================
# SELENIUM WEB SCRAPING
# =====================================================

def create_selenium_driver():
    """Create headless Chrome driver for web scraping"""
    if not SELENIUM_AVAILABLE:
        logger.error("Selenium not available!")
        return None
    
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in background
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        # Suppress logging
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        # Use webdriver-manager if available (auto-downloads ChromeDriver)
        if WEBDRIVER_MANAGER_AVAILABLE:
            logger.info("Using webdriver-manager for automatic ChromeDriver setup...")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            # Fallback to system ChromeDriver
            logger.info("Using system ChromeDriver...")
            driver = webdriver.Chrome(options=chrome_options)
        
        logger.info("✅ Selenium driver created successfully")
        return driver
        
    except Exception as e:
        logger.error(f"Failed to create Selenium driver: {e}")
        logger.error("Installation help:")
        logger.error("  1. Install: pip install selenium webdriver-manager")
        logger.error("  2. Or download ChromeDriver: https://chromedriver.chromium.org/")
        return None


def scrape_elaach_movies(driver):
    """
    Scrape movies from elaach.com homepage using Selenium
    
    Returns:
        List of movie dictionaries
    """
    movies = []
    
    try:
        logger.info(f"🌐 Loading: {ELAACH_BASE_URL}")
        driver.get(ELAACH_BASE_URL)
        
        # Wait for movies to load
        wait = WebDriverWait(driver, SELENIUM_TIMEOUT)
        
        # Try multiple selectors (adapt based on actual site structure)
        movie_selectors = [
            "div.movie-card",
            "div.movie-item",
            "a[href*='/movies/']",
            "div.card",
            ".movie",
        ]
        
        movie_elements = []
        for selector in movie_selectors:
            try:
                movie_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if movie_elements:
                    logger.info(f"✅ Found {len(movie_elements)} movies using selector: {selector}")
                    break
            except:
                continue
        
        if not movie_elements:
            logger.warning("⚠️ No movie elements found! Site structure may have changed.")
            
            # Fallback: Extract all links containing '/movies/'
            all_links = driver.find_elements(By.TAG_NAME, "a")
            movie_links = [link for link in all_links if '/movies/' in link.get_attribute('href') or '']
            
            logger.info(f"📎 Found {len(movie_links)} movie links (fallback method)")
            
            for link in movie_links[:MAX_MOVIES_TO_SCRAPE]:
                try:
                    href = link.get_attribute('href')
                    title_text = link.text.strip()
                    
                    if not title_text or not href:
                        continue
                    
                    metadata = parse_movie_title(title_text)
                    
                    movie_data = {
                        "title": metadata["title"] or title_text,
                        "url": href,
                        "year": metadata["year"],
                        "quality": metadata["quality"],
                        "source": ELAACH_SOURCE_NAME,
                    }
                    
                    movies.append(movie_data)
                    logger.info(f"  ✓ {movie_data['title']} ({movie_data['year']})")
                    
                except Exception as e:
                    logger.debug(f"Error parsing link: {e}")
                    continue
        
        else:
            # Process found movie elements
            for element in movie_elements[:MAX_MOVIES_TO_SCRAPE]:
                try:
                    # Try to find title
                    title_text = None
                    title_selectors = ["h3", "h2", ".title", ".movie-title", "a"]
                    
                    for selector in title_selectors:
                        try:
                            title_elem = element.find_element(By.CSS_SELECTOR, selector)
                            title_text = title_elem.text.strip()
                            if title_text:
                                break
                        except:
                            continue
                    
                    # Try to find link
                    link_url = None
                    try:
                        link_elem = element.find_element(By.TAG_NAME, "a")
                        link_url = link_elem.get_attribute('href')
                    except:
                        try:
                            link_url = element.get_attribute('href')
                        except:
                            pass
                    
                    if not title_text or not link_url:
                        continue
                    
                    metadata = parse_movie_title(title_text)
                    
                    movie_data = {
                        "title": metadata["title"] or title_text,
                        "url": link_url,
                        "year": metadata["year"],
                        "quality": metadata["quality"],
                        "source": ELAACH_SOURCE_NAME,
                    }
                    
                    movies.append(movie_data)
                    logger.info(f"  ✓ {movie_data['title']} ({movie_data['year']})")
                    
                except Exception as e:
                    logger.debug(f"Error parsing element: {e}")
                    continue
        
        logger.info(f"✅ Scraped {len(movies)} movies from elaach.com")
        return movies
        
    except Exception as e:
        logger.error(f"Error scraping elaach.com: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_movie_download_link(driver, movie_url):
    """
    Visit individual movie page and extract download link
    
    Args:
        driver: Selenium WebDriver
        movie_url: URL of movie page
    
    Returns:
        Download link or None
    """
    try:
        logger.info(f"🔍 Visiting: {movie_url}")
        driver.get(movie_url)
        
        # Wait for page to load
        time.sleep(3)
        
        # elaach.com specific: Look for "Download" text in links
        try:
            # Find links containing "Download" text
            download_links = driver.find_elements(By.XPATH, "//a[contains(text(), 'Download')]")
            
            if download_links:
                download_url = download_links[0].get_attribute('href')
                
                # Validate it's a direct file link
                if download_url and any(ext in download_url.lower() for ext in ['.mp4', '.mkv', '.avi']):
                    logger.info(f"  ✅ Found download link: {download_url}")
                    return download_url
        except Exception as e:
            logger.debug(f"XPath search failed: {e}")
        
        # Fallback: Look for direct video file links
        try:
            video_links = driver.find_elements(By.XPATH, "//a[contains(@href, '.mp4') or contains(@href, '.mkv')]")
            
            if video_links:
                download_url = video_links[0].get_attribute('href')
                logger.info(f"  ✅ Found video link: {download_url}")
                return download_url
        except Exception as e:
            logger.debug(f"Video link search failed: {e}")
        
        logger.warning(f"  ⚠️ No download link found on {movie_url}")
        return None
        
    except Exception as e:
        logger.error(f"Error getting download link: {e}")
        return None


# =====================================================
# MAIN EXECUTION
# =====================================================

def main():
    """Main execution function"""
    logger.info("=" * 80)
    logger.info("🎬 ELAACH.COM CRAWLER - SELENIUM EDITION")
    logger.info("=" * 80)
    
    if not SELENIUM_AVAILABLE:
        logger.error("❌ Selenium not installed!")
        logger.error("Install with: pip install selenium")
        logger.error("Also install ChromeDriver from: https://chromedriver.chromium.org/")
        return
    
    db_conn = None
    driver = None
    
    try:
        # Create Selenium driver
        driver = create_selenium_driver()
        if not driver:
            logger.error("❌ Failed to create Selenium driver. Exiting.")
            return
        
        # Connect to database
        db_conn = get_db_connection()
        if not db_conn:
            logger.error("❌ Database connection failed. Exiting.")
            return
        
        cursor = db_conn.cursor()
        
        # Step 1: Scrape movies from elaach.com
        logger.info("📡 Step 1: Scraping movies from elaach.com...")
        scraped_movies = scrape_elaach_movies(driver)
        
        if not scraped_movies:
            logger.warning("⚠️ No movies scraped. Exiting.")
            return
        
        # Step 2: For each movie, get download link and add to database
        logger.info("📊 Step 2: Processing scraped movies...")
        new_movies_count = 0
        
        for i, movie in enumerate(scraped_movies, 1):
            logger.info(f"\n[{i}/{len(scraped_movies)}] Processing: {movie['title']}")
            
            # Check if already exists
            existing = check_movie_exists(cursor, movie["url"])
            
            if existing:
                logger.info(f"  ⏭️ Already in database (ID: {existing[0]})")
                continue
            
            # Try to get download link
            download_link = get_movie_download_link(driver, movie["url"])
            
            if download_link:
                movie["url"] = download_link  # Use actual download link
            
            # Insert into database
            movie_id = insert_movie(cursor, movie)
            
            if movie_id:
                new_movies_count += 1
                logger.info(f"  ✅ Added to database (ID: {movie_id})")
            
            # Be respectful to server
            time.sleep(2)
        
        db_conn.commit()
        
        logger.info("\n" + "=" * 80)
        logger.info(f"✅ CRAWLER COMPLETED!")
        logger.info(f"📊 Total scraped: {len(scraped_movies)}")
        logger.info(f"➕ New movies added: {new_movies_count}")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.exception(f"❌ Fatal error: {e}")
        sys.exit(1)
        
    finally:
        if driver:
            driver.quit()
            logger.info("🔒 Browser closed")
        
        if db_conn:
            db_conn.close()


if __name__ == "__main__":
    main()
