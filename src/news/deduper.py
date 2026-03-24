"""News deduplication utility for AI News Bot."""
import json
import os
from difflib import SequenceMatcher
from typing import Dict, List, Set

# Path to the persistent seen-URLs log at the repo root
_SEEN_URLS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "seen_urls.json")


def _normalize_text(text: str) -> str:
    """Normalize text for similarity comparison."""
    if not isinstance(text, str):
        return ""
    return text.strip().lower()


def load_seen_urls(path: str = _SEEN_URLS_PATH) -> Set[str]:
    """Load previously seen URLs from the JSON log file."""
    try:
        with open(path, "r") as f:
            data = json.load(f)
            return set(data) if isinstance(data, list) else set()
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen_urls(urls: Set[str], path: str = _SEEN_URLS_PATH) -> None:
    """Persist the seen-URLs set back to the JSON log file."""
    with open(path, "w") as f:
        json.dump(sorted(urls), f, indent=2)


def deduplicate_news(
    news_items: List[Dict[str, str]],
    similarity_threshold: float = 0.85,
) -> List[Dict[str, str]]:
    """
    Deduplicate a list of news items within a single batch.

    Removes items that share an exact URL or whose titles are highly similar
    (ratio >= similarity_threshold). When two similar titles are found, the
    item with the longer description is kept.
    """
    unique_items: List[Dict[str, str]] = []
    seen_links: Set[str] = set()

    for item in news_items:
        link = (item.get("link") or "").strip()
        title = _normalize_text(item.get("title", ""))

        # Skip completely empty items
        if not title and not link:
            continue

        # Exact URL duplicate
        if link and link in seen_links:
            continue

        # Title-similarity duplicate check
        is_duplicate = False
        for existing in unique_items:
            existing_title = _normalize_text(existing.get("title", ""))
            if title and existing_title:
                ratio = SequenceMatcher(None, title, existing_title).ratio()
                if ratio >= similarity_threshold:
                    is_duplicate = True
                    # Keep whichever version has the richer description
                    cur_desc = len((item.get("description") or "").strip())
                    existing_desc = len((existing.get("description") or "").strip())
                    if cur_desc > existing_desc:
                        unique_items.remove(existing)
                        unique_items.append(item)
                        if link:
                            seen_links.add(link)
                    break

        if not is_duplicate:
            unique_items.append(item)
            if link:
                seen_links.add(link)

    return unique_items


def deduplicate_news_data(
    news_data: Dict[str, List[Dict[str, str]]],
    similarity_threshold: float = 0.85,
    seen_urls_path: str = _SEEN_URLS_PATH,
) -> Dict[str, List[Dict[str, str]]]:
    """
    Deduplicate both international and domestic news sections.

    Cross-run deduplication: articles whose URLs appear in seen_urls.json are
    dropped before in-session similarity deduplication runs. All surviving
    article URLs are then appended to seen_urls.json so future runs skip them.
    """
    seen_urls = load_seen_urls(seen_urls_path)

    def _filter_and_dedup(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
        # Drop articles already covered in a previous run
        fresh = [
            item for item in items
            if (item.get("link") or "").strip() not in seen_urls
        ]
        return deduplicate_news(fresh, similarity_threshold)

    result = {
        "international": _filter_and_dedup(news_data.get("international", [])),
        "domestic": _filter_and_dedup(news_data.get("domestic", [])),
    }

    # Persist all new URLs so the next run skips them
    new_urls = {
        (item.get("link") or "").strip()
        for section in result.values()
        for item in section
        if (item.get("link") or "").strip()
    }
    seen_urls.update(new_urls)
    save_seen_urls(seen_urls, seen_urls_path)

    return result
