#!/usr/bin/env python3
"""
AI News Bot — Scheduler

Runs the daily digest and/or specialty channel searches automatically at configured times.

Usage:
  python scheduler.py                                    # uses times from .env
  python scheduler.py --ai-time 07:00                   # AI digest at 7:00 AM daily
  python scheduler.py --medical-time 08:00              # Medical news at 8:00 AM daily
  python scheduler.py --pharma-time 08:30               # Pharma news at 8:30 AM daily
  python scheduler.py --genome-time 09:00               # Genome Research at 9:00 AM daily
  python scheduler.py --genetics-time 09:30             # Genetics Research at 9:30 AM daily
  python scheduler.py --energy-time 10:00               # Energy news at 10:00 AM daily
  python scheduler.py --rare-earth-time 10:30           # Rare Earth news at 10:30 AM daily
  python scheduler.py --ai-time 07:00 --run-now         # also fire immediately on start
"""
import argparse
import os
import sys
import time
import schedule
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()


# ── Channel configurations ─────────────────────────────────────────────────────
_CHANNEL_CONFIGS = {
    "medical": {
        "key": "medical",
        "title": "Medical News",
        "token_env": "TELEGRAM_MEDICAL_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_MEDICAL_CHAT_ID",
        "feeds_category": "Health & Medicine",
        "topic": "cardiology pulmonology nephrology pediatrics endocrinology diabetes psychiatry oncology AI medicine",
    },
    "pharma": {
        "key": "pharma",
        "title": "Pharma News",
        "token_env": "TELEGRAM_PHARMA_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_PHARMA_CHAT_ID",
        "feeds_category": "Pharmaceutical",
        "topic": "pharmaceutical drug discovery FDA clinical trial biotech biopharma drug approval",
    },
    "genome": {
        "key": "genome",
        "title": "Genome Research",
        "token_env": "TELEGRAM_GENOME_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_GENOME_CHAT_ID",
        "feeds_category": "Genome Research",
        "topic": "genomics genome sequencing CRISPR gene editing bioinformatics",
    },
    "genetics": {
        "key": "genetics",
        "title": "Genetics Research",
        "token_env": "TELEGRAM_GENETICS_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_GENETICS_CHAT_ID",
        "feeds_category": "Genetics Research",
        "topic": "genetics gene therapy genetic disorder hereditary mutation chromosome",
    },
    "energy": {
        "key": "energy",
        "title": "Energy News",
        "token_env": "TELEGRAM_ENERGY_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_ENERGY_CHAT_ID",
        "feeds_category": "Energy",
        "topic": "energy solar wind nuclear renewable battery grid clean energy hydrogen",
    },
    "rare_earth": {
        "key": "rare_earth",
        "title": "Rare Earth News",
        "token_env": "TELEGRAM_RARE_EARTH_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_RARE_EARTH_CHAT_ID",
        "feeds_category": "Rare Earth",
        "topic": "rare earth minerals lithium cobalt mining critical minerals supply chain",
    },
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def _run_ai_digest() -> None:
    """Run the full daily AI news digest (same as python main.py)."""
    _log("Running AI News digest...")
    try:
        import main as _main
        result = _main.main()
        if result == 0:
            _log("AI News digest sent successfully.")
        else:
            _log("AI News digest finished with errors.")
    except Exception as exc:
        _log(f"AI News digest failed: {exc}")


def _run_channel(cfg: dict) -> None:
    """Run a topic search for the given channel config and send to Telegram."""
    title = cfg["title"]
    _log(f"Running {title} search...")
    try:
        from src.config import Config
        from src.news.agent import TopicNewsAgent
        from src.news.deduper import deduplicate_news
        from src.news.fetcher import NewsFetcher
        from src.news.summarizer import Summarizer
        from src.notifiers import TelegramNotifier

        config = Config()
        today = datetime.now().strftime("%Y-%m-%d")

        fetcher = NewsFetcher()
        fetcher.rss_feeds = fetcher.get_feeds_for_category(cfg["feeds_category"])

        agent = TopicNewsAgent(
            provider_name=config.llm_provider,
            api_key=config.llm_api_key,
            model=config.llm_model,
            fetcher=fetcher,
        )

        articles = agent.collect(cfg["topic"], max_sources=20)
        if not articles:
            _log(f"No articles found for {title}.")
            return

        articles = deduplicate_news(articles)
        _log(f"Collected {len(articles)} unique articles for {title}.")

        summarizer = Summarizer(
            provider_name=config.llm_provider,
            api_key=config.llm_api_key,
            model=config.llm_model,
        )
        digest = summarizer.summarize(articles, topics=[cfg["topic"]], today=today)

        from src.db import Database

        chat_id = os.getenv(cfg["chat_id_env"], "").strip()
        bot_token = os.getenv(cfg["token_env"], "").strip()
        ai_bot_token = os.getenv("TELEGRAM_AI_BOT_TOKEN", "").strip()

        # Broadcast to the dedicated channel (if configured)
        if chat_id:
            telegram = TelegramNotifier(bot_token=bot_token or None, chat_id=chat_id)
            if telegram.send_digest_summary(digest, channel_title=title):
                _log(f"{title} sent successfully.")
            else:
                _log(f"{title} send failed.")
        else:
            _log(f"{cfg['chat_id_env']} not set — skipping channel broadcast.")

        # Deliver to individual subscribers
        db = Database()
        channel_key = cfg.get("key", "")
        if channel_key:
            subscribers = db.get_subscribers(channel_key)
            _log(f"Delivering {title} to {len(subscribers)} subscriber(s)...")
            for sub_chat_id in subscribers:
                TelegramNotifier(
                    bot_token=ai_bot_token or None,
                    chat_id=sub_chat_id,
                ).send_digest_summary(digest, channel_title=title)

    except Exception as exc:
        _log(f"{title} search failed: {exc}")


def _validate_time(value: str) -> str:
    """Validate HH:MM format."""
    try:
        datetime.strptime(value, "%H:%M")
        return value
    except ValueError:
        raise argparse.ArgumentTypeError(f"Time must be in HH:MM format (e.g. 07:00), got: {value!r}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Schedule daily AI and specialty news digests to Telegram."
    )
    parser.add_argument("--ai-time",         type=_validate_time, default=os.getenv("SCHEDULE_AI_TIME", ""),         metavar="HH:MM", help="Time to send the AI News digest daily.")
    parser.add_argument("--medical-time",    type=_validate_time, default=os.getenv("SCHEDULE_MEDICAL_TIME", ""),    metavar="HH:MM", help="Time to send Medical News daily.")
    parser.add_argument("--pharma-time",     type=_validate_time, default=os.getenv("SCHEDULE_PHARMA_TIME", ""),     metavar="HH:MM", help="Time to send Pharmaceutical News daily.")
    parser.add_argument("--genome-time",     type=_validate_time, default=os.getenv("SCHEDULE_GENOME_TIME", ""),     metavar="HH:MM", help="Time to send Genome Research daily.")
    parser.add_argument("--genetics-time",   type=_validate_time, default=os.getenv("SCHEDULE_GENETICS_TIME", ""),   metavar="HH:MM", help="Time to send Genetics Research daily.")
    parser.add_argument("--energy-time",     type=_validate_time, default=os.getenv("SCHEDULE_ENERGY_TIME", ""),     metavar="HH:MM", help="Time to send Energy News daily.")
    parser.add_argument("--rare-earth-time", type=_validate_time, default=os.getenv("SCHEDULE_RARE_EARTH_TIME", ""), metavar="HH:MM", help="Time to send Rare Earth News daily.")
    parser.add_argument("--run-now",         action="store_true",                                                                      help="Fire all scheduled jobs immediately on startup.")
    args = parser.parse_args()

    # Build list of (time, label, job_fn) for all enabled schedules
    scheduled = []
    if args.ai_time:
        scheduled.append((args.ai_time, "AI News digest", _run_ai_digest))
    for key, attr, label in [
        ("medical",   "medical_time",    "Medical News"),
        ("pharma",    "pharma_time",     "Pharmaceutical News"),
        ("genome",    "genome_time",     "Genome Research"),
        ("genetics",  "genetics_time",   "Genetics Research"),
        ("energy",    "energy_time",     "Energy News"),
        ("rare_earth","rare_earth_time", "Rare Earth News"),
    ]:
        t = getattr(args, attr)
        if t:
            cfg = _CHANNEL_CONFIGS[key]
            scheduled.append((t, label, lambda c=cfg: _run_channel(c)))

    if not scheduled:
        parser.error(
            "Provide at least one schedule time (e.g. --ai-time 07:00).\n"
            "You can also set SCHEDULE_AI_TIME, SCHEDULE_MEDICAL_TIME, etc. in your .env file."
        )

    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║           AI News Bot — Scheduler               ║")
    print("╠══════════════════════════════════════════════════╣")
    for t, label, fn in scheduled:
        schedule.every().day.at(t).do(fn)
        print(f"║  {label:<24}  →  daily at {t}     ║")
    print("╠══════════════════════════════════════════════════╣")
    print("║  Press Ctrl+C to stop                           ║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    if args.run_now:
        _log("--run-now specified: firing all jobs immediately.")
        schedule.run_all()

    try:
        while True:
            schedule.run_pending()
            next_run = schedule.next_run()
            if next_run:
                remaining = (next_run - datetime.now()).total_seconds()
                if int(remaining) % 3600 < 1:
                    _log(f"Next job at {next_run.strftime('%Y-%m-%d %H:%M:%S')} "
                         f"({int(remaining // 60)} min away)")
            time.sleep(30)
    except KeyboardInterrupt:
        _log("Scheduler stopped.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
