#!/bin/bash
# Deployment Verification Script
# Checks if elaach.com crawler is properly deployed

echo "=========================================="
echo "elaach.com Crawler - Deployment Verification"
echo "=========================================="
echo

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check counter
checks_passed=0
checks_total=0

# Function to check and report
check() {
    checks_total=$((checks_total + 1))
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
        checks_passed=$((checks_passed + 1))
        return 0
    else
        echo -e "${RED}❌ $2${NC}"
        if [ ! -z "$3" ]; then
            echo -e "   ${YELLOW}→ $3${NC}"
        fi
        return 1
    fi
}

# 1. Check project directory
echo "1. Checking project directory..."
[ -d "/home/techandc/movie_bot_new/ftp_movie_bot" ]
check $? "Project directory exists" "Run: cd ~/movie_bot_new/ftp_movie_bot"
echo

# 2. Check Python virtualenv
echo "2. Checking Python virtualenv..."
[ -f "/home/techandc/virtualenv/movie_bot_new/3.11/bin/python" ]
check $? "Python virtualenv exists" "Create virtualenv first"
echo

# 3. Check Selenium installation
echo "3. Checking Selenium installation..."
source ~/virtualenv/movie_bot_new/3.11/bin/activate 2>/dev/null
python -c "import selenium" 2>/dev/null
check $? "Selenium installed" "Run: pip install selenium webdriver-manager"
echo

# 4. Check database source column
echo "4. Checking database schema..."
COLUMN_EXISTS=$(mysql -h localhost -u techandc_bot -p'12345Sajibs6@' techandc_prompts -sNe "SHOW COLUMNS FROM ftp_movies LIKE 'source';" 2>/dev/null | wc -l)
[ "$COLUMN_EXISTS" -gt 0 ]
check $? "Database 'source' column exists" "Run: mysql -u techandc_bot -p techandc_prompts < add_source_column.sql"
echo

# 5. Check crawler file
echo "5. Checking crawler files..."
[ -f "/home/techandc/movie_bot_new/ftp_movie_bot/elaach_crawler.py" ]
check $? "elaach_crawler.py exists" "Upload the file to server"
echo

# 6. Check cron job
echo "6. Checking cron job..."
crontab -l 2>/dev/null | grep -q "elaach_crawler.py"
check $? "Cron job configured" "Run: bash setup_cron.sh"
echo

# 7. Check logs directory
echo "7. Checking logs directory..."
[ -d "/home/techandc/movie_bot_new/ftp_movie_bot/logs" ]
check $? "Logs directory exists" "Run: mkdir -p logs"
echo

# 8. Check if any movies from elaach.com
echo "8. Checking database for elaach.com movies..."
ELAACH_MOVIES=$(mysql -h localhost -u techandc_bot -p'12345Sajibs6@' techandc_prompts -sNe "SELECT COUNT(*) FROM ftp_movies WHERE source='elaach.com';" 2>/dev/null)
[ ! -z "$ELAACH_MOVIES" ] && [ "$ELAACH_MOVIES" -gt 0 ]
check $? "Movies from elaach.com found: $ELAACH_MOVIES" "Run crawler manually: python elaach_crawler.py"
echo

# Summary
echo "=========================================="
echo "Verification Summary"
echo "=========================================="
echo -e "Checks passed: ${GREEN}$checks_passed${NC} / $checks_total"
echo

if [ $checks_passed -eq $checks_total ]; then
    echo -e "${GREEN}🎉 All checks passed! Deployment is successful!${NC}"
    echo
    echo "System is ready! Latest movies will be automatically fetched every 6 hours."
    echo
    echo "Monitor with:"
    echo "  tail -f ~/movie_bot_new/ftp_movie_bot/logs/elaach_cron.log"
    echo
    exit 0
else
    echo -e "${YELLOW}⚠️  Some checks failed. Please fix the issues above.${NC}"
    echo
    echo "Need help? Check: DEPLOYMENT_GUIDE.md"
    echo
    exit 1
fi
