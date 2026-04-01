#!/usr/bin/env python3
"""
AI News Bot - Main Application

Pipeline: Fetch RSS → Deduplicate (seen_urls.json) → Summarize (JSON) → Deliver
"""
import os
import sys
from datetime import datetime
from src.config import Config
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


_MEDICAL_KEYWORDS = {
    "cardiology", "pulmonology", "nephrology", "pediatrics", "endocrinology",
    "psychiatry", "oncology", "health", "medicine", "medical", "biomedical",
    "healthcare", "clinical", "pharma", "biotech", "kidney", "heart", "lung",
    "cardiac", "pediatric", "children", "diabetes", "thyroid", "mental health",
    "psychiatric", "metabolic", "cancer", "tumor", "ai in medicine", "medical ai",
}


def _is_medical_category(name: str) -> bool:
    """Return True if a category name contains any medical keyword."""
    lower = name.lower()
    return any(kw in lower for kw in _MEDICAL_KEYWORDS)


def _medical_digest(digest: dict) -> dict | None:
    """Return a copy of *digest* containing only medical categories, or None if none found."""
    medical_cats = [c for c in digest.get("categories", []) if _is_medical_category(c.get("name", ""))]
    if not medical_cats:
        return None
    return {**digest, "categories": medical_cats}


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

                    # Send medical categories to Medical News Channel if configured
                    medical_chat_id = os.getenv("TELEGRAM_MEDICAL_CHAT_ID", "").strip()
                    medical_bot_token = os.getenv("TELEGRAM_MEDICAL_BOT_TOKEN", "").strip()
                    if medical_chat_id:
                        med_digest = _medical_digest(digest)
                        if med_digest:
                            logger.info("Sending medical digest to Medical News Channel...")
                            medical_notifier = TelegramNotifier(
                                bot_token=medical_bot_token or None,
                                chat_id=medical_chat_id,
                            )
                            medical_notifier.send_digest_summary(med_digest, language=language)

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
