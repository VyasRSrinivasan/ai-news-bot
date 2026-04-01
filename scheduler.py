#!/usr/bin/env python3
"""
AI News Bot — Scheduler

Runs the daily digest and/or medical news search automatically at configured times.

Usage:
  python scheduler.py                               # uses times from .env
  python scheduler.py --ai-time 07:00              # AI digest at 7:00 AM daily
  python scheduler.py --medical-time 08:00         # Medical news at 8:00 AM daily
  python scheduler.py --ai-time 07:00 --medical-time 08:00   # both
  python scheduler.py --ai-time 07:00 --run-now    # also fire immediately on start
"""
import argparse
import os
import sys
import time
import schedule
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _run_medical_news() -> None:
    """Run the medical news topic search and send to the Medical News Channel."""
    _log("Running Medical News search...")
    try:
        import os as _os
        from src.config import Config
        from src.logger import setup_logger
        from src.news.agent import TopicNewsAgent
        from src.news.deduper import deduplicate_news
        from src.news.fetcher import NewsFetcher
        from src.news.summarizer import Summarizer
        from src.notifiers import TelegramNotifier

        config = Config()
        today = datetime.now().strftime("%Y-%m-%d")
        topic = "cardiology pulmonology nephrology pediatrics endocrinology psychiatry oncology AI medicine"

        fetcher = NewsFetcher()
        fetcher.rss_feeds = fetcher.get_feeds_for_category("Health & Medicine")

        agent = TopicNewsAgent(
            provider_name=config.llm_provider,
            api_key=config.llm_api_key,
            model=config.llm_model,
            fetcher=fetcher,
        )

        articles = agent.collect(topic, max_sources=20)
        if not articles:
            _log("No medical articles found.")
            return

        articles = deduplicate_news(articles)
        _log(f"Collected {len(articles)} unique medical articles.")

        summarizer = Summarizer(
            provider_name=config.llm_provider,
            api_key=config.llm_api_key,
            model=config.llm_model,
        )
        digest = summarizer.summarize(articles, topics=[topic], today=today)

        medical_chat_id = _os.getenv("TELEGRAM_MEDICAL_CHAT_ID", "").strip()
        medical_bot_token = _os.getenv("TELEGRAM_MEDICAL_BOT_TOKEN", "").strip()

        if medical_chat_id:
            telegram = TelegramNotifier(
                bot_token=medical_bot_token or None,
                chat_id=medical_chat_id,
            )
        else:
            _log("TELEGRAM_MEDICAL_CHAT_ID not set — sending to default channel.")
            telegram = TelegramNotifier()

        if telegram.send_digest_summary(digest):
            _log("Medical News sent successfully.")
        else:
            _log("Medical News send failed.")

    except Exception as exc:
        _log(f"Medical News search failed: {exc}")


def _validate_time(value: str) -> str:
    """Validate HH:MM format."""
    try:
        datetime.strptime(value, "%H:%M")
        return value
    except ValueError:
        raise argparse.ArgumentTypeError(f"Time must be in HH:MM format (e.g. 07:00), got: {value!r}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Schedule daily AI and/or Medical news digests to Telegram."
    )
    parser.add_argument(
        "--ai-time",
        type=_validate_time,
        default=os.getenv("SCHEDULE_AI_TIME", ""),
        metavar="HH:MM",
        help="Time to send the AI News digest daily (e.g. 07:00). Reads SCHEDULE_AI_TIME from .env if omitted.",
    )
    parser.add_argument(
        "--medical-time",
        type=_validate_time,
        default=os.getenv("SCHEDULE_MEDICAL_TIME", ""),
        metavar="HH:MM",
        help="Time to send Medical News daily (e.g. 08:00). Reads SCHEDULE_MEDICAL_TIME from .env if omitted.",
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Fire all scheduled jobs immediately on startup (in addition to the scheduled time).",
    )
    args = parser.parse_args()

    if not args.ai_time and not args.medical_time:
        parser.error(
            "Provide at least one of --ai-time or --medical-time.\n"
            "You can also set SCHEDULE_AI_TIME and/or SCHEDULE_MEDICAL_TIME in your .env file."
        )

    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║           AI News Bot — Scheduler               ║")
    print("╠══════════════════════════════════════════════════╣")

    if args.ai_time:
        schedule.every().day.at(args.ai_time).do(_run_ai_digest)
        print(f"║  AI News digest      →  daily at {args.ai_time}          ║")

    if args.medical_time:
        schedule.every().day.at(args.medical_time).do(_run_medical_news)
        print(f"║  Medical News        →  daily at {args.medical_time}          ║")

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
            # Show next scheduled run every hour so user knows the process is alive
            next_run = schedule.next_run()
            if next_run:
                remaining = (next_run - datetime.now()).total_seconds()
                if int(remaining) % 3600 < 1:  # log once per hour
                    _log(f"Next job at {next_run.strftime('%Y-%m-%d %H:%M:%S')} "
                         f"({int(remaining // 60)} min away)")
            time.sleep(30)
    except KeyboardInterrupt:
        _log("Scheduler stopped.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
