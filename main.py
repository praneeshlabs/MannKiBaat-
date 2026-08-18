"""
CLI entrypoint.

Examples:
    python main.py                     # full run, resume from checkpoint
    python main.py --no-resume         # ignore checkpoint, start clean
    python main.py --edition 48        # scrape only the 48th edition (good smoke test)
    python main.py --workers 2         # override concurrency
"""
import argparse

from src.pipeline import run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape Mann Ki Baat regional-language playlists into Postgres."
    )
    parser.add_argument(
        "--no-resume", action="store_true",
        help="Ignore existing checkpoint and start fresh.",
    )
    parser.add_argument(
        "--edition", type=int, default=None,
        help="Scrape only this edition number (1-136). Useful as a smoke test.",
    )
    parser.add_argument(
        "--workers", type=int, default=None,
        help="Override MAX_WORKERS from settings.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(resume=not args.no_resume, only_edition=args.edition, max_workers=args.workers)
