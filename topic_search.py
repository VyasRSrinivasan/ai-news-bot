#!/usr/bin/env python3
"""
AI News Bot — Interactive Topic Search

Usage:
  python topic_search.py                   # prompts for news type, then topic
  python topic_search.py "electric vehicles"
  python topic_search.py technology --no-telegram
  python topic_search.py --medical         # go straight to Medical News Channel
"""
import argparse
import os
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
    ("7", "All Categories",      "all topics combined"),
    ("8", "Custom",              "enter your own topic"),
]

MEDICAL_CATEGORIES = [
    ("1",  "Cardiology",      "heart disease, cardiac, arrhythmia"),
    ("2",  "Pulmonology",     "lung disease, COPD, asthma, respiratory"),
    ("3",  "Nephrology",      "kidney disease, dialysis, renal"),
    ("4",  "Pediatrics",      "child health, neonatal, vaccines"),
    ("5",  "Endocrinology",   "thyroid, hormones, metabolic"),
    ("6",  "Diabetes",        "diabetes, insulin, glucose, T1D, T2D"),
    ("7",  "Psychiatry",      "mental health, depression, anxiety"),
    ("8",  "Oncology",        "cancer, immunotherapy, chemotherapy"),
    ("9",  "AI in Medicine",  "medical AI, diagnostics, imaging"),
    ("10", "All Specialties", "all of the above"),
]

# Maps each medical category name to its focused search topic
# ── Specialty channel configuration (non-AI, non-Medical) ─────────────────────
_SPECIALTY_CHANNELS = {
    "pharma": {
        "title": "Pharmaceutical News",
        "token_env": "TELEGRAM_PHARMA_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_PHARMA_CHAT_ID",
        "feeds_category": "Pharmaceutical",
        "topic": "pharmaceutical drug discovery FDA clinical trial biotech biopharma drug approval",
    },
    "genome": {
        "title": "Genome Research News",
        "token_env": "TELEGRAM_GENOME_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_GENOME_CHAT_ID",
        "feeds_category": "Genome Research",
        "topic": "genomics genome sequencing CRISPR gene editing bioinformatics",
    },
    "genetics": {
        "title": "Genetics Research News",
        "token_env": "TELEGRAM_GENETICS_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_GENETICS_CHAT_ID",
        "feeds_category": "Genetics Research",
        "topic": "genetics gene therapy genetic disorder hereditary mutation chromosome",
    },
    "energy": {
        "title": "Energy News",
        "token_env": "TELEGRAM_ENERGY_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_ENERGY_CHAT_ID",
        "feeds_category": "Energy",
        "topic": "energy solar wind nuclear renewable battery grid clean energy hydrogen",
    },
    "rare_earth": {
        "title": "Rare Earth News",
        "token_env": "TELEGRAM_RARE_EARTH_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_RARE_EARTH_CHAT_ID",
        "feeds_category": "Rare Earth",
        "topic": "rare earth minerals lithium cobalt mining critical minerals supply chain",
    },
    "psychology": {
        "title": "Psychology News",
        "token_env": "TELEGRAM_PSYCHOLOGY_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_PSYCHOLOGY_CHAT_ID",
        "feeds_category": "Psychology",
        "topic": "psychology behavioral science neuroscience cognitive science mental health research",
    },
    "sports": {
        "title": "Sports News",
        "token_env": "TELEGRAM_SPORTS_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_SPORTS_CHAT_ID",
        "feeds_category": "Sports",
        "topic": "sports football american football basketball soccer baseball cricket tennis NFL NBA MLB IPL FIFA Premier League Olympics championship",
    },
}

_MEDICAL_TOPIC_MAP = {
    "Cardiology":      "cardiology heart disease cardiac",
    "Pulmonology":     "pulmonology lung disease respiratory COPD asthma",
    "Nephrology":      "nephrology kidney disease renal dialysis",
    "Pediatrics":      "pediatrics child health pediatric medicine",
    "Endocrinology":   "endocrinology thyroid metabolic disease hormones",
    "Diabetes":        "diabetes insulin resistance glucose type 1 diabetes type 2 diabetes T1D T2D",
    "Psychiatry":      "psychiatry mental health depression anxiety",
    "Oncology":        "oncology cancer treatment immunotherapy chemotherapy",
    "AI in Medicine":  "artificial intelligence medicine healthcare AI diagnostics medical imaging",
    "All Specialties": "cardiology pulmonology nephrology pediatrics endocrinology diabetes psychiatry oncology AI medicine",
}


# ── All-channels list (used by --all) ─────────────────────────────────────────
_ALL_CHANNELS = [
    {
        "title": "AI News",
        "token_env": "TELEGRAM_AI_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_AI_CHAT_ID",
        "feeds_category": "All Categories",
        "topic": "AI technology software machine learning",
    },
    {
        "title": "Medical News",
        "token_env": "TELEGRAM_MEDICAL_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_MEDICAL_CHAT_ID",
        "feeds_category": "Health & Medicine",
        "topic": "cardiology pulmonology nephrology pediatrics endocrinology diabetes psychiatry oncology AI medicine",
    },
    *_SPECIALTY_CHANNELS.values(),
]


def _run_single_channel(ch: dict, config, max_sources: int, no_telegram: bool, today: str) -> bool:
    """Run the full fetch→summarize→deliver pipeline for one channel. Returns True on success."""
    print(f"\n{'─' * 60}")
    print(f"  Channel: {ch['title']}")
    print(f"  Topic:   {ch['topic']}")
    print(f"{'─' * 60}")

    fetcher = NewsFetcher()
    feeds = fetcher.get_feeds_for_category(ch["feeds_category"])
    if feeds:
        fetcher.rss_feeds = feeds
        print(f"  Using {len(feeds)} curated sources for '{ch['feeds_category']}'.")

    agent = TopicNewsAgent(
        provider_name=config.llm_provider,
        api_key=config.llm_api_key,
        model=config.llm_model,
        fetcher=fetcher,
    )

    print("  Fetching sources...")
    articles = agent.collect(ch["topic"], max_sources=max_sources)
    if not articles:
        print(f"  No articles found — skipping {ch['title']}.", file=sys.stderr)
        return False

    articles = deduplicate_news(articles)
    print(f"  {len(articles)} unique articles collected.")

    summarizer = Summarizer(
        provider_name=config.llm_provider,
        api_key=config.llm_api_key,
        model=config.llm_model,
    )
    digest = summarizer.summarize(articles, topics=[ch["topic"]], today=today)
    print(f"  Headline: {digest.get('headline', '')}")

    if no_telegram:
        _print_digest(digest)
        return True

    chat_id = os.getenv(ch["chat_id_env"], "").strip()
    bot_token = os.getenv(ch["token_env"], "").strip()

    if not chat_id:
        print(f"  {ch['chat_id_env']} not set — skipping Telegram send.")
        return False

    telegram = TelegramNotifier(bot_token=bot_token or None, chat_id=chat_id)
    if telegram.send_digest_summary(digest, channel_title=ch["title"]):
        print(f"  Sent to {ch['title']} Channel.")
        return True
    else:
        print(f"  Failed to send to {ch['title']} Channel.")
        return False


def _prompt_medical_category() -> str:
    """Show the medical specialty menu and return the chosen topic string."""
    print()
    print("┌─────────────────────────────────────────────────┐")
    print("│       Medical News — Specialty Selection        │")
    print("├────┬────────────────────────┬───────────────────┤")
    for num, name, desc in MEDICAL_CATEGORIES:
        print(f"│ {num:>2} │ {name:<22} │ {desc:<17} │")
    print("└────┴────────────────────────┴───────────────────┘")
    print()

    while True:
        try:
            choice = input(f"Select a specialty [1-{len(MEDICAL_CATEGORIES)}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            sys.exit(130)

        match = next((c for c in MEDICAL_CATEGORIES if c[0] == choice), None)
        if match is None:
            print(f"  Please enter a number between 1 and {len(MEDICAL_CATEGORIES)}.")
            continue

        _, name, _ = match
        return _MEDICAL_TOPIC_MAP[name]


def _prompt_news_type() -> str:
    """Show channel selection menu. Returns 'ai', 'medical', or a key from _SPECIALTY_CHANNELS."""
    print()
    print("┌─────────────────────────────────────────────────┐")
    print("│           AI News Bot — News Type               │")
    print("├────┬────────────────────────────────────────────┤")
    print("│  1 │ AI & Technology News                       │")
    print("│  2 │ Medical News                               │")
    print("│    │ Cardiology · Pulmonology · Nephrology      │")
    print("│    │ Pediatrics · Endocrinology · Diabetes      │")
    print("│    │ Psychiatry · Oncology · AI in Medicine     │")
    print("│  3 │ Pharmaceutical News                        │")
    print("│    │ Pharma · Biotech · FDA · Clinical Trials   │")
    print("│  4 │ Genome Research News                       │")
    print("│    │ Genomics · CRISPR · Sequencing             │")
    print("│  5 │ Genetics Research News                     │")
    print("│    │ Gene Therapy · Genetic Disorders           │")
    print("│  6 │ Energy News                                │")
    print("│    │ Solar · Wind · Nuclear · Battery · Grid    │")
    print("│  7 │ Rare Earth News                            │")
    print("│    │ Lithium · Cobalt · Mining · Critical Min.  │")
    print("│  8 │ Psychology News                            │")
    print("│    │ Behavioral Science · Neuroscience          │")
    print("│  9 │ Sports News                                │")
    print("│    │ Football · Basketball · Soccer · Baseball  │")
    print("│    │ Cricket · Tennis · NFL · NBA · IPL         │")
    print("└────┴────────────────────────────────────────────┘")
    print()

    _map = {
        "1": "ai", "2": "medical", "3": "pharma", "4": "genome",
        "5": "genetics", "6": "energy", "7": "rare_earth", "8": "psychology",
        "9": "sports",
    }
    while True:
        try:
            choice = input("Select news type [1-9]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            sys.exit(130)
        if choice in _map:
            return _map[choice]
        print("  Please enter a number between 1 and 9.")


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
            choice = input("Select a category [1-8]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            sys.exit(130)

        match = next((c for c in CATEGORIES if c[0] == choice), None)
        if match is None:
            print(f"  Please enter a number between 1 and {len(CATEGORIES)}.")
            continue

        num, name, _ = match
        if num == "8":
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
    parser.add_argument(
        "--medical",
        action="store_true",
        help="Search medical news and send to Medical News Channel. Prompts for specialty selection.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Update all channels at once (AI, Medical, Pharma, Genome, Genetics, Energy, Rare Earth, Psychology).",
    )
    args = parser.parse_args()

    # ── --all: run every channel in sequence ──────────────────────────────────
    if args.all:
        config = Config()
        setup_logger("topic_search", level=config.log_level, log_format=config.log_format)
        today = datetime.now().strftime("%Y-%m-%d")
        print(f"\nUpdating all {len(_ALL_CHANNELS)} channels...")
        results = {"ok": [], "failed": []}
        for ch in _ALL_CHANNELS:
            ok = _run_single_channel(ch, config, args.max_sources, args.no_telegram, today)
            (results["ok"] if ok else results["failed"]).append(ch["title"])
        print(f"\n{'=' * 60}")
        print(f"  Done.  Sent: {len(results['ok'])}  Failed: {len(results['failed'])}")
        if results["ok"]:
            print(f"  ✓ {', '.join(results['ok'])}")
        if results["failed"]:
            print(f"  ✗ {', '.join(results['failed'])}")
        print(f"{'=' * 60}\n")
        return 0 if not results["failed"] else 1

    # ── Resolve topic & channel ────────────────────────────────────────────────
    preset_category: str | None = None
    is_medical = False
    specialty_ch: dict | None = None

    if args.topic:
        topic = " ".join(args.topic).strip()
        matched = next((c for c in CATEGORIES if c[1].lower() == topic.lower()), None)
        if matched and matched[0] != "7":
            preset_category = matched[1]
            topic = matched[1]
        if preset_category == "Health & Medicine" or args.medical:
            is_medical = True
    elif args.medical:
        is_medical = True
        preset_category = "Health & Medicine"
        topic = "cardiology, pulmonology, nephrology, pediatrics"
    else:
        # Interactive: ask news type first, then category/specialty
        news_type = _prompt_news_type()
        if news_type == "medical":
            is_medical = True
            preset_category = "Health & Medicine"
            topic = _prompt_medical_category()
        elif news_type == "ai":
            result = _prompt_category()
            matched = next((c for c in CATEGORIES if c[1] == result and c[0] != "7"), None)
            if matched:
                preset_category = matched[1]
            topic = result
        else:
            specialty_ch = _SPECIALTY_CHANNELS[news_type]
            preset_category = specialty_ch["feeds_category"]
            topic = specialty_ch["topic"]

    if not topic:
        print("Error: topic cannot be empty.", file=sys.stderr)
        return 1

    # ── Setup ─────────────────────────────────────────────────────────────────
    config = Config()
    setup_logger("topic_search", level=config.log_level, log_format=config.log_format)
    today = datetime.now().strftime("%Y-%m-%d")

    print(f"\nSearching for news about: {topic!r}")
    print(f"Using provider: {config.llm_provider}")
    print(f"Max sources: {args.max_sources}")
    print()

    # ── Step 1: Agentic fetch ─────────────────────────────────────────────────
    fetcher = NewsFetcher()

    # Restrict feeds to those curated for the selected preset category
    if preset_category:
        category_feeds = fetcher.get_feeds_for_category(preset_category)
        if category_feeds:
            fetcher.rss_feeds = category_feeds
            print(f"Using {len(category_feeds)} curated sources for '{preset_category}'.")

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

    # Route to the correct Telegram channel
    if is_medical:
        ch_token_env, ch_chat_id_env = "TELEGRAM_MEDICAL_BOT_TOKEN", "TELEGRAM_MEDICAL_CHAT_ID"
        channel_title = "Medical News"
    elif specialty_ch:
        ch_token_env, ch_chat_id_env = specialty_ch["token_env"], specialty_ch["chat_id_env"]
        channel_title = specialty_ch["title"]
    else:
        ch_token_env, ch_chat_id_env = "TELEGRAM_AI_BOT_TOKEN", "TELEGRAM_AI_CHAT_ID"
        channel_title = "AI News"

    ch_chat_id = os.getenv(ch_chat_id_env, "").strip()
    ch_bot_token = os.getenv(ch_token_env, "").strip()

    if ch_chat_id:
        telegram = TelegramNotifier(bot_token=ch_bot_token or None, chat_id=ch_chat_id)
        print(f"Routing to {channel_title} Channel.")
    else:
        telegram = TelegramNotifier()
        print(f"Note: {ch_chat_id_env} not set — falling back to AI News Channel.")

    if not telegram.bot_token or not telegram.chat_id:
        print(
            f"Telegram not configured ({ch_token_env} / {ch_chat_id_env} not set).\n"
            "Printing digest instead:\n"
        )
        _print_digest(digest)
        return 0

    print("Sending digest to Telegram...")
    if telegram.send_digest_summary(digest, channel_title=channel_title):
        print("Sent successfully!")
        return 0
    else:
        print("Telegram send failed. Printing digest instead:")
        _print_digest(digest)
        return 1


if __name__ == "__main__":
    sys.exit(main())
