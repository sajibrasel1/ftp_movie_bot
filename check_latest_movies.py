#!/usr/bin/env python3
"""
Check Latest Movies on FTP Servers
Manually browse movie directories to find recent uploads
"""

import requests
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime

# Working servers
SERVERS = [
    {"name": "Media CTG Fun", "url": "http://media.ctgfun.com/"},
    {"name": "BDCine", "url": "http://www.bdcine.com/"},
    {"name": "Fun Villa", "url": "http://funvilla.com/"},
    {"name": "Flix BD", "url": "http://flixbd.com/"},
]

# Common movie folder paths
MOVIE_PATHS = [
    "Movies/",
    "Movie/",
    "Hollywood/",
    "Hollywood Movies/",
    "2026/",
    "2026 Movies/",
    "English/",
    "Latest/",
    "New/",
]

def browse_server(server):
    """Browse a server for movie directories"""
    print(f"\n{'='*80}")
    print(f"Checking: {server['name']} - {server['url']}")
    print('='*80)
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    try:
        # Get main page
        response = session.get(server['url'], timeout=15)
        if response.status_code != 200:
            print(f"  ERROR: Status {response.status_code}")
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a')
        
        print(f"\nMain Directory Contents:")
        print("-"*80)
        
        folders = []
        for link in links:
            href = link.get('href', '')
            text = link.get_text().strip()
            
            if href and href != '../' and '/' in href:
                folders.append({'href': href, 'text': text})
                print(f"  [{href}] {text}")
        
        # Try common movie paths
        print(f"\nChecking common movie folders:")
        print("-"*80)
        
        for path in MOVIE_PATHS:
            try:
                folder_url = urllib.parse.urljoin(server['url'], path)
                print(f"\nTrying: {folder_url}")
                
                r = session.get(folder_url, timeout=10)
                if r.status_code == 200:
                    print(f"  FOUND! Status: {r.status_code}")
                    
                    folder_soup = BeautifulSoup(r.text, 'html.parser')
                    folder_links = folder_soup.find_all('a')
                    
                    # Show first 20 items
                    print(f"  Contents (first 20 items):")
                    count = 0
                    for f_link in folder_links[:20]:
                        f_href = f_link.get('href', '')
                        f_text = f_link.get_text().strip()
                        if f_href and f_href != '../':
                            print(f"    - {f_text}")
                            count += 1
                    
                    if count > 0:
                        print(f"\n  Total items found: {count}")
                else:
                    print(f"  Not found (Status: {r.status_code})")
            except Exception as e:
                print(f"  Error: {str(e)}")
        
    except Exception as e:
        print(f"  ERROR: {str(e)}")

if __name__ == '__main__':
    print("="*80)
    print("CHECKING FTP SERVERS FOR LATEST MOVIES")
    print("="*80)
    print(f"Time: {datetime.now()}")
    
    for server in SERVERS:
        browse_server(server)
        print("\n")
    
    print("\n" + "="*80)
    print("FINISHED")
    print("="*80)
