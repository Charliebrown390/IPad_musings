"""
Freight Rate Tracker — main entry point.

Usage
-----
    python main.py [--mode weekly|intraday|scrape-only|report-only]

Modes
-----
weekly      : scrape all sources → store → run signals → generate report  (default)
intraday    : scrape all sources → store → check spike alerts only
scrape-only : scrape and store without analysis or reporting
report-only : generate report from existing DB data (no scraping)
"""

import argparse
import logging
import logging.handlers
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Logging setup — must happen before importing project modules
# ---------------------------------------------------------------------------

LOG_FILE = Path(__file__).parent / "scraper.log"


def _configure_logging() -> None:
    fmt = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%SZ"

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(ch)

    # Rotating file handler (scraper.log, 5 MB × 3 backups)
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(fh)


_configure_logging()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Project imports (after logging is configured)
# ---------------------------------------------------------------------------

from scrapers import scrape_drewry, scrape_freightos, scrape_scfi
from database.db import init_db, insert_rates, get_latest_rates
from analysis.signals import generate_weekly_signals
from reports.reporter import generate_weekly_report, generate_intraday_alert


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


# ---------------------------------------------------------------------------
# Scraping orchestrator
# ---------------------------------------------------------------------------

def run_scrapers(config: dict) -> list[dict]:
    """
    Run all configured scrapers sequentially with 3-second inter-scraper delays.

    Returns the combined list of rate dicts.
    """
    all_rates: list[dict] = []
    enabled = config.get("scrapers", {})

    scrapers = [
        ("drewry",    scrape_drewry,    enabled.get("drewry",    True)),
        ("freightos", scrape_freightos, enabled.get("freightos", True)),
        ("scfi",      scrape_scfi,      enabled.get("scfi",      True)),
    ]

    for name, fn, is_enabled in scrapers:
        if not is_enabled:
            logger.info("Scraper '%s' is disabled in config — skipping", name)
            continue
        logger.info("Running scraper: %s", name)
        try:
            rates = fn()
            logger.info("Scraper '%s' returned %d records", name, len(rates))
            all_rates.extend(rates)
        except Exception as exc:
            logger.error(
                "[%s] Scraper '%s' failed: %s",
                datetime.now(timezone.utc).isoformat(),
                name,
                exc,
                exc_info=True,
            )
        # 3-second delay between scrapers (rate limiting / politeness)
        time.sleep(3)

    return all_rates


# ---------------------------------------------------------------------------
# Intraday alert checker
# ---------------------------------------------------------------------------

def check_intraday_alerts(config: dict) -> None:
    """
    After a fresh scrape, compare new rates against configurable thresholds
    and fire alerts for any route that breached a limit.
    """
    thresholds = config.get("alerts", {}).get("rate_thresholds", {})
    spike_pct = config.get("alerts", {}).get("spike_pct", 10.0)

    latest = get_latest_rates()
    for row in latest:
        route = row["route"]
        rate = row["rate_usd"]

        # Hard threshold breach
        if route in thresholds:
            limit = thresholds[route]
            if rate > limit:
                generate_intraday_alert(
                    route=route,
                    alert_type="threshold_breach",
                    message=(
                        f"{row['index_name']} rate for '{route}' is "
                        f"${rate:,.0f}/FEU — above configured threshold of ${limit:,.0f}."
                    ),
                )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Container Freight Rate Tracker")
    parser.add_argument(
        "--mode",
        choices=["weekly", "intraday", "scrape-only", "report-only"],
        default="weekly",
        help="Execution mode (default: weekly)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    config = _load_config()

    logger.info("=" * 60)
    logger.info("Freight Tracker starting — mode=%s", args.mode)
    logger.info("=" * 60)

    # Always ensure the DB schema exists
    init_db()

    if args.mode == "report-only":
        logger.info("Generating report from existing data (no scraping)")
        signals = generate_weekly_signals()
        path = generate_weekly_report(signals=signals)
        logger.info("Report saved to %s", path)
        return

    # --- Scrape ---
    rates = run_scrapers(config)
    inserted = insert_rates(rates)
    logger.info("Total records scraped: %d | new inserts: %d", len(rates), inserted)

    if args.mode == "scrape-only":
        logger.info("scrape-only mode — done.")
        return

    if args.mode == "intraday":
        check_intraday_alerts(config)
        logger.info("Intraday check complete.")
        return

    # --- Weekly: full pipeline ---
    logger.info("Running signal analysis …")
    signals = generate_weekly_signals(
        spike_threshold=config.get("analysis", {}).get("spike_threshold_pct", 10.0)
    )

    logger.info("Generating weekly report …")
    report_path = generate_weekly_report(signals=signals)
    logger.info("Weekly pipeline complete. Report: %s", report_path)


if __name__ == "__main__":
    main()
