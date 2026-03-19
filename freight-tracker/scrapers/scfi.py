"""
Shanghai Containerized Freight Index (SCFI) scraper.
Source: https://en.sse.net.cn/indices/scfinew.jsp
Uses httpx + BeautifulSoup (static HTML, no JS required).
"""

import logging
import re
import time
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SOURCE_URL = "https://en.sse.net.cn/indices/scfinew.jsp"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://en.sse.net.cn/",
}

# Known SCFI routes (composite + individual lanes)
SCFI_ROUTES = {
    "Composite": "SCFI Composite Index",
    "Europe": "Shanghai → Europe",
    "Mediterranean": "Shanghai → Mediterranean",
    "Persian Gulf": "Shanghai → Persian Gulf & Red Sea",
    "West Africa": "Shanghai → West Africa",
    "South Africa": "Shanghai → South Africa",
    "Australia/NZ": "Shanghai → Australia / New Zealand",
    "US West Coast": "Shanghai → US West Coast",
    "US East Coast": "Shanghai → US East Coast",
    "Japan": "Shanghai → Japan",
    "SE Asia": "Shanghai → South East Asia",
    "Korea": "Shanghai → Korea",
    "Hong Kong": "Shanghai → Hong Kong",
    "Taiwan": "Shanghai → Taiwan",
}


def _parse_rate(value: str) -> float | None:
    """Parse a numeric string, removing commas, and return float."""
    if not value:
        return None
    cleaned = re.sub(r"[^\d.]", "", value.replace(",", ""))
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_date(value: str) -> str | None:
    """Normalise various date strings to ISO format (YYYY-MM-DD)."""
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d %b %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return value


def _extract_week_ending(soup: BeautifulSoup) -> str:
    """Try to find the 'week ending' date anywhere on the page."""
    # Look for text like "2024-01-05" or "January 5, 2024"
    date_pattern = re.compile(
        r"\b(\d{4}[-/]\d{2}[-/]\d{2}|\d{1,2}\s+\w{3}\s+\d{4}|\w+\s+\d{1,2},\s+\d{4})\b"
    )
    for tag in soup.find_all(["p", "td", "th", "div", "span", "h2", "h3"]):
        text = tag.get_text(strip=True)
        match = date_pattern.search(text)
        if match:
            parsed = _parse_date(match.group(1))
            if parsed:
                return parsed
    return datetime.utcnow().strftime("%Y-%m-%d")


def scrape_scfi() -> list[dict[str, Any]]:
    """
    Scrape SCFI composite and route-level indices.

    Returns
    -------
    list[dict]: Each item contains:
        index_name, route, rate_usd_per_feu, week_ending, source_url
    """
    results: list[dict[str, Any]] = []

    try:
        time.sleep(3)
        with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as client:
            response = client.get(SOURCE_URL)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "[%s] SCFI HTTP error %s for %s",
            datetime.utcnow().isoformat(),
            exc.response.status_code,
            SOURCE_URL,
        )
        return results
    except httpx.RequestError as exc:
        logger.error(
            "[%s] SCFI request error: %s",
            datetime.utcnow().isoformat(),
            exc,
        )
        return results

    soup = BeautifulSoup(response.text, "lxml")
    week_ending = _extract_week_ending(soup)

    # --- Strategy 1: parse HTML tables ---
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        header_cells = rows[0].find_all(["th", "td"])
        headers = [c.get_text(strip=True).lower() for c in header_cells]

        # We need at least a route column and a numeric index/rate column
        route_idx = next(
            (i for i, h in enumerate(headers) if "route" in h or "service" in h or "name" in h),
            None,
        )
        rate_idx = next(
            (
                i
                for i, h in enumerate(headers)
                if "index" in h or "rate" in h or "usd" in h or "value" in h
            ),
            None,
        )

        if route_idx is None and rate_idx is None:
            # Fallback: try col 0 as route, col 1 as rate
            if len(headers) >= 2:
                route_idx, rate_idx = 0, 1
            else:
                continue

        if route_idx is None:
            route_idx = 0
        if rate_idx is None:
            rate_idx = 1

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) <= max(route_idx, rate_idx):
                continue

            route_raw = cells[route_idx].get_text(strip=True)
            rate_raw = cells[rate_idx].get_text(strip=True)

            # Skip header-like or empty rows
            if not route_raw or not rate_raw:
                continue
            if re.match(r"^[a-zA-Z\s]+$", rate_raw):
                # Looks like text, not a number — skip
                continue

            rate = _parse_rate(rate_raw)
            if rate is None:
                continue

            # Attempt to map the route name to a known SCFI route
            route_label = route_raw
            for key, label in SCFI_ROUTES.items():
                if key.lower() in route_raw.lower():
                    route_label = label
                    break

            results.append(
                {
                    "index_name": "SCFI",
                    "route": route_label,
                    "rate_usd_per_feu": rate,
                    "week_ending": week_ending,
                    "source_url": SOURCE_URL,
                }
            )

    # --- Strategy 2: scan for labelled spans / divs ---
    if not results:
        logger.warning(
            "[%s] SCFI: table strategy yielded no results; trying element fallback",
            datetime.utcnow().isoformat(),
        )
        for item in soup.select(".index-item, .route-row, [data-index]"):
            name_el = item.select_one(".index-name, .route-name")
            value_el = item.select_one(".index-value, .route-value")
            if not name_el or not value_el:
                continue
            rate = _parse_rate(value_el.get_text(strip=True))
            if rate is None:
                continue
            results.append(
                {
                    "index_name": "SCFI",
                    "route": name_el.get_text(strip=True),
                    "rate_usd_per_feu": rate,
                    "week_ending": week_ending,
                    "source_url": SOURCE_URL,
                }
            )

    if not results:
        logger.warning(
            "[%s] SCFI: no rate data extracted. The page layout may have changed.",
            datetime.utcnow().isoformat(),
        )

    logger.info("[%s] SCFI: extracted %d records", datetime.utcnow().isoformat(), len(results))
    return results
