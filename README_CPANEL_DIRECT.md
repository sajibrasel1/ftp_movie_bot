# 🎬 MLSBD Movie Bot - cPanel Direct System

**Simplified architecture without GitHub Actions**

All processing happens directly on cPanel server.

---

## 🚀 **Architecture**

```
MLSBD Website
     ↓
mlsbd_trigger.py (Scrape & Save to DB)
     ↓
Database (status: pending)
     ↓
cpanel_movie_processor.py (Download poster & Post to Telegram)
     ↓
Telegram Group + Movie Website
     ↓
Database (status: completed)
```

---

## 📂 **Files Structure**

```
ftp_movie_bot/
├── mlsbd_trigger.py              # Scrapes MLSBD, saves to DB
├── cpanel_movie_processor.py     # Posts to Telegram (NEW)
├── send_movie_to_telegram.py     # Manual posting script
├── slug_generator.py             # Generate SEO slugs
├── config.py                     # Configuration
├── setup_cpanel_cron.sh          # Cron job setup
├── dashboard/                    # Web dashboard
│   ├── index.php
│   ├── movies.php
│   ├── ads_manager.php          # NEW - Ads management
│   └── api/
└── logs/
    ├── mlsbd_trigger.log
    ├── cpanel_movie_processor.log
    └── cron_processor.log
```

---

## ⚙️ **Setup Instructions**

### **1. Server Setup**

```bash
cd ~/movie_bot_new/ftp_movie_bot

# Install Python packages
pip3 install --user telethon requests mysql-connector-python beautifulsoup4

# Create required directories
mkdir -p logs temp_posters

# Set permissions
chmod +x *.py
chmod +x setup_cpanel_cron.sh
```

### **2. Configure Telegram**

Edit `cpanel_movie_processor.py`:

```python
TELEGRAM_API_ID = 12345678  # Your API ID
TELEGRAM_API_HASH = "your_api_hash"  # Your API Hash
TELEGRAM_SESSION = "your_session_string"  # Your session string
TELEGRAM_CHAT_ID = -1003916118619  # Your group ID
```

### **3. Setup Cron Jobs**

**Option A: Using cPanel UI**

1. Login to cPanel
2. Go to **Cron Jobs**
3. Add two cron jobs:

**MLSBD Trigger (Every 30 minutes):**
```
*/30 * * * * cd ~/movie_bot_new/ftp_movie_bot && python3 mlsbd_trigger.py >> logs/cron_mlsbd_trigger.log 2>&1
```

**Movie Processor (Every 5 minutes):**
```
*/5 * * * * cd ~/movie_bot_new/ftp_movie_bot && python3 cpanel_movie_processor.py >> logs/cron_processor.log 2>&1
```

**Option B: Using SSH**

```bash
# Run setup script
bash setup_cpanel_cron.sh

# Or manually add to crontab
crontab -e

# Add these lines:
*/30 * * * * cd ~/movie_bot_new/ftp_movie_bot && python3 mlsbd_trigger.py >> logs/cron_mlsbd_trigger.log 2>&1
*/5 * * * * cd ~/movie_bot_new/ftp_movie_bot && python3 cpanel_movie_processor.py >> logs/cron_processor.log 2>&1
```

---

## 🎯 **How It Works**

### **Step 1: Scrape MLSBD (mlsbd_trigger.py)**

- Runs every 30 minutes
- Scrapes homepage for new movies
- Extracts:
  - Movie title
  - Poster URL
  - GDFlix download link
  - Quality, year, size
- Generates SEO slug
- Saves to database with status: `pending`

### **Step 2: Process & Post (cpanel_movie_processor.py)**

- Runs every 5 minutes
- Gets movies with status: `pending`
- For each movie:
  1. Download poster image
  2. Create Telegram message with:
     - Poster image
     - Movie title, quality, year, size
     - "Watch Now" button → website link
  3. Post to Telegram group
  4. Update database: status = `completed`
  5. Cleanup poster file

---

## 📊 **Database Schema**

### **mlsbd_movies table:**

```sql
- id (primary key)
- movie_title
- slug (SEO-friendly URL)
- poster_url
- gdflix_url
- download_links (JSON)
- quality (720p, 1080p, etc.)
- year
- movie_size_readable
- status (pending, processing, completed, failed)
- telegram_message_ids (JSON array)
- view_count
- is_featured
- created_at, updated_at
```

---

## 🎬 **Telegram Message Format**

```
🎬 Malik (2026) Bengali WEB-DL – 720P | 1080P

📺 Quality: 720p HD
📅 Year: 2026
💾 Size: 1.2 GB

🔗 Watch & Download:
Click the button below 👇

[🎬 Watch Now] → https://movies.techandclick.site/malik-2026-bengali
```

---

## 🔍 **Monitoring & Logs**

### **Check Logs:**

```bash
# MLSBD trigger log
tail -f logs/mlsbd_trigger.log

# Movie processor log
tail -f logs/cpanel_movie_processor.log

# Cron execution log
tail -f logs/cron_processor.log
```

### **Check Database:**

```sql
-- Pending movies
SELECT id, movie_title, status, created_at 
FROM mlsbd_movies 
WHERE status = 'pending';

-- Recently completed
SELECT id, movie_title, telegram_message_ids, processing_completed_at 
FROM mlsbd_movies 
WHERE status = 'completed' 
ORDER BY processing_completed_at DESC 
LIMIT 10;

-- Failed movies
SELECT id, movie_title, error_message, retry_count 
FROM mlsbd_movies 
WHERE status = 'failed';
```

---

## 🛠️ **Manual Testing**

### **Test MLSBD Scraping:**

```bash
cd ~/movie_bot_new/ftp_movie_bot
python3 mlsbd_trigger.py
```

### **Test Movie Posting:**

```bash
cd ~/movie_bot_new/ftp_movie_bot
python3 cpanel_movie_processor.py
```

### **Test Single Movie:**

```bash
# Mark a movie as pending
mysql -u techandc_bot -p techandc_prompts -e "UPDATE mlsbd_movies SET status='pending' WHERE id=123"

# Run processor
python3 cpanel_movie_processor.py
```

---

## 🚨 **Troubleshooting**

### **Movies not being posted:**

1. Check if movies are pending:
   ```sql
   SELECT COUNT(*) FROM mlsbd_movies WHERE status='pending';
   ```

2. Check processor log:
   ```bash
   tail -50 logs/cpanel_movie_processor.log
   ```

3. Test manually:
   ```bash
   python3 cpanel_movie_processor.py
   ```

### **Telegram connection errors:**

1. Verify credentials in `cpanel_movie_processor.py`
2. Check Telegram session is valid
3. Verify group ID is correct

### **Poster download fails:**

- Check poster URL is accessible
- Verify internet connection on server
- Check temp_posters directory permissions

---

## 📈 **Performance**

- **MLSBD Scraping:** ~5-10 seconds
- **Movie Processing:** ~3-5 seconds per movie
- **Database queries:** <100ms
- **Telegram posting:** ~2 seconds per movie

**Total:** ~5-7 seconds per movie

---

## ✅ **Benefits Over GitHub Actions**

1. ✅ **Faster** - No upload/download delays
2. ✅ **Simpler** - One script does everything
3. ✅ **Reliable** - No external dependencies
4. ✅ **No limits** - Unlimited processing
5. ✅ **Cost-effective** - No GitHub Actions minutes used
6. ✅ **Better control** - Everything on your server

---

## 🔐 **Security**

- Database credentials in environment variables (recommended)
- Telegram session string encrypted
- Log files protected
- No sensitive data in git

---

## 📝 **Future Enhancements**

- [ ] Add retry mechanism for failed movies
- [ ] Email notifications for errors
- [ ] Better poster quality detection
- [ ] Multiple download sources support
- [ ] Admin dashboard improvements

---

## 👤 **Support**

For issues or questions:
- Check logs first
- Review this documentation
- Test manually
- Contact: @YourTelegramUsername

---

**Version:** 2.0 (cPanel Direct)  
**Last Updated:** 2026-08-14  
**Status:** Production Ready ✅
