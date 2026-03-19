"""
Signal generation for the freight rate tracker.

Public API
----------
generate_signals(df)
    Primary entry point. Takes a 12-week history DataFrame and returns a
    dict keyed by route, each value being a dict of signal labels and
    supporting numeric values.

generate_weekly_signals()
    Orchestrator that pulls history from the DB, calls generate_signals(),
    and persists results via insert_signal(). Returns the flat signal list.

Signal types produced
---------------------
- wow_pct          : week-on-week % change (latest week)
- momentum         : "SPIKE" | "COOLING" | "STABLE"  (4-week rolling avg)
- divergence       : "DIVERGENCE" | None  (FBX vs WCI >15% spread)
- stress           : "STRESS" | None  (key EU routes >40% above 12W avg)
- inflation_score  : 0–100 composite across all routes
"""

import logging
from typing import Any

import pandas as pd

from database.db import (
    get_rate_history,
    get_cross_index_comparison,
    get_latest_rates,
    insert_signal,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
SPIKE_MOMENTUM_PCT = 10.0          # WoW % above this → SPIKE
COOLING_MOMENTUM_PCT = -5.0        # WoW % below this → COOLING
DIVERGENCE_THRESHOLD_PCT = 15.0    # FBX vs WCI spread → DIVERGENCE
STRESS_THRESHOLD_PCT = 40.0        # route above 12W avg → STRESS
STRESS_ROUTES = {
    "Shanghai → Rotterdam",
    "Shanghai → Genoa",
    # common alternative spellings that scrapers may produce
    "Shanghai/Rotterdam",
    "Shanghai/Genoa",
    "SHANGHAI-ROTTERDAM",
    "SHANGHAI-GENOA",
}


# ---------------------------------------------------------------------------
# Per-route signal helpers
# ---------------------------------------------------------------------------

def _wow_pct_change(series: pd.Series) -> float | None:
    """
    Return the week-on-week % change for the most-recent data point.

    Parameters
    ----------
    series : pd.Series
        Values = rate_usd, sorted ascending by date index.
    """
    s = series.dropna().sort_index()
    if len(s) < 2:
        return None
    prev, curr = s.iloc[-2], s.iloc[-1]
    if prev == 0:
        return None
    return round((curr - prev) / prev * 100, 2)


def _momentum_label(series: pd.Series) -> tuple[str, float | None]:
    """
    Compare the latest rate against the 4-week rolling average.

    Returns
    -------
    (label, pct_vs_4w_avg)  where label is "SPIKE" | "COOLING" | "STABLE"
    """
    s = series.dropna().sort_index()
    if len(s) < 2:
        return "STABLE", None

    window = min(4, len(s) - 1)
    rolling_avg = s.iloc[-window - 1 : -1].mean()
    if rolling_avg == 0:
        return "STABLE", None

    current = s.iloc[-1]
    pct = (current - rolling_avg) / rolling_avg * 100

    if pct >= SPIKE_MOMENTUM_PCT:
        label = "SPIKE"
    elif pct <= COOLING_MOMENTUM_PCT:
        label = "COOLING"
    else:
        label = "STABLE"

    return label, round(pct, 2)


def _stress_flag(route: str, series: pd.Series) -> tuple[str | None, float | None]:
    """
    Flag STRESS if the route is a key EU lane AND its current rate is
    more than STRESS_THRESHOLD_PCT above its 12-week average.

    Returns
    -------
    ("STRESS", pct_above_avg) or (None, None)
    """
    # Normalise for comparison
    route_upper = route.upper().replace(" ", "").replace("→", "-").replace("/", "-")
    is_stress_route = any(
        r.upper().replace(" ", "").replace("→", "-").replace("/", "-") in route_upper
        or route_upper in r.upper().replace(" ", "").replace("→", "-").replace("/", "-")
        for r in STRESS_ROUTES
    )
    if not is_stress_route:
        return None, None

    s = series.dropna().sort_index()
    if len(s) < 2:
        return None, None

    avg_12w = s.mean()
    if avg_12w == 0:
        return None, None

    current = s.iloc[-1]
    pct_above = (current - avg_12w) / avg_12w * 100

    if pct_above >= STRESS_THRESHOLD_PCT:
        return "STRESS", round(pct_above, 2)
    return None, None


def _divergence_flag(
    route: str,
    df_all: pd.DataFrame,
) -> tuple[str | None, float | None, float | None]:
    """
    Compare the latest FBX and WCI rates for *route*.

    Returns
    -------
    ("DIVERGENCE", fbx_rate, wci_rate)  or  (None, fbx_rate, wci_rate)
    The rates may be None if the index has no data for this route.
    """
    route_df = df_all[df_all["route"] == route]

    fbx_rows = route_df[route_df["index_name"].str.contains("FBX|Freightos", case=False, na=False)]
    wci_rows = route_df[route_df["index_name"].str.contains("WCI|Drewry", case=False, na=False)]

    fbx_rate = fbx_rows.sort_values("week_ending").iloc[-1]["rate_usd"] if not fbx_rows.empty else None
    wci_rate = wci_rows.sort_values("week_ending").iloc[-1]["rate_usd"] if not wci_rows.empty else None

    if fbx_rate is None or wci_rate is None:
        return None, fbx_rate, wci_rate

    mean_rate = (fbx_rate + wci_rate) / 2
    if mean_rate == 0:
        return None, fbx_rate, wci_rate

    spread_pct = abs(fbx_rate - wci_rate) / mean_rate * 100
    label = "DIVERGENCE" if spread_pct >= DIVERGENCE_THRESHOLD_PCT else None
    return label, round(fbx_rate, 2), round(wci_rate, 2)


def _inflation_score(route_wow_pcts: list[float]) -> float:
    """
    Composite inflationary pressure score, normalised 0–100.

    Uses the mean of all positive WoW % changes, capped at 50 % for
    normalisation (i.e. a 50 %+ average maps to a score of 100).
    """
    if not route_wow_pcts:
        return 0.0
    positive = [p for p in route_wow_pcts if p > 0]
    if not positive:
        return 0.0
    mean_positive = sum(positive) / len(positive)
    score = min(mean_positive / 50.0 * 100, 100.0)
    return round(score, 1)


# ---------------------------------------------------------------------------
# Primary public function
# ---------------------------------------------------------------------------

def generate_signals(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """
    Compute all signals for every route present in *df*.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns: index_name, route, rate_usd, week_ending.
        Typically covers 12 weeks of history per route.

    Returns
    -------
    dict[route_str, signal_dict]

    Each signal_dict contains:
        wow_pct          : float | None   — week-on-week % change
        momentum         : "SPIKE" | "COOLING" | "STABLE"
        momentum_vs_4w   : float | None   — % vs 4-week rolling avg
        divergence       : "DIVERGENCE" | None
        fbx_rate         : float | None   — latest FBX rate for route
        wci_rate         : float | None   — latest WCI rate for route
        stress           : "STRESS" | None
        stress_pct_above : float | None   — % above 12-week avg (stress routes)
        inflation_score  : float          — 0–100 composite (same value for all routes)
        four_week_avg    : float | None   — 4-week rolling average of rate_usd
    """
    if df.empty:
        logger.warning("generate_signals: received empty DataFrame")
        return {}

    required_cols = {"index_name", "route", "rate_usd", "week_ending"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"generate_signals: DataFrame missing columns: {missing}")

    df = df.copy()
    df["week_ending"] = pd.to_datetime(df["week_ending"])
    df = df.sort_values(["route", "index_name", "week_ending"])

    routes = df["route"].unique().tolist()
    results: dict[str, dict[str, Any]] = {}
    wow_pcts_all: list[float] = []

    for route in routes:
        route_df = df[df["route"] == route]

        # Aggregate across all indices for this route (mean if multiple)
        agg_series = (
            route_df.groupby("week_ending")["rate_usd"]
            .mean()
            .sort_index()
        )

        # 1. Week-on-week % change
        wow = _wow_pct_change(agg_series)
        if wow is not None:
            wow_pcts_all.append(wow)

        # 2. Momentum label (4-week rolling avg vs current)
        momentum, momentum_vs_4w = _momentum_label(agg_series)

        # 4-week average (for report table)
        window = min(4, len(agg_series))
        four_week_avg = round(agg_series.iloc[-window:].mean(), 2) if window > 0 else None

        # 3. Cross-index divergence (FBX vs WCI)
        div_label, fbx_rate, wci_rate = _divergence_flag(route, df)

        # 4. Geopolitical stress proxy
        stress_label, stress_pct = _stress_flag(route, agg_series)

        results[route] = {
            "wow_pct": wow,
            "momentum": momentum,
            "momentum_vs_4w": momentum_vs_4w,
            "divergence": div_label,
            "fbx_rate": fbx_rate,
            "wci_rate": wci_rate,
            "stress": stress_label,
            "stress_pct_above": stress_pct,
            "inflation_score": 0.0,   # back-filled below after all routes processed
            "four_week_avg": four_week_avg,
        }

    # 5. Inflationary pressure score (same value for every route — portfolio-level)
    score = _inflation_score(wow_pcts_all)
    for route in results:
        results[route]["inflation_score"] = score

    logger.info(
        "generate_signals: processed %d routes, inflation_score=%.1f",
        len(results),
        score,
    )
    return results


# ---------------------------------------------------------------------------
# DB-backed orchestrator (called from main.py)
# ---------------------------------------------------------------------------

def generate_weekly_signals(
    spike_threshold: float = SPIKE_MOMENTUM_PCT,
) -> list[dict[str, Any]]:
    """
    Pull 12 weeks of history from the DB, run generate_signals(), persist
    results via insert_signal(), and return a flat list of signal dicts.

    Parameters
    ----------
    spike_threshold : float
        Overrides SPIKE_MOMENTUM_PCT if supplied from config.
    """
    latest = get_latest_rates()
    routes = list({r["route"] for r in latest})
    logger.info("generate_weekly_signals: fetching history for %d routes", len(routes))

    all_rows: list[dict] = []
    for route in routes:
        history = get_rate_history(route, weeks=12)
        all_rows.extend(history)

    if not all_rows:
        logger.warning("generate_weekly_signals: no history rows found in DB")
        return []

    df = pd.DataFrame(all_rows)
    signals_by_route = generate_signals(df)

    flat: list[dict[str, Any]] = []
    for route, sig in signals_by_route.items():
        # Determine the most-recent week_ending for this route
        route_rows = [r for r in all_rows if r["route"] == route]
        week_ending = max(r["week_ending"] for r in route_rows) if route_rows else ""

        # Persist each non-None signal label
        for signal_type, value, notes in [
            ("wow_pct", sig["wow_pct"], f"WoW change: {sig['wow_pct']}%"),
            ("momentum", sig["momentum"], f"vs 4W avg: {sig['momentum_vs_4w']}%"),
            ("divergence", sig["divergence"], f"FBX={sig['fbx_rate']} WCI={sig['wci_rate']}"),
            ("stress", sig["stress"], f"{sig['stress_pct_above']}% above 12W avg"),
            ("inflation_score", sig["inflation_score"], f"Composite score: {sig['inflation_score']}"),
        ]:
            if value is None:
                continue
            try:
                insert_signal(
                    route=route,
                    signal_type=str(signal_type),
                    value=float(value) if isinstance(value, (int, float)) else None,
                    week_ending=week_ending,
                    notes=notes,
                )
            except Exception as exc:
                logger.error("generate_weekly_signals: insert_signal failed: %s", exc)

            flat.append(
                {
                    "route": route,
                    "signal_type": signal_type,
                    "value": value,
                    "week_ending": week_ending,
                    "notes": notes,
                    **{k: sig[k] for k in sig if k != signal_type},
                }
            )

    logger.info("generate_weekly_signals: persisted signals for %d routes", len(signals_by_route))
    return flat
