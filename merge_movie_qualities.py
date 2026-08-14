#!/usr/bin/env python3
"""
Movie Quality Merger
====================
Merges duplicate movies with different qualities into single entries

Example:
- "Malik (2026) [720p HD]"
- "Malik (2026) [1080p Full HD]"
- "Malik (2026) [480p SD]"

Becomes:
- "Malik (2026)" with 3 quality options

Author: AI Assistant
"""

import json
import re
import sys
from collections import defaultdict

import mysql.connector

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'techandc_prompts',
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci'
}


def extract_base_title_and_quality(title):
    """
    Extract base movie title and quality from full title
    
    Args:
        title: Full movie title
        
    Returns:
        tuple: (base_title, quality)
    """
    # Remove quality indicators
    quality_patterns = [
        (r'\s*\[?(480p?|SD)\]?\s*', '480p'),
        (r'\s*\[?(720p?|HD)\]?\s*', '720p'),
        (r'\s*\[?(1080p?|Full\s*HD|FHD)\]?\s*', '1080p'),
        (r'\s*\[?(4K|2160p?|Ultra\s*HD|UHD)\]?\s*', '4K'),
    ]
    
    detected_quality = None
    base_title = title
    
    for pattern, quality in quality_patterns:
        if re.search(pattern, title, re.IGNORECASE):
            detected_quality = quality
            base_title = re.sub(pattern, ' ', title, flags=re.IGNORECASE)
            break
    
    # Clean up extra spaces and brackets
    base_title = re.sub(r'\s+', ' ', base_title).strip()
    base_title = re.sub(r'\s*\[\s*\]\s*', '', base_title)
    
    return base_title, detected_quality


def merge_duplicate_movies():
    """Merge movies with same base title but different qualities"""
    
    print("🎬 Starting Movie Quality Merger...\n")
    print("=" * 70)
    
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        # Get all movies
        cursor.execute("""
            SELECT id, movie_title, slug, quality, movie_size_readable, 
                   download_links, poster_url, mlsbd_url, year,
                   created_at, status
            FROM mlsbd_movies
            WHERE status = 'completed'
            ORDER BY movie_title, quality
        """)
        
        all_movies = cursor.fetchall()
        print(f"📊 Found {len(all_movies)} movies to process\n")
        
        # Group movies by base title
        movie_groups = defaultdict(list)
        
        for movie in all_movies:
            base_title, detected_quality = extract_base_title_and_quality(movie['movie_title'])
            
            # Use detected quality if available, else use database quality
            final_quality = detected_quality or movie['quality']
            
            movie_groups[base_title].append({
                **movie,
                'base_title': base_title,
                'detected_quality': final_quality
            })
        
        print(f"📦 Grouped into {len(movie_groups)} unique movies\n")
        
        # Process groups with multiple qualities
        merged_count = 0
        kept_ids = set()
        delete_ids = set()
        
        for base_title, variants in movie_groups.items():
            if len(variants) <= 1:
                # Single quality - keep as is
                kept_ids.add(variants[0]['id'])
                continue
            
            print(f"🔀 Merging: {base_title}")
            print(f"   Found {len(variants)} quality variants:")
            
            # Sort by quality priority (highest first)
            quality_priority = {'4K': 4, '1080p': 3, '720p': 2, '480p': 1}
            variants.sort(key=lambda x: quality_priority.get(x['detected_quality'], 0), reverse=True)
            
            # Use highest quality as primary
            primary = variants[0]
            kept_ids.add(primary['id'])
            
            # Build quality_variants JSON
            quality_variants = {}
            available_qualities = []
            
            for variant in variants:
                quality = variant['detected_quality'] or 'Unknown'
                available_qualities.append(quality)
                
                # Parse download links
                download_links = {}
                if variant['download_links']:
                    try:
                        download_links = json.loads(variant['download_links'])
                    except:
                        pass
                
                quality_variants[quality] = {
                    'size': variant['movie_size_readable'] or 'Unknown',
                    'download_links': download_links,
                    'mlsbd_url': variant['mlsbd_url']
                }
                
                print(f"      • {quality}: {variant['movie_size_readable']}")
                
                # Mark others for deletion
                if variant['id'] != primary['id']:
                    delete_ids.add(variant['id'])
            
            # Update primary movie with merged data
            cursor.execute("""
                UPDATE mlsbd_movies
                SET base_movie_title = %s,
                    available_qualities = %s,
                    quality_variants = %s,
                    movie_title = %s
                WHERE id = %s
            """, (
                base_title,
                json.dumps(available_qualities),
                json.dumps(quality_variants),
                base_title,  # Clean title without quality
                primary['id']
            ))
            
            merged_count += 1
            print(f"   ✅ Merged into movie ID: {primary['id']}\n")
        
        # Delete duplicate entries
        if delete_ids:
            print(f"🗑️  Deleting {len(delete_ids)} duplicate entries...")
            
            # Delete from category links first
            cursor.execute(f"""
                DELETE FROM movie_category_links
                WHERE movie_id IN ({','.join(map(str, delete_ids))})
            """)
            
            # Delete movies
            cursor.execute(f"""
                DELETE FROM mlsbd_movies
                WHERE id IN ({','.join(map(str, delete_ids))})
            """)
        
        conn.commit()
        
        print("\n" + "=" * 70)
        print(f"✅ Merge completed!")
        print(f"   Unique movies: {len(movie_groups)}")
        print(f"   Multi-quality movies: {merged_count}")
        print(f"   Deleted duplicates: {len(delete_ids)}")
        print("=" * 70)
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    merge_duplicate_movies()
