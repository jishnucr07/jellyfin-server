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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WATCH_FOLDER = os.getenv("WATCH_FOLDER")
MOVIES_PATH = os.getenv("MOVIES_PATH")
SERIES_PATH = os.getenv("SERIES_PATH")
JELLYFIN_URL = "http://jellyfin:8096"
JELLYFIN_API_KEY = os.getenv("JELLYFIN_API_KEY")

STABILITY_THRESHOLD = 15
# ----------------

SORT_RE_ADV = re.compile(
    r"(?P<title>.+?)[.\s_-]+[sS](?:eason\s*)?(?P<season>\d{1,2})", re.IGNORECASE
)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

print(f"👀 Watchdog active on: {WATCH_FOLDER}")


def get_total_size(path):
    """
    Calculates size of a file OR a directory (recursively).
    Required because os.path.getsize() on a folder only returns 4096 bytes.
    """
    total = 0
    try:
        if os.path.isfile(path):
            return os.path.getsize(path)

        # If it's a folder, sum all files inside
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total += os.path.getsize(fp)
    except Exception:
        return 0
    return total


def is_stable(path):
    """Checks if file/folder size remains constant over time."""
    try:
        size_1 = get_total_size(path)
        # If size is 0, it might be just created
        if size_1 == 0:
            return False

        time.sleep(STABILITY_THRESHOLD)

        size_2 = get_total_size(path)
        if size_1 == size_2:
            return True
        return False
    except FileNotFoundError:
        return False


def normalize_file_name(name: str):
    clean_name = re.sub(r"^[^A-Z0-9]*", "", name, flags=re.IGNORECASE)
    match = SORT_RE_ADV.search(clean_name)
    return match


def find_if_folder_exists(root_dir, prefix):
    if not prefix:
        return None
    try:
        # Search for exact or close match
        for path in Path(root_dir).iterdir():
            if path.is_dir() and path.name.lower().startswith(prefix.lower()):
                return path
    except:
        return None
    return None


def scan_jellyfin():
    if not JELLYFIN_URL:
        return
    try:
        print("📡 Triggering Jellyfin Scan...")
        requests.post(
            f"{JELLYFIN_URL}/Library/Refresh?api_key={JELLYFIN_API_KEY}", timeout=5
        )
    except:
        pass


def ask_gemini(filename):
    try:
        prompt = (
            f"Analyze filename: '{filename}'. Is it a Movie or Series? "
            "Format: TYPE|SHOW|SEASON. Example: SERIES|The Bear|1"
        )
        response = model.generate_content(prompt).text.strip()
        parts = response.split("|")
        if len(parts) < 3:
            return "MOVIE", None, None
        return parts[0].strip().upper(), parts[1].strip(), parts[2].strip()
    except:
        return "MOVIE", None, None


def process_files():
    if not os.path.exists(WATCH_FOLDER):
        print(f"❌ Error: Watch folder does not exist: {WATCH_FOLDER}")
        return

    # Loop through everything (Files AND Folders)
    for item in os.listdir(WATCH_FOLDER):
        target = os.path.join(WATCH_FOLDER, item)

        # Skip hidden stuff and specific temp names
        if item.startswith(".") or item in ["incomplete", "temp", "aria2"]:
            continue

        print(f"⏳ Checking stability: {item}")
        if not is_stable(target):
            print(f"   ...Still downloading/writing. Skipping.")
            continue

        print(f"🚀 Processing: {item}")

        match = normalize_file_name(item)
        dest_base = MOVIES_PATH
        final_dest_dir = MOVIES_PATH

        # --- LOGIC START ---
        if match:
            # Regex Hit
            title = match.group("title").replace(".", " ").strip()
            season = match.group("season").lstrip("0") or "1"

            existing = find_if_folder_exists(SERIES_PATH, title)
            if existing:
                final_dest_dir = os.path.join(existing, f"Season {season}")
            else:
                final_dest_dir = os.path.join(SERIES_PATH, title, f"Season {season}")
        else:
            # AI Hit
            cat, show, seas = ask_gemini(item)
            if cat == "SERIES":
                seas = seas.lstrip("0") if seas.isdigit() else "1"
                existing = find_if_folder_exists(SERIES_PATH, show)
                if existing:
                    final_dest_dir = os.path.join(existing, f"Season {seas}")
                else:
                    final_dest_dir = os.path.join(SERIES_PATH, show, f"Season {seas}")
            else:
                final_dest_dir = MOVIES_PATH
        # --- LOGIC END ---

        # Move
        try:
            os.makedirs(final_dest_dir, exist_ok=True)
            destination = os.path.join(final_dest_dir, item)

            shutil.move(target, destination)
            print(f"✅ Moved to: {destination}")

            # Permissions
            os.system(f'chown -R 1000:1000 "{destination}"')
            os.system(f'chmod -R 777 "{destination}"')

            scan_jellyfin()
        except Exception as e:
            print(f"❌ Failed to move {item}: {e}")


if __name__ == "__main__":
    while True:
        try:
            process_files()
        except Exception as e:
            print(f"Global Crash: {e}")
