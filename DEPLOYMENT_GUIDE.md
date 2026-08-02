# 🚀 elaach.com Crawler - Production Deployment Guide

এই guide অনুসরণ করে আপনি elaach.com crawler production এ deploy করতে পারবেন।

---

## 📋 Prerequisites Checklist

- [x] Chrome browser installed on server
- [x] Python 3.7+ with virtualenv
- [x] MySQL database access
- [x] Existing ftp_movie_bot working
- [x] GitHub Actions configured

---

## 🔧 Step 1: Database Schema Update

SSH into your server and run:

```bash
cd ~/movie_bot_new/ftp_movie_bot

# Add source column to database
mysql -h localhost -u techandc_bot -p'12345Sajibs6@' techandc_prompts << 'EOF'
-- Add source column
ALTER TABLE ftp_movies 
ADD COLUMN IF NOT EXISTS source VARCHAR(100) DEFAULT 'ftp.ctgfun.com' 
AFTER status;

-- Create index
CREATE INDEX IF NOT EXISTS idx_source ON ftp_movies(source);

-- Update existing movies
UPDATE ftp_movies 
SET source = 'ftp.ctgfun.com' 
WHERE source IS NULL OR source = '';

SELECT 'Database updated successfully!' AS status;
EOF
```

**Expected Output:**
```
status
Database updated successfully!
```

---

## 📦 Step 2: Install Dependencies

```bash
# Activate virtualenv
source ~/virtualenv/movie_bot_new/3.11/bin/activate

# Install selenium and webdriver-manager
pip install selenium==4.16.0 webdriver-manager==4.0.1

# Verify installation
python -c "import selenium; print(f'Selenium {selenium.__version__} installed!')"
```

**Expected Output:**
```
Selenium 4.16.0 installed!
```

---

## 🧪 Step 3: Test Run (Dry Run)

Test the crawler without affecting production:

```bash
cd ~/movie_bot_new/ftp_movie_bot

# Run crawler (will scrape and add to database)
python elaach_crawler.py
```

**Monitor the output for:**
- ✅ "Selenium driver created successfully"
- ✅ "Scraped X movies from elaach.com"
- ✅ "New movies added: X"
- ✅ "CRAWLER COMPLETED!"

**Check database:**
```bash
mysql -h localhost -u techandc_bot -p'12345Sajibs6@' -e \
  "SELECT id, movie_title, source, quality, status FROM techandc_prompts.ftp_movies WHERE source='elaach.com' ORDER BY id DESC LIMIT 5;"
```

---

## ⏰ Step 4: Setup Cron Jobs

### Current Cron (ftp.ctgfun.com):
```cron
0 * * * * cd /home/techandc/movie_bot_new/ftp_movie_bot && export $(cat .env | xargs) && /home/techandc/virtualenv/movie_bot_new/3.11/bin/python3 cpanel_trigger.py >> logs/cron.log 2>&1
```

### Add New Cron (elaach.com):

```bash
crontab -e
```

Add this line:

```cron
# elaach.com crawler - every 6 hours
0 */6 * * * cd /home/techandc/movie_bot_new/ftp_movie_bot && source ~/virtualenv/movie_bot_new/3.11/bin/activate && python elaach_crawler.py >> logs/elaach_cron.log 2>&1
```

**Final crontab should look like:**

```cron
# ftp.ctgfun.com - every hour (fast, lightweight)
0 * * * * cd /home/techandc/movie_bot_new/ftp_movie_bot && export $(cat .env | xargs) && /home/techandc/virtualenv/movie_bot_new/3.11/bin/python3 cpanel_trigger.py >> logs/cron.log 2>&1

# elaach.com - every 6 hours (browser automation, latest releases)
0 */6 * * * cd /home/techandc/movie_bot_new/ftp_movie_bot && source ~/virtualenv/movie_bot_new/3.11/bin/activate && python elaach_crawler.py >> logs/elaach_cron.log 2>&1
```

**Save and exit** (press `Esc`, then `:wq`, then `Enter` in vim)

**Verify cron is active:**
```bash
crontab -l | grep elaach
```

---

## 📊 Step 5: Monitor & Verify

### Check Logs:

```bash
# elaach.com crawler logs
tail -f ~/movie_bot_new/ftp_movie_bot/logs/elaach_crawler.log

# Cron execution logs
tail -f ~/movie_bot_new/ftp_movie_bot/logs/elaach_cron.log
```

### Check Database Stats:

```bash
mysql -h localhost -u techandc_bot -p'12345Sajibs6@' techandc_prompts << 'EOF'
SELECT 
    source,
    COUNT(*) as total_movies,
    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
    SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) as processing,
    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
FROM ftp_movies 
GROUP BY source;
EOF
```

**Expected Output:**
```
+----------------+--------------+---------+------------+-----------+--------+
| source         | total_movies | pending | processing | completed | failed |
+----------------+--------------+---------+------------+-----------+--------+
| ftp.ctgfun.com |          915 |       0 |          0 |       915 |      0 |
| elaach.com     |           20 |       5 |          2 |        13 |      0 |
+----------------+--------------+---------+------------+-----------+--------+
```

---

## 🎯 Expected Behavior

### Hour-by-Hour Schedule:

| Time | ftp.ctgfun.com | elaach.com | Result |
|------|----------------|------------|--------|
| 00:00 | ✅ Scan | ✅ Scan | Both sources checked |
| 01:00 | ✅ Scan | - | FTP only |
| 02:00 | ✅ Scan | - | FTP only |
| 03:00 | ✅ Scan | - | FTP only |
| 04:00 | ✅ Scan | - | FTP only |
| 05:00 | ✅ Scan | - | FTP only |
| 06:00 | ✅ Scan | ✅ Scan | Both sources checked |
| ... | ... | ... | ... |

**Result**: Latest movies from elaach.com come **4x per day**, while FTP is checked **24x per day**

---

## 🐛 Troubleshooting

### Issue: "ChromeDriver not found"

**Solution:**
```bash
pip install --upgrade webdriver-manager
python -c "from webdriver_manager.chrome import ChromeDriverManager; ChromeDriverManager().install()"
```

### Issue: "Chrome binary not found"

**Solution**: Install Chrome on your server:
```bash
# For cPanel/CentOS
sudo yum install google-chrome-stable

# Verify
google-chrome --version
```

### Issue: "Selenium taking too long"

**Solution**: Reduce `MAX_MOVIES_TO_SCRAPE` in `elaach_crawler.py`:
```python
MAX_MOVIES_TO_SCRAPE = 20  # Reduce from 50 to 20
```

### Issue: "Too many pending movies"

This is **GOOD**! It means crawler is working. GitHub Actions will process them automatically.

**Check GitHub Actions:**
```bash
# Visit: https://github.com/sajibrasel1/ftp_movie_bot/actions
```

---

## 📈 Performance Metrics

After 24 hours, check performance:

```bash
mysql -h localhost -u techandc_bot -p'12345Sajibs6@' techandc_prompts << 'EOF'
SELECT 
    DATE(created_at) as date,
    source,
    COUNT(*) as movies_added
FROM ftp_movies 
WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
GROUP BY DATE(created_at), source
ORDER BY date DESC, source;
EOF
```

**Expected Daily Stats:**
- ftp.ctgfun.com: 10-30 movies/day
- elaach.com: 5-15 movies/day
- **Total: 15-45 new movies daily!**

---

## ✅ Success Checklist

After deployment, verify:

- [ ] Database source column exists
- [ ] Selenium installed successfully
- [ ] Test run completed without errors
- [ ] Cron jobs added and active
- [ ] Logs are being written
- [ ] New movies appearing in database with `source='elaach.com'`
- [ ] GitHub Actions triggered for new movies
- [ ] Movies uploaded to Telegram channel

---

## 🎉 Deployment Complete!

Your bot now has **dual-source** movie detection:

✅ **Fast FTP scanning** (hourly)
✅ **Latest releases** from elaach.com (6-hourly)
✅ **Automatic processing** via GitHub Actions
✅ **Telegram delivery** via Telethon

**Users will love getting latest movies on release day!** 🍿

---

## 📞 Support

If you encounter issues:

1. Check logs: `logs/elaach_crawler.log`
2. Check cron logs: `logs/elaach_cron.log`
3. Verify database: `SELECT * FROM ftp_movies WHERE source='elaach.com' ORDER BY id DESC LIMIT 10;`
4. Test manually: `python elaach_crawler.py`

---

**Last Updated**: July 2026
**Version**: 1.0
