import asyncio
import os
import subprocess
from telethon import TelegramClient, events
from telethon.tl.types import DocumentAttributeFilename
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION (PUT YOUR KEYS HERE) ---
API_ID = os.getenv("API_ID")  # Replace with your App api_id from my.telegram.org
API_HASH = os.getenv("API_HASH")  # Replace with your App api_hash
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Replace with your BotFather token
# ------------------------------------------
AUTHORIZED_USER = os.getenv("AUTHORIZED_USER")
# Download to a temporary staging folder first


# ---------------------

# Docker Paths (Internal)
STAGING_PATH = os.getenv("STAGING_PATH")  # Shared volume
# ---------------------

client = TelegramClient("bot_session", API_ID, API_HASH).start(bot_token=BOT_TOKEN)
CHUNK_SIZE = os.getenv("CHUNK_SIZE")
WORKERS = os.getenv("WORKERS")


async def fast_download(client, message, filename, progress_callback):
    os.makedirs(STAGING_PATH, exist_ok=True)
    full_path = os.path.join(STAGING_PATH, filename)
    file = message.media.document
    file_size = file.size

    with open(full_path, "wb") as fd:
        chunks = list(range(0, file_size, CHUNK_SIZE))
        queue = asyncio.Queue()
        for chunk in chunks:
            queue.put_nowait(chunk)

        async def worker():
            while True:
                offset = await queue.get()
                if offset is None:
                    break
                async for part in client.iter_download(
                    file, offset=offset, limit=CHUNK_SIZE, request_size=CHUNK_SIZE
                ):
                    fd.seek(offset)
                    fd.write(part)
                    break
                queue.task_done()

        tasks = [asyncio.create_task(worker()) for _ in range(WORKERS)]
        for _ in range(WORKERS):
            queue.put_nowait(None)
        await asyncio.gather(*tasks)
    return full_path


@client.on(events.NewMessage(incoming=True))
async def handler(event):
    sender = await event.get_sender()
    if sender.username != AUTHORIZED_USER:
        return

    if event.file:
        file_name = "Unknown.mp4"
        for attr in event.file.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                file_name = attr.file_name
                break

        msg = await event.reply(f"⬇️ Downloading `{file_name}`...")

        try:
            # 1. Download to Staging
            await fast_download(client, event.message, file_name, None)

            # 2. DONE! No script triggering needed.
            # The 'sorter' container is watching this folder and will pick it up automatically.
            await msg.edit(f"✅ Downloaded!\nSorter will handle it now.")

        except Exception as e:
            await msg.edit(f"❌ Error: {str(e)}")


print("🤖 Bot Active...")
client.run_until_disconnected()
