#!/bin/bash
# Cron Job Setup Script for elaach.com Crawler
# Run this on your cPanel server

echo "=========================================="
echo "elaach.com Crawler - Cron Setup"
echo "=========================================="
echo

# Check if running on correct server
if [[ ! -d "/home/techandc/movie_bot_new/ftp_movie_bot" ]]; then
    echo "❌ Error: Project directory not found!"
    echo "   Make sure you're running this on the correct server."
    exit 1
fi

echo "✅ Project directory found"

# Backup current crontab
echo
echo "📋 Backing up current crontab..."
crontab -l > ~/crontab_backup_$(date +%Y%m%d_%H%M%S).txt
echo "✅ Backup saved to ~/crontab_backup_*.txt"

# Check if elaach cron already exists
if crontab -l 2>/dev/null | grep -q "elaach_crawler.py"; then
    echo
    echo "⚠️  elaach.com cron job already exists!"
    echo "   Current cron:"
    crontab -l | grep elaach_crawler.py
    echo
    read -p "   Do you want to update it? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Cancelled"
        exit 0
    fi
    # Remove old elaach cron
    crontab -l | grep -v "elaach_crawler.py" | crontab -
    echo "✅ Old cron removed"
fi

# Add new cron job
echo
echo "📝 Adding elaach.com cron job..."

(crontab -l 2>/dev/null; echo "# elaach.com crawler - every 6 hours") | crontab -
(crontab -l 2>/dev/null; echo "0 */6 * * * cd /home/techandc/movie_bot_new/ftp_movie_bot && source ~/virtualenv/movie_bot_new/3.11/bin/activate && python elaach_crawler.py >> logs/elaach_cron.log 2>&1") | crontab -

echo "✅ Cron job added successfully!"

# Display current crontab
echo
echo "=========================================="
echo "Current Crontab:"
echo "=========================================="
crontab -l
echo

# Verify cron service is running
echo "=========================================="
echo "Verifying cron service..."
echo "=========================================="
if systemctl is-active --quiet crond 2>/dev/null || service cron status >/dev/null 2>&1; then
    echo "✅ Cron service is running"
else
    echo "⚠️  Warning: Could not verify cron service status"
    echo "   Make sure cron is running on your system"
fi

echo
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo
echo "Next steps:"
echo "1. Wait for next cron execution (runs every 6 hours at 00:00, 06:00, 12:00, 18:00)"
echo "2. Monitor logs: tail -f ~/movie_bot_new/ftp_movie_bot/logs/elaach_cron.log"
echo "3. Check database: mysql -u techandc_bot -p techandc_prompts -e \"SELECT COUNT(*) FROM ftp_movies WHERE source='elaach.com';\""
echo
echo "To manually trigger now: python ~/movie_bot_new/ftp_movie_bot/elaach_crawler.py"
echo
