"""
Signal generation for the freight rate tracker.

Signals produced
----------------
- trend_up / trend_down : rolling 4-week linear trend direction
- spike_up  / spike_down : single-week % change above threshold
- crossover_up / crossover_down : short MA crosses long MA
- yoy_change : year-on-year rate delta
- multi_index_divergence : spread between highest and lowest index for same route
"""

import logging
from datetime import datetime
from typing import Any

import pandas as pd

from database.db import (
    get_rate_history,
    get_cross_index_comparison,
    insert_signal,
    get_latest_rates,
)

logger = logging.getLogger(__name__)

# Thresholds (configurable via config.yaml — defaults here)
SPIKE_THRESHOLD_PCT = 10.0     # % weekly change that triggers a spike signal
SHORT_MA_WEEKS = 4
LONG_MA_WEEKS = 12
TREND_WINDOW = 4               # weeks used for linear trend


# ---------------------------------------------------------------------------
# Low-level detectors
# ---------------------------------------------------------------------------

def detect_spike(
    series: pd.Series,
    threshold_pct: float = SPIKE_THRESHOLD_PCT,
) -> list[dict[str, Any]]:
    """
    Return spike events where week-on-week % change exceeds *threshold_pct*.

    Parameters
    ----------
    series : pd.Series indexed by ISO date string, values = rate_usd.

    Returns list of dicts: {week_ending, pct_change, signal_type}
    """
    if len(series) < 2:
        return []

    s = series.sort_index()
    pct = s.pct_change() * 100
    events = []
    for date, val in pct.items():
        if pd.isna(val):
            continue
        if val >= threshold_pct:
            events.append({"week_ending": date, "value": round(val, 2), "signal_type": "spike_up"})
        elif val <= -threshold_pct:
            events.append({"week_ending": date, "value": round(val, 2), "signal_type": "spike_down"})
    return events


def detect_trend(
    series: pd.Series,
    window: int = TREND_WINDOW,
) -> list[dict[str, Any]]:
    """
    Identify trend direction over a rolling *window*.

    Uses the sign of the linear regression slope for each window.

    Returns list of dicts: {week_ending, value (slope), signal_type}
    """
    if len(series) < window:
        return []

    s = series.sort_index().dropna()
    events = []
    for i in range(window - 1, len(s)):
        window_data = s.iloc[i - window + 1 : i + 1]
        x = list(range(len(window_data)))
        y = window_data.values
        # Simple least-squares slope
        n = len(x)
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        den = sum((xi - mean_x) ** 2 for xi in x)
        slope = num / den if den != 0 else 0.0

        signal_type = "trend_up" if slope > 0 else "trend_down"
        events.append(
            {
                "week_ending": s.index[i],
                "value": round(slope, 4),
                "signal_type": signal_type,
            }
        )
    return events


def detect_crossover(
    series: pd.Series,
    short_window: int = SHORT_MA_WEEKS,
    long_window: int = LONG_MA_WEEKS,
) -> list[dict[str, Any]]:
    """
    Detect golden-cross / death-cross events between short and long moving averages.

    Returns list of dicts: {week_ending, value (spread), signal_type}
    """
    if len(series) < long_window:
        return []

    s = series.sort_index().dropna()
    short_ma = s.rolling(short_window).mean()
    long_ma = s.rolling(long_window).mean()

    above = short_ma > long_ma
    crossovers = above.ne(above.shift())

    events = []
    for date in crossovers[crossovers].index:
        if pd.isna(short_ma.get(date)) or pd.isna(long_ma.get(date)):
            continue
        spread = round(float(short_ma[date] - long_ma[date]), 2)
        signal_type = "crossover_up" if above[date] else "crossover_down"
        events.append({"week_ending": date, "value": spread, "signal_type": signal_type})

    return events


# ---------------------------------------------------------------------------
# High-level orchestrators
# ---------------------------------------------------------------------------

def compute_signals(
    route: str,
    index_name: str | None = None,
    weeks: int = 24,
    spike_threshold: float = SPIKE_THRESHOLD_PCT,
) -> list[dict[str, Any]]:
    """
    Run all signal detectors for a single route and return combined events.

    Parameters
    ----------
    route       : Exact route label as stored in the DB.
    index_name  : Optional — filter to a single index source.
    weeks       : History depth to pull.
    spike_threshold : % change threshold for spike detection.

    Returns
    -------
    list[dict]: Each dict contains: route, index_name, signal_type, value, week_ending, notes
    """
    history = get_rate_history(route, weeks=weeks, index_name=index_name)
    if not history:
        logger.warning("compute_signals: no history for route=%s index=%s", route, index_name)
        return []

    df = pd.DataFrame(history)
    df["week_ending"] = pd.to_datetime(df["week_ending"])
    df = df.sort_values("week_ending")

    all_signals: list[dict[str, Any]] = []

    # Process each index separately if multiple are present
    for idx_name, group in df.groupby("index_name"):
        series = group.set_index("week_ending")["rate_usd"].sort_index()
        series.index = series.index.strftime("%Y-%m-%d")

        for event in detect_spike(series, threshold_pct=spike_threshold):
            all_signals.append(
                {
                    "route": route,
                    "index_name": idx_name,
                    **event,
                    "notes": f"Weekly change: {event['value']:.1f}%",
                }
            )
        for event in detect_trend(series):
            all_signals.append(
                {
                    "route": route,
                    "index_name": idx_name,
                    **event,
                    "notes": f"Slope over {TREND_WINDOW}-week window: {event['value']}",
                }
            )
        for event in detect_crossover(series):
            all_signals.append(
                {
                    "route": route,
                    "index_name": idx_name,
                    **event,
                    "notes": (
                        f"MA{SHORT_MA_WEEKS} vs MA{LONG_MA_WEEKS} spread: {event['value']}"
                    ),
                }
            )

    return all_signals


def _compute_multi_index_divergence(route: str) -> list[dict[str, Any]]:
    """
    Emit a signal when the spread between highest and lowest current index
    rate for a route exceeds 20 % of the mean.
    """
    comparison = get_cross_index_comparison(route)
    if len(comparison) < 2:
        return []

    rates = [r["rate_usd"] for r in comparison]
    max_rate = max(rates)
    min_rate = min(rates)
    mean_rate = sum(rates) / len(rates)
    spread_pct = ((max_rate - min_rate) / mean_rate * 100) if mean_rate else 0

    if spread_pct < 20:
        return []

    week_ending = max(r["week_ending"] for r in comparison)
    return [
        {
            "route": route,
            "index_name": "cross-index",
            "signal_type": "multi_index_divergence",
            "value": round(spread_pct, 2),
            "week_ending": week_ending,
            "notes": (
                f"Spread {spread_pct:.1f}% between "
                f"{max(comparison, key=lambda x: x['rate_usd'])['index_name']} "
                f"and {min(comparison, key=lambda x: x['rate_usd'])['index_name']}"
            ),
        }
    ]


def generate_weekly_signals(
    spike_threshold: float = SPIKE_THRESHOLD_PCT,
) -> list[dict[str, Any]]:
    """
    Run signal detection across ALL routes currently in the database and
    persist new signals via insert_signal().

    Returns the full list of generated signal dicts.
    """
    latest = get_latest_rates()
    routes = list({r["route"] for r in latest})
    logger.info("generate_weekly_signals: processing %d routes", len(routes))

    all_signals: list[dict[str, Any]] = []

    for route in routes:
        signals = compute_signals(route, spike_threshold=spike_threshold)
        divergence = _compute_multi_index_divergence(route)
        signals.extend(divergence)

        for sig in signals:
            try:
                insert_signal(
                    route=sig["route"],
                    signal_type=sig["signal_type"],
                    value=sig.get("value"),
                    week_ending=sig["week_ending"],
                    notes=sig.get("notes", ""),
                )
            except Exception as exc:
                logger.error("generate_weekly_signals: failed to insert signal: %s", exc)

        all_signals.extend(signals)

    logger.info("generate_weekly_signals: generated %d signals total", len(all_signals))
    return all_signals
