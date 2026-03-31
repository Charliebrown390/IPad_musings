"""
Crude oil spot price fetcher via yfinance.

Tickers
-------
BZ=F  — Brent Crude (ICE futures front month, USD/bbl)
CL=F  — WTI Crude   (NYMEX futures front month, USD/bbl)

Returns
-------
list[dict]: Each item contains:
    commodity, price_usd, date, source
"""

import logging
from datetime import datetime
from typing import Any

import yfinance as yf

logger = logging.getLogger(__name__)

TICKERS: dict[str, str] = {
    "Brent Crude": "BZ=F",
    "WTI Crude":   "CL=F",
}

SOURCE = "yfinance / ICE-NYMEX futures"


def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def scrape_crude() -> list[dict[str, Any]]:
    """
    Fetch the latest Brent and WTI crude spot prices.

    Uses yfinance to pull the most recent trading day's closing price.
    Falls back to the previous close if today's session is not yet settled.

    Returns
    -------
    list[dict]: Each item contains:
        commodity, price_usd, date, source
    """
    results: list[dict[str, Any]] = []

    for commodity, ticker_symbol in TICKERS.items():
        try:
            ticker = yf.Ticker(ticker_symbol)
            # "5d" gives the last 5 trading days; we take the most recent close
            hist = ticker.history(period="5d")

            if hist.empty:
                logger.warning(
                    "[%s] crude: no data returned for %s (%s)",
                    _today(), commodity, ticker_symbol,
                )
                continue

            latest_row  = hist.iloc[-1]
            price       = float(latest_row["Close"])
            trade_date  = hist.index[-1].strftime("%Y-%m-%d")

            if price <= 0:
                logger.warning(
                    "[%s] crude: non-positive price %.2f for %s — skipping",
                    _today(), price, commodity,
                )
                continue

            results.append({
                "commodity": commodity,
                "price_usd": round(price, 2),
                "date":      trade_date,
                "source":    SOURCE,
            })
            logger.info(
                "[%s] crude: %s (%s) = $%.2f on %s",
                _today(), commodity, ticker_symbol, price, trade_date,
            )

        except Exception as exc:
            logger.error(
                "[%s] crude: failed to fetch %s (%s): %s",
                _today(), commodity, ticker_symbol, exc,
            )

    logger.info("[%s] crude: fetched %d record(s)", _today(), len(results))
    return results
