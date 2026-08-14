#!/usr/bin/env python3
"""
Apply categories to existing movies
"""

import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mysql.connector
from category_detector import CategoryDetector

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'techandc_bot',
    'password': '12345Sajibs6@',
    'database': 'techandc_prompts',
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci'
}

def ensure_categories_exist(cursor, conn):
    """Insert default categories if table is empty"""
    cursor.execute("SELECT COUNT(*) as cnt FROM movie_categories")
    row = cursor.fetchone()
    if row['cnt'] > 0:
        return  # Already has data

    print("📂 movie_categories is empty — inserting default categories...")
    default_categories = [
        # (category_name, category_slug, icon, display_order)
        ('Bengali Movies',    'bengali-movies',  'fa-language',     1),
        ('Hindi Movies',      'hindi-movies',    'fa-film',         2),
        ('English Movies',    'english-movies',  'fa-video',        3),
        ('Tamil Movies',      'tamil-movies',    'fa-film',         4),
        ('Telugu Movies',     'telugu-movies',   'fa-film',         5),
        ('Dual Audio',        'dual-audio',      'fa-headphones',   6),
        ('Web Series',        'web-series',      'fa-tv',           7),
        ('4K Ultra HD',       '4k-ultra-hd',     'fa-star',         8),
        ('1080p Full HD',     '1080p-full-hd',   'fa-hd-video',     9),
        ('720p HD',           '720p-hd',         'fa-hd-video',     10),
        ('480p',              '480p',            'fa-check-circle', 11),
        ('Action',            'action',          'fa-bolt',         12),
        ('Comedy',            'comedy',          'fa-laugh',        13),
        ('Drama',             'drama',           'fa-theater-masks',14),
    ]
    for name, slug, icon, order in default_categories:
        cursor.execute("""
            INSERT IGNORE INTO movie_categories
                (category_name, category_slug, icon, display_order, is_active)
            VALUES (%s, %s, %s, %s, 1)
        """, (name, slug, icon, order))
    conn.commit()
    print(f"   ✅ Inserted {len(default_categories)} default categories\n")


def apply_categories_to_movies():
    """Apply categories to all existing movies"""
    
    print("🎬 Starting category application...\n")
    
    try:
        # Connect to database
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        # Get all movies
        cursor.execute("""
            SELECT id, movie_title, quality
            FROM mlsbd_movies
            ORDER BY created_at DESC
        """)
        movies = cursor.fetchall()
        
        print(f"📊 Found {len(movies)} movies to process\n")
        
        # Ensure default categories exist
        ensure_categories_exist(cursor, conn)
        
        detector = CategoryDetector()
        processed = 0
        skipped = 0
        
        for movie in movies:
            movie_id = movie['id']
            title = movie['movie_title']
            
            print(f"Processing: {title[:60]}...")
            
            # Detect categories
            category_slugs = detector.get_category_slugs(title)
            detected_info = detector.detect_from_title(title)
            primary_lang = detector.get_primary_language(title)
            primary_genre = detector.get_primary_genre(title)
            
            if not category_slugs:
                print(f"  ⚠️  No categories detected, skipping")
                skipped += 1
                continue
            
            # Update movie with detected info
            cursor.execute("""
                UPDATE mlsbd_movies
                SET detected_categories = %s,
                    language = %s,
                    genre = %s
                WHERE id = %s
            """, (
                json.dumps(detected_info),
                primary_lang,
                primary_genre,
                movie_id
            ))
            
            # Get category IDs
            cursor.execute("""
                SELECT id, category_slug
                FROM movie_categories
                WHERE category_slug IN ({})
            """.format(','.join(['%s'] * len(category_slugs))), category_slugs)
            
            categories = cursor.fetchall()
            
            if not categories:
                print(f"  ⚠️  No matching categories in database")
                skipped += 1
                continue
            
            # Link movie to categories
            for category in categories:
                try:
                    cursor.execute("""
                        INSERT IGNORE INTO movie_category_links (movie_id, category_id)
                        VALUES (%s, %s)
                    """, (movie_id, category['id']))
                except mysql.connector.IntegrityError:
                    pass  # Already exists
            
            conn.commit()
            
            print(f"  ✅ Assigned to: {', '.join([c['category_slug'] for c in categories])}")
            processed += 1
        
        cursor.close()
        conn.close()
        
        print(f"\n{'='*60}")
        print(f"✅ Completed!")
        print(f"   Processed: {processed} movies")
        print(f"   Skipped: {skipped} movies")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == '__main__':
    apply_categories_to_movies()
