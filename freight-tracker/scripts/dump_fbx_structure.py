"""
One-off evidence collector for the Freightos FBX page.

Purpose
-------
The FBX code -> lane mapping in ``scrapers/freightos.py::KNOWN_ROUTES`` is
hardcoded and is suspected of having drifted from the published page. This
script does not fix that. It only captures what the page actually says, so the
mapping can be corrected from evidence rather than from guesswork:

    fbx_structure_dump.txt   every table header, the first 8 data rows in
                             full, and per row the FBX code, printed lane
                             label and rate; plus every unit/currency string
                             found anywhere on the page
    fbx_raw_table.html       raw rendered HTML of the table container
    fbx_page.png             full-page screenshot

Run from GitHub Actions, which can reach the host; local sandboxes are
blocked by egress policy.

The script is deliberately forgiving. A run that finds no table still writes a
dump containing the page text and full HTML, because a failed selector is
itself evidence and a silent failure would waste the run.
"""

from __future__ import annotations

import asyncio
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

SOURCE_URL = "https://fbx.freightos.com/"

REPO_ROOT = Path(__file__).resolve().parent.parent
DUMP_TXT = REPO_ROOT / "fbx_structure_dump.txt"
RAW_HTML = REPO_ROOT / "fbx_raw_table.html"
SCREENSHOT = REPO_ROOT / "fbx_page.png"

MAX_DATA_ROWS = 8

# Unit / currency vocabulary. The FEU-vs-TEU question is the reason for the
# run, so the net is cast wide and every hit is reported with its context
# rather than reduced to a verdict here.
UNIT_PATTERNS = [
    r"\bFEU\b", r"\bTEU\b", r"\b40'?\s*(?:ft|foot|HC|container)?\b",
    r"\b20'?\s*(?:ft|foot|container)?\b", r"\bUSD\b", r"\bUS\$", r"\$",
    r"per\s+(?:container|box|unit|FEU|TEU)", r"\bcontainer\b", r"\bindex\b",
]
UNIT_RE = re.compile("|".join(UNIT_PATTERNS), re.IGNORECASE)

FBX_CODE_RE = re.compile(r"\bFBX\s*\d{2}\b", re.IGNORECASE)
RATE_RE = re.compile(r"\$?\s*\d[\d,]{2,}(?:\.\d+)?")


def _section(title: str) -> str:
    return f"\n{'=' * 78}\n{title}\n{'=' * 78}\n"


async def _collect(page) -> list[str]:
    """Build the dump text. Never raises; records failures inline."""
    out: list[str] = []

    out.append(_section("RUN METADATA"))
    out.append(f"url            : {SOURCE_URL}")
    out.append(f"captured_at    : {datetime.now(timezone.utc).isoformat()}")
    out.append(f"page_title     : {await page.title()}")
    out.append(f"viewport       : {page.viewport_size}")

    # ------------------------------------------------------------------
    # Tables
    # ------------------------------------------------------------------
    tables = await page.query_selector_all("table")
    out.append(_section(f"TABLES FOUND: {len(tables)}"))

    for t_idx, table in enumerate(tables):
        out.append(f"\n--- TABLE {t_idx} ---")

        # Headers: prefer real <th>, fall back to the first row's cells.
        headers = [
            (await h.inner_text()).strip()
            for h in await table.query_selector_all("th")
        ]
        if not headers:
            first_row = await table.query_selector("tr")
            if first_row:
                headers = [
                    (await c.inner_text()).strip()
                    for c in await first_row.query_selector_all("td, th")
                ]
                out.append("(no <th>; headers taken from the first row)")
        out.append(f"HEADERS ({len(headers)}): {headers}")

        rows = await table.query_selector_all("tr")
        out.append(f"TOTAL ROWS: {len(rows)}")

        shown = 0
        for row in rows:
            cells = await row.query_selector_all("td")
            if not cells:          # header-only row
                continue
            if shown >= MAX_DATA_ROWS:
                break
            texts = [(await c.inner_text()).strip() for c in cells]
            joined = " | ".join(texts)

            code_hit = FBX_CODE_RE.search(joined)
            rate_hits = RATE_RE.findall(joined)
            # The lane label is whichever cell carries an arrow or a
            # recognisable origin-destination phrase, excluding the code cell.
            label = ""
            for cell in texts:
                if FBX_CODE_RE.fullmatch(cell.strip()):
                    continue
                if any(sep in cell for sep in ("→", "->", " to ", "-")) and len(cell) > 6:
                    label = cell
                    break

            out.append(f"\n  ROW {shown}:")
            out.append(f"    cells      : {texts}")
            out.append(f"    fbx_code   : {code_hit.group(0) if code_hit else '(none found)'}")
            out.append(f"    lane_label : {label or '(none found)'}")
            out.append(f"    rate_values: {rate_hits or '(none found)'}")
            shown += 1

        if shown == 0:
            out.append("  (no data rows with <td> cells)")

    # ------------------------------------------------------------------
    # Unit / currency evidence — the FEU vs TEU question
    # ------------------------------------------------------------------
    out.append(_section("UNIT AND CURRENCY STRINGS (whole page)"))
    body_text = await page.inner_text("body")
    seen: set[str] = set()
    for line in body_text.splitlines():
        line = line.strip()
        if not line or line in seen:
            continue
        if UNIT_RE.search(line):
            seen.add(line)
            out.append(f"  {line}")
    if not seen:
        out.append("  (no unit or currency strings matched)")

    out.append(_section("EXPLICIT FEU / TEU MENTIONS"))
    for token in ("FEU", "TEU", "40ft", "40'", "20ft", "20'"):
        hits = [ln.strip() for ln in body_text.splitlines() if token.lower() in ln.lower()]
        out.append(f"  {token:6}: {len(hits)} mention(s)")
        for h in hits[:5]:
            out.append(f"           {h}")

    # ------------------------------------------------------------------
    # Full page text — the safety net when selectors miss
    # ------------------------------------------------------------------
    out.append(_section("FULL PAGE TEXT (first 400 lines)"))
    for line in body_text.splitlines()[:400]:
        if line.strip():
            out.append(f"  {line.rstrip()}")

    return out


async def _save_table_html(page) -> str:
    """Save the table container's rendered HTML; fall back to full page."""
    for selector in ("table", "[class*='table']", "[class*='grid']", "main"):
        el = await page.query_selector(selector)
        if el:
            # Prefer the parent container, which usually carries the unit
            # caption and legend that the <table> itself omits.
            html = await el.evaluate(
                "e => (e.closest('section,div[class],main') || e).outerHTML"
            )
            if html and len(html) > 200:
                RAW_HTML.write_text(html, encoding="utf-8")
                return f"table container HTML saved via selector {selector!r} ({len(html)} bytes)"
    html = await page.content()
    RAW_HTML.write_text(html, encoding="utf-8")
    return f"no table container matched; saved full page HTML ({len(html)} bytes)"


async def main() -> int:
    lines: list[str] = []
    status = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 1600, "height": 1200})
        try:
            await page.goto(SOURCE_URL, wait_until="networkidle", timeout=90_000)

            # Wait for the rate table specifically, not merely for load.
            try:
                await page.wait_for_selector("table tr td", timeout=45_000)
                waited = "table rows rendered"
            except Exception as exc:
                waited = f"table selector timed out ({type(exc).__name__}); dumping anyway"
                status = 1

            # Late-rendering rows: settle before reading.
            await page.wait_for_timeout(3_000)

            lines = await _collect(page)
            lines.insert(0, f"wait_state     : {waited}")

            lines.append(_section("ARTIFACTS"))
            lines.append(f"  {await _save_table_html(page)}")

            await page.screenshot(path=str(SCREENSHOT), full_page=True)
            lines.append(f"  screenshot saved to {SCREENSHOT.name}")

        except Exception as exc:
            status = 1
            lines.append(_section("FATAL ERROR"))
            lines.append(f"  {type(exc).__name__}: {exc}")
            # Salvage whatever rendered, so the run still yields evidence.
            try:
                RAW_HTML.write_text(await page.content(), encoding="utf-8")
                await page.screenshot(path=str(SCREENSHOT), full_page=True)
                lines.append("  salvaged page HTML and screenshot after the error")
            except Exception as inner:
                lines.append(f"  salvage also failed: {type(inner).__name__}: {inner}")
        finally:
            await browser.close()

    DUMP_TXT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {DUMP_TXT.name} ({DUMP_TXT.stat().st_size} bytes)")
    for artifact in (RAW_HTML, SCREENSHOT):
        if artifact.exists():
            print(f"wrote {artifact.name} ({artifact.stat().st_size} bytes)")
        else:
            print(f"MISSING {artifact.name}")
    return status


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
