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

# Time (seconds) file size must remain unchanged to be considered "done"
STABILITY_THRESHOLD = 15
# ----------------

# Regex with NAMED groups (?P<name>...) to avoid logic errors
SORT_RE_ADV = re.compile(
    r"(?P<title>.+?)[.\s_-]+[sS](?:eason\s*)?(?P<season>\d{1,2})", re.IGNORECASE
)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

print("👀 Sorter Watchdog started... waiting for files.")


def normalize_file_name(name: str):
    """
    Returns a match object if it looks like a Series (S01),
    otherwise returns None.
    """
    # Simple cleanup of common release group prefixes if needed
    clean_name = re.sub(r"^[^A-Z0-9]*", "", name, flags=re.IGNORECASE)

    match = SORT_RE_ADV.search(clean_name)
    return match  # Returns None if no match found


def find_if_folder_exists(root_dir, prefix):
    if not prefix:
        return None
    prefix = prefix.lower().strip()
    # Safely iterate directory
    try:
        for path in Path(root_dir).iterdir():
            if path.is_dir() and path.name.lower().startswith(prefix):
                return path
    except FileNotFoundError:
        return None
    return None


def scan_jellyfin():
    if not JELLYFIN_URL or not JELLYFIN_API_KEY:
        return
    try:
        url = f"{JELLYFIN_URL}/Library/Refresh?api_key={JELLYFIN_API_KEY}"
        requests.post(url, timeout=5)
        print("📡 Sent 'Scan Library' Command to Jellyfin")
    except Exception as e:
        print(f"⚠️ Failed to trigger Jellyfin scan: {e}")


def ask_gemini(filename):
    try:
        prompt = (
            f"Analyze filename: '{filename}'. Is it a Movie or TV Series? "
            "If it is a Series, extract the Show Name and the Season Number. "
            "Reply strictly in this format: TYPE|SHOW|SEASON "
            "Example: SERIES|The Bear|1 "
            "Example: MOVIE|Inception|None"
        )
        response = model.generate_content(prompt).text.strip()
        parts = response.split("|")

        if len(parts) < 3:
            return "MOVIE", None, None
        return parts[0].strip().upper(), parts[1].strip(), parts[2].strip()
    except Exception as e:
        print(f"🤖 Gemini Error: {e}")
        return "MOVIE", None, None


def is_file_stable(filepath):
    """
    Checks if a file is still being written to.
    Returns True if stable (download done), False otherwise.
    """
    try:
        initial_size = os.path.getsize(filepath)
        time.sleep(STABILITY_THRESHOLD)
        final_size = os.path.getsize(filepath)

        # If size changed, it's definitely downloading
        if initial_size != final_size:
            return False

        # Optional: Safety check - ignore 0 byte files
        if final_size == 0:
            return False

        return True
    except FileNotFoundError:
        return False  # File was moved/deleted during check


def process_files():
    # snapshot of current files
    try:
        files = os.listdir(WATCH_FOLDER)
    except FileNotFoundError:
        print(f"❌ Watch folder not found: {WATCH_FOLDER}")
        return

    for item in files:
        target = os.path.join(WATCH_FOLDER, item)

        # Skip directories, temp files, hidden files
        if item.startswith(".") or item in ["incomplete", "temp"]:
            continue
        if not os.path.isfile(target):
            continue

        # 1. Check for stability (Fixes Corruption)
        print(f"⏳ Checking stability: {item}...")
        if not is_file_stable(target):
            print(f"   Still downloading (size changed). Skipping.")
            continue

        print(f"🔎 Processing: {item}")

        # 2. Logic: Regex -> AI -> Move
        match = normalize_file_name(item)
        dest_base = MOVIES_PATH
        final_dest_dir = MOVIES_PATH  # Default

        if match:
            # IT IS A SERIES (Regex identified S01/Season 1)
            show_title = match.group("title").replace(".", " ").strip()
            season_num = match.group("season").lstrip("0") or "1"  # Handle '01' -> '1'

            existing_folder = find_if_folder_exists(SERIES_PATH, show_title)

            if existing_folder:
                final_dest_dir = os.path.join(existing_folder, f"Season {season_num}")
            else:
                final_dest_dir = os.path.join(
                    SERIES_PATH, show_title, f"Season {season_num}"
                )

        else:
            # Fallback to AI
            cat, show, seas = ask_gemini(item)

            if cat == "SERIES":
                seas = seas.lstrip("0") if seas and seas.isdigit() else "1"
                existing_folder = find_if_folder_exists(SERIES_PATH, show)

                if existing_folder:
                    final_dest_dir = os.path.join(existing_folder, f"Season {seas}")
                else:
                    final_dest_dir = os.path.join(SERIES_PATH, show, f"Season {seas}")
            else:
                # It's a Movie
                final_dest_dir = MOVIES_PATH

        # 3. Move Execution
        try:
            os.makedirs(final_dest_dir, exist_ok=True)
            final_path = os.path.join(final_dest_dir, item)

            shutil.move(target, final_path)
            print(f"✅ Moved to: {final_path}")

            # 4. Permissions Fix (chown for owner, chmod for perms)
            # Assuming 1000:1000 is the user:group ID
            os.system(f'chown -R 1000:1000 "{final_dest_dir}"')
            os.system(f'chmod -R 777 "{final_dest_dir}"')

            scan_jellyfin()

        except Exception as e:
            print(f"❌ Move Failed: {e}")


# Run forever
if __name__ == "__main__":
    while True:
        try:
            process_files()
        except Exception as e:
            print(f"Global Error: {e}")
        time.sleep(30)
