#!/usr/bin/env python3
"""
MLSBD Auto Domain Detector
===========================
Automatically detects new MLSBD domain when old one fails.

Strategy:
1. Try current domain from database
2. If fails, Google search "mlsbd movies download"
3. Extract working MLSBD domain from search results
4. Update database automatically
5. Continue scraping with new domain

Author: AI Assistant
Version: 1.0
"""

import re
import logging
import requests
from bs4 import BeautifulSoup
import mysql.connector

# Database credentials
DB_CONFIG = {
    "host": "localhost",
    "user": "techandc_bot",
    "password": "12345Sajibs6@",
    "database": "techandc_prompts",
}

# User-Agent for requests
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

logger = logging.getLogger(__name__)

def test_domain(domain):
    """
    Test if domain is accessible and looks like MLSBD site.
    Returns True if accessible, False otherwise.
    """
    try:
        # Ensure domain starts with http(s)
        if not domain.startswith('http'):
            domain = 'https://' + domain
        
        # Try to access homepage
        response = requests.get(domain, headers=HEADERS, timeout=10, allow_redirects=True)
        
        # Check if accessible
        if response.status_code != 200:
            return False
        
        # Check if it looks like MLSBD (has "mlsbd" in content or typical markers)
        html_lower = response.text.lower()
        
        # MLSBD indicators
        indicators = [
            'mlsbd',
            'bengali movie',
            'download',
            'web-dl',
            'bongobd'
        ]
        
        # At least 2 indicators should match
        matches = sum(1 for indicator in indicators if indicator in html_lower)
        
        if matches >= 2:
            logger.info(f"✅ Domain {domain} appears to be valid MLSBD site (matched {matches} indicators)")
            return True
        else:
            logger.warning(f"⚠️ Domain {domain} accessible but doesn't look like MLSBD")
            return False
            
    except Exception as e:
        logger.debug(f"❌ Domain {domain} test failed: {e}")
        return False

def google_search_mlsbd():
    """
    Search Google for "mlsbd" and extract potential domains.
    Returns list of potential MLSBD domains.
    """
    search_queries = [
        'mlsbd movies download site',
        'mlsbd bengali movies',
        'mlsbd.co alternatives',
    ]
    
    potential_domains = set()
    
    for query in search_queries:
        try:
            # Google search URL
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            
            logger.info(f"🔍 Searching Google: {query}")
            
            response = requests.get(search_url, headers=HEADERS, timeout=10)
            
            if response.status_code != 200:
                continue
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract all links from search results
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link.get('href', '')
                
                # Extract actual URL from Google redirect
                # Google wraps URLs like: /url?q=https://mlsbd.xyz/...
                if '/url?q=' in href:
                    match = re.search(r'/url\?q=([^&]+)', href)
                    if match:
                        actual_url = match.group(1)
                        
                        # Check if it's an MLSBD domain
                        if 'mlsbd' in actual_url.lower():
                            # Extract base domain
                            domain_match = re.match(r'https?://([^/]+)', actual_url)
                            if domain_match:
                                domain = domain_match.group(0)
                                potential_domains.add(domain)
                                logger.info(f"   Found potential domain: {domain}")
            
            # Add small delay between searches
            import time
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"❌ Google search failed for '{query}': {e}")
    
    return list(potential_domains)

def find_working_mlsbd_domain():
    """
    Find a working MLSBD domain by:
    1. Trying common known domains
    2. Google searching if those fail
    3. Testing each found domain
    
    Returns working domain or None
    """
    logger.info("🔍 Auto-detecting MLSBD domain...")
    
    # Step 1: Try common known domains first (fast)
    common_domains = [
        'https://mlsbd.co',
        'https://mlsbd.biz',
        'https://mlsbd.net',
        'https://mlsbd.shop',
        'https://mlsbd.site',
        'https://mlsbd.xyz',
        'https://mlsbd.info',
        'https://mlsbd.me',
    ]
    
    logger.info("📋 Testing common MLSBD domains...")
    for domain in common_domains:
        logger.info(f"   Testing: {domain}")
        if test_domain(domain):
            logger.info(f"✅ Found working domain: {domain}")
            return domain
    
    # Step 2: If common domains fail, Google search
    logger.info("🔍 Common domains failed. Searching Google...")
    potential_domains = google_search_mlsbd()
    
    if not potential_domains:
        logger.error("❌ No potential domains found via Google search")
        return None
    
    logger.info(f"📋 Testing {len(potential_domains)} domains from Google...")
    for domain in potential_domains:
        logger.info(f"   Testing: {domain}")
        if test_domain(domain):
            logger.info(f"✅ Found working domain: {domain}")
            return domain
    
    logger.error("❌ No working MLSBD domain found")
    return None

def update_domain_in_db(new_domain):
    """Update MLSBD domain in database config table"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Update domain
        cursor.execute(
            "UPDATE mlsbd_config SET config_value = %s WHERE config_key = 'base_url'",
            (new_domain,)
        )
        conn.commit()
        
        logger.info(f"✅ Database updated with new domain: {new_domain}")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to update database: {e}")
        return False

def auto_detect_and_update():
    """
    Main function: Auto-detect working MLSBD domain and update database.
    Returns the working domain or None.
    """
    working_domain = find_working_mlsbd_domain()
    
    if working_domain:
        logger.info(f"🎯 Detected working domain: {working_domain}")
        
        # Update database
        if update_domain_in_db(working_domain):
            logger.info("✅ Domain auto-detection and update successful!")
            return working_domain
        else:
            logger.error("❌ Failed to update database")
            return None
    else:
        logger.error("❌ Could not find any working MLSBD domain")
        return None

if __name__ == "__main__":
    # Setup logging for standalone run
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    
    print("=" * 60)
    print("🔍 MLSBD Auto Domain Detection Starting...")
    print("=" * 60)
    
    result = auto_detect_and_update()
    
    if result:
        print(f"\n✅ Success! New domain: {result}")
    else:
        print("\n❌ Failed to detect working domain")
