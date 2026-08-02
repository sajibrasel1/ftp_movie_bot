# Auto Retry Failed Movies Setup Guide

## 🎯 Overview

The system now automatically retries failed movies up to **5 times** with two methods:

### 1️⃣ **Built-in Retry (cpanel_trigger.py)**
- Every time cron runs `cpanel_trigger.py`, it automatically picks up failed movies
- Failed movies with `retry_count < 5` are treated as pending
- Priority: pending movies first, then failed movies

### 2️⃣ **Stuck Movie Detection (auto_retry_failed.py)**
- Detects movies stuck in "processing" status for more than 60 minutes
- Automatically resets them to "pending" status
- Runs via separate cron job

---

## 📋 Setup Instructions

### Step 1: Add Auto Retry Cron Job

Add this cron job to run **every 30 minutes**:

```bash
# Auto retry failed/stuck movies (every 30 minutes)
*/30 * * * * cd /home/techandc/movie_bot_new/ftp_movie_bot && source set_env.sh && /home/techandc/virtualenv/movie_bot_new/3.11/bin/python auto_retry_failed.py >> logs/auto_retry.log 2>&1
```

### Step 2: Existing Cron Job (No Changes Needed)

Your existing cron job already supports auto-retry:

```bash
# Main trigger (every hour)
0 * * * * cd /home/techandc/movie_bot_new/ftp_movie_bot && source set_env.sh && /home/techandc/virtualenv/movie_bot_new/3.11/bin/python cpanel_trigger.py >> logs/cpanel_trigger.log 2>&1
```

---

## 🔄 How Auto Retry Works

### Scenario 1: Download Failed (Connection Timeout)
```
Movie ID: 1
Status: failed
Error: Connection broken: IncompleteRead
Retry Count: 1

↓ Next cron run (within 1 hour) ↓

cpanel_trigger.py detects failed movie
→ Triggers GitHub Action again
→ Retry Count: 2
```

### Scenario 2: Stuck Processing (GitHub Action Timeout)
```
Movie ID: 2
Status: processing
Processing Started: 2 hours ago

↓ auto_retry_failed.py runs (every 30 min) ↓

Detects stuck movie (>60 min)
→ Resets to pending
→ Retry Count: +1
→ Next cpanel_trigger.py picks it up
```

### Scenario 3: Max Retries Reached
```
Movie ID: 3
Status: failed
Retry Count: 5

↓ cpanel_trigger.py runs ↓

Skips this movie (retry_count >= 5)
→ Manual intervention required
```

---

## 📊 Monitoring

### Check Current Status
```sql
SELECT status, COUNT(*) as count 
FROM ftp_movies 
GROUP BY status;
```

### Check Failed Movies
```sql
SELECT id, movie_title, error_message, retry_count, last_retry_at
FROM ftp_movies 
WHERE status = 'failed'
ORDER BY retry_count DESC, last_retry_at DESC
LIMIT 20;
```

### Check Stuck Movies
```sql
SELECT id, movie_title, status, retry_count,
       TIMESTAMPDIFF(MINUTE, processing_started_at, NOW()) as minutes_stuck
FROM ftp_movies 
WHERE status = 'processing'
  AND TIMESTAMPDIFF(MINUTE, processing_started_at, NOW()) > 60
ORDER BY processing_started_at ASC;
```

### Manually Reset a Failed Movie
```sql
-- Reset Movie ID 123 to retry immediately
UPDATE ftp_movies 
SET status = 'pending', 
    error_message = NULL,
    github_run_id = NULL
WHERE id = 123;
```

---

## 🎛️ Configuration

### Adjust Retry Limits

**File:** `cpanel_trigger.py` (Line 126)
```python
WHERE (status = 'pending' OR (status = 'failed' AND retry_count < 5))
```
Change `5` to increase/decrease max retries.

**File:** `auto_retry_failed.py` (Line 25)
```python
MAX_RETRY_COUNT = 5  # Maximum 5 retries
STUCK_TIMEOUT_MINUTES = 60  # 60 minutes timeout
```

### Adjust Cron Frequency

**For faster processing:**
```bash
# Main trigger every 30 minutes (instead of 1 hour)
*/30 * * * * cd /home/techandc/movie_bot_new/ftp_movie_bot && ...
```

**For less aggressive retry:**
```bash
# Auto retry every 2 hours (instead of 30 minutes)
0 */2 * * * cd /home/techandc/movie_bot_new/ftp_movie_bot && ...
```

---

## 🧹 Logs

### View Auto Retry Logs
```bash
tail -f /home/techandc/movie_bot_new/ftp_movie_bot/logs/auto_retry.log
```

### View Main Trigger Logs
```bash
tail -f /home/techandc/movie_bot_new/ftp_movie_bot/logs/cpanel_trigger.log
```

---

## ✅ Benefits

1. **Automatic Recovery**: Failed movies automatically retry without manual intervention
2. **Stuck Detection**: Movies hanging in "processing" status get auto-reset
3. **Rate Limiting**: Max 5 retries prevents infinite loops
4. **Zero Downtime**: Works alongside existing cron job
5. **Smart Priority**: Pending movies always processed before failed ones

---

## 🚨 When Manual Intervention is Needed

### Movies with 5+ Failed Retries
```sql
-- Find movies that need manual check
SELECT id, movie_title, error_message, retry_count
FROM ftp_movies 
WHERE status = 'failed' AND retry_count >= 5
ORDER BY updated_at DESC;
```

**Possible reasons:**
- FTP URL is dead/broken
- File is corrupted
- Telegram bot token expired
- GitHub Secrets not configured

**Manual fix:**
```sql
-- Option 1: Force retry (increase limit)
UPDATE ftp_movies 
SET retry_count = 0, status = 'pending'
WHERE id = <movie_id>;

-- Option 2: Mark as permanently failed
UPDATE ftp_movies 
SET status = 'completed', 
    error_message = 'Skipped - permanent failure'
WHERE id = <movie_id>;
```

---

## 📞 Support

If movies keep failing after 5 retries, check:

1. **GitHub Actions Logs**: https://github.com/sajibrasel1/ftp_movie_bot/actions
2. **Telegram Bot**: Is the bot token valid?
3. **FTP Server**: Is http://ftp.ctgfun.com accessible?
4. **Database**: Are connection details correct in `set_env.sh`?
5. **GitHub Secrets**: Are `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` set?

---

**Created:** August 2026  
**Version:** 1.0
