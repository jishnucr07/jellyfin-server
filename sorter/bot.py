import os
import asyncio
import math
from telethon import TelegramClient, events, utils
from telethon.tl.types import DocumentAttributeFilename

# --- CONFIGURATION ---
# Force Integer conversion to prevent "str" errors
try:
    API_ID = int(os.getenv("API_ID").strip())
    API_HASH = os.getenv("API_HASH").strip()
    BOT_TOKEN = os.getenv("BOT_TOKEN").strip()
    AUTHORIZED_USER = os.getenv("AUTHORIZED_USER").strip()
except Exception as e:
    print(f"❌ Config Error: {e}")
    exit(1)

DOWNLOAD_PATH = "/downloads"
# ---------------------

print("🤖 Initializing High-Speed Bot...")
client = TelegramClient("bot_session", API_ID, API_HASH).start(bot_token=BOT_TOKEN)


async def fast_download(client, message, filename):
    """
    High-performance parallel downloader.
    Downloads in 1MB chunks using 4 concurrent workers.
    """
    # 1. Get the exact file object and size
    media = message.media
    if not media or not hasattr(media, "document"):
        raise ValueError("No document found")

    doc = media.document
    input_location = utils.get_input_location(media)
    file_size = int(doc.size)  # <--- FORCE INT TO FIX YOUR ERROR

    path = os.path.join(DOWNLOAD_PATH, filename)

    # 2. Parallel Config
    chunk_size = 1024 * 1024  # 1 MB per chunk
    total_chunks = math.ceil(file_size / chunk_size)
    semaphore = asyncio.Semaphore(4)  # 4 Parallel connections (Safe for Telegram)

    # Display helper
    last_display_time = 0
    downloaded_chunks = 0

    async def download_chunk(file_obj, offset, size_to_download):
        nonlocal downloaded_chunks, last_display_time
        async with semaphore:
            try:
                # Request specific byte range from Telegram
                async for chunk in client.iter_download(
                    input_location,
                    offset=offset,
                    limit=size_to_download,
                    request_size=64 * 1024,
                ):
                    file_obj.seek(offset)
                    file_obj.write(chunk)

                downloaded_chunks += 1

                # Update Progress (Every 3 seconds)
                import time

                now = time.time()
                if now - last_display_time > 3:
                    percent = (downloaded_chunks / total_chunks) * 100
                    try:
                        await message.edit(
                            f"🚀 Downloading `{filename}`: {percent:.1f}%"
                        )
                        last_display_time = now
                    except:
                        pass
            except Exception as e:
                print(f"Chunk error at {offset}: {e}")
                raise e

    # 3. Create file and start tasks
    print(
        f"⬇️ Starting Parallel Download: {filename} ({file_size / 1024 / 1024:.2f} MB)"
    )
    with open(path, "wb") as f:
        # Pre-allocate file size (Prevents fragmentation)
        f.truncate(file_size)

        tasks = []
        for i in range(total_chunks):
            offset = i * chunk_size
            # Calculate size for this specific chunk (handle last chunk)
            current_chunk_size = min(chunk_size, file_size - offset)

            # Create async task
            task = asyncio.create_task(download_chunk(f, offset, current_chunk_size))
            tasks.append(task)

        # Wait for all chunks to finish
        await asyncio.gather(*tasks)

    return path


@client.on(events.NewMessage(incoming=True))
async def handler(event):
    sender = await event.get_sender()
    if not sender or sender.username != AUTHORIZED_USER:
        return

    # Only process Documents (Video/Files)
    if event.media and hasattr(event.media, "document"):
        doc = event.media.document

        # Extract Filename
        file_name = "Unknown.mp4"
        if hasattr(doc, "attributes"):
            for attr in doc.attributes:
                if isinstance(attr, DocumentAttributeFilename):
                    file_name = attr.file_name
                    break

        status_msg = await event.reply(f"🚀 Allocating space for `{file_name}`...")

        try:
            await fast_download(client, status_msg, file_name)
            await status_msg.edit(f"✅ **Done!** `{file_name}` is ready for sorting.")
        except Exception as e:
            print(f"❌ Download Failed: {e}")
            await status_msg.edit(f"❌ Error: `{str(e)}`")


print("✅ High-Speed Bot Active!")
client.run_until_disconnected()
