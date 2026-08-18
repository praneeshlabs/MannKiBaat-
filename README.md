# Mann Ki Baat Regional-Language Playlist Scraper

Scrapes every "*xth Edition of 'Mann Ki Baat' - Regional Languages (Month 20yy)*"
playlist from `@OfficialMannKiBaat` and loads video metadata into the
existing `yt_data` Postgres schema (`channels`, `videos`).

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Git Bash on Windows: source venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env            # then fill in DB_PASSWORD
```

## Run

```bash
# Sanity-check on a single edition first -- do this before a full run.
python main.py --edition 48

# Full run (safe to Ctrl+C and rerun -- resumes from checkpoint automatically)
python main.py

# Start completely fresh, ignoring any existing checkpoint
python main.py --no-resume

# Throttle down further if YouTube starts rate-limiting
python main.py --workers 2
```

## Project structure

```
mkb_scraper/
├── config/
│   └── settings.py        # DB conninfo, playlist title regex, rate-limit knobs
├── src/
│   ├── discover_playlists.py  # Step 1: list + regex-filter channel playlists
│   ├── scrape_videos.py       # Step 2: per-video yt-dlp extraction + retry/backoff
│   ├── language_parser.py     # Infers regional language from title/description
│   ├── db_writer.py           # psycopg3 pooled, idempotent upserts
│   ├── checkpoint.py          # JSON checkpoint for safe resume
│   └── pipeline.py            # Orchestrator (threaded, per-playlist)
├── state/
│   ├── checkpoint.json        # created at runtime
│   └── failed_videos.log      # created at runtime
├── logs/                      # one timestamped log file per run
├── requirements.txt
├── .env.example
└── main.py
```

## How it works

1. **Discovery** — `extract_flat` over the channel's `/playlists` tab (cheap,
   one request). Titles are matched against a regex anchored on the
   `"Nth Edition of 'Mann Ki Baat' - Regional Languages"` prefix; the
   `(Month 20yy)` suffix is optional since older playlists omit it. Any
   edition number in 1–136 that isn't found is logged as a warning so you
   can check it manually rather than it silently going missing.
2. **Per-playlist scrape** — `extract_flat` again to list that playlist's
   videos (cheap), then a **full** `extract_info()` per video to get
   duration, description, and age-restriction. This per-video call is the
   expensive/risky part, so it's throttled (`VIDEO_EXTRACT_SLEEP_MIN/MAX`)
   and retried with exponential backoff on transient failures.
3. **Language tagging** — inferred from the video title/description against
   a table of regional language names. Unmatched titles get `language=None`
   and are still inserted — check `state/failed_videos.log` and query
   `WHERE language IS NULL` afterward to patch the alias table if needed.
4. **DB write** — `channels` is upserted once at startup (required first,
   since `videos.channel_id` has a foreign key to it). Every video is
   upserted on `video_id` (unique), so reruns never create duplicates.
   `metadata_extracted` stores a trimmed JSON snapshot of the raw yt-dlp
   info dict for anything not explicitly mapped to a column.
5. **Checkpointing** — `state/checkpoint.json` tracks per-playlist status
   and per-video completion. `python main.py` (default) skips anything
   already marked done, so an interrupted ~4,000-video run just picks back
   up where it left off.

## Notes / things to verify before a full run

- **Run `--edition 48` (or any known edition) first** and check the regex
  actually matched the playlist title as it appears live on YouTube —
  channel playlist titles can drift slightly from spec over time.
- **`audio_status` is intentionally left at its DB default (`PENDING`)** —
  this scraper only populates metadata; your existing audio/comment
  pipelines pick up from there via the `group = 'MannKiBaat'` tag.
- **Rate limiting**: ~4,000 full `extract_info()` calls is the real risk of
  a YouTube-side temporary block. If you see repeated 429s, drop
  `--workers` to 1–2 and/or raise `VIDEO_EXTRACT_SLEEP_MIN/MAX` in `.env`.
- **Do not commit `.env`** — it holds the DB password.
