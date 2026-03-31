"""
News sentiment analyser for the freight rate tracker.

Fetches the 10 most-recent headlines from shipping-focused RSS feeds,
batches them to claude-haiku-4-5-20251001, and returns structured risk scores.

RSS sources
-----------
- https://splash247.com/feed/
- https://www.tradewindsnews.com/rss

Anthropic API key is read from the ANTHROPIC_API_KEY environment variable.
Returns None silently when the key is absent (no API cost incurred).

Return schema
-------------
{
    "date":                str         — ISO date YYYY-MM-DD (UTC)
    "geopolitical_score":  float       — 0-100
    "labour_score":        float       — 0-100
    "port_score":          float       — 0-100
    "key_events":          list[str]   — up to 3 significant events
    "affected_routes":     list[str]   — routes likely impacted
    "headlines_used":      int         — number of headlines analysed
    "scraped_at":          str         — ISO datetime UTC
}
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

import anthropic
import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RSS_FEEDS: list[str] = [
    "https://splash247.com/feed/",
    "https://www.tradewindsnews.com/rss",
]

HEADLINES_PER_FEED = 10       # cap per feed before deduplication
MAX_HEADLINES_TOTAL = 20      # hard cap sent to the model

HAIKU_MODEL = "claude-haiku-4-5-20251001"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

# JSON keys the model must return
_REQUIRED_KEYS = {
    "geopolitical_risk_score",
    "labour_disruption_risk",
    "port_congestion_risk",
    "key_events",
    "affected_routes",
}


# ---------------------------------------------------------------------------
# RSS headline fetcher
# ---------------------------------------------------------------------------

def _extract_titles_rss(root: ET.Element) -> list[str]:
    """Parse titles from an RSS 2.0 feed (//channel/item/title)."""
    titles: list[str] = []
    for item in root.iter("item"):
        title_el = item.find("title")
        if title_el is not None and title_el.text:
            titles.append(title_el.text.strip())
    return titles


def _extract_titles_atom(root: ET.Element, ns: str) -> list[str]:
    """Parse titles from an Atom feed (//entry/title), handling the namespace."""
    titles: list[str] = []
    for entry in root.iter(f"{{{ns}}}entry"):
        title_el = entry.find(f"{{{ns}}}title")
        if title_el is not None and title_el.text:
            titles.append(title_el.text.strip())
    return titles


def _fetch_headlines(feed_url: str, limit: int = HEADLINES_PER_FEED) -> list[str]:
    """
    Fetch up to *limit* headlines from *feed_url*.
    Handles both RSS 2.0 and Atom 1.0 feeds.
    Returns an empty list on any error.
    """
    try:
        resp = httpx.get(feed_url, headers=HEADERS, timeout=20, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "[news] HTTP %s fetching feed %s", exc.response.status_code, feed_url
        )
        return []
    except httpx.RequestError as exc:
        logger.error("[news] Request error fetching feed %s: %s", feed_url, exc)
        return []

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as exc:
        logger.error("[news] XML parse error for %s: %s", feed_url, exc)
        return []

    tag = root.tag  # e.g. '{http://www.w3.org/2005/Atom}feed' or 'rss'

    if "atom" in tag.lower() or tag.startswith("{http://www.w3.org/2005/Atom}"):
        ns = re.search(r"\{(.+?)\}", tag)
        titles = _extract_titles_atom(root, ns.group(1)) if ns else []
    else:
        # RSS 2.0 — root is <rss>, channel inside
        titles = _extract_titles_rss(root)

    titles = [t for t in titles if t][:limit]
    logger.info("[news] Fetched %d headlines from %s", len(titles), feed_url)
    return titles


# ---------------------------------------------------------------------------
# Anthropic analysis
# ---------------------------------------------------------------------------

def _build_prompt(headlines: list[str]) -> str:
    numbered = "\n".join(f"{i+1}. {h}" for i, h in enumerate(headlines))
    return (
        "You are a shipping market analyst. Scan these headlines and return "
        "a JSON object with:\n"
        "- geopolitical_risk_score: 0-100\n"
        "- labour_disruption_risk: 0-100\n"
        "- port_congestion_risk: 0-100\n"
        "- key_events: list of up to 3 significant events detected\n"
        "- affected_routes: list of routes likely impacted\n\n"
        f"Headlines:\n{numbered}\n\n"
        "Return only valid JSON, no markdown fences, no explanation."
    )


def _extract_json(text: str) -> dict[str, Any] | None:
    """
    Extract a JSON object from the model response.
    Handles raw JSON and markdown-fenced blocks.
    """
    # Strip optional ```json … ``` wrapper
    text = re.sub(r"```(?:json)?\s*", "", text).strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fall back: find the first {...} block
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    logger.error("[news] Could not extract JSON from model response: %.200s", text)
    return None


def _clamp(val: Any, lo: float = 0.0, hi: float = 100.0) -> float:
    """Coerce a value to a float clamped to [lo, hi]."""
    try:
        return max(lo, min(hi, float(val)))
    except (TypeError, ValueError):
        return 0.0


def _analyse_headlines(headlines: list[str], api_key: str) -> dict[str, Any] | None:
    """
    Send *headlines* to Haiku and return the parsed, validated result dict.
    Returns None on API error or if the response fails validation.
    """
    prompt = _build_prompt(headlines)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=512,
            system="You are a shipping market analyst. Return only valid JSON.",
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
    except anthropic.APIStatusError as exc:
        logger.error("[news] Anthropic API error %s: %s", exc.status_code, exc.message)
        return None
    except Exception as exc:
        logger.error("[news] Anthropic call failed: %s", exc)
        return None

    data = _extract_json(raw)
    if data is None:
        return None

    # Validate required keys
    missing = _REQUIRED_KEYS - set(data.keys())
    if missing:
        logger.error("[news] Model response missing keys: %s", missing)
        return None

    return data


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def scrape_news_sentiment() -> dict[str, Any] | None:
    """
    Fetch headlines from all configured RSS feeds, analyse with Haiku,
    and return a structured risk-score record.

    Returns None when ANTHROPIC_API_KEY is unset or any step fails
    (so the caller can skip gracefully without crashing the pipeline).

    Returns
    -------
    dict with keys:
        date, geopolitical_score, labour_score, port_score,
        key_events, affected_routes, headlines_used, scraped_at
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        logger.info("[news] ANTHROPIC_API_KEY not set — skipping news sentiment")
        return None

    # Collect headlines from all feeds
    all_headlines: list[str] = []
    for feed_url in RSS_FEEDS:
        time.sleep(1)   # polite inter-feed pause
        all_headlines.extend(_fetch_headlines(feed_url))

    # Deduplicate while preserving order, then cap total
    seen: set[str] = set()
    unique: list[str] = []
    for h in all_headlines:
        if h not in seen:
            seen.add(h)
            unique.append(h)
    headlines = unique[:MAX_HEADLINES_TOTAL]

    if not headlines:
        logger.warning("[news] No headlines fetched from any feed — skipping analysis")
        return None

    logger.info("[news] Analysing %d headlines via %s", len(headlines), HAIKU_MODEL)
    data = _analyse_headlines(headlines, api_key)
    if data is None:
        return None

    now = datetime.now(timezone.utc)
    result: dict[str, Any] = {
        "date":                now.strftime("%Y-%m-%d"),
        "geopolitical_score":  _clamp(data["geopolitical_risk_score"]),
        "labour_score":        _clamp(data["labour_disruption_risk"]),
        "port_score":          _clamp(data["port_congestion_risk"]),
        "key_events":          list(data.get("key_events") or [])[:3],
        "affected_routes":     list(data.get("affected_routes") or []),
        "headlines_used":      len(headlines),
        "scraped_at":          now.isoformat(),
    }

    logger.info(
        "[news] Scores — geo=%.0f  labour=%.0f  port=%.0f  events=%d",
        result["geopolitical_score"],
        result["labour_score"],
        result["port_score"],
        len(result["key_events"]),
    )
    return result
