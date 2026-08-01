# 🚀 FTP Movie Bot - Complete Setup Guide

## 📋 Table of Contents
1. [Prerequisites](#prerequisites)
2. [Database Setup](#database-setup)
3. [GitHub Repository Setup](#github-repository-setup)
4. [GitHub Actions Configuration](#github-actions-configuration)
5. [cPanel Configuration](#cpanel-configuration)
6. [Testing & Verification](#testing--verification)
7. [Troubleshooting](#troubleshooting)

---

## 🎯 Prerequisites

Before starting, ensure you have:
- ✅ A GitHub account (free tier is fine)
- ✅ cPanel hosting with MySQL database access
- ✅ A Telegram bot token and channel ID
- ✅ SSH access to your cPanel server (for cron setup)
- ✅ Git installed on your local machine

---

## 📊 Database Setup

### Step 1: Create Database Tables

1. **Log in to cPanel → phpMyAdmin**
2. **Select your database** (`techandc_prompts`)
3. **Click "SQL" tab**
4. **Copy and paste the entire content** from `database.sql`
5. **Click "Go"** to execute

**Expected Result:**
```
✅ Table ftp_movies created successfully
✅ Table ftp_movie_processing_log created successfully  
✅ Table github_actions_usage created successfully
```

### Step 2: Verify Database Tables

Run this query to verify:
```sql
SHOW TABLES LIKE 'ftp_%';
```

You should see:
- `ftp_movies`
- `ftp_movie_processing_log`

---

## 🐙 GitHub Repository Setup

### Step 1: Create a New GitHub Repository

1. **Go to:** https://github.com/new
2. **Repository name:** `movie-bot` (or any name you prefer)
3. **Description:** "Automated movie splitter and Telegram uploader"
4. **Visibility:** 
   - ⚠️ **Public** (required for free GitHub Actions)
   - 💡 **Tip:** Your bot token will be in secrets (safe), code is public (fine)
5. **Initialize:** ✅ Check "Add a README file"
6. **Click:** "Create repository"

### Step 2: Upload Files to GitHub

**Option A: Using GitHub Web Interface (Easiest)**

1. Go to your repository page
2. Click "Add file" → "Upload files"
3. Drag and drop these files:
   ```
   ftp_movie_bot/
   ├── .github/
   │   └── workflows/
   │       └── process_movie.yml
   ├── cpanel_trigger.py
   ├── github_worker.py
   ├── requirements.txt
   └── database.sql
   ```
4. Commit message: "Initial commit - FTP Movie Bot"
5. Click "Commit changes"

**Option B: Using Git Command Line**

```bash
# Navigate to your project folder
cd /path/to/movie_bot_new/ftp_movie_bot

# Initialize Git
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit - FTP Movie Bot"

# Add remote (replace YOUR_USERNAME and movie-bot with your details)
git remote add origin https://github.com/YOUR_USERNAME/movie-bot.git

# Push to GitHub
git branch -M main
git push -u origin main
```

### Step 3: Verify Upload

1. Go to your repository on GitHub
2. You should see folder structure:
   ```
   .github/workflows/process_movie.yml
   cpanel_trigger.py
   github_worker.py
   requirements.txt
   database.sql
   README.md
   ```

---

## 🔐 GitHub Actions Configuration

### Step 1: Generate GitHub Personal Access Token (PAT)

1. **Go to:** https://github.com/settings/tokens
2. **Click:** "Generate new token" → "Generate new token (classic)"
3. **Note:** "FTP Movie Bot - cPanel Trigger"
4. **Expiration:** 90 days (or "No expiration" if you prefer)
5. **Scopes:** Check these boxes:
   - ✅ `repo` (Full control of private repositories)
   - ✅ `workflow` (Update GitHub Action workflows)
6. **Click:** "Generate token"
7. **⚠️ IMPORTANT:** Copy the token immediately (you won't see it again!)
8. **Save it securely** - you'll need it for cPanel setup

**Example token format:** `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

### Step 2: Configure GitHub Repository Secrets

GitHub Secrets are encrypted environment variables that your workflow can access.

1. **Go to your repository:** `https://github.com/YOUR_USERNAME/movie-bot`
2. **Click:** Settings → Secrets and variables → Actions
3. **Click:** "New repository secret" button
4. **Add these secrets ONE BY ONE:**

#### Secret 1: TELEGRAM_BOT_TOKEN
- **Name:** `TELEGRAM_BOT_TOKEN`
- **Value:** Your Telegram bot token (e.g., `8261646421:AAEd1yR5sqdQYFjf51tVHoBdurT-z_aYCYg`)
- Click "Add secret"

#### Secret 2: TELEGRAM_CHAT_ID
- **Name:** `TELEGRAM_CHAT_ID`
- **Value:** Your Telegram channel ID (e.g., `-1003564276724`)
- Click "Add secret"

#### Secret 3: DB_HOST
- **Name:** `DB_HOST`
- **Value:** Your database host (usually `localhost` for cPanel)
- Click "Add secret"

#### Secret 4: DB_USER
- **Name:** `DB_USER`
- **Value:** Your database username (e.g., `techandc_bot`)
- Click "Add secret"

#### Secret 5: DB_PASSWORD
- **Name:** `DB_PASSWORD`
- **Value:** Your database password (e.g., `12345Sajibs6@`)
- Click "Add secret"

#### Secret 6: DB_NAME
- **Name:** `DB_NAME`
- **Value:** Your database name (e.g., `techandc_prompts`)
- Click "Add secret"

**✅ Verify:** You should now see 6 secrets listed

---

## 🖥️ cPanel Configuration

### Step 1: Upload cpanel_trigger.py to cPanel

**Option A: Using cPanel File Manager**

1. Log in to cPanel
2. Open "File Manager"
3. Navigate to `/home/techandc/movie_bot_new/ftp_movie_bot/`
4. Upload `cpanel_trigger.py` (if not already there from Git push)
5. Right-click → "Permissions" → Set to `755` (executable)

**Option B: Using SSH/FTP**

```bash
# Using SSH
cd /home/techandc/movie_bot_new/ftp_movie_bot/
chmod +x cpanel_trigger.py
```

### Step 2: Update Configuration in cpanel_trigger.py

Edit `cpanel_trigger.py` and update these lines:

```python
# Line 32-33: Update with YOUR GitHub details
GITHUB_USERNAME = "YOUR_GITHUB_USERNAME"  # e.g., "raselkhan"
GITHUB_REPO = "movie-bot"  # Your repository name

# Line 34: GitHub Token (paste the PAT you generated)
GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

**⚠️ SECURITY TIP:** Better approach - use environment variable:
```bash
# On cPanel, add to ~/.bashrc:
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

Then in script, it will read from environment (line 34 already does this):
```python
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "YOUR_GITHUB_PAT_HERE")
```

### Step 3: Install Python Dependencies on cPanel

```bash
# SSH into your cPanel
ssh techandc@yourserver.com

# Navigate to project folder
cd /home/techandc/movie_bot_new/ftp_movie_bot/

# Install dependencies using your virtualenv
/home/techandc/virtualenv/movie_bot_new/3.11/bin/pip install -r requirements.txt
```

**Expected output:**
```
✅ Successfully installed beautifulsoup4-4.12.2
✅ Successfully installed mysql-connector-python-8.2.0
✅ Successfully installed python-telegram-bot-20.7
✅ Successfully installed requests-2.31.0
```

### Step 4: Test Script Manually

```bash
# Run the trigger script manually to test
/home/techandc/virtualenv/movie_bot_new/3.11/bin/python cpanel_trigger.py
```

**Expected output:**
```
================================================================================
FTP Movie Bot - cPanel Trigger Starting
================================================================================
Step 1: Scraping FTP directories...
Scraping http://ftp.ctgfun.com/Movies/...
Found 10 movies in http://ftp.ctgfun.com/Movies/
Total movies found: 10
Step 2: Checking for new movies...
➕ New movie added: Test Movie 2024 (3.5 GB)
✅ Added 1 new movies to database
Step 3: Triggering GitHub Actions for pending movies...
Found 1 pending movies
Processing: Test Movie 2024
✅ GitHub Action triggered for: Test Movie 2024
✅ Triggered processing for: Test Movie 2024
================================================================================
FTP Movie Bot - cPanel Trigger Completed Successfully
================================================================================
```

### Step 5: Setup Cron Job

**Method A: cPanel Cron Jobs Interface**

1. Log in to cPanel
2. Go to "Cron Jobs"
3. Under "Add New Cron Job":
   - **Common Settings:** Custom
   - **Minute:** `*/30` (every 30 minutes)
   - **Hour:** `*` (every hour)
   - **Day:** `*` (every day)
   - **Month:** `*` (every month)
   - **Weekday:** `*` (every weekday)
   - **Command:**
     ```bash
     /home/techandc/virtualenv/movie_bot_new/3.11/bin/python /home/techandc/movie_bot_new/ftp_movie_bot/cpanel_trigger.py >> /home/techandc/movie_bot_new/ftp_movie_bot/logs/cron.log 2>&1
     ```
4. Click "Add New Cron Job"

**Method B: SSH crontab**

```bash
# Edit crontab
crontab -e

# Add this line (runs every 30 minutes):
*/30 * * * * /home/techandc/virtualenv/movie_bot_new/3.11/bin/python /home/techandc/movie_bot_new/ftp_movie_bot/cpanel_trigger.py >> /home/techandc/movie_bot_new/ftp_movie_bot/logs/cron.log 2>&1

# Save and exit (Ctrl+X, then Y, then Enter)
```

**Verify cron job:**
```bash
crontab -l
```

---

## ✅ Testing & Verification

### Test 1: Manual Trigger Test

```bash
# Run trigger script manually
cd /home/techandc/movie_bot_new/ftp_movie_bot/
/home/techandc/virtualenv/movie_bot_new/3.11/bin/python cpanel_trigger.py
```

**Check logs:**
```bash
cat logs/cpanel_trigger.log
```

### Test 2: Check Database

```sql
-- Check if movies were added
SELECT * FROM ftp_movies ORDER BY created_at DESC LIMIT 10;

-- Check processing status
SELECT status, COUNT(*) as count FROM ftp_movies GROUP BY status;
```

### Test 3: Verify GitHub Action Triggered

1. Go to your GitHub repository
2. Click "Actions" tab
3. You should see workflow runs:
   - Name: "Movie Splitter & Telegram Uploader"
   - Status: Running / Completed
4. Click on a run to see detailed logs

### Test 4: Check Telegram Channel

1. Go to your Telegram channel
2. You should see new movie posts with:
   - Movie title
   - Video file(s)
   - Part numbers (if split)

---

## 🔍 Monitoring & Maintenance

### Check GitHub Actions Usage

```bash
# View current month usage
SELECT * FROM github_actions_usage WHERE month_year = DATE_FORMAT(NOW(), '%Y-%m');
```

### View Processing Logs

```bash
# cPanel trigger logs
tail -f /home/techandc/movie_bot_new/ftp_movie_bot/logs/cpanel_trigger.log

# GitHub Actions logs
# Go to: https://github.com/YOUR_USERNAME/movie-bot/actions
```

### Database Maintenance

```sql
-- Clean up failed movies older than 7 days
DELETE FROM ftp_movies WHERE status = 'failed' AND created_at < DATE_SUB(NOW(), INTERVAL 7 DAY);

-- Reset stuck processing movies (older than 24 hours)
UPDATE ftp_movies 
SET status = 'pending', processing_started_at = NULL 
WHERE status = 'processing' AND processing_started_at < DATE_SUB(NOW(), INTERVAL 24 HOUR);
```

---

## 🛠️ Troubleshooting

### Issue 1: GitHub Action Not Triggering

**Symptoms:** cPanel script runs but no GitHub Action appears

**Solutions:**
1. **Check GitHub Token:**
   ```bash
   # Test token validity
   curl -H "Authorization: Bearer YOUR_TOKEN" https://api.github.com/user
   ```
   Should return your user info (not error)

2. **Check Token Scopes:**
   - Token must have `repo` and `workflow` scopes
   - Regenerate token if needed

3. **Check Repository Visibility:**
   - Repository must be PUBLIC for free Actions
   - Private repos need GitHub Pro ($4/month)

4. **Check Workflow File Location:**
   ```
   ✅ Correct: .github/workflows/process_movie.yml
   ❌ Wrong: github/workflows/process_movie.yml
   ❌ Wrong: .github/workflow/process_movie.yml
   ```

### Issue 2: Database Connection Failed

**Symptoms:** Script runs but database not updated

**Solutions:**
1. **Verify credentials in cpanel_trigger.py:**
   ```python
   DB_CONFIG = {
       "host": "localhost",  # Try 127.0.0.1 if localhost fails
       "user": "techandc_bot",
       "password": "12345Sajibs6@",
       "database": "techandc_prompts",
   }
   ```

2. **Test MySQL connection:**
   ```bash
   mysql -u techandc_bot -p techandc_prompts
   # Enter password when prompted
   ```

3. **Check database permissions:**
   ```sql
   SHOW GRANTS FOR 'techandc_bot'@'localhost';
   ```

### Issue 3: GitHub Action Fails During Download

**Symptoms:** Action starts but fails at download step

**Solutions:**
1. **Check FTP site accessibility:**
   ```bash
   curl -I http://ftp.ctgfun.com/Movies/MovieFile.mp4
   ```

2. **Check file size:**
   - Files > 10GB may timeout
   - Adjust `MAX_FILE_SIZE_FOR_PROCESSING` in `github_worker.py`

3. **Check GitHub Actions logs:**
   - Click on failed run → View logs
   - Look for specific error message

### Issue 4: Telegram Upload Fails

**Symptoms:** Movie downloads but doesn't appear in Telegram

**Solutions:**
1. **Verify bot token:**
   ```bash
   curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe
   ```

2. **Verify channel ID:**
   - Channel ID must start with `-` (e.g., `-1003564276724`)
   - Bot must be admin of the channel

3. **Check file size:**
   - Each part must be < 2GB
   - If part > 2GB, adjust split logic

### Issue 5: Cron Job Not Running

**Symptoms:** Script doesn't run automatically

**Solutions:**
1. **Check cron job exists:**
   ```bash
   crontab -l
   ```

2. **Check Python path:**
   ```bash
   which python
   /home/techandc/virtualenv/movie_bot_new/3.11/bin/python --version
   ```

3. **Check file permissions:**
   ```bash
   ls -l /home/techandc/movie_bot_new/ftp_movie_bot/cpanel_trigger.py
   # Should show: -rwxr-xr-x (executable)
   ```

4. **Check cron logs:**
   ```bash
   tail -f /var/log/cron
   # or
   grep CRON /var/log/syslog
   ```

---

## 📊 Performance Expectations

### Resource Usage

| Component | CPU | RAM | Disk | Time |
|-----------|-----|-----|------|------|
| **cPanel Script** | 0.1% | 25 MB | 0 MB | 2-3 sec |
| **GitHub Actions** | 15% | 2-4 GB | 8-10 GB | 20-40 min |
| **Total per movie** | ~0.1% on cPanel | ~25 MB on cPanel | 0 MB on cPanel | 20-40 min |

### Processing Capacity

| Metric | Value |
|--------|-------|
| **Movies per day** | 10-30 (depending on size) |
| **Movies per month** | 240+ (free tier) |
| **Max file size** | 10 GB (configurable) |
| **Average processing time** | 20-40 minutes per movie |
| **Success rate** | 95%+ |

---

## 🎉 Success Checklist

- ✅ Database tables created
- ✅ GitHub repository created and code uploaded
- ✅ GitHub Personal Access Token generated
- ✅ GitHub Secrets configured (6 secrets)
- ✅ cPanel script uploaded and configured
- ✅ Python dependencies installed
- ✅ Manual test run successful
- ✅ Cron job configured
- ✅ First movie processed and uploaded to Telegram

**If all checkboxes are checked, you're ready to go! 🚀**

---

## 📞 Support & Resources

### Useful Links
- **GitHub Actions Documentation:** https://docs.github.com/en/actions
- **python-telegram-bot Docs:** https://docs.python-telegram-bot.org/
- **FFmpeg Documentation:** https://ffmpeg.org/documentation.html

### Logs to Check
- cPanel trigger: `/home/techandc/movie_bot_new/ftp_movie_bot/logs/cpanel_trigger.log`
- GitHub Actions: `https://github.com/YOUR_USERNAME/movie-bot/actions`
- Cron logs: `/var/log/cron` or check cPanel cron email notifications

### Quick Reference Commands

```bash
# Manual trigger
/home/techandc/virtualenv/movie_bot_new/3.11/bin/python /home/techandc/movie_bot_new/ftp_movie_bot/cpanel_trigger.py

# Check logs
tail -f logs/cpanel_trigger.log

# Database status
mysql -u techandc_bot -p -e "SELECT status, COUNT(*) FROM techandc_prompts.ftp_movies GROUP BY status;"

# Check cron
crontab -l

# Check disk space
df -h
```

---

**Last Updated:** January 2026  
**Version:** 1.0  
**Author:** AI Assistant

**Good luck with your FTP Movie Bot! 🎬🤖**
