"""
Agentic news collector.

Uses LLM tool-calling to dynamically select and fetch RSS feeds based on a
user-provided topic.  Falls back to keyword filtering for providers that do
not support tool use.
"""
import json
from typing import Any, Dict, List, Optional

from ..llm_providers import BaseLLMProvider, get_llm_provider
from ..logger import setup_logger
from .fetcher import NewsFetcher


logger = setup_logger(__name__)

# ── Tool definition (Anthropic / OpenAI schema) ──────────────────────────────

_FETCH_RSS_TOOL: Dict[str, Any] = {
    "name": "fetch_rss_feed",
    "description": (
        "Fetch news articles from a single RSS feed URL. "
        "Call this once per source you want to retrieve. "
        "Returns the number of articles fetched and the source name."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The RSS feed URL to fetch.",
            },
            "max_items": {
                "type": "integer",
                "description": "Maximum articles to return from this feed (default 8).",
                "default": 8,
            },
        },
        "required": ["url"],
    },
}


def _build_source_catalogue(fetcher: NewsFetcher) -> str:
    """Return a formatted catalogue of every available RSS feed."""
    lines = ["Available RSS sources — name: url"]
    for name, url in fetcher.rss_feeds.items():
        lines.append(f"  • {name}: {url}")
    return "\n".join(lines)


class TopicNewsAgent:
    """
    Agentic news collector driven by LLM tool-calling.

    Workflow (Claude path):
      1. Present the LLM with the full RSS source catalogue.
      2. The LLM calls `fetch_rss_feed` for each source it deems relevant.
      3. Articles are collected as a side-effect of each tool call.
      4. The agent stops once the LLM signals it is done or max_sources is reached.

    Fallback (non-Claude or on error):
      Keyword-match the topic against article titles/descriptions across all feeds.
    """

    def __init__(
        self,
        provider: Optional[BaseLLMProvider] = None,
        provider_name: str = "claude",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        fetcher: Optional[NewsFetcher] = None,
    ):
        if provider is not None:
            self.provider = provider
        else:
            self.provider = get_llm_provider(
                provider_name=provider_name,
                api_key=api_key,
                model=model,
            )
        self.fetcher = fetcher or NewsFetcher()
        logger.info(
            f"TopicNewsAgent initialised with {self.provider.provider_name} "
            f"(model: {self.provider.model})"
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def collect(self, topic: str, max_sources: int = 20) -> List[Dict[str, str]]:
        """
        Collect news articles relevant to *topic* from up to *max_sources* feeds.

        Args:
            topic: User-provided topic string (e.g. "renewable energy", "AI policy").
            max_sources: Maximum number of RSS feeds the agent may fetch.

        Returns:
            Flat list of article dicts with keys: title, source, link, description.
        """
        if self.provider.provider_name == "claude":
            return self._agentic_collect(topic, max_sources)
        return self._fallback_collect(topic, max_sources)

    # ── Agentic path (Claude tool-use) ───────────────────────────────────────

    def _agentic_collect(self, topic: str, max_sources: int) -> List[Dict[str, str]]:
        collected: List[Dict[str, str]] = []
        url_to_name = {url: name for name, url in self.fetcher.rss_feeds.items()}

        catalogue = _build_source_catalogue(self.fetcher)
        prompt = f"""\
You are a news research agent. Gather recent news articles on the topic: "{topic}".

{catalogue}

Instructions:
1. Review the source catalogue above.
2. Identify every source that publishes content relevant to "{topic}".
3. Call fetch_rss_feed for each relevant source (up to {max_sources} sources).
4. When you have fetched all relevant sources, reply with exactly: DONE

Do not summarise or comment — just call the tool for each relevant source, then say DONE."""

        def tool_handler(tool_name: str, tool_input: Dict, _tool_id: str) -> str:
            if tool_name != "fetch_rss_feed":
                return json.dumps({"error": f"Unknown tool: {tool_name}"})

            url = (tool_input.get("url") or "").strip()
            max_items = int(tool_input.get("max_items") or 8)

            if not url:
                return json.dumps({"error": "url is required"})

            source_name = url_to_name.get(url) or url.split("/")[2]
            logger.info(f"Agent fetching feed: {source_name}")

            items = self.fetcher.fetch_rss_feed(url, max_items)
            for item in items:
                item["source"] = source_name
                collected.append(item)

            return json.dumps({"fetched": len(items), "source": source_name})

        try:
            self.provider.generate_with_tools(
                messages=[{"role": "user", "content": prompt}],
                tools=[_FETCH_RSS_TOOL],
                max_tokens=4096,
                max_iterations=max_sources + 4,
                tool_handler=tool_handler,
            )
        except Exception as exc:
            logger.warning(
                f"Agentic collection failed ({exc}). "
                f"Falling back to keyword filter ({len(collected)} articles collected so far)."
            )
            if not collected:
                return self._fallback_collect(topic, max_sources)

        logger.info(f"Agentic collection finished: {len(collected)} articles for '{topic}'")
        return collected

    # ── Fallback path (keyword filter) ───────────────────────────────────────

    def _fallback_collect(
        self, topic: str, max_sources: int
    ) -> List[Dict[str, str]]:
        """Fetch all feeds and keep articles whose text mentions the topic keywords."""
        keywords = [w for w in topic.lower().split() if len(w) > 2]
        collected: List[Dict[str, str]] = []
        fetched_sources = 0

        for name, url in self.fetcher.rss_feeds.items():
            if fetched_sources >= max_sources:
                break
            items = self.fetcher.fetch_rss_feed(url, 8)
            fetched_sources += 1
            for item in items:
                text = (
                    (item.get("title") or "") + " " + (item.get("description") or "")
                ).lower()
                if not keywords or any(kw in text for kw in keywords):
                    item["source"] = name
                    collected.append(item)

        logger.info(
            f"Fallback collection: {len(collected)} articles "
            f"from {fetched_sources} sources for '{topic}'"
        )
        return collected
