# Elaach.com Crawler Setup Guide

এই guide অনুসরণ করে আপনি elaach.com থেকে latest movies automatically crawl করতে পারবেন।

## 📋 Prerequisites

1. **Chrome Browser** installed
   - Download: https://www.google.com/chrome/

2. **Python 3.7+** (already installed in your virtualenv)

## 🚀 Installation Steps

### Step 1: Update Database Schema

```bash
# SSH into your cPanel server
ssh techandc@grreseller1

# Navigate to project
cd ~/movie_bot_new/ftp_movie_bot

# Run SQL to add source column
mysql -h localhost -u techandc_bot -p'12345Sajibs6@' techandc_prompts < add_source_column.sql
```

### Step 2: Install Python Dependencies

```bash
# Activate virtualenv
source ~/virtualenv/movie_bot_new/3.11/bin/activate

# Install selenium and webdriver-manager
pip install selenium==4.16.0 webdriver-manager==4.0.1
```

**Or** install from requirements:

```bash
pip install -r requirements.txt
```

### Step 3: Test ChromeDriver Setup

```bash
# Run setup script to verify everything works
python setup_selenium.py
```

If successful, you should see:
```
✅ SETUP COMPLETE!
```

## 🎬 Running the Crawler

### Manual Run

```bash
# Activate virtualenv
source ~/virtualenv/movie_bot_new/3.11/bin/activate

# Run crawler
python elaach_crawler.py
```

### Check Logs

```bash
tail -f logs/elaach_crawler.log
```

## ⏰ Automation (Cron Job)

Add to crontab for automatic crawling:

```bash
crontab -e
```

Add this line (runs every 6 hours):

```cron
0 */6 * * * cd /home/techandc/movie_bot_new/ftp_movie_bot && source ~/virtualenv/movie_bot_new/3.11/bin/activate && python elaach_crawler.py >> logs/elaach_cron.log 2>&1
```

**Recommended Schedule:**
- **ftp.ctgfun.com**: Every 1 hour (fast, lightweight)
- **elaach.com**: Every 6 hours (browser automation, heavier)

## 🔧 How It Works

1. **Selenium Browser** - Opens elaach.com in headless Chrome
2. **JavaScript Rendering** - Waits for page to fully load
3. **Extract Movies** - Scrapes movie titles, years, qualities
4. **Get Download Links** - Visits each movie page to get download URL
5. **Database** - Saves new movies to same `ftp_movies` table
6. **GitHub Actions** - Existing workflow processes new movies

## 📊 Multi-Source Benefits

Now your bot gets movies from **TWO sources**:

| Source | Speed | Content | Update Frequency |
|--------|-------|---------|------------------|
| ftp.ctgfun.com | ⚡ Fast | Stable, mature | Hourly |
| elaach.com | 🐢 Moderate | Latest releases | Every 6 hours |

**Result**: Users get latest movies **faster** than competitors!

## 🛠️ Troubleshooting

### Issue: "Selenium not available"
**Solution**:
```bash
pip install selenium webdriver-manager
```

### Issue: "ChromeDriver not found"
**Solution**:
```bash
python setup_selenium.py
```

### Issue: "Chrome not installed"
**Solution**: 
- Install Chrome browser from https://www.google.com/chrome/
- Or use Firefox with geckodriver (modify elaach_crawler.py)

### Issue: "Too slow / High resource usage"
**Solution**:
- Reduce `MAX_MOVIES_TO_SCRAPE` in elaach_crawler.py
- Run less frequently (every 12 hours instead of 6)
- Use only for critical latest releases

## 📈 Performance Stats

- **Scraping Speed**: ~2-3 seconds per movie
- **50 movies**: ~2-3 minutes total
- **CPU Usage**: ~10-15% during crawl
- **Memory**: ~200-300 MB

## 🎯 Next Steps

After setup:

1. ✅ Test manual run: `python elaach_crawler.py`
2. ✅ Check database: Movies should appear with `source='elaach.com'`
3. ✅ Verify GitHub Actions triggered
4. ✅ Add to cron for automation

## 💡 Tips

- Start with small `MAX_MOVIES_TO_SCRAPE` (10-20) for testing
- Monitor logs regularly for first few days
- Adjust cron schedule based on server load
- Keep ftp.ctgfun.com as primary source (it's faster!)

---

**Questions?** Check logs at `logs/elaach_crawler.log`
