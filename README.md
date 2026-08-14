# 🎬 MLSBD Movie Bot

**Automated movie scraping and Telegram posting system**

Scrapes MLSBD.co for latest movies and posts to Telegram with website links.

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip3 install -r requirements.txt

# 2. Configure Telegram (see README_CPANEL_DIRECT.md)
nano cpanel_movie_processor.py

# 3. Setup cron jobs
bash setup_cpanel_cron.sh

# 4. Test
python3 mlsbd_trigger.py
python3 cpanel_movie_processor.py
```

---

## 📂 Project Structure

```
├── mlsbd_trigger.py              # Scrape MLSBD & save to DB
├── cpanel_movie_processor.py     # Post to Telegram
├── slug_generator.py             # SEO slug generator
├── send_movie_to_telegram.py     # Manual posting
├── auto_retry_failed.py          # Retry failed movies
├── dashboard/                    # Web dashboard
│   ├── index.php                 # Dashboard home
│   ├── movies.php                # Movies manager
│   ├── ads_manager.php           # Ads control panel
│   └── api/                      # API endpoints
└── README_CPANEL_DIRECT.md       # Full documentation
```

---

## 🎯 Core Features

### ✅ **Automated Scraping**
- Scrapes MLSBD.co every 30 minutes
- Extracts movie details, posters, download links
- Stores in MySQL database

### ✅ **Telegram Integration**
- Posts movie poster + details to Telegram
- "Watch Now" button → Movie website
- Automatic processing every 5 minutes

### ✅ **Movie Website**
- Netflix-style dark theme
- SEO-friendly URLs
- Multiple download sources
- Mobile responsive

### ✅ **Ads Management**
- Dashboard to control all ads
- Support: Adsterra, Monetag, AdSense
- Per-ad enable/disable
- Placement management

### ✅ **Web Dashboard**
- Movie status tracking
- Failed movie retry
- Ads management
- View statistics

---

## 🔧 Key Scripts

### **mlsbd_trigger.py**
Scrapes MLSBD homepage and saves movies to database.

**Run:** `python3 mlsbd_trigger.py`

### **cpanel_movie_processor.py**
Processes pending movies and posts to Telegram.

**Run:** `python3 cpanel_movie_processor.py`

### **send_movie_to_telegram.py**
Manually post specific movies to Telegram.

**Run:** `python3 send_movie_to_telegram.py`

### **auto_retry_failed.py**
Retry failed movies automatically.

**Run:** `python3 auto_retry_failed.py`

---

## 📊 Database

**Main Table:** `mlsbd_movies`

Key columns:
- `slug` - SEO-friendly URL
- `poster_url` - Movie poster image
- `download_links` - JSON with GDFlix, HubCloud, etc.
- `status` - pending, processing, completed, failed
- `telegram_message_ids` - Posted message IDs

---

## 🌐 URLs

- **Dashboard:** `https://techandclick.site/movie_bot_new/ftp_movie_bot/dashboard/`
- **Movie Site:** `https://movies.techandclick.site/`
- **Telegram:** `@getlatestmovienewgroup`

---

## 📖 Documentation

**For complete setup guide, see:**
👉 **[README_CPANEL_DIRECT.md](README_CPANEL_DIRECT.md)**

---

## 🔐 Configuration Files

- `config_example.py` - Example configuration
- `telegram_session.session` - Telegram session (keep secret!)
- `.gitignore` - Git ignore rules

---

## 🛠️ Maintenance

### Check Logs:
```bash
tail -f logs/mlsbd_trigger.log
tail -f logs/cpanel_movie_processor.log
```

### Database Status:
```sql
SELECT status, COUNT(*) FROM mlsbd_movies GROUP BY status;
```

### Retry Failed:
```bash
python3 auto_retry_failed.py
```

---

## 📝 License

Proprietary - TechAndClick.site

## 👤 Author

Sajib Rasel + AI Assistant

---

**Version:** 2.0 (cPanel Direct)  
**Last Updated:** 2026-08-14
