"""
Telethon-based Movie Uploader (Supports up to 2GB files natively)
================================================================
No self-hosted API server needed! Uses MTProto directly.
"""

import os
import sys
import asyncio
from pathlib import Path
from telethon import TelegramClient
from telethon.tl.types import DocumentAttributeVideo

# Configuration from environment
API_ID = int(os.environ.get("TELEGRAM_API_ID"))
API_HASH = os.environ.get("TELEGRAM_API_HASH")
PHONE_NUMBER = os.environ.get("TELEGRAM_PHONE_NUMBER")  # Your phone number
CHANNEL_ID = int(os.environ.get("TELEGRAM_CHAT_ID"))  # Channel ID

# Session file will be stored here
SESSION_FILE = "telegram_session"


async def upload_video(file_path, caption, channel_id):
    """Upload video file to Telegram channel using Telethon"""
    
    print(f"📤 Uploading: {file_path}")
    print(f"📦 Size: {os.path.getsize(file_path) / (1024**3):.2f} GB")
    print(f"📢 Channel: {channel_id}")
    
    # Create client
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    
    try:
        # Connect
        await client.start(phone=PHONE_NUMBER)
        print("✅ Connected to Telegram")
        
        # Get video duration and dimensions (optional but recommended)
        file_size = os.path.getsize(file_path)
        
        # Upload with progress callback
        print("📤 Starting upload...")
        
        def progress_callback(current, total):
            percent = (current / total) * 100
            print(f"📊 Progress: {current / (1024**3):.2f} GB / {total / (1024**3):.2f} GB ({percent:.1f}%)", end='\r')
        
        # Upload as video
        message = await client.send_file(
            channel_id,
            file_path,
            caption=caption,
            supports_streaming=True,
            progress_callback=progress_callback,
            attributes=[
                DocumentAttributeVideo(
                    duration=0,  # Will be auto-detected
                    w=1920,      # Width (adjust if needed)
                    h=1080,      # Height (adjust if needed)
                    supports_streaming=True
                )
            ]
        )
        
        print(f"\n✅ Upload successful!")
        print(f"📨 Message ID: {message.id}")
        
        return message.id
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        raise
    finally:
        await client.disconnect()


def main():
    """Main entry point"""
    if len(sys.argv) < 3:
        print("Usage: python telethon_uploader.py <file_path> <caption>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    caption = sys.argv[2]
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        sys.exit(1)
    
    # Run async upload
    asyncio.run(upload_video(file_path, caption, CHANNEL_ID))


if __name__ == "__main__":
    main()
