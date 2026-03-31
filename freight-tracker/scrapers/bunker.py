"""
Ship & Bunker VLSFO 0.5% price scraper.
Source: https://shipandbunker.com/prices

Fetches Very Low Sulphur Fuel Oil (VLSFO 0.5%) spot prices for three key
bunkering hubs: Rotterdam, Singapore, and Houston.

Strategy
--------
Primary  — parse the main /prices page global table (fastest, one request).
Fallback — fetch each port's dedicated page and extract the VLSFO price block.

Returns
-------
list[dict]: Each item contains:
    port, fuel_type, price_usd_per_mt, date, source_url
"""

import logging
import time
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL   = "https://shipandbunker.com"
PRICES_URL = f"{BASE_URL}/prices"

# Port-specific page URLs for the fallback strategy
PORT_URLS: dict[str, str] = {
    "Rotterdam": f"{BASE_URL}/prices/emea/nwe/nl-rtm-rotterdam",
    "Singapore": f"{BASE_URL}/prices/apac/sea/sg-sin-singapore",
    "Houston":   f"{BASE_URL}/prices/am/usac/us-hou-houston",
}

FUEL_TYPE = "VLSFO 0.5%"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer":         "https://shipandbunker.com/",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_price(value: str) -> float | None:
    """Strip currency symbols/commas and return float, or None on failure."""
    if not value:
        return None
    cleaned = value.replace("$", "").replace(",", "").replace("\xa0", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _get(client: httpx.Client, url: str) -> httpx.Response | None:
    try:
        resp = client.get(url)
        resp.raise_for_status()
        return resp
    except httpx.HTTPStatusError as exc:
        logger.error(
            "[%s] bunker: HTTP %s fetching %s",
            _today(), exc.response.status_code, url,
        )
    except httpx.RequestError as exc:
        logger.error("[%s] bunker: request error fetching %s: %s", _today(), url, exc)
    return None


# ---------------------------------------------------------------------------
# Primary strategy — global prices table on /prices
# ---------------------------------------------------------------------------

def _scrape_global_table(client: httpx.Client) -> list[dict[str, Any]]:
    """
    Parse the main /prices page.  Ship & Bunker renders a large HTML table
    where each row represents a port and columns map to fuel grades.
    We look for rows containing our three target ports and extract the
    VLSFO column value.
    """
    resp = _get(client, PRICES_URL)
    if resp is None:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    results: list[dict[str, Any]] = []
    target_ports = {p.lower(): p for p in PORT_URLS}

    for table in soup.find_all("table"):
        headers_el = table.find("tr")
        if not headers_el:
            continue
        headers = [th.get_text(strip=True).lower() for th in headers_el.find_all(["th", "td"])]

        # Identify VLSFO column — accepts "vlsfo", "0.5%", "lsfo"
        vlsfo_idx = next(
            (i for i, h in enumerate(headers)
             if "vlsfo" in h or "0.5" in h or ("ls" in h and "fo" in h)),
            None,
        )
        # Identify port/location column
        port_idx = next(
            (i for i, h in enumerate(headers) if "port" in h or "location" in h or "name" in h),
            0,  # first column is usually the port name
        )

        if vlsfo_idx is None:
            continue

        for row in table.find_all("tr")[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) <= vlsfo_idx:
                continue

            port_text = cells[port_idx].get_text(strip=True)
            port_lower = port_text.lower()

            matched_port = next(
                (canonical for key, canonical in target_ports.items() if key in port_lower),
                None,
            )
            if not matched_port:
                continue

            price = _parse_price(cells[vlsfo_idx].get_text(strip=True))
            if price is None or price <= 0:
                continue

            results.append({
                "port":              matched_port,
                "fuel_type":         FUEL_TYPE,
                "price_usd_per_mt":  price,
                "date":              _today(),
                "source_url":        PRICES_URL,
            })

    return results


# ---------------------------------------------------------------------------
# Fallback strategy — per-port dedicated pages
# ---------------------------------------------------------------------------

def _scrape_port_page(client: httpx.Client, port: str, url: str) -> dict[str, Any] | None:
    """
    Fetch a port-specific page and extract the VLSFO 0.5% price.

    Ship & Bunker port pages typically render a summary card or table at the
    top with the current day's prices for each fuel grade.
    """
    time.sleep(2)
    resp = _get(client, url)
    if resp is None:
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    # --- Strategy A: table with fuel grade rows ---
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            row_text = cells[0].get_text(strip=True).lower()
            if "vlsfo" in row_text or "0.5" in row_text:
                price = _parse_price(cells[1].get_text(strip=True))
                if price and price > 0:
                    return {
                        "port":             port,
                        "fuel_type":        FUEL_TYPE,
                        "price_usd_per_mt": price,
                        "date":             _today(),
                        "source_url":       url,
                    }

    # --- Strategy B: look for a data attribute or labelled div ---
    for el in soup.find_all(attrs={"data-fuel": True}):
        fuel_attr = el.get("data-fuel", "").lower()
        if "vlsfo" in fuel_attr or "0.5" in fuel_attr:
            price = _parse_price(el.get_text(strip=True))
            if price and price > 0:
                return {
                    "port":             port,
                    "fuel_type":        FUEL_TYPE,
                    "price_usd_per_mt": price,
                    "date":             _today(),
                    "source_url":       url,
                }

    # --- Strategy C: regex over visible text ---
    import re
    body_text = soup.get_text(" ", strip=True)
    pattern = re.compile(
        r"VLSFO[^$\d]*\$?\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE
    )
    m = pattern.search(body_text)
    if m:
        price = _parse_price(m.group(1))
        if price and price > 0:
            return {
                "port":             port,
                "fuel_type":        FUEL_TYPE,
                "price_usd_per_mt": price,
                "date":             _today(),
                "source_url":       url,
            }

    logger.warning("[%s] bunker: could not extract VLSFO price for %s", _today(), port)
    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def scrape_bunker() -> list[dict[str, Any]]:
    """
    Scrape VLSFO 0.5% bunker prices for Rotterdam, Singapore, and Houston.

    Returns
    -------
    list[dict]: Each item contains:
        port, fuel_type, price_usd_per_mt, date, source_url
    """
    results: list[dict[str, Any]] = []

    with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as client:
        time.sleep(2)  # polite delay before first request

        # Primary: global table
        results = _scrape_global_table(client)

        # Determine which ports are still missing
        found_ports = {r["port"] for r in results}
        missing_ports = {p: u for p, u in PORT_URLS.items() if p not in found_ports}

        # Fallback: port-specific pages
        for port, url in missing_ports.items():
            record = _scrape_port_page(client, port, url)
            if record:
                results.append(record)

    found = {r["port"] for r in results}
    still_missing = set(PORT_URLS) - found
    if still_missing:
        logger.warning(
            "[%s] bunker: no price found for port(s): %s",
            _today(), ", ".join(sorted(still_missing)),
        )

    logger.info("[%s] bunker: extracted %d record(s)", _today(), len(results))
    return results
