"""
Step 1: List every playlist on the MannKiBaat channel and keep only the ones
matching the required title format:
    "xth Edition of 'Mann Ki Baat' - Regional Languages (Month 20yy)"
The "(Month 20yy)" suffix is optional -- older playlists omit it.
"""
import logging
from typing import Dict, List

import yt_dlp

from config import settings

logger = logging.getLogger("mkb_scraper.discover")

def _flat_ydl_opts() -> dict:
    return {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
        "ignoreerrors": True,
        "cookiesfrombrowser": ("chrome",),
    }

# NEW
def fetch_all_playlists() -> tuple:
    """Return (playlist entries, channel_id) from the base channel URL."""
    with yt_dlp.YoutubeDL(_flat_ydl_opts()) as ydl:
        info = ydl.extract_info(settings.CHANNEL_PLAYLISTS_URL, download=False)
    info = info or {}
    channel_id = info.get("channel_id") or info.get("uploader_id") or info.get("id")

    # Channel page returns tabs as top-level entries; each tab has its own entries.
    # We need to find the Playlists tab and pull from it, falling back to a flat scan.
    all_entries = list(info.get("entries") or [])
    playlist_entries = []
    for entry in all_entries:
        if not entry:
            continue
        # Tab-level entry (e.g. "Playlists" tab) contains nested entries
        if entry.get("ie_key") == "YoutubeTab" or entry.get("_type") == "playlist":
            nested = list(entry.get("entries") or [])
            if nested:
                playlist_entries.extend(nested)
                continue
        # Flat playlist entry directly
        if entry.get("playlist_count") is not None or "list=" in (entry.get("url") or ""):
            playlist_entries.append(entry)

    # Deduplicate by id
    seen = set()
    deduped = []
    for e in playlist_entries:
        eid = e.get("id")
        if eid and eid not in seen:
            seen.add(eid)
            deduped.append(e)

    logger.info("Fetched %d playlist entries from channel (channel_id=%s)", len(deduped), channel_id)
    return deduped, channel_id

def filter_mkb_playlists(raw_entries: List[dict]) -> List[Dict]:
    """Filter + parse the edition number from playlist titles matching the required format."""
    matched = []
    seen_editions = set()

    for entry in raw_entries:
        if not entry:
            continue
        title = (entry.get("title") or "").strip()
        m = settings.PLAYLIST_TITLE_REGEX.match(title)
        if not m:
            continue

        edition = int(m.group("edition"))
        if edition in seen_editions:
            logger.warning("Duplicate playlist found for edition %d: %r", edition, title)
        seen_editions.add(edition)

        playlist_id = entry.get("id")
        entry_url = entry.get("url") or ""
        playlist_url = entry_url if entry_url.startswith("http") else (
            f"https://www.youtube.com/playlist?list={playlist_id}"
        )

        matched.append({
            "edition": edition,
            "playlist_id": playlist_id,
            "playlist_title": title,
            "playlist_url": playlist_url,
            "month_year": m.group("month_year"),
        })

    matched.sort(key=lambda p: p["edition"])

    missing = sorted(set(settings.EDITION_RANGE) - seen_editions)
    if missing:
        logger.warning(
            "%d expected editions not found among channel playlists: %s",
            len(missing), missing,
        )

    logger.info("Matched %d playlists against the required title format", len(matched))
    return matched


# NEW
def discover() -> tuple:
    """Returns (filtered_playlists, channel_id)."""
    raw, channel_id = fetch_all_playlists()
    return filter_mkb_playlists(raw), channel_id