import os
import shutil
import re
import time
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# --- CONFIG ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # <--- PASTE KEY
WATCH_FOLDER = os.getenv("WATCH_FOLDER")  # Inside Docker, this maps to your staging
MOVIES_PATH = os.getenv("MOVIES_PATH")
SERIES_PATH = os.getenv("SERIES_PATH")
# --------------

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

print("👀 Sorter Watchdog started... waiting for files.")


def ask_gemini(filename):
    try:
        prompt = (
            f"Analyze filename: '{filename}'. Is it Movie or Series? "
            "If Series, extract Show Name and Season. "
            "Format: TYPE|SHOW|SEASON. Example: SERIES|The Bear|1"
        )
        return model.generate_content(prompt).text.strip().split("|")
    except:
        return "MOVIE", None, None


def process_files():
    # Scan the folder
    for item in os.listdir(WATCH_FOLDER):
        target = os.path.join(WATCH_FOLDER, item)
        if item.startswith("."):
            continue  # Skip hidden temp files

        # Wait if file is still growing (downloading)
        initial_size = os.path.getsize(target)
        time.sleep(2)
        if os.path.getsize(target) > initial_size:
            continue  # Skip, it's still writing

        print(f"🔎 Processing: {item}")

        # Logic: Regex -> AI -> Move
        match = re.search(r"(.+?)\s*[sS](?:eason\s*)?(\d{1,2})", item, re.IGNORECASE)
        dest = MOVIES_PATH

        if match:
            dest = os.path.join(
                SERIES_PATH,
                match.group(1).replace(".", " ").strip(),
                f"Season {match.group(2)}",
            )
        else:
            cat, show, seas = ask_gemini(item)
            if cat == "SERIES":
                dest = os.path.join(SERIES_PATH, show, f"Season {seas}")

        os.makedirs(dest, exist_ok=True)
        try:
            shutil.move(target, os.path.join(dest, item))
            print(f"✅ Moved to: {dest}")
            # Fix permissions for Jellyfin
            os.system(f"chmod -R 777 '{dest}'")
        except Exception as e:
            print(f"❌ Error: {e}")


# Run forever
while True:
    try:
        process_files()
    except Exception as e:
        print(f"Global Error: {e}")
    time.sleep(60)  # Check every minute
