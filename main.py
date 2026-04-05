#!/usr/bin/env python3
"""
AI News Bot - Main Application

Pipeline: Fetch RSS → Deduplicate (seen_urls.json) → Summarize (JSON) → Deliver
"""
import os
import sys
from datetime import datetime
from src.config import Config
from src.db import Database
from src.logger import setup_logger
from src.news.fetcher import NewsFetcher
from src.news.summarizer import Summarizer
from src.news.deduper import deduplicate_news_data
from src.notifiers import (
    EmailNotifier,
    WebhookNotifier,
    SlackNotifier,
    TelegramNotifier,
    DiscordNotifier,
)


# ── Channel routing configuration ─────────────────────────────────────────────
# Each entry defines a specialty Telegram channel. The channel receives a filtered
# digest containing only categories whose name matches any of the channel's keywords.
_CHANNEL_ROUTING = [
    {
        "key": "medical",
        "title": "Medical News",
        "token_env": "TELEGRAM_MEDICAL_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_MEDICAL_CHAT_ID",
        "keywords": {
            "cardiology", "pulmonology", "nephrology", "pediatrics", "endocrinology",
            "psychiatry", "oncology", "health", "medicine", "medical", "biomedical",
            "healthcare", "clinical", "kidney", "heart", "lung", "cardiac", "pediatric",
            "children", "diabetes", "thyroid", "mental health", "psychiatric", "metabolic",
            "cancer", "tumor", "ai in medicine", "medical ai",
        },
    },
    {
        "key": "pharma",
        "title": "Pharma News",
        "token_env": "TELEGRAM_PHARMA_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_PHARMA_CHAT_ID",
        "keywords": {
            "pharmaceutical", "pharma", "drug discovery", "drug approval", "fda",
            "clinical trial", "biotech", "biopharma", "therapeutics", "medication",
            "drug pipeline", "drug development", "biologics", "vaccine",
        },
    },
    {
        "key": "genome",
        "title": "Genome Research",
        "token_env": "TELEGRAM_GENOME_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_GENOME_CHAT_ID",
        "keywords": {
            "genomics", "genome", "genomic", "bioinformatics", "sequencing",
            "crispr", "gene editing", "dna sequencing", "transcriptomics",
            "proteomics", "whole genome", "metagenomics",
        },
    },
    {
        "key": "genetics",
        "title": "Genetics Research",
        "token_env": "TELEGRAM_GENETICS_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_GENETICS_CHAT_ID",
        "keywords": {
            "genetics", "genetic", "gene therapy", "hereditary", "mutation",
            "genetic disorder", "gene expression", "chromosome",
            "heredity", "genetic testing", "genetic engineering",
        },
    },
    {
        "key": "energy",
        "title": "Energy News",
        "token_env": "TELEGRAM_ENERGY_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_ENERGY_CHAT_ID",
        "keywords": {
            "energy", "solar", "wind power", "nuclear", "renewable",
            "battery", "power grid", "clean energy", "hydrogen", "energy storage",
            "fossil fuel", "electricity", "grid",
        },
    },
    {
        "key": "rare_earth",
        "title": "Rare Earth News",
        "token_env": "TELEGRAM_RARE_EARTH_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_RARE_EARTH_CHAT_ID",
        "keywords": {
            "rare earth", "lithium", "cobalt", "mining", "critical minerals",
            "rare metals", "mineral supply", "tungsten", "neodymium", "palladium",
            "copper mining", "battery materials",
        },
    },
    {
        "key": "psychology",
        "title": "Psychology News",
        "token_env": "TELEGRAM_PSYCHOLOGY_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_PSYCHOLOGY_CHAT_ID",
        "keywords": {
            "psychology", "psychological", "behavioral science", "behaviour", "behavior",
            "neuroscience", "cognitive science", "cognition", "mental health research",
            "psychotherapy", "psychologist", "emotional intelligence", "social psychology",
            "developmental psychology", "neuropsychology", "mindfulness", "emotional maturity", "emotional immaturity"
        },
    },
]


def _filter_digest(digest: dict, keywords: set) -> dict | None:
    """Return a copy of *digest* with only categories whose name matches any keyword, or None."""
    lower_kws = {kw.lower() for kw in keywords}
    matching = [
        c for c in digest.get("categories", [])
        if any(kw in c.get("name", "").lower() for kw in lower_kws)
    ]
    if not matching:
        return None
    return {**digest, "categories": matching}


def _digest_to_text(digest: dict) -> str:
    """Convert a JSON digest to plain markdown text for webhook/slack notifiers."""
    lines = [
        f"# AI News Digest — {digest.get('date', '')}",
        "",
        f"_{digest.get('headline', '')}_",
        "",
    ]
    for cat in digest.get("categories", []):
        lines.append(f"## {cat.get('name', '')}")
        for story in cat.get("stories", []):
            lines.append(f"### {story.get('title', '')}")
            lines.append(story.get("summary", ""))
            lines.append(f"[{story.get('source', '')}]({story.get('url', '#')})")
            lines.append("")
    return "\n".join(lines)


def main():
    """Main application entry point."""
    try:
        config = Config()
        logger = setup_logger(
            "ai_news_bot",
            level=config.log_level,
            log_format=config.log_format,
        )

        today = datetime.now().strftime("%Y-%m-%d")
        languages = config.ai_response_languages

        logger.info("=" * 60)
        logger.info("AI News Bot Starting")
        logger.info(f"Date: {today}")
        logger.info(f"LLM Provider: {config.llm_provider}")
        if config.llm_model:
            logger.info(f"LLM Model: {config.llm_model}")
        logger.info(f"Languages: {', '.join(languages)}")
        logger.info("=" * 60)

        fetcher = NewsFetcher()
        summarizer = Summarizer(
            provider_name=config.llm_provider,
            api_key=config.llm_api_key,
            model=config.llm_model,
        )

        notification_methods = config.notification_methods
        logger.info(f"Enabled notification methods: {notification_methods}")

        overall_results = {"sent": [], "failed": []}

        for language in languages:
            logger.info("=" * 60)
            logger.info(f"Processing language: {language.upper()}")
            logger.info("=" * 60)

            try:
                # ── 1. Fetch ──────────────────────────────────────────────
                logger.info("Fetching news from RSS feeds...")
                news_data = fetcher.fetch_recent_news(
                    language=language,
                    max_items_per_source=config.max_items_per_source,
                )

                # ── 2. Deduplicate (persists seen_urls.json) ──────────────
                logger.info("Deduplicating articles...")
                deduped = deduplicate_news_data(news_data)
                articles = deduped["international"] + deduped["domestic"]

                if not articles:
                    logger.warning(
                        f"No new articles for {language.upper()} after deduplication — skipping"
                    )
                    continue

                logger.info(f"{len(articles)} unique articles after deduplication")

                # ── 3. Summarize → JSON digest ────────────────────────────
                logger.info("Generating JSON digest via LLM...")
                digest = summarizer.summarize(
                    articles,
                    topics=config.news_topics,
                    today=today,
                    language=language,
                )
                logger.info(
                    f"Digest generated: {len(digest.get('categories', []))} categories, "
                    f"headline: {digest.get('headline', '')[:80]}"
                )

                # ── 4. Deliver ────────────────────────────────────────────
                lang_results = {"sent": [], "failed": []}

                if "email" in notification_methods:
                    logger.info(f"Sending HTML email digest ({language.upper()})...")
                    notifier = EmailNotifier()
                    if notifier.send_digest(digest, language=language):
                        lang_results["sent"].append("email")
                    else:
                        lang_results["failed"].append("email")

                if "telegram" in notification_methods:
                    logger.info(f"Sending Telegram summary ({language.upper()})...")
                    notifier = TelegramNotifier()
                    if notifier.send_digest_summary(digest, language=language):
                        lang_results["sent"].append("telegram")
                    else:
                        lang_results["failed"].append("telegram")

                    db = Database()
                    ai_bot_token = os.getenv("TELEGRAM_AI_BOT_TOKEN", "").strip()

                    # Deliver AI News to individual subscribers
                    for sub_chat_id in db.get_subscribers("ai"):
                        TelegramNotifier(
                            bot_token=ai_bot_token or None,
                            chat_id=sub_chat_id,
                        ).send_digest_summary(digest, language=language, channel_title="AI News")

                    # Route filtered digest to each configured specialty channel
                    for ch in _CHANNEL_ROUTING:
                        chat_id = os.getenv(ch["chat_id_env"], "").strip()
                        bot_token = os.getenv(ch["token_env"], "").strip()
                        ch_digest = _filter_digest(digest, ch["keywords"])
                        if not ch_digest:
                            continue

                        # Broadcast to the channel (if configured)
                        if chat_id:
                            logger.info(f"Sending {ch['title']} digest to channel...")
                            TelegramNotifier(
                                bot_token=bot_token or None,
                                chat_id=chat_id,
                            ).send_digest_summary(ch_digest, language=language, channel_title=ch["title"])

                        # Deliver to individual subscribers
                        for sub_chat_id in db.get_subscribers(ch["key"]):
                            TelegramNotifier(
                                bot_token=ai_bot_token or None,
                                chat_id=sub_chat_id,
                            ).send_digest_summary(ch_digest, language=language, channel_title=ch["title"])

                if "discord" in notification_methods:
                    logger.info(f"Sending Discord summary ({language.upper()})...")
                    notifier = DiscordNotifier()
                    if notifier.send_digest_summary(digest, language=language):
                        lang_results["sent"].append("discord")
                    else:
                        lang_results["failed"].append("discord")

                if "webhook" in notification_methods:
                    logger.info(f"Sending webhook ({language.upper()})...")
                    notifier = WebhookNotifier()
                    if notifier.send(_digest_to_text(digest), language=language):
                        lang_results["sent"].append("webhook")
                    else:
                        lang_results["failed"].append("webhook")

                if "slack" in notification_methods:
                    logger.info(f"Sending Slack notification ({language.upper()})...")
                    notifier = SlackNotifier()
                    if notifier.send(_digest_to_text(digest), language=language):
                        lang_results["sent"].append("slack")
                    else:
                        lang_results["failed"].append("slack")

                for method in lang_results["sent"]:
                    key = f"{method} ({language.upper()})"
                    if key not in overall_results["sent"]:
                        overall_results["sent"].append(key)

                for method in lang_results["failed"]:
                    key = f"{method} ({language.upper()})"
                    if key not in overall_results["failed"]:
                        overall_results["failed"].append(key)

                logger.info(f"Language {language.upper()} completed")

            except Exception as lang_error:
                logger.error(
                    f"Error processing {language.upper()}: {lang_error}", exc_info=True
                )
                for method in notification_methods:
                    key = f"{method} ({language.upper()})"
                    if key not in overall_results["failed"]:
                        overall_results["failed"].append(key)

        # ── Final summary ─────────────────────────────────────────────────
        logger.info("=" * 60)
        logger.info("AI News Bot Completed")
        logger.info(f"Processed {len(languages)} language(s): {', '.join(l.upper() for l in languages)}")
        logger.info(
            f"Sent: {', '.join(overall_results['sent']) if overall_results['sent'] else 'None'}"
        )
        if overall_results["failed"]:
            logger.warning(f"Failed: {', '.join(overall_results['failed'])}")
        logger.info("=" * 60)

        if notification_methods and not overall_results["sent"]:
            logger.error("All notifications failed")
            return 1
        return 0

    except KeyboardInterrupt:
        print("Interrupted")
        return 130
    except Exception as e:
        print(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
