"""
Simple JSON-backed checkpoint so a run can be safely resumed after a crash,
a network ban, or a manual interrupt. Deliberately file-based (not the DB)
so it works even before the DB connection is confirmed healthy, and so a
`--no-resume` run can start clean without touching Postgres state.
"""
import json
import os
import threading
from typing import Any, Dict

from config import settings

_lock = threading.RLock()


def _ensure_dir() -> None:
    os.makedirs(settings.STATE_DIR, exist_ok=True)


def load() -> Dict[str, Any]:
    _ensure_dir()
    if not os.path.exists(settings.CHECKPOINT_FILE):
        return {"playlists": {}}
    with open(settings.CHECKPOINT_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            # Corrupted checkpoint (e.g. process killed mid-write) -- don't
            # crash the run, just start fresh. Upserts are idempotent so
            # already-written DB rows just get re-verified, not duplicated.
            return {"playlists": {}}


def _save_locked(state: Dict[str, Any]) -> None:
    _ensure_dir()
    tmp_path = settings.CHECKPOINT_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp_path, settings.CHECKPOINT_FILE)  # atomic on POSIX + Windows


def save(state: Dict[str, Any]) -> None:
    with _lock:
        _save_locked(state)


def mark_playlist_status(state: Dict[str, Any], playlist_id: str, status: str, **extra) -> None:
    with _lock:
        entry = state["playlists"].setdefault(playlist_id, {"videos_done": []})
        entry["status"] = status
        entry.update(extra)
        _save_locked(state)


def mark_video_done(state: Dict[str, Any], playlist_id: str, video_id: str) -> None:
    with _lock:
        entry = state["playlists"].setdefault(playlist_id, {"videos_done": []})
        if video_id not in entry["videos_done"]:
            entry["videos_done"].append(video_id)
        _save_locked(state)


def is_video_done(state: Dict[str, Any], playlist_id: str, video_id: str) -> bool:
    with _lock:
        return video_id in state.get("playlists", {}).get(playlist_id, {}).get("videos_done", [])


def log_failed_video(playlist_id: str, video_id: str, error: str) -> None:
    _ensure_dir()
    with _lock:
        with open(settings.FAILED_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{playlist_id}\t{video_id}\t{error}\n")
