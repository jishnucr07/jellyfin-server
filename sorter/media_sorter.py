import os
from pathlib import Path
import shutil
import re
import time
import google.generativeai as genai
from dotenv import load_dotenv
import requests

load_dotenv()

# --- CONFIG ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # <--- PASTE KEY
WATCH_FOLDER = os.getenv("WATCH_FOLDER")  # Inside Docker, this maps to your staging
MOVIES_PATH = os.getenv("MOVIES_PATH")
SERIES_PATH = os.getenv("SERIES_PATH")
JELLYFIN_URL = "http://jellyfin:8096"
JELLYFIN_API_KEY = os.getenv("JELLYFIN_API_KEY")
# --------------

SORT_RE = re.compile(r"(.+?)\s*[sS](?:eason\s*)?(\d{1,2})")

CLEAN_PREFIX_RE = re.compile(r"^[^A-Z]*")
SORT_RE_adv = re.compile(
    r"(?:^|[.\-_ ])s(?:eason\s*)?(\d{1,2})(?:\b|[.\-_ ])",
    re.IGNORECASE,
)


genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

print("👀 Sorter Watchdog started... waiting for files.")


def normalize_file_name(name: str):
    name = CLEAN_PREFIX_RE.sub("", name)

    match = SORT_RE_adv.search(name)

    if not match:
        return name, None
    return match


def find_if_folder_exists(root_dir, prefix):
    prefix = prefix.lower()
    for path in Path(root_dir).rglob("*"):
        if path.is_dir() and path.name.lower().startswith(prefix):
            return path
    return None


def scan_jellyfin():
    try:
        url = f"{JELLYFIN_URL}/Library/Refresh?api_key={JELLYFIN_API_KEY}"
        requests.post(url)
        print("Sent 'Scan Library' Command to Jellyfin")
    except Exception as e:
        print(f"⚠️ Failed to trigger Jellyfin scan: {e}")


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
        if item.startswith(".") or item == "incomplete" or item == "temp":
            continue  # Skip hidden temp files

        # Wait if file is still growing (downloading)
        initial_size = os.path.getsize(target)
        time.sleep(2)
        if os.path.getsize(target) > initial_size:
            continue  # Skip, it's still writing

        print(f"🔎 Processing: {item}")

        # Logic: Regex -> AI -> Move
        match = normalize_file_name(item)
        dest = MOVIES_PATH

        def normalise_number(number: str):
            if number.startswith("0"):
                return number.strip("0")
            else:
                return number

        if match:
            existing_folder_path = find_if_folder_exists(
                SERIES_PATH, match.group("title")
            )
            season_number = normalise_number(match.group("season"))
            if existing_folder_path is not None:
                dest = os.path.join(existing_folder_path, f"Season {season_number}")
            else:
                dest = os.path.join(
                    SERIES_PATH,
                    match.group("title"),
                    f"Season {season_number}",
                )
        else:
            cat, show, seas = ask_gemini(item)

            if cat == "SERIES":
                existing_folder_path = find_if_folder_exists(SERIES_PATH, show)

                if existing_folder_path is not None:
                    dest = os.path.join(existing_folder_path, f"Season {seas}")
                else:
                    dest = os.path.join(SERIES_PATH, show, f"Season {seas}")

        os.makedirs(dest, exist_ok=True)
        try:
            shutil.move(target, os.path.join(dest, item))
            print(f"✅ Moved to: {dest}")
            # Fix permissions for Jellyfin
            os.system(f"chmod -R 1000:1000'{dest}'")
            os.system(f"chmod -R 777 '{dest}'")

            scan_jellyfin()
        except Exception as e:
            print(f"❌ Error: {e}")


# Run forever
while True:
    try:
        process_files()
    except Exception as e:
        print(f"Global Error: {e}")
    time.sleep(60)  # Check every minute
