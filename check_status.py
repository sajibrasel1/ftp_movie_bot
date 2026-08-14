#!/usr/bin/env python3
"""
Check Spider-Man and Peaky Blinders status from database
"""
import pymysql
from datetime import datetime

# Database connection
conn = pymysql.connect(
    host='localhost',
    user='techandc_bot',
    password='12345Sajibs6@',
    database='techandc_prompts',
    charset='utf8mb4'
)

cursor = conn.cursor(pymysql.cursors.DictCursor)

print("=" * 80)
print("🎬 SPIDER-MAN (ID 1939) & PEAKY BLINDERS (ID 1920) STATUS")
print("=" * 80)

# Get detailed status
cursor.execute("""
    SELECT 
        id,
        SUBSTRING(movie_title, 1, 60) as title,
        status,
        telegram_message_ids,
        total_parts,
        is_split,
        processing_started_at,
        processing_completed_at,
        error_message
    FROM ftp_movies 
    WHERE id IN (1939, 1920)
    ORDER BY id
""")

movies = cursor.fetchall()

for movie in movies:
    print(f"\n📽️  Movie ID: {movie['id']}")
    print(f"   Title: {movie['title']}")
    print(f"   Status: {movie['status']}")
    print(f"   Split: {'Yes' if movie['is_split'] else 'No'}")
    print(f"   Total Parts: {movie['total_parts'] or 0}")
    
    if movie['telegram_message_ids']:
        import json
        msg_ids = json.loads(movie['telegram_message_ids'])
        print(f"   Telegram Messages: {len(msg_ids)} uploaded")
        print(f"   Message IDs: {msg_ids}")
    else:
        print(f"   Telegram Messages: None")
    
    if movie['processing_started_at']:
        print(f"   Started: {movie['processing_started_at']}")
    
    if movie['processing_completed_at']:
        print(f"   Completed: {movie['processing_completed_at']}")
    
    if movie['error_message']:
        print(f"   Error: {movie['error_message']}")

print("\n" + "=" * 80)
print("📊 OVERALL STATUS SUMMARY")
print("=" * 80)

cursor.execute("""
    SELECT status, COUNT(*) as total 
    FROM ftp_movies 
    GROUP BY status
    ORDER BY 
        CASE status
            WHEN 'pending' THEN 1
            WHEN 'processing' THEN 2
            WHEN 'completed' THEN 3
            ELSE 4
        END
""")

summary = cursor.fetchall()
for row in summary:
    print(f"   {row['status']:15} : {row['total']:4} movies")

print("\n" + "=" * 80)
print("🔄 CURRENTLY PROCESSING MOVIES")
print("=" * 80)

cursor.execute("""
    SELECT 
        id,
        SUBSTRING(movie_title, 1, 50) as title,
        TIMESTAMPDIFF(MINUTE, processing_started_at, NOW()) as minutes_running
    FROM ftp_movies 
    WHERE status = 'processing'
    ORDER BY processing_started_at DESC
    LIMIT 10
""")

processing = cursor.fetchall()
if processing:
    for movie in processing:
        print(f"   ID {movie['id']}: {movie['title']} (running {movie['minutes_running']} min)")
else:
    print("   No movies currently processing")

conn.close()
print("\n" + "=" * 80)
