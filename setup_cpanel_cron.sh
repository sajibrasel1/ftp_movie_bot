#!/bin/bash
# =====================================================
# cPanel Cron Job Setup Script
# Runs movie processor every 5 minutes
# =====================================================

echo "🎬 Setting up cPanel Movie Processor Cron Jobs"
echo "=============================================="

# Get Python path
PYTHON_PATH=$(which python3)
SCRIPT_DIR="$HOME/movie_bot_new/ftp_movie_bot"

echo "Python path: $PYTHON_PATH"
echo "Script directory: $SCRIPT_DIR"

# Add to crontab
echo ""
echo "Add these cron jobs to cPanel:"
echo "=============================================="
echo ""
echo "1. MLSBD Trigger (Every 30 minutes)"
echo "*/30 * * * * cd $SCRIPT_DIR && $PYTHON_PATH mlsbd_trigger.py >> logs/cron_mlsbd_trigger.log 2>&1"
echo ""
echo "2. Movie Processor (Every 5 minutes)"
echo "*/5 * * * * cd $SCRIPT_DIR && $PYTHON_PATH cpanel_movie_processor.py >> logs/cron_processor.log 2>&1"
echo ""
echo "=============================================="
echo ""
echo "📋 Steps to add in cPanel:"
echo "1. Go to cPanel → Cron Jobs"
echo "2. Set: Common Settings = */5 * * * * (Every 5 minutes)"
echo "3. Command: cd $SCRIPT_DIR && $PYTHON_PATH cpanel_movie_processor.py >> logs/cron_processor.log 2>&1"
echo "4. Click 'Add New Cron Job'"
echo ""
echo "✅ Done! Movie processor will run automatically"
