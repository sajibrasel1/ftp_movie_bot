#!/bin/bash
# Quick script to run poster backfill with recommended settings

cd ~/movie_bot_new/ftp_movie_bot

echo "========================================"
echo "  MLSBD Poster Backfill Script"
echo "========================================"
echo ""

# Check how many movies need posters
echo "📊 Checking database..."
MISSING_COUNT=$(mysql -u techandc_bot -p'12345Sajibs6@' techandc_prompts -sN -e "
SELECT COUNT(*) 
FROM mlsbd_movies 
WHERE (poster_url IS NULL OR poster_url = '') 
  AND mlsbd_url IS NOT NULL 
  AND mlsbd_url != '';
")

echo "Found $MISSING_COUNT movies without posters"
echo ""

if [ "$MISSING_COUNT" -eq 0 ]; then
    echo "✅ All movies already have posters!"
    exit 0
fi

# Ask user how many to process
if [ "$1" == "" ]; then
    echo "Usage:"
    echo "  ./run_poster_backfill.sh 50      # Process 50 movies"
    echo "  ./run_poster_backfill.sh 100     # Process 100 movies"
    echo "  ./run_poster_backfill.sh all     # Process ALL movies"
    echo ""
    echo "Running with default limit of 50..."
    LIMIT=50
elif [ "$1" == "all" ]; then
    echo "⚠️  Processing ALL $MISSING_COUNT movies..."
    echo "Press Ctrl+C within 3 seconds to cancel..."
    sleep 3
    /usr/bin/python3 poster_backfill.py --all --batch 20 --delay 2
    exit 0
else
    LIMIT=$1
fi

echo "🚀 Processing $LIMIT movies..."
echo ""

/usr/bin/python3 poster_backfill.py --limit $LIMIT --batch 10 --delay 2

echo ""
echo "✅ Done! Check logs/poster_backfill_*.log for details"
