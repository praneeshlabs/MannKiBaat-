"""
Central configuration for the Mann Ki Baat scraper.
All secrets are read from environment variables (.env) -- never hardcoded.
"""
import os
import re

from dotenv import load_dotenv

load_dotenv()

# Database
DB_HOST = os.getenv("DB_HOST", "e2e-93-86.ssdcloudindia.net")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "yt_data")

DB_CONNINFO = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
DB_POOL_MIN_SIZE = int(os.getenv("DB_POOL_MIN_SIZE", "1"))
DB_POOL_MAX_SIZE = int(os.getenv("DB_POOL_MAX_SIZE", "5"))

# Target channel
CHANNEL_HANDLE = "@OfficialMannKiBaat"

# Use the stable YouTube channel ID rather than the @handle.
# The @handle URL is currently failing to resolve in yt-dlp.
CHANNEL_ID = "UCEKXNa0XpMKDkRatg58PGmg"

CHANNEL_PLAYLISTS_URL = (
    f"https://www.youtube.com/channel/{CHANNEL_ID}/playlists"
)

CHANNEL_ABOUT_URL = (
    f"https://www.youtube.com/channel/{CHANNEL_ID}/about"
)

# Edition numbers we expect to find (1 through 136 inclusive, per spec).
EDITION_RANGE = range(1, 137)

# Matches: 48th Edition of 'Mann Ki Baat' - Regional Languages
# Tolerates single/double quotes and an optional trailing "(Month 20yy)"
# since older playlists omit the month/year suffix.
PLAYLIST_TITLE_REGEX = re.compile(
    r"""
    (?P<base>
        mann\s+ki\s+baat(?:\s+2\.0)?
    )
    .*?
    (?P<language>
        regional\s+languages?
        |
        indian\s+languages?
    )
    .*?
    (?P<month_year>
        january|february|march|april|may|june|
        july|august|september|october|november|december
    )
    \s+
    (?P<year>20\d{2})
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Group tag written to videos.group so downstream audio/comment workers can
# claim these rows using the existing ix_videos_claim_group index.
VIDEO_GROUP_TAG = "MannKiBaat"

# Scrape behavior / rate limiting
FLAT_EXTRACT_SLEEP = float(os.getenv("FLAT_EXTRACT_SLEEP", "0.5"))
VIDEO_EXTRACT_SLEEP_MIN = float(os.getenv("VIDEO_EXTRACT_SLEEP_MIN", "1.0"))
VIDEO_EXTRACT_SLEEP_MAX = float(os.getenv("VIDEO_EXTRACT_SLEEP_MAX", "2.5"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
RETRY_BACKOFF_MIN = float(os.getenv("RETRY_BACKOFF_MIN", "2"))
RETRY_BACKOFF_MAX = float(os.getenv("RETRY_BACKOFF_MAX", "60"))

# Paths
STATE_DIR = os.getenv("STATE_DIR", "state")
CHECKPOINT_FILE = os.path.join(STATE_DIR, "checkpoint.json")
FAILED_LOG_FILE = os.path.join(STATE_DIR, "failed_videos.log")
LOG_DIR = os.getenv("LOG_DIR", "logs")
