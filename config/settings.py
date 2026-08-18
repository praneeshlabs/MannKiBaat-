"""
Central configuration for the Mann Ki Baat scraper.
All secrets are read from environment variables (.env) -- never hardcoded.
"""
import os
import re

from dotenv import load_dotenv

load_dotenv()

# --- Database ---
DB_HOST = os.getenv("DB_HOST", "e2e-93-86.ssdcloudindia.net")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "yt_data")

DB_CONNINFO = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
DB_POOL_MIN_SIZE = int(os.getenv("DB_POOL_MIN_SIZE", "1"))
DB_POOL_MAX_SIZE = int(os.getenv("DB_POOL_MAX_SIZE", "5"))

# --- Target channel ---
CHANNEL_HANDLE = "@OfficialMannKiBaat"
CHANNEL_PLAYLISTS_URL = f"https://www.youtube.com/{CHANNEL_HANDLE}/playlists"
CHANNEL_ABOUT_URL = f"https://www.youtube.com/{CHANNEL_HANDLE}/about"

# Edition numbers we expect to find (1 through 136 inclusive, per spec).
EDITION_RANGE = range(1, 137)

# Matches: 48th Edition of 'Mann Ki Baat' - Regional Languages
# Tolerates single/double quotes and an optional trailing "(Month 20yy)"
# since older playlists omit the month/year suffix.
PLAYLIST_TITLE_REGEX = re.compile(
    r"""^\s*(?P<edition>\d{1,3})(?:st|nd|rd|th)\s+Edition\s+of\s+
        ['"]Mann\s+Ki\s+Baat['"]\s*-\s*Regional\s+Languages
        (?:\s*\(\s*(?P<month_year>[A-Za-z]+\s+\d{4})\s*\))?
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Group tag written to videos.group so downstream audio/comment workers can
# claim these rows using the existing ix_videos_claim_group index.
VIDEO_GROUP_TAG = "MannKiBaat"

# --- Scrape behavior / rate limiting ---
FLAT_EXTRACT_SLEEP = float(os.getenv("FLAT_EXTRACT_SLEEP", "0.5"))
VIDEO_EXTRACT_SLEEP_MIN = float(os.getenv("VIDEO_EXTRACT_SLEEP_MIN", "1.0"))
VIDEO_EXTRACT_SLEEP_MAX = float(os.getenv("VIDEO_EXTRACT_SLEEP_MAX", "2.5"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
RETRY_BACKOFF_MIN = float(os.getenv("RETRY_BACKOFF_MIN", "2"))
RETRY_BACKOFF_MAX = float(os.getenv("RETRY_BACKOFF_MAX", "60"))

# --- Paths ---
STATE_DIR = os.getenv("STATE_DIR", "state")
CHECKPOINT_FILE = os.path.join(STATE_DIR, "checkpoint.json")
FAILED_LOG_FILE = os.path.join(STATE_DIR, "failed_videos.log")
LOG_DIR = os.getenv("LOG_DIR", "logs")
