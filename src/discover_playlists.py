"""
Step 1: List every playlist on the MannKiBaat channel and keep only the ones
matching the required title format:
    "xth Edition of 'Mann Ki Baat' - Regional Languages (Month 20yy)"
The "(Month 20yy)" suffix is optional -- older playlists omit it.
"""
import logging
from typing import Dict, List

import yt_dlp
import re 
from config import settings

logger = logging.getLogger("mkb_scraper.discover")

MONTHS = {
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
}

BASE_PATTERNS = [
    re.compile(r"\bmann\s+ki\s+baat\b", re.IGNORECASE),
    re.compile(r"\bmann\s+ki\s+baat\s+2\.0\b", re.IGNORECASE),
]

LANGUAGE_PATTERNS = [
    re.compile(r"\bregional\s+languages?\b", re.IGNORECASE),
    re.compile(r"\bindian\s+languages?\b", re.IGNORECASE),
]

MONTH_YEAR_PATTERN = re.compile(
    r"\b("
    + "|".join(MONTHS)
    + r")\s+(20\d{2})\b",
    re.IGNORECASE,
)

EDITION_PATTERN = re.compile(
    r"\b(?P<edition>\d{1,3})(?:st|nd|rd|th)?\s*(?:edition)?\b",
    re.IGNORECASE,
)



def _flat_ydl_opts() -> dict:
    return {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
        "ignoreerrors": True
    }


def fetch_all_playlists() -> tuple:
    """Return (playlist entries, channel_id) from the base channel URL."""
    with yt_dlp.YoutubeDL(_flat_ydl_opts()) as ydl:
        info = ydl.extract_info(
            settings.CHANNEL_PLAYLISTS_URL,
            download=False,
        )

    info = info or {}
    channel_id = (
        info.get("channel_id")
        or info.get("uploader_id")
        or info.get("id")
        or settings.CHANNEL_ID
    )
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


def parse_playlist_title(title: str) -> dict | None:
    """
    Determine whether a playlist title is a Mann Ki Baat
    language playlist.

    Requirements:
      - Mann Ki Baat / Mann Ki Baat 2.0
      - Regional Language(s) OR Indian Language(s)
      - Month + 4-digit year
      - Edition number is optional
      - Separators/punctuation are ignored
    """

    if not title:
        return None

    # Normalize whitespace only.
    # Punctuation such as -, /, |, :, etc. is intentionally retained
    # because the regexes ignore it naturally.
    normalized = re.sub(r"\s+", " ", title).strip()

    # 1. Mann Ki Baat
    if not any(pattern.search(normalized) for pattern in BASE_PATTERNS):
        return None

    # 2. Regional / Indian Languages
    language_match = next(
        (
            pattern.search(normalized)
            for pattern in LANGUAGE_PATTERNS
            if pattern.search(normalized)
        ),
        None,
    )

    if not language_match:
        return None

  
    # 3. Month + Year
   
    month_year_match = MONTH_YEAR_PATTERN.search(normalized)

    if not month_year_match:
        return None

    month = month_year_match.group(1).capitalize()
    year = month_year_match.group(2)

    # 4. Optional edition number
    edition_match = EDITION_PATTERN.search(normalized)

    edition = None

    if edition_match:
        candidate = edition_match.group("edition")

        # Don't accidentally interpret the "2" from "2.0"
        # as an edition number.
        before = normalized[max(0, edition_match.start() - 5):edition_match.start()]
        after = normalized[edition_match.end():edition_match.end() + 3]

        if not re.search(r"\d\s*$", before) and not re.match(r"\.\d", after):
            edition = int(candidate)


    # 5. Playlist type
    language_text = language_match.group(0).lower()

    if language_text.startswith("regional"):
        playlist_type = "regional_languages"
    else:
        playlist_type = "indian_languages"

    return {
        "edition": edition,
        "month_year": f"{month} {year}",
        "playlist_type": playlist_type,
    }
    
    
def filter_mkb_playlists(raw_entries: List[dict]) -> List[Dict]:
    """Filter + parse the edition number from playlist titles matching the required format."""
    matched = []
    seen_editions = set()

    for entry in raw_entries:
        if not entry:
            continue
        title = (entry.get("title") or "").strip()

        parsed = parse_playlist_title(title)

        if not parsed:
            continue

        edition = parsed["edition"]
        month_year = parsed["month_year"]
        playlist_type = parsed["playlist_type"]

        if edition is not None:
            if edition in seen_editions:
                logger.warning(
                    "Duplicate playlist found for edition %d: %r",
                    edition,
                    title,
                )
            seen_editions.add(edition)

        playlist_id = entry.get("id")
        entry_url = entry.get("url") or ""
        playlist_url = entry_url if entry_url.startswith("http") else (
            f"https://www.youtube.com/playlist?list={playlist_id}"
        )


        playlist_type = (
            "edition_regional"
            if edition is not None
            else "indian_languages"
        )

        matched.append({
        "edition": edition,
        "playlist_id": playlist_id,
        "playlist_title": title,
        "playlist_url": playlist_url,
        "month_year": month_year,
        "playlist_type": playlist_type,
        })

    matched.sort(
    key=lambda p: (
        p["edition"] is None,
        p["edition"] if p["edition"] is not None else 9999,
        p["month_year"] or "",
        )
    )

    missing = sorted(set(settings.EDITION_RANGE) - seen_editions)
    if missing:
        logger.warning(
            "%d expected editions not found among channel playlists: %s",
            len(missing), missing,
        )

    edition_count = sum(
    1 for p in matched
    if p["playlist_type"] == "edition_regional"
)

    indian_language_count = sum(
        1 for p in matched
        if p["playlist_type"] == "indian_languages"
    )

    logger.info(
        "Matched %d playlists: %d numbered regional editions, %d Indian-language playlists",
        len(matched),
        edition_count,
        indian_language_count,
    )

    print("\n" + "-" * 100)
    print("DISCOVERED MANN KI BAAT REGIONAL-LANGUAGE PLAYLISTS")
    print("-" * 100)

    for p in matched:
        print(
        f"Edition {str(p['edition'] or '-'):>3} | "
        f"{p['playlist_title']} | "
        f"Playlist ID: {p['playlist_id']}"
)

    print("\n" + "-" * 50)
    print(f"TOTAL MATCHED PLAYLISTS: {len(matched)}")
    print("-" * 50)

    return matched

# NEW
def discover() -> tuple:
    """Returns (filtered_playlists, channel_id)."""
    raw, channel_id = fetch_all_playlists()
    return filter_mkb_playlists(raw), channel_id