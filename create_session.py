#!/usr/bin/env python3
from telethon.sync import TelegramClient

api_id = 28186143
api_hash = '6073c3149388bbc06e818add0be1622d'
phone = '+8801739354392'

print("=" * 60)
print("Creating Telegram Session")
print("=" * 60)
print(f"Phone: {phone}")
print("You will receive a code on Telegram.")
print()

client = TelegramClient('telegram_session', api_id, api_hash)
client.start(phone=phone)
print()
print("=" * 60)
print("SUCCESS! Session file created.")
print("=" * 60)
client.disconnect()
