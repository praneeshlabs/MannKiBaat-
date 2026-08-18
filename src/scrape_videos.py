"""
Step 2: For a given playlist, resolve every video's full metadata via yt-dlp.

Two-pass approach:
  1. extract_flat=True over the playlist -> cheap list of video ids/titles,
     no per-video network hit.
  2. Full extract_info() per video (throttled + retried with exponential
     backoff) -> duration, description, age-restriction, etc. for the DB row.
"""
import logging
import random
import time
from typing import Dict, List, Optional

import yt_dlp
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import settings
from src.language_parser import detect_language

logger = logging.getLogger("mkb_scraper.scrape")


class VideoExtractionError(Exception):
    pass


def list_playlist_videos(playlist_url: str) -> List[dict]:
    """Cheap pass: video ids + titles only, no per-video network hit."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "ignoreerrors": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)
    entries = [e for e in ((info or {}).get("entries") or []) if e]
    time.sleep(settings.FLAT_EXTRACT_SLEEP)
    return entries


@retry(
    reraise=True,
    stop=stop_after_attempt(settings.MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=settings.RETRY_BACKOFF_MIN, max=settings.RETRY_BACKOFF_MAX),
    retry=retry_if_exception_type(VideoExtractionError),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def _extract_video_info(video_url: str) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "ignoreerrors": False,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(video_url, download=False)
    except Exception as exc:  # yt-dlp raises several distinct exception types
        raise VideoExtractionError(str(exc)) from exc


def build_video_row(video_url: str, channel_id: str, group_tag: str) -> Optional[Dict]:
    """Full extract + map onto the `videos` table schema."""
    try:
        info = _extract_video_info(video_url)
    except VideoExtractionError as exc:
        logger.error("Giving up on %s after retries: %s", video_url, exc)
        return None

    if not info:
        return None

    title = info.get("title") or ""
    description = info.get("description") or ""

    return {
        "video_id": info.get("id"),
        "channel_id": channel_id,
        "video_url": f"https://www.youtube.com/watch?v={info.get('id')}",
        "description_preview": description[:1000],
        "language": detect_language(title, description),
        "age_restriction": info.get("age_limit"),
        "duration": _format_duration(info.get("duration")),
        "duration_secs": float(info["duration"]) if info.get("duration") is not None else None,
        "metadata_extracted": _safe_subset(info),
        "group": group_tag,
    }


def _format_duration(seconds: Optional[float]) -> Optional[str]:
    if seconds is None:
        return None
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _safe_subset(info: dict) -> dict:
    """Keep metadata_extracted small/relevant rather than dumping yt-dlp's
    entire (very large) info dict into the jsonb column."""
    keys = (
        "id", "title", "upload_date", "duration", "view_count", "like_count",
        "channel", "channel_id", "uploader", "age_limit", "categories",
        "tags", "webpage_url", "thumbnail",
    )
    return {k: info.get(k) for k in keys if k in info}


def sleep_jitter() -> None:
    time.sleep(random.uniform(settings.VIDEO_EXTRACT_SLEEP_MIN, settings.VIDEO_EXTRACT_SLEEP_MAX))
