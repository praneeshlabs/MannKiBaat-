"""
Step 3: Persist scraped data using psycopg3 with a small connection pool.
All writes are idempotent upserts, so reruns / resumed runs are safe and
never produce duplicate rows.
"""
import logging
from typing import Optional

from psycopg.types.json import Json
from psycopg_pool import ConnectionPool

from config import settings

logger = logging.getLogger("mkb_scraper.db")

_pool: Optional[ConnectionPool] = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=settings.DB_CONNINFO,
            min_size=settings.DB_POOL_MIN_SIZE,
            max_size=settings.DB_POOL_MAX_SIZE,
            open=True,
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def upsert_channel(channel_id: str, name: str, url: str) -> None:
    """Must run before any video insert -- videos.channel_id has an FK to this table."""
    pool = get_pool()
    with pool.connection() as conn:
        conn.execute(
            """
            INSERT INTO channels (channel_id, name, url, created_at)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (channel_id) DO UPDATE SET
                name = EXCLUDED.name,
                url = EXCLUDED.url;
            """,
            (channel_id, name, url),
        )
    logger.info("Upserted channel %s", channel_id)


def upsert_video(video: dict) -> None:
    if not video.get("video_id"):
        logger.warning("Skipping video row with no video_id: %r", video)
        return

    pool = get_pool()
    payload = {**video, "metadata_extracted": Json(video.get("metadata_extracted") or {})}

    with pool.connection() as conn:
        conn.execute(
            """
            INSERT INTO videos (
                video_id, channel_id, video_url, description_preview,
                language, age_restriction, duration, duration_secs,
                metadata_extracted, "group", created_at, updated_at
            ) VALUES (
                %(video_id)s, %(channel_id)s, %(video_url)s, %(description_preview)s,
                %(language)s, %(age_restriction)s, %(duration)s, %(duration_secs)s,
                %(metadata_extracted)s, %(group)s, now(), now()
            )
            ON CONFLICT (video_id) DO UPDATE SET
                description_preview = EXCLUDED.description_preview,
                language = EXCLUDED.language,
                age_restriction = EXCLUDED.age_restriction,
                duration = EXCLUDED.duration,
                duration_secs = EXCLUDED.duration_secs,
                metadata_extracted = EXCLUDED.metadata_extracted,
                "group" = EXCLUDED."group",
                updated_at = now();
            """,
            payload,
        )
