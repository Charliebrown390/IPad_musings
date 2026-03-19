"""
Freightos Baltic Index (FBX) scraper.
Source: https://fbx.freightos.com/
Uses Playwright because the page is JS-rendered.
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Any

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

SOURCE_URL = "https://fbx.freightos.com/"

# Common FBX route codes and their descriptions
KNOWN_ROUTES = {
    "FBX01": "China/East Asia → North America West Coast",
    "FBX02": "China/East Asia → North America East Coast",
    "FBX03": "China/East Asia → North Europe",
    "FBX04": "China/East Asia → Mediterranean",
    "FBX05": "Europe → North America East Coast",
    "FBX06": "North America East Coast → Europe",
    "FBX07": "North America West Coast → China/East Asia",
    "FBX11": "China/East Asia → South America",
    "FBX13": "China/East Asia → Oceania",
}


def _parse_rate(value: str) -> float | None:
    """Strip currency symbols and commas, return float or None."""
    if not value:
        return None
    cleaned = re.sub(r"[^\d.]", "", value.replace(",", ""))
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_date(value: str) -> str | None:
    """Normalise a date string to ISO format."""
    if not value:
        return None
    value = value.strip()
    for fmt in ("%d %b %Y", "%B %d, %Y", "%Y-%m-%d", "%d/%m/%Y", "%b %d, %Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return value


async def _scrape_with_playwright() -> list[dict[str, Any]]:
    """Launch a headless browser, wait for JS render, then parse the FBX page."""
    results: list[dict[str, Any]] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        try:
            await page.goto(SOURCE_URL, wait_until="networkidle", timeout=60_000)
            # Allow extra time for any deferred JS hydration
            await asyncio.sleep(3)
        except PlaywrightTimeout:
            logger.error(
                "[%s] Freightos: page load timed out for %s",
                datetime.utcnow().isoformat(),
                SOURCE_URL,
            )
            await browser.close()
            return results
        except Exception as exc:
            logger.error(
                "[%s] Freightos: unexpected error during page load: %s",
                datetime.utcnow().isoformat(),
                exc,
            )
            await browser.close()
            return results

        html = await page.content()

        # --- Strategy 1: look for a table with rate data ---
        rows = await page.query_selector_all("table tr")
        if rows:
            headers: list[str] = []
            for i, row in enumerate(rows):
                cells = await row.query_selector_all("th, td")
                cell_texts = [await c.inner_text() for c in cells]

                if i == 0:
                    headers = [t.lower().strip() for t in cell_texts]
                    continue

                if not headers:
                    continue

                route_idx = next(
                    (j for j, h in enumerate(headers) if "route" in h or "fbx" in h), None
                )
                rate_idx = next(
                    (j for j, h in enumerate(headers) if "rate" in h or "usd" in h or "$" in h),
                    None,
                )
                date_idx = next(
                    (j for j, h in enumerate(headers) if "date" in h or "week" in h), None
                )

                if route_idx is None or rate_idx is None:
                    continue
                if len(cell_texts) <= max(
                    filter(None, [route_idx, rate_idx, date_idx or 0])
                ):
                    continue

                route = cell_texts[route_idx].strip()
                rate = _parse_rate(cell_texts[rate_idx])
                date_raw = cell_texts[date_idx].strip() if date_idx is not None else ""

                if not route or rate is None:
                    continue

                results.append(
                    {
                        "index_name": "Freightos FBX",
                        "route": route,
                        "rate_usd_per_feu": rate,
                        "week_ending": _parse_date(date_raw) or datetime.utcnow().strftime("%Y-%m-%d"),
                        "source_url": SOURCE_URL,
                    }
                )

        # --- Strategy 2: scan for FBX route codes and adjacent numbers ---
        if not results:
            logger.warning(
                "[%s] Freightos: table strategy yielded no results; trying regex fallback",
                datetime.utcnow().isoformat(),
            )
            # Extract all visible text and look for patterns like "FBX01 ... $1,234"
            body_text = await page.evaluate("() => document.body.innerText")
            pattern = re.compile(
                r"(FBX\d+)[^\d]*?\$?\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE
            )
            for match in pattern.finditer(body_text):
                code = match.group(1).upper()
                rate = _parse_rate(match.group(2))
                if rate is None or rate == 0:
                    continue
                route_label = KNOWN_ROUTES.get(code, code)
                results.append(
                    {
                        "index_name": "Freightos FBX",
                        "route": f"{code} – {route_label}",
                        "rate_usd_per_feu": rate,
                        "week_ending": datetime.utcnow().strftime("%Y-%m-%d"),
                        "source_url": SOURCE_URL,
                    }
                )

        await browser.close()

    if not results:
        logger.warning(
            "[%s] Freightos: no rate data extracted. Page structure may have changed.",
            datetime.utcnow().isoformat(),
        )

    logger.info(
        "[%s] Freightos: extracted %d records", datetime.utcnow().isoformat(), len(results)
    )
    return results


def scrape_freightos() -> list[dict[str, Any]]:
    """Synchronous entry point — runs the async Playwright scraper."""
    return asyncio.run(_scrape_with_playwright())
