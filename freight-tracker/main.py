"""
Freight Rate Tracker — main entry point.

Usage
-----
    python main.py --run-now          # full weekly pipeline
    python main.py --intraday-check   # DB-only WoW spike check
    python main.py --backfill         # scrape + store, no Telegram

Flags
-----
--run-now
    Runs all scrapers → inserts rates into DB → computes signals →
    generates Markdown report → sends full Telegram report.

--intraday-check
    Reads latest two readings per route from DB only (no scraping).
    Computes week-on-week % change. Sends a Telegram alert for every
    route that moved more than alert_thresholds.wow_pct (default 10 %).

--backfill
    Runs all scrapers and stores results in the DB. Does not compute
    signals or send any Telegram messages. Useful for seeding history.
"""

import argparse
import logging
import logging.handlers
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

# ---------------------------------------------------------------------------
# Logging — must be configured before any project imports so that module-level
# loggers pick up the handlers.
# ---------------------------------------------------------------------------

LOG_FILE = Path(__file__).parent / "scraper.log"


def _configure_logging() -> None:
    fmt = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%SZ"

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(ch)

    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(fh)


_configure_logging()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------

from scrapers import scrape_drewry, scrape_freightos, scrape_scfi          # noqa: E402
from database.db import init_db, insert_rates, get_latest_rates, get_rate_history  # noqa: E402
from analysis.signals import generate_signals, generate_weekly_signals      # noqa: E402
from reports.reporter import generate_weekly_report, generate_intraday_alert  # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as fh:
            return yaml.safe_load(fh) or {}
    return {}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _build_history_df(routes: list[str], weeks: int = 12) -> pd.DataFrame:
    """Fetch *weeks* of DB history for *routes* and return as a DataFrame."""
    rows: list[dict] = []
    for route in routes:
        rows.extend(get_rate_history(route, weeks=weeks))
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _run_scrapers(config: dict) -> list[dict[str, Any]]:
    """
    Execute all enabled scrapers sequentially with 3-second inter-scraper pauses.
    Logs failures with UTC timestamps; never raises.
    """
    all_rates: list[dict[str, Any]] = []
    enabled = config.get("scrapers", {})

    scrapers = [
        ("drewry",    scrape_drewry,    enabled.get("drewry",    True)),
        ("freightos", scrape_freightos, enabled.get("freightos", True)),
        ("scfi",      scrape_scfi,      enabled.get("scfi",      True)),
    ]

    for name, fn, is_enabled in scrapers:
        if not is_enabled:
            logger.info("[%s] Scraper '%s' disabled — skipping",
                        datetime.now(timezone.utc).isoformat(), name)
            continue

        logger.info("[%s] Starting scraper: %s",
                    datetime.now(timezone.utc).isoformat(), name)
        try:
            rates = fn()
            logger.info("[%s] Scraper '%s' returned %d records",
                        datetime.now(timezone.utc).isoformat(), name, len(rates))
            all_rates.extend(rates)
        except Exception as exc:
            logger.error("[%s] Scraper '%s' failed: %s",
                         datetime.now(timezone.utc).isoformat(), name, exc,
                         exc_info=True)

        time.sleep(3)

    return all_rates


# ---------------------------------------------------------------------------
# Mode: --run-now
# ---------------------------------------------------------------------------

def run_now(config: dict) -> None:
    """
    Full weekly pipeline:
      scrape → insert → generate signals → build report → send Telegram.
    """
    logger.info("=== run-now: starting full pipeline ===")

    # 1. Scrape all sources
    rates = _run_scrapers(config)
    inserted = insert_rates(rates)
    logger.info("Scraped %d records; %d new inserts", len(rates), inserted)

    # 2. Compute signals from 12-week history
    latest_rates = get_latest_rates()
    routes = list({r["route"] for r in latest_rates})
    history_df = _build_history_df(routes, weeks=12)

    signals_by_route = generate_signals(history_df) if not history_df.empty else {}

    # Persist signal rows to DB
    generate_weekly_signals(
        spike_threshold=config.get("alert_thresholds", {}).get("wow_pct", 10.0)
    )

    # 3. Build report + send Telegram
    report_path = generate_weekly_report(
        signals_by_route=signals_by_route,
        latest_rates=latest_rates,
    )
    logger.info("=== run-now: complete. Report → %s ===", report_path)


# ---------------------------------------------------------------------------
# Mode: --intraday-check
# ---------------------------------------------------------------------------

def intraday_check(config: dict) -> None:
    """
    DB-only spike check — no scraping.

    Reads the two most-recent rate readings per route, computes week-on-week
    % change, and fires a Telegram alert for any route that moved more than
    alert_thresholds.wow_pct (default 10 %).
    """
    logger.info("=== intraday-check: reading DB ===")

    wow_threshold = float(
        config.get("alert_thresholds", {}).get("wow_pct", 10.0)
    )
    routes_of_interest: list[str] = config.get("routes_of_interest", [])

    latest_rates = get_latest_rates()
    if not latest_rates:
        logger.warning("intraday-check: no rates in DB — nothing to check")
        return

    all_db_routes = list({r["route"] for r in latest_rates})

    if routes_of_interest:
        # Resolve config patterns to actual DB route names via case-insensitive
        # substring matching so config entries like "US West Coast" match the
        # scraped label "Shanghai → US West Coast".
        resolved: list[str] = []
        for pattern in routes_of_interest:
            pat_lower = pattern.strip().lower()
            matched = [r for r in all_db_routes if pat_lower in r.lower() or r.lower() in pat_lower]
            if matched:
                resolved.extend(matched)
            else:
                logger.debug("intraday-check: no DB route matched pattern '%s'", pattern)
        routes = list(dict.fromkeys(resolved))  # dedupe, preserve order
        if not routes:
            logger.warning(
                "intraday-check: routes_of_interest configured but none matched DB routes %s",
                all_db_routes,
            )
    else:
        routes = all_db_routes

    alerts_fired = 0

    for route in routes:
        # Pull only the last 2 data points to compute WoW change
        history = get_rate_history(route, weeks=2)
        if len(history) < 2:
            logger.debug("intraday-check: insufficient history for route '%s'", route)
            continue

        # Sort ascending by week_ending and pick the two most-recent unique weeks
        df = (
            pd.DataFrame(history)
            .sort_values("week_ending")
            .drop_duplicates(subset=["week_ending", "index_name"])
        )
        # Average across indices if multiple sources report the same route
        weekly_avg = df.groupby("week_ending")["rate_usd"].mean().sort_index()
        if len(weekly_avg) < 2:
            continue

        prev_rate = weekly_avg.iloc[-2]
        curr_rate = weekly_avg.iloc[-1]
        prev_week = weekly_avg.index[-2]
        curr_week = weekly_avg.index[-1]

        if prev_rate == 0:
            continue

        wow_pct = (curr_rate - prev_rate) / prev_rate * 100

        logger.info(
            "intraday-check | %-50s | %s→%s | WoW: %+.1f%%",
            route, prev_week, curr_week, wow_pct,
        )

        if abs(wow_pct) >= wow_threshold:
            direction = "UP" if wow_pct > 0 else "DOWN"
            message = (
                f"Rate moved {direction} {abs(wow_pct):.1f}% week-on-week.\n"
                f"Previous ({prev_week}): ${prev_rate:,.0f}/FEU\n"
                f"Current  ({curr_week}): ${curr_rate:,.0f}/FEU"
            )
            generate_intraday_alert(
                route=route,
                alert_type=f"wow_{direction.lower()}",
                message=message,
                notify=True,
            )
            alerts_fired += 1

    logger.info("=== intraday-check: complete. %d alert(s) fired ===", alerts_fired)


# ---------------------------------------------------------------------------
# Mode: --backfill
# ---------------------------------------------------------------------------

def backfill(config: dict) -> None:
    """
    Scrape all sources and persist to DB. No signal computation, no Telegram.
    Use this to seed historical data before the first weekly run.
    """
    logger.info("=== backfill: scraping without notifications ===")
    rates = _run_scrapers(config)
    inserted = insert_rates(rates)
    logger.info("=== backfill: %d scraped, %d inserted ===", len(rates), inserted)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Container Freight Rate Tracker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py --run-now          # full weekly pipeline\n"
            "  python main.py --intraday-check   # DB-only spike alert check\n"
            "  python main.py --backfill         # scrape + store, no Telegram\n"
        ),
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--run-now",
        action="store_true",
        help="Full pipeline: scrape → store → signals → report → Telegram",
    )
    group.add_argument(
        "--intraday-check",
        action="store_true",
        help="DB-only WoW spike check; sends Telegram alert if threshold breached",
    )
    group.add_argument(
        "--backfill",
        action="store_true",
        help="Scrape and store without sending any notifications",
    )

    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    config = _load_config()

    logger.info("=" * 60)
    logger.info(
        "Freight Tracker | %s | UTC %s",
        "run-now" if args.run_now else "intraday-check" if args.intraday_check else "backfill",
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    )
    logger.info("=" * 60)

    # Ensure DB schema exists on every invocation
    init_db()

    if args.run_now:
        run_now(config)
    elif args.intraday_check:
        intraday_check(config)
    else:
        backfill(config)


if __name__ == "__main__":
    main()
