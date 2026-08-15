# Poster Backfill Script

## 📝 Overview
This script fetches missing posters for existing movies in the database by scraping MLSBD movie detail pages.

## 🚀 Usage

### Basic Usage (Process 50 movies)
```bash
cd ~/movie_bot_new/ftp_movie_bot
/usr/bin/python3 poster_backfill.py
```

### Process Specific Number of Movies
```bash
# Process 100 movies
/usr/bin/python3 poster_backfill.py --limit 100

# Process 200 movies
/usr/bin/python3 poster_backfill.py --limit 200
```

### Process ALL Movies Without Poster (⚠️ Use carefully!)
```bash
/usr/bin/python3 poster_backfill.py --all
```

### Custom Batch Settings
```bash
# Process 100 movies, batch size 20, 3 seconds delay between batches
/usr/bin/python3 poster_backfill.py --limit 100 --batch 20 --delay 3
```

## ⚙️ Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--limit` | 50 | Maximum number of movies to process |
| `--batch` | 10 | Number of movies to process before delay |
| `--delay` | 2 | Delay in seconds between batches |
| `--all` | False | Process ALL movies (ignores --limit) |

## 📊 What It Does

1. **Finds movies** without posters (`poster_url IS NULL`)
2. **Fetches MLSBD page** for each movie
3. **Extracts poster** using multiple methods:
   - WordPress post thumbnail
   - Featured image in article
   - Open Graph meta tags
   - Twitter image meta tags
   - Images with poster/thumbnail classes
4. **Updates database** with found poster URL
5. **Logs results** to `logs/poster_backfill_YYYYMMDD_HHMMSS.log`

## 📈 Example Output

```
🎨 Starting poster backfill process...
⚙️ Settings: limit=50, batch=10, delay=2s
📋 Found 50 movies without posters

[1/50] 📥 Fetching poster: Emergency Room 2026...
  URL: https://mlsbd.co/emergency-room-2026-s01-bengali-dubbed-org-bongobd
  ✅ Success! Poster: https://cdn.imgnest.io/uploads/images/2026/08/...

[2/50] 📥 Fetching poster: Thukra Ke Mera Pyaar 2026...
  URL: https://mlsbd.co/thukra-ke-mera-pyaar-2026-s02-dual-audio-bengali...
  ❌ No poster found

...

============================================================
🎉 Backfill complete!
  ✅ Success: 42
  ❌ Failed: 8
  📊 Total processed: 50
  📈 Success rate: 84.0%
============================================================
```

## 🔍 Check Progress

```bash
# View live log
tail -f logs/poster_backfill_*.log

# Count movies without posters
mysql -u techandc_bot -p'12345Sajibs6@' techandc_prompts -e "
SELECT COUNT(*) as no_poster 
FROM mlsbd_movies 
WHERE poster_url IS NULL OR poster_url = '';"
```

## ⚠️ Important Notes

1. **Rate Limiting**: The script includes delays to avoid overwhelming MLSBD servers
2. **Batch Processing**: Use `--limit` for controlled processing
3. **Logs**: All actions are logged to `logs/` directory
4. **Safe**: Only updates movies with NULL posters (won't overwrite existing posters)

## 🎯 Recommended Strategy

**For large backlogs (500+ movies):**
```bash
# Process in multiple sessions
/usr/bin/python3 poster_backfill.py --limit 100 --batch 20 --delay 3
# Wait and check results, then run again
/usr/bin/python3 poster_backfill.py --limit 100 --batch 20 --delay 3
# Repeat until satisfied
```

**For small touch-ups (< 50 movies):**
```bash
# Quick default run
/usr/bin/python3 poster_backfill.py
```

## 🛠️ Troubleshooting

### "No poster found" for many movies
- Some MLSBD pages may not have images
- Pages may have changed structure
- Network issues

### Database connection errors
- Check MySQL credentials in script
- Ensure MySQL server is running
- Verify database name is correct

### Slow performance
- Increase `--batch` size
- Decrease `--delay` (but respect rate limits!)
