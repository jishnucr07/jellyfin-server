import os
import asyncio
import math
import sys
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


async def fast_download(client, message, filename, status_msg):
    media = message.media
    if not media or not hasattr(media, "document"):
        raise ValueError("No document found")

    doc = media.document
    # FIX: We use the 'doc' object directly. No utils.get_input_location needed.

    file_size = int(doc.size)
    path = os.path.join(DOWNLOAD_PATH, filename)
    chunk_size = 1024 * 1024  # 1 MB chunks
    total_chunks = math.ceil(file_size / chunk_size)

    # 4 Parallel connections
    semaphore = asyncio.Semaphore(4)

    last_display_time = 0
    downloaded_chunks = 0

    async def download_chunk(file_obj, offset, size_to_download):
        nonlocal downloaded_chunks, last_display_time
        async with semaphore:
            # FIX IS HERE: We pass 'doc' directly to iter_download
            async for chunk in client.iter_download(
                doc, offset=offset, limit=size_to_download, request_size=64 * 1024
            ):
                file_obj.seek(offset)
                file_obj.write(chunk)

            downloaded_chunks += 1

            import time

            now = time.time()
            if now - last_display_time > 3:
                percent = (downloaded_chunks / total_chunks) * 100
                try:
                    await status_msg.edit(
                        f"🚀 Downloading `{filename}`: {percent:.1f}%"
                    )
                    last_display_time = now
                except:
                    pass

    print(f"⬇️ Starting Parallel Download: {filename}")
    with open(path, "wb") as f:
        f.truncate(file_size)
        tasks = []
        for i in range(total_chunks):
            offset = i * chunk_size
            current_chunk_size = min(chunk_size, file_size - offset)
            task = asyncio.create_task(download_chunk(f, offset, current_chunk_size))
            tasks.append(task)
        await asyncio.gather(*tasks)

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

        status_msg = await event.reply(f"🚀 Found `{file_name}`. Initializing...")

        try:
            await fast_download(client, event.message, file_name, status_msg)
            await status_msg.edit(f"✅ **Done!** `{file_name}` is ready.")
            print(f"✅ Finished: {file_name}")
        except Exception as e:
            print(f"❌ Error: {e}")
            await status_msg.edit(f"❌ Error: `{str(e)}`")


print("✅ Bot Active! Waiting for files...")
client.run_until_disconnected()
