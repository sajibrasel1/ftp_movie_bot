#!/usr/bin/env python3
"""
Movie Quality Merger
====================
Merges duplicate movies with different qualities into single entries.
Always deletes duplicates BEFORE updating primary to avoid unique constraint errors.
"""

import json
import re
from collections import defaultdict
import mysql.connector

DB_CONFIG = {
    'host': 'localhost',
    'user': 'techandc_bot',
    'password': '12345Sajibs6@',
    'database': 'techandc_prompts',
    'charset': 'utf8mb4',
}

QP = {'4K Ultra HD': 4, '1080p Full HD': 3, '720p HD': 2, '480p': 1}


def extract_quality(title):
    for pattern, quality in [
        (r'4K Ultra HD|4K|2160p', '4K Ultra HD'),
        (r'1080p Full HD|1080p|Full HD', '1080p Full HD'),
        (r'720p HD|720p', '720p HD'),
        (r'480p|SD', '480p'),
    ]:
        if re.search(pattern, title, re.IGNORECASE):
            return quality
    return None


def clean_base_title(title):
    t = re.sub(
        r'\s*\[?(4K Ultra HD|4K|2160p|1080p Full HD|1080p|Full HD|720p HD|720p|480p|SD)\]?\s*',
        ' ', title, flags=re.IGNORECASE
    )
    return re.sub(r'\s+', ' ', t).strip().strip('[]').strip()


def merge_duplicate_movies():
    print("🎬 Starting Movie Quality Merger...\n" + "=" * 70)

    conn = mysql.connector.connect(**DB_CONFIG)
    conn.autocommit = False
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, movie_title, slug, quality, movie_size_readable,
               download_links, poster_url, mlsbd_url, year, base_movie_title
        FROM mlsbd_movies ORDER BY id ASC
    """)
    all_movies = cursor.fetchall()
    print(f"📊 Found {len(all_movies)} movies to process\n")

    # Group by base title
    groups = defaultdict(list)
    for m in all_movies:
        base = (m.get('base_movie_title') or '').strip()
        if not base:
            base = clean_base_title(m['movie_title'])
        base = clean_base_title(base)
        detected_q = extract_quality(m['movie_title']) or m.get('quality') or '720p HD'
        groups[base].append({**m, '_base': base, '_q': detected_q})

    print(f"📦 Grouped into {len(groups)} unique movies\n")

    merged_count = 0
    deleted_count = 0
    skipped_count = 0

    for base_title, variants in groups.items():
        # Single entry — just ensure base_movie_title is set
        if len(variants) == 1:
            m = variants[0]
            if not (m.get('base_movie_title') or '').strip():
                try:
                    cursor.execute(
                        "UPDATE mlsbd_movies SET base_movie_title=%s WHERE id=%s",
                        (base_title, m['id'])
                    )
                    conn.commit()
                except Exception:
                    conn.rollback()
            continue

        # Sort: highest quality first
        variants.sort(key=lambda x: QP.get(x['_q'], 0), reverse=True)
        primary = variants[0]

        # Build merged data
        available_qualities = []
        quality_variants = {}
        for v in variants:
            q = v['_q']
            available_qualities.append(q)
            dl = {}
            if v.get('download_links'):
                try:
                    dl = json.loads(v['download_links'])
                except Exception:
                    pass
            quality_variants[q] = {
                'size': v.get('movie_size_readable') or 'Unknown',
                'download_links': dl,
                'mlsbd_url': v.get('mlsbd_url', ''),
            }

        dup_ids = [v['id'] for v in variants if v['id'] != primary['id']]

        try:
            # ── 1. DELETE duplicates first (avoids unique constraint on UPDATE) ──
            if dup_ids:
                id_list = ','.join(map(str, dup_ids))
                try:
                    cursor.execute(
                        f"DELETE FROM movie_category_links WHERE movie_id IN ({id_list})"
                    )
                except Exception:
                    pass
                cursor.execute(
                    f"DELETE FROM mlsbd_movies WHERE id IN ({id_list})"
                )
                deleted_count += len(dup_ids)

            # ── 2. UPDATE primary with merged data ──
            best_quality = max(available_qualities, key=lambda q: QP.get(q, 0))
            cursor.execute("""
                UPDATE mlsbd_movies
                SET base_movie_title    = %s,
                    movie_title         = %s,
                    quality             = %s,
                    available_qualities = %s,
                    quality_variants    = %s
                WHERE id = %s
            """, (
                base_title,
                base_title,
                best_quality,
                json.dumps(available_qualities),
                json.dumps(quality_variants),
                primary['id'],
            ))

            conn.commit()
            merged_count += 1
            print(f"  ✅ Merged: {base_title[:60]} ({len(variants)} → 1)")

        except mysql.connector.Error as e:
            conn.rollback()
            skipped_count += 1
            print(f"  ⚠️  Skipped: {base_title[:60]} — {e}")

    print(f"\n{'=' * 70}")
    print(f"✅ Done!")
    print(f"   Merged : {merged_count} groups")
    print(f"   Deleted: {deleted_count} duplicates")
    print(f"   Skipped: {skipped_count}")
    print("=" * 70)

    cursor.close()
    conn.close()


if __name__ == '__main__':
    merge_duplicate_movies()
