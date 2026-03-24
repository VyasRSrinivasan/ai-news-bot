#!/usr/bin/env python3
"""
AI News Bot — Interactive Topic Search

Usage:
  python topic_search.py                   # prompts for topic interactively
  python topic_search.py "electric vehicles"
  python topic_search.py technology --no-telegram
"""
import argparse
import sys
from datetime import datetime

from src.config import Config
from src.logger import setup_logger
from src.news.agent import TopicNewsAgent
from src.news.deduper import deduplicate_news
from src.news.fetcher import NewsFetcher
from src.news.summarizer import Summarizer
from src.notifiers import TelegramNotifier


def _print_digest(digest: dict) -> None:
    """Print digest to stdout in a readable format."""
    print()
    print("=" * 70)
    print(f"  {digest.get('date', '')}  |  {digest.get('headline', '')}")
    print("=" * 70)
    for cat in digest.get("categories", []):
        print(f"\n── {cat.get('name', '').upper()} ──")
        for story in cat.get("stories", []):
            imp = story.get("importance", "").upper()
            print(f"\n  [{imp}] {story.get('title', '')}")
            print(f"  {story.get('summary', '')}")
            print(f"  {story.get('source', '')}  →  {story.get('url', '')}")
    print()


CATEGORIES = [
    ("1", "Technology",          "AI, software, hardware, cybersecurity, startups"),
    ("2", "Business & Finance",  "markets, earnings, M&A, economy, crypto"),
    ("3", "Science & Research",  "academic papers, discoveries, climate, space"),
    ("4", "Health & Medicine",   "biotech, pharma, public health, medical AI"),
    ("5", "Politics & Policy",   "government, regulation, elections, geopolitics"),
    ("6", "Robotics & EVs",      "autonomous vehicles, drones, industrial robots"),
    ("7", "Custom",              "enter your own topic"),
]


def _prompt_category() -> str:
    """Show a numbered category menu and return the chosen topic string."""
    print()
    print("┌─────────────────────────────────────────────────┐")
    print("│          AI News Bot — Topic Selection          │")
    print("├────┬────────────────────────┬───────────────────┤")
    for num, name, desc in CATEGORIES:
        print(f"│ {num:>2} │ {name:<22} │ {desc:<17} │")
    print("└────┴────────────────────────┴───────────────────┘")
    print()

    while True:
        try:
            choice = input("Select a category [1-7]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            sys.exit(130)

        match = next((c for c in CATEGORIES if c[0] == choice), None)
        if match is None:
            print(f"  Please enter a number between 1 and {len(CATEGORIES)}.")
            continue

        num, name, _ = match
        if num == "7":
            try:
                custom = input("Enter your topic: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nCancelled.")
                sys.exit(130)
            if not custom:
                print("  Topic cannot be empty.")
                continue
            return custom

        return name


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Search for news on any topic and publish to Telegram."
    )
    parser.add_argument(
        "topic",
        nargs="*",
        help="Topic to search for (e.g. 'renewable energy'). Prompted if omitted.",
    )
    parser.add_argument(
        "--max-sources",
        type=int,
        default=20,
        help="Maximum number of RSS feeds the agent may fetch (default: 20).",
    )
    parser.add_argument(
        "--no-telegram",
        action="store_true",
        help="Print digest to stdout instead of sending to Telegram.",
    )
    args = parser.parse_args()

    # ── Resolve topic ─────────────────────────────────────────────────────────
    if args.topic:
        topic = " ".join(args.topic).strip()
    else:
        topic = _prompt_category()

    if not topic:
        print("Error: topic cannot be empty.", file=sys.stderr)
        return 1

    # ── Setup ─────────────────────────────────────────────────────────────────
    config = Config()
    logger = setup_logger("topic_search", level=config.log_level, log_format=config.log_format)
    today = datetime.now().strftime("%Y-%m-%d")

    print(f"\nSearching for news about: {topic!r}")
    print(f"Using provider: {config.llm_provider}")
    print(f"Max sources: {args.max_sources}")
    print()

    # ── Step 1: Agentic fetch ─────────────────────────────────────────────────
    fetcher = NewsFetcher()
    agent = TopicNewsAgent(
        provider_name=config.llm_provider,
        api_key=config.llm_api_key,
        model=config.llm_model,
        fetcher=fetcher,
    )

    print("Agent is selecting and fetching relevant sources...")
    articles = agent.collect(topic, max_sources=args.max_sources)

    if not articles:
        print("No articles found for the given topic.", file=sys.stderr)
        return 1

    # ── Step 2: Dedup within this batch ──────────────────────────────────────
    articles = deduplicate_news(articles)
    print(f"Collected {len(articles)} unique articles.\n")

    # ── Step 3: Summarise → JSON digest ──────────────────────────────────────
    summarizer = Summarizer(
        provider_name=config.llm_provider,
        api_key=config.llm_api_key,
        model=config.llm_model,
    )

    print("Generating digest...")
    digest = summarizer.summarize(articles, topics=[topic], today=today)
    print(f"Headline: {digest.get('headline', '')}\n")

    # ── Step 4: Deliver ───────────────────────────────────────────────────────
    if args.no_telegram:
        _print_digest(digest)
        return 0

    telegram = TelegramNotifier()
    if not telegram.bot_token or not telegram.chat_id:
        print(
            "Telegram not configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set).\n"
            "Printing digest instead:\n"
        )
        _print_digest(digest)
        return 0

    print("Sending digest to Telegram...")
    if telegram.send_digest_summary(digest):
        print("Sent successfully!")
        return 0
    else:
        print("Telegram send failed. Printing digest instead:")
        _print_digest(digest)
        return 1


if __name__ == "__main__":
    sys.exit(main())
