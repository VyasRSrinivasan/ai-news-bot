"""News summarizer — calls the configured LLM and returns a structured digest."""
import json
import re
import time
from datetime import date as _date
from typing import Any, Dict, List, Optional

from ..llm_providers import BaseLLMProvider, get_llm_provider
from ..config import LANGUAGE_NAMES
from ..logger import setup_logger


logger = setup_logger(__name__)

# System prompt instructs the LLM to act as a news editor and return JSON.
# The curly braces below are part of the literal JSON schema example, NOT
# Python format placeholders — do not call .format() on this string directly.
PROMPT = '''You are a senior news editor creating a daily digest for a professional audience.
You will receive a list of news articles fetched from RSS feeds today.
Your job is to:
  1. Select the 10-15 most significant, interesting, or novel stories.
  2. Remove duplicates (same story from multiple sources — keep only the best-sourced version).
  3. Group stories into categories (e.g. "Research", "Products", "Industry", "Policy").
  4. For each story write a 2-sentence summary: one sentence of fact, one of significance.
  5. Return ONLY valid JSON — no preamble, no markdown fences.

Output schema:
{
  "date": "YYYY-MM-DD",
  "headline": "One punchy sentence summarizing the day in AI",
  "categories": [
    {
      "name": "Category name",
      "stories": [
        {
          "title": "Story title",
          "summary": "Two-sentence summary.",
          "source": "Publication name",
          "url": "https://...",
          "importance": "high | medium | low"
        }
      ]
    }
  ]
}'''


def _format_article_list(articles: List[Dict[str, str]]) -> str:
    """Format articles into a compact numbered list for the LLM."""
    lines = []
    for i, art in enumerate(articles, 1):
        title = (art.get("title") or "").strip()
        source = (art.get("source") or "").strip()
        url = (art.get("link") or art.get("url") or "").strip()
        snippet = (art.get("description") or "")[:200].strip()
        lines.append(f"{i}. [{source}] {title}\n   URL: {url}\n   {snippet}")
    return "\n\n".join(lines)


class Summarizer:
    """Calls the LLM with the news editor prompt and parses the JSON digest."""

    def __init__(
        self,
        provider: Optional[BaseLLMProvider] = None,
        provider_name: str = "claude",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Args:
            provider: An already-initialised LLM provider. If given, the
                      remaining arguments are ignored.
            provider_name: Provider to create when no provider is passed.
            api_key: API key for the provider (reads from env if omitted).
            model: Model override. Uses provider default when omitted.
        """
        if provider is not None:
            self.provider = provider
        else:
            self.provider = get_llm_provider(
                provider_name=provider_name,
                api_key=api_key,
                model=model,
            )
        logger.info(
            f"Summarizer initialised with {self.provider.provider_name} "
            f"(model: {self.provider.model})"
        )

    def summarize(
        self,
        articles: List[Dict[str, str]],
        topics: Optional[List[str]] = None,
        today: Optional[str] = None,
        language: str = "en",
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> Dict[str, Any]:
        """
        Summarize a list of articles into a structured JSON digest.

        Args:
            articles: List of article dicts with keys: title, source, link/url, description.
            topics: Topic labels shown to the LLM.
            today: ISO date string (YYYY-MM-DD). Defaults to today's date.
            language: BCP-47 language code. Non-English adds a translation instruction.
            max_retries: Number of retry attempts on API or parse failure.
            retry_delay: Seconds to wait between retries.

        Returns:
            Parsed digest dict matching the schema in PROMPT.

        Raises:
            ValueError: If no valid JSON digest can be obtained after all retries.
        """
        today = today or str(_date.today())
        topics = topics or ["AI", "Machine Learning", "Technology"]
        topics_str = ", ".join(topics)

        article_list = _format_article_list(articles)
        user_content = (
            f"Today is {today}.\n"
            f"Topics of interest: {topics_str}\n\n"
            f"Here are today's fetched articles (title, source, URL, and snippet):\n\n"
            f"{article_list}\n\n"
            "Select the best stories and return the JSON digest."
        )

        # Add language instruction for non-English responses
        if language and language.lower() != "en":
            language_name = LANGUAGE_NAMES.get(language.lower(), language.upper())
            user_content += f"\n\nIMPORTANT: Write all 'summary' and 'headline' fields in {language_name}."

        # Embed system instructions directly in the user message for cross-provider compatibility
        full_prompt = PROMPT + "\n\n---\n\n" + user_content

        messages = [{"role": "user", "content": full_prompt}]

        last_error: Exception = ValueError("No attempts made")

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"Summarizer: calling LLM (attempt {attempt}/{max_retries}) "
                    f"with {len(articles)} articles"
                )
                raw = self.provider.generate(
                    messages=messages,
                    max_tokens=8192,
                )
                digest = self._parse_json(raw)
                logger.info("Summarizer: digest parsed successfully")
                return digest

            except Exception as exc:
                last_error = exc
                logger.warning(f"Summarizer attempt {attempt} failed: {exc}")
                if attempt < max_retries:
                    time.sleep(retry_delay)

        raise ValueError(
            f"Summarizer failed after {max_retries} attempts. "
            f"Last error: {last_error}"
        )

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        """
        Extract and parse a JSON object from the LLM response.

        Handles responses that wrap JSON in markdown fences even though the
        prompt asks the model not to.
        """
        # Strip markdown code fences if present
        fenced = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
        candidate = fenced.group(1) if fenced else text.strip()

        # Find the outermost JSON object
        obj_match = re.search(r"\{[\s\S]*\}", candidate)
        if not obj_match:
            raise ValueError("No JSON object found in LLM response")

        return json.loads(obj_match.group(0))
