import os
import asyncio
import math
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


async def fast_download(client, message, filename, status_msg):
    media = message.media
    if not media or not hasattr(media, "document"):
        raise ValueError("No document found")

    doc = media.document
    file_size = int(doc.size)
    path = os.path.join(DOWNLOAD_PATH, filename)

    # Download Config
    chunk_size = 1024 * 1024  # 1 MB chunks
    total_chunks = math.ceil(file_size / chunk_size)
    semaphore = asyncio.Semaphore(4)  # 4 Concurrent Downloads
    file_lock = asyncio.Lock()  # <--- THE FIX: Prevents write conflicts

    # Shared Progress Tracking
    downloaded_chunks = 0
    is_downloading = True

    # --- THE REPORTER TASK ---
    async def progress_reporter():
        start_time = time.time()
        while is_downloading:
            await asyncio.sleep(4)
            if not is_downloading:
                break

            # Calculate stats
            elapsed = time.time() - start_time
            if elapsed == 0:
                elapsed = 1
            current_bytes = downloaded_chunks * chunk_size
            speed = current_bytes / elapsed / 1024 / 1024  # MB/s

            progress_str = get_progress_bar(downloaded_chunks, total_chunks)

            try:
                await status_msg.edit(
                    f"⬇️ **Downloading:** `{filename}`\n"
                    f"{progress_str}\n"
                    f"⚡ Speed: {speed:.1f} MB/s"
                )
                print(f"⏳ {progress_str} @ {speed:.1f} MB/s", flush=True)
            except Exception as e:
                pass  # Ignore FloodWait

    # --- THE WORKER TASK ---
    async def download_chunk(file_obj, offset, size_to_download):
        nonlocal downloaded_chunks
        async with semaphore:
            # 1. Download to RAM first (Parallel & Fast)
            chunk_data = bytearray()
            async for part in client.iter_download(
                doc, offset=offset, limit=size_to_download, request_size=64 * 1024
            ):
                chunk_data.extend(part)

            # 2. Write to Disk (Locked & Safe)
            async with file_lock:  # <--- CRITICAL LOCK
                file_obj.seek(offset)
                file_obj.write(chunk_data)

            downloaded_chunks += 1

    # --- START ENGINE ---
    print(f"⬇️ Starting Parallel Download: {filename}")
    reporter_task = asyncio.create_task(progress_reporter())

    with open(path, "wb") as f:
        f.truncate(file_size)  # Pre-allocate space
        tasks = []
        for i in range(total_chunks):
            offset = i * chunk_size
            current_chunk_size = min(chunk_size, file_size - offset)
            task = asyncio.create_task(download_chunk(f, offset, current_chunk_size))
            tasks.append(task)

        await asyncio.gather(*tasks)

    is_downloading = False
    await reporter_task
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
            await fast_download(client, event.message, file_name, status_msg)
            await status_msg.edit(
                f"✅ **Download Complete!**\n`{file_name}`\n\nWaiting for Sorter..."
            )
            print(f"✅ Finished: {file_name}")
        except Exception as e:
            print(f"❌ Error: {e}")
            await status_msg.edit(f"❌ Error: `{str(e)}`")


print("✅ Bot Active! Waiting for files...")
client.run_until_disconnected()
