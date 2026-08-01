#!/usr/bin/env python3
"""
Mark all pending movies as completed
Use this to skip old movies and only process new ones
"""

import mysql.connector
import sys

# Database credentials
DB_CONFIG = {
    "host": "localhost",
    "user": "techandc_bot",
    "password": "12345Sajibs6@",
    "database": "techandc_prompts",
}

def main():
    print("=" * 80)
    print("🔧 MARKING ALL PENDING MOVIES AS COMPLETED")
    print("=" * 80)
    
    try:
        # Connect to database
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Count pending movies
        cursor.execute("SELECT COUNT(*) FROM ftp_movies WHERE status = 'pending'")
        pending_count = cursor.fetchone()[0]
        
        if pending_count == 0:
            print("✅ No pending movies found. All done!")
            return
        
        print(f"📊 Found {pending_count} pending movies")
        print("🔄 Marking them as completed...")
        
        # Update all pending to completed
        cursor.execute(
            """
            UPDATE ftp_movies 
            SET status = 'completed', 
                processing_completed_at = NOW()
            WHERE status = 'pending'
            """
        )
        
        conn.commit()
        affected_rows = cursor.rowcount
        
        print(f"✅ Successfully marked {affected_rows} movies as completed!")
        print()
        print("=" * 80)
        print("✅ DONE! Now only new movies will be processed.")
        print("=" * 80)
        
        cursor.close()
        conn.close()
        
    except mysql.connector.Error as e:
        print(f"❌ Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
