#!/usr/bin/env python3
"""
cPanel Movie Processor
======================
Posts pending movies to @newmoviesarena4u via Bot API.
@GetLatestMoviesBot must be admin of the channel.
"""

import json
import logging
import sys
import time
from pathlib import Path

import mysql.connector
import requests

# ── Config ──────────────────────────────────────────
DB_CONFIG = {
    "host":     "localhost",
    "user":     "techandc_bot",
    "password": "12345Sajibs6@",
    "database": "techandc_prompts",
}

BOT_TOKEN      = "8294665841:AAGA0fldnAJj0dazXQsa9p67HARnqACwW0E"
CHAT_ID        = "@newmoviesarena4u"
SITE_URL       = "https://movies.techandclick.site"
BOT_API        = f"https://api.telegram.org/bot{BOT_TOKEN}"
BATCH_SIZE     = 10

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR  = BASE_DIR / "logs";  LOG_DIR.mkdir(exist_ok=True)
TEMP_DIR = BASE_DIR / "temp_posters"; TEMP_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "cpanel_movie_processor.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ── Database ─────────────────────────────────────────
def get_db():
    conn = mysql.connector.connect(**DB_CONFIG)
    conn.autocommit = False
    return conn

def get_pending(cursor, limit):
    cursor.execute("""
        SELECT id, movie_title, slug, poster_url, quality,
               movie_size_readable, year, available_qualities
        FROM mlsbd_movies
        WHERE poster_url IS NOT NULL
          AND slug IS NOT NULL
          AND (telegram_message_ids IS NULL OR telegram_message_ids = '')
        ORDER BY created_at ASC
        LIMIT %s
    """, (limit,))
    return cursor.fetchall()

def mark_posted(cursor, movie_id, message_id):
    cursor.execute("""
        UPDATE mlsbd_movies
        SET telegram_message_ids    = %s,
            telegram_channel_id     = %s,
            processing_completed_at = NOW()
        WHERE id = %s
    """, (json.dumps([message_id]), CHAT_ID, movie_id))

def assign_cats(cursor, movie_id, title, quality=''):
    import re
    t = f"{title} {quality}".lower()
    slugs = {
        'bengali-movies': re.search(r'\b(bengali|bangla|hoichoi|chorki|bongodb|iscreen|fridaay|klikk|utshob|bongo)\b', t),
        'hindi-movies':   re.search(r'\b(hindi|bollywood)\b', t),
        'english-movies': re.search(r'\b(english|hollywood)\b', t),
        'tamil-movies':   re.search(r'\b(tamil|kollywood)\b', t),
        'telugu-movies':  re.search(r'\b(telugu|tollywood)\b', t),
        'dual-audio':     re.search(r'\bdual\s*audio\b', t),
        'web-series':     re.search(r'\b(s\d{2}e\d{2}|season\s*\d+|web\s*series|netflix|amazon|hoichoi|hotstar|zee5|sonyliv)\b', t),
        '4k-ultra-hd':    re.search(r'\b(4k|2160p)\b', t),
        '1080p-full-hd':  re.search(r'\b1080p?\b', t),
        '720p-hd':        re.search(r'\b720p?\b', t),
        '480p':           re.search(r'\b480p?\b', t),
    }
    for slug, m in slugs.items():
        if not m: continue
        try:
            cursor.execute("SELECT id FROM movie_categories WHERE category_slug=%s LIMIT 1", (slug,))
            row = cursor.fetchone()
            if row:
                cid = row[0] if isinstance(row, tuple) else row['id']
                cursor.execute(
                    "INSERT IGNORE INTO movie_category_links (movie_id,category_id) VALUES (%s,%s)",
                    (movie_id, cid))
        except Exception:
            pass

# ── Telegram ──────────────────────────────────────────
def download_poster(url, movie_id):
    try:
        r = requests.get(url, timeout=20, headers={'User-Agent': 'Mozilla/5.0'})
        r.raise_for_status()
        ct  = r.headers.get('Content-Type', '')
        ext = '.png' if 'png' in ct else '.webp' if 'webp' in ct else '.jpg'
        p   = TEMP_DIR / f"poster_{movie_id}{ext}"
        p.write_bytes(r.content)
        return p
    except Exception as e:
        log.warning(f"Poster download failed: {e}")
        return None

def post_movie(movie, poster_path):
    mid, title, slug, _, quality, size, year, avail_q = movie
    url = f"{SITE_URL}/movie.php?slug={slug}"

    # Qualities
    qs = ''
    if avail_q:
        try:
            lst = json.loads(avail_q)
            if isinstance(lst, list): qs = ' | '.join(lst)
        except Exception:
            pass
    qs = qs or quality or ''

    # Caption
    lines = [f"🎬 <b>{title}</b>", ""]
    if year: lines.append(f"📅 {year}")
    if qs:   lines.append(f"🎞 {qs}")
    if size: lines.append(f"💾 {size}")
    lines += ["", "👇 Watch &amp; Download"]
    caption = '\n'.join(lines)

    kb = json.dumps({"inline_keyboard": [[{"text": "🎬 Watch Now & Download", "url": url}]]})

    if poster_path and poster_path.exists():
        with open(poster_path, 'rb') as f:
            resp = requests.post(f"{BOT_API}/sendPhoto",
                data={"chat_id": CHAT_ID, "caption": caption,
                      "parse_mode": "HTML", "reply_markup": kb},
                files={"photo": f}, timeout=60)
    else:
        resp = requests.post(f"{BOT_API}/sendMessage",
            json={"chat_id": CHAT_ID, "text": caption,
                  "parse_mode": "HTML", "reply_markup": json.loads(kb)},
            timeout=30)

    data = resp.json()
    if data.get('ok'):
        return data['result']['message_id']
    raise Exception(data.get('description', 'Unknown Telegram error'))

# ── Main ──────────────────────────────────────────────
def main():
    log.info("=" * 70)
    log.info("🎬 MOVIE PROCESSOR STARTED (Bot API)")
    log.info("=" * 70)

    conn   = get_db()
    cursor = conn.cursor()
    movies = get_pending(cursor, BATCH_SIZE)

    if not movies:
        log.info("✅ No pending movies to post.")
        conn.close(); return

    log.info(f"📋 {len(movies)} movies to post")
    ok = err = 0

    for movie in movies:
        movie_id, title = movie[0], movie[1]
        log.info(f"\n{'─'*50}\n{title} (id={movie_id})")
        try:
            assign_cats(cursor, movie_id, title, movie[4] or '')
            conn.commit()

            poster = download_poster(movie[3], movie_id) if movie[3] else None
            msg_id = post_movie(movie, poster)
            mark_posted(cursor, movie_id, msg_id)
            conn.commit()

            if poster and poster.exists(): poster.unlink()
            log.info(f"✅ Posted  msg_id={msg_id}")
            ok += 1
            time.sleep(2)

        except Exception as e:
            conn.rollback()
            log.error(f"❌ Failed: {e}")
            err += 1

    log.info(f"\n{'='*70}")
    log.info(f"✅ Success: {ok}   ❌ Failed: {err}")
    log.info("=" * 70)
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
