import os
import asyncio
import time
from telethon import TelegramClient, events
from telethon.tl.types import DocumentAttributeFilename

# --- CONFIGURATION ---
try:
    API_ID = int(os.getenv("API_ID").strip())
    API_HASH = os.getenv("API_HASH").strip()
    BOT_TOKEN = os.getenv("BOT_TOKEN").strip()
    AUTHORIZED_USER = os.getenv("AUTHORIZED_USER").strip()
except Exception as e:
    print(f"❌ Config Error: {e}")
    exit(1)

# Check for Speed Booster
try:
    import cryptg

    print("🚀 Speed Booster (cryptg) found! Fast download enabled.")
except ImportError:
    print("⚠️ cryptg not found. Downloads might be slower.")

DOWNLOAD_PATH = "/downloads"

print("🤖 Initializing Client...")
client = TelegramClient("bot_session", API_ID, API_HASH).start(bot_token=BOT_TOKEN)


# --- HELPER: Progress Bar ---
def get_progress_bar(current, total):
    percent = (current / total) * 100
    bar_len = 10
    filled = int(bar_len * percent / 100)
    bar = "▓" * filled + "░" * (bar_len - filled)
    return f"[{bar}] {percent:.1f}%"


async def reliable_download(client, message, filename, status_msg):
    path = os.path.join(DOWNLOAD_PATH, filename)

    # Progress Tracker
    last_display_time = 0
    start_time = time.time()

    async def progress_callback(current, total):
        nonlocal last_display_time
        now = time.time()

        # Only update every 4 seconds to avoid FloodWait
        if now - last_display_time > 4:
            elapsed = now - start_time
            if elapsed == 0:
                elapsed = 1

            speed_mb = (current / 1024 / 1024) / elapsed
            progress_str = get_progress_bar(current, total)

            try:
                await status_msg.edit(
                    f"⬇️ **Downloading:** `{filename}`\n"
                    f"{progress_str}\n"
                    f"⚡ Speed: {speed_mb:.1f} MB/s"
                )
                print(f"⏳ {progress_str} @ {speed_mb:.1f} MB/s", flush=True)
                last_display_time = now
            except:
                pass  # Ignore Telegram errors

    print(f"⬇️ Starting Native Download: {filename}")

    # The Native Downloader (Reliable & Fast with cryptg)
    await client.download_media(message, file=path, progress_callback=progress_callback)

    return path


@client.on(events.NewMessage(incoming=True))
async def handler(event):
    sender = await event.get_sender()
    if not sender or sender.username != AUTHORIZED_USER:
        return

    if event.media and hasattr(event.media, "document"):
        doc = event.media.document

        file_name = "Unknown.mp4"
        if hasattr(doc, "attributes"):
            for attr in doc.attributes:
                if isinstance(attr, DocumentAttributeFilename):
                    file_name = attr.file_name
                    break

        status_msg = await event.reply(f"🚀 Found `{file_name}`. Starting...")

        try:
            await reliable_download(client, event.message, file_name, status_msg)
            await status_msg.edit(
                f"✅ **Download Complete!**\n`{file_name}`\n\nWaiting for Sorter..."
            )
            print(f"✅ Finished: {file_name}")
        except Exception as e:
            print(f"❌ Error: {e}")
            await status_msg.edit(f"❌ Error: `{str(e)}`")


print("✅ Bot Active! Waiting for files...")
client.run_until_disconnected()
