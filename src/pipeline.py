"""
Orchestrator: ties discovery -> scrape -> DB write together with logging,
checkpointing, and bounded concurrency across playlists.
"""
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional



from config import settings
from src import checkpoint, db_writer
from src.discover_playlists import discover
from src.scrape_videos import build_video_row, list_playlist_videos, sleep_jitter

logger = logging.getLogger("mkb_scraper.pipeline")

CHANNEL_NAME = "Mann Ki Baat"


def _setup_logging() -> None:
    os.makedirs(settings.LOG_DIR, exist_ok=True)
    log_path = os.path.join(settings.LOG_DIR, f"run_{datetime.now():%Y%m%d_%H%M%S}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler()],
    )



def scrape_playlist(playlist: dict, channel_id: str, state: dict) -> None:
    playlist_id = playlist["playlist_id"]
    logger.info("Starting playlist edition %s (%s)", playlist["edition"], playlist_id)
    checkpoint.mark_playlist_status(state, playlist_id, "in_progress", **playlist)

    try:
        entries = list_playlist_videos(playlist["playlist_url"])
    except Exception as exc:
        logger.error("Failed to list videos for playlist %s: %s", playlist_id, exc)
        checkpoint.mark_playlist_status(state, playlist_id, "failed", error=str(exc))
        return

    logger.info("Playlist edition %s has %d videos", playlist["edition"], len(entries))

    for entry in entries:
        video_id = entry.get("id")
        if not video_id:
            continue
        if checkpoint.is_video_done(state, playlist_id, video_id):
            continue

        video_url = f"https://www.youtube.com/watch?v={video_id}"
        row = build_video_row(video_url, channel_id, settings.VIDEO_GROUP_TAG)
        sleep_jitter()

        if row is None:
            checkpoint.log_failed_video(playlist_id, video_id, "extraction_failed")
            continue

        try:
            db_writer.upsert_video(row)
            checkpoint.mark_video_done(state, playlist_id, video_id)
        except Exception as exc:
            logger.error("DB upsert failed for video %s: %s", video_id, exc)
            checkpoint.log_failed_video(playlist_id, video_id, f"db_error:{exc}")

    checkpoint.mark_playlist_status(state, playlist_id, "done", **playlist)
    logger.info("Finished playlist edition %s", playlist["edition"])


def run(resume: bool = True, only_edition: Optional[int] = None, max_workers: Optional[int] = None) -> None:
    _setup_logging()
    logger.info("=== Mann Ki Baat scrape starting ===")

    state = checkpoint.load() if resume else {"playlists": {}}

    # NEW (inside run())
    playlists, channel_id = discover()
    if not channel_id:
        raise RuntimeError("Could not resolve MannKiBaat channel_id from playlists page")
    db_writer.upsert_channel(channel_id, CHANNEL_NAME, settings.CHANNEL_PLAYLISTS_URL)

    playlists = discover()
    if only_edition is not None:
        playlists = [p for p in playlists if p["edition"] == only_edition]

    if resume:
        playlists = [
            p for p in playlists
            if state["playlists"].get(p["playlist_id"], {}).get("status") != "done"
        ]

    logger.info("%d playlists queued for this run", len(playlists))

    workers = max_workers or settings.MAX_WORKERS
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(scrape_playlist, playlist, channel_id, state): playlist
            for playlist in playlists
        }
        for future in as_completed(futures):
            playlist = futures[future]
            try:
                future.result()
            except Exception as exc:
                logger.exception(
                    "Unhandled error scraping playlist %s: %s", playlist["playlist_id"], exc
                )

    db_writer.close_pool()
    logger.info("=== Mann Ki Baat scrape finished ===")
