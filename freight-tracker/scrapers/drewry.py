"""
Drewry World Container Index (WCI) scraper.
Source: https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SOURCE_URL = (
    "https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/"
    "world-container-index-assessed-by-drewry"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def _parse_rate(value: str) -> float | None:
    """Parse a rate string like '$1,234' or '1234.56' into a float."""
    if not value:
        return None
    cleaned = value.replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_date(value: str) -> str | None:
    """Attempt to normalise a date string to ISO format (YYYY-MM-DD)."""
    if not value:
        return None
    value = value.strip()
    for fmt in ("%d %b %Y", "%B %d, %Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return value  # return as-is if we cannot parse


def scrape_drewry() -> list[dict[str, Any]]:
    """
    Scrape the Drewry WCI page and return a list of rate dicts.

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
            "[%s] Drewry HTTP error %s for %s",
            datetime.utcnow().isoformat(),
            exc.response.status_code,
            SOURCE_URL,
        )
        return results
    except httpx.RequestError as exc:
        logger.error(
            "[%s] Drewry request error: %s",
            datetime.utcnow().isoformat(),
            exc,
        )
        return results

    soup = BeautifulSoup(response.text, "lxml")

    # --- Primary strategy: look for a data table ---
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        header_cells = rows[0].find_all(["th", "td"])
        headers = [c.get_text(strip=True).lower() for c in header_cells]

        # Identify relevant column indices
        route_idx = next(
            (i for i, h in enumerate(headers) if "route" in h or "corridor" in h), None
        )
        rate_idx = next(
            (
                i
                for i, h in enumerate(headers)
                if "rate" in h or "index" in h or "usd" in h or "$" in h
            ),
            None,
        )
        date_idx = next(
            (i for i, h in enumerate(headers) if "date" in h or "week" in h), None
        )

        if route_idx is None or rate_idx is None:
            continue

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) <= max(filter(None, [route_idx, rate_idx, date_idx or 0])):
                continue

            route = cells[route_idx].get_text(strip=True)
            rate_raw = cells[rate_idx].get_text(strip=True)
            date_raw = cells[date_idx].get_text(strip=True) if date_idx is not None else ""

            rate = _parse_rate(rate_raw)
            if not route or rate is None:
                continue

            results.append(
                {
                    "index_name": "Drewry WCI",
                    "route": route,
                    "rate_usd_per_feu": rate,
                    "week_ending": _parse_date(date_raw) or datetime.utcnow().strftime("%Y-%m-%d"),
                    "source_url": SOURCE_URL,
                }
            )

    # --- Fallback: look for structured div/list content ---
    if not results:
        logger.warning(
            "[%s] Drewry: table strategy yielded no results; attempting div fallback",
            datetime.utcnow().isoformat(),
        )
        # Many CMS sites render data in dl/dt/dd or div pairs
        for item in soup.select(".wci-route, .route-item, [data-route]"):
            route_el = item.select_one(".route-name, [data-label='route']")
            rate_el = item.select_one(".route-rate, [data-label='rate']")
            date_el = item.select_one(".route-date, [data-label='date']")

            if not route_el or not rate_el:
                continue

            rate = _parse_rate(rate_el.get_text(strip=True))
            if rate is None:
                continue

            results.append(
                {
                    "index_name": "Drewry WCI",
                    "route": route_el.get_text(strip=True),
                    "rate_usd_per_feu": rate,
                    "week_ending": (
                        _parse_date(date_el.get_text(strip=True))
                        if date_el
                        else datetime.utcnow().strftime("%Y-%m-%d")
                    ),
                    "source_url": SOURCE_URL,
                }
            )

    if not results:
        logger.warning(
            "[%s] Drewry: no rate data extracted. The page layout may have changed.",
            datetime.utcnow().isoformat(),
        )

    logger.info("[%s] Drewry: extracted %d records", datetime.utcnow().isoformat(), len(results))
    return results
