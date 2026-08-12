#!/usr/bin/env python3
"""
MLSBD Domain Updater
====================
Quick script to update MLSBD domain when it changes.

Usage:
    python update_mlsbd_domain.py https://mlsbd.biz
    python update_mlsbd_domain.py https://mlsbd.net
"""

import sys
import mysql.connector

# Database credentials
DB_CONFIG = {
    "host": "localhost",
    "user": "techandc_bot",
    "password": "12345Sajibs6@",
    "database": "techandc_prompts",
}

def update_domain(new_domain):
    """Update MLSBD domain in database"""
    # Clean domain
    new_domain = new_domain.rstrip('/')
    if not new_domain.startswith('http'):
        new_domain = 'https://' + new_domain
    
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Update domain
        cursor.execute(
            "UPDATE mlsbd_config SET config_value = %s WHERE config_key = 'base_url'",
            (new_domain,)
        )
        conn.commit()
        
        # Verify
        cursor.execute("SELECT config_value FROM mlsbd_config WHERE config_key = 'base_url'")
        result = cursor.fetchone()
        
        if result:
            print(f"✅ Domain updated successfully!")
            print(f"   Old domain: (check logs)")
            print(f"   New domain: {result[0]}")
        else:
            print("❌ Failed to verify domain update")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python update_mlsbd_domain.py <new_domain>")
        print("Example: python update_mlsbd_domain.py https://mlsbd.biz")
        sys.exit(1)
    
    new_domain = sys.argv[1]
    print(f"🔄 Updating MLSBD domain to: {new_domain}")
    update_domain(new_domain)
