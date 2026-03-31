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
- wow_pct                        : week-on-week % change (latest week)
- momentum                       : "SPIKE" | "COOLING" | "STABLE"  (4-week rolling avg)
- divergence                     : "DIVERGENCE" | None  (FBX vs WCI >15% spread)
- stress                         : "STRESS" | None  (key EU routes >40% above 12W avg)
- inflation_score                : 0–100 composite (weighted, 52-week normalised)
- inflationary_pressure_breakdown: per-component breakdown + optional warning
"""

import logging
from typing import Any

import pandas as pd

from database.db import (
    get_rate_history,
    get_cross_index_comparison,
    get_latest_rates,
    get_input_cost_history,
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
# Inflation score weights and indicator keys
# ---------------------------------------------------------------------------
_INFLATION_WEIGHTS: dict[str, float] = {
    "bunker": 0.35,   # VLSFO 0.5% Singapore 4-week % change
    "crude":  0.20,   # Brent crude 4-week % change
    "rates":  0.25,   # freight rate composite 4-week % change
    "bdi":    0.20,   # Baltic Dry Index 4-week % change
}

_BUNKER_INDICATOR = "VLSFO 0.5% - Singapore"
_CRUDE_INDICATOR  = "Brent Crude"
_BDI_INDICATOR    = "Baltic Dry Index"

# History window for min-max normalization
_NORM_WEEKS = 52


# ---------------------------------------------------------------------------
# Per-route signal helpers  (unchanged)
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


# ---------------------------------------------------------------------------
# Inflation score — component helpers
# ---------------------------------------------------------------------------

def _fetch_input_cost_weekly(indicator: str, weeks: int = _NORM_WEEKS) -> pd.Series:
    """
    Pull *indicator* rows from input_costs and resample to a weekly Series.
    Returns an empty Series when data is absent or the DB read fails.
    """
    try:
        rows = get_input_cost_history(indicator, weeks=weeks)
    except Exception as exc:
        logger.warning(
            "inflation_score: DB read failed for indicator '%s': %s", indicator, exc
        )
        return pd.Series(dtype=float)

    if not rows:
        logger.debug("inflation_score: no data for indicator '%s'", indicator)
        return pd.Series(dtype=float)

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    series = df.set_index("date")["value"].sort_index()
    # Resample to weekly end-of-period to align with freight data cadence
    return series.resample("W").last().dropna()


def _fetch_freight_composite_weekly(weeks: int = _NORM_WEEKS) -> pd.Series:
    """
    Build a weekly composite freight rate series (mean across all routes and
    indices) by pulling history for every route currently in the DB.
    Returns an empty Series when no freight data is available.
    """
    try:
        latest = get_latest_rates()
    except Exception as exc:
        logger.warning("inflation_score: could not fetch latest rates: %s", exc)
        return pd.Series(dtype=float)

    routes = list({r["route"] for r in latest})
    if not routes:
        return pd.Series(dtype=float)

    all_rows: list[dict] = []
    for route in routes:
        try:
            all_rows.extend(get_rate_history(route, weeks=weeks))
        except Exception as exc:
            logger.warning(
                "inflation_score: rate_history fetch failed for route '%s': %s", route, exc
            )

    if not all_rows:
        return pd.Series(dtype=float)

    df = pd.DataFrame(all_rows)
    df["week_ending"] = pd.to_datetime(df["week_ending"])
    # Weekly mean across all routes and indices
    weekly = df.groupby("week_ending")["rate_usd"].mean().sort_index()
    weekly.index = weekly.index.to_period("W").to_timestamp("W")  # align to week-end
    return weekly.dropna()


def _4w_pct_change(series: pd.Series) -> float | None:
    """
    Compute the 4-period (4-week) % change using the most-recent values.
    Requires at least 5 data points.
    """
    s = series.dropna().sort_index()
    if len(s) < 5:
        return None
    base = s.iloc[-5]
    curr = s.iloc[-1]
    if base == 0:
        return None
    return round((curr - base) / base * 100, 4)


def _rolling_4w_pct_changes(series: pd.Series) -> pd.Series:
    """Full rolling series of 4-period % changes (used as the normalization window)."""
    return series.pct_change(periods=4).mul(100).dropna()


def _minmax_normalize(value: float, history: pd.Series) -> float:
    """
    Normalize *value* to 0–100 using the min/max of *history*.
    Returns 50.0 when the range is zero (flat history — can't distinguish).
    Clamps to [0, 100].
    """
    h = history.dropna()
    if len(h) < 2:
        return 50.0
    lo, hi = float(h.min()), float(h.max())
    if hi == lo:
        return 50.0
    normalized = (value - lo) / (hi - lo) * 100.0
    return round(max(0.0, min(100.0, normalized)), 1)


# ---------------------------------------------------------------------------
# Inflation score — composite computation
# ---------------------------------------------------------------------------

def _compute_inflation_score() -> dict[str, Any]:
    """
    Weighted inflationary pressure score with per-component breakdown.

    Each component is:
      1. Expressed as a 4-week % change
      2. Normalised 0–100 against the 52-week rolling min-max of that
         same 4-week % change series
      3. Weighted and summed into a composite 0–100 score

    If a component's data is absent (e.g. BDI not yet scraped), its weight
    is redistributed proportionally across the available components.

    Returns
    -------
    dict with keys:
        bunker_fuel_component : float | None
        crude_component       : float | None
        rate_component        : float | None
        bdi_component         : float | None
        composite_score       : float
        warning               : str | None  ("COST SQUEEZE INCOMING" when applicable)
    """
    # ------------------------------------------------------------------
    # 1. Fetch weekly series for each component
    # ------------------------------------------------------------------
    bunker_series  = _fetch_input_cost_weekly(_BUNKER_INDICATOR)
    crude_series   = _fetch_input_cost_weekly(_CRUDE_INDICATOR)
    freight_series = _fetch_freight_composite_weekly()
    bdi_series     = _fetch_input_cost_weekly(_BDI_INDICATOR)

    # ------------------------------------------------------------------
    # 2. Compute 4-week % change and 52-week normalised score per component
    # ------------------------------------------------------------------
    def _score_series(series: pd.Series, label: str) -> float | None:
        current_4w = _4w_pct_change(series)
        if current_4w is None:
            logger.debug("inflation_score: insufficient data for component '%s'", label)
            return None
        norm_history = _rolling_4w_pct_changes(series)
        # Include the current value in the normalization window
        norm_history = pd.concat(
            [norm_history, pd.Series([current_4w])], ignore_index=True
        )
        return _minmax_normalize(current_4w, norm_history)

    components: dict[str, float | None] = {
        "bunker": _score_series(bunker_series,  "bunker"),
        "crude":  _score_series(crude_series,   "crude"),
        "rates":  _score_series(freight_series, "rates"),
        "bdi":    _score_series(bdi_series,     "bdi"),
    }

    # ------------------------------------------------------------------
    # 3. Composite — redistribute weights for missing components
    # ------------------------------------------------------------------
    available = {k: v for k, v in components.items() if v is not None}

    if not available:
        composite = 0.0
        logger.warning(
            "inflation_score: no component data available; returning score=0"
        )
    else:
        total_weight = sum(_INFLATION_WEIGHTS[k] for k in available)
        composite = sum(
            v * (_INFLATION_WEIGHTS[k] / total_weight)
            for k, v in available.items()
        )
        composite = round(composite, 1)

        missing = set(_INFLATION_WEIGHTS) - set(available)
        if missing:
            logger.info(
                "inflation_score: components %s unavailable; weights redistributed",
                sorted(missing),
            )

    # ------------------------------------------------------------------
    # 4. Cost squeeze warning
    # ------------------------------------------------------------------
    bunker_val = components["bunker"]
    rate_val   = components["rates"]
    warning: str | None = None
    if bunker_val is not None and rate_val is not None:
        if bunker_val > 60 and rate_val < 30:
            warning = "COST SQUEEZE INCOMING"
            logger.warning(
                "inflation_score: COST SQUEEZE INCOMING — "
                "bunker_fuel_component=%.1f, rate_component=%.1f",
                bunker_val,
                rate_val,
            )

    return {
        "bunker_fuel_component": bunker_val,
        "crude_component":       components["crude"],
        "rate_component":        rate_val,
        "bdi_component":         components["bdi"],
        "composite_score":       composite,
        "warning":               warning,
    }


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
        wow_pct                        : float | None
        momentum                       : "SPIKE" | "COOLING" | "STABLE"
        momentum_vs_4w                 : float | None
        divergence                     : "DIVERGENCE" | None
        fbx_rate                       : float | None
        wci_rate                       : float | None
        stress                         : "STRESS" | None
        stress_pct_above               : float | None
        inflation_score                : float   — composite 0–100
        four_week_avg                  : float | None
        inflationary_pressure_breakdown: dict    — per-component scores + warning
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
            "wow_pct":          wow,
            "momentum":         momentum,
            "momentum_vs_4w":   momentum_vs_4w,
            "divergence":       div_label,
            "fbx_rate":         fbx_rate,
            "wci_rate":         wci_rate,
            "stress":           stress_label,
            "stress_pct_above": stress_pct,
            "inflation_score":  0.0,   # back-filled below
            "four_week_avg":    four_week_avg,
            "inflationary_pressure_breakdown": {},  # back-filled below
        }

    # 5. Inflationary pressure score — portfolio-level, same for all routes
    breakdown = _compute_inflation_score()
    composite  = breakdown["composite_score"]

    for route in results:
        results[route]["inflation_score"] = composite
        results[route]["inflationary_pressure_breakdown"] = breakdown

    logger.info(
        "generate_signals: processed %d routes | inflation_score=%.1f%s",
        len(results),
        composite,
        " | ⚠ COST SQUEEZE INCOMING" if breakdown.get("warning") else "",
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

        breakdown = sig.get("inflationary_pressure_breakdown", {})

        # Persist each non-None signal label
        for signal_type, value, notes in [
            ("wow_pct",        sig["wow_pct"],        f"WoW change: {sig['wow_pct']}%"),
            ("momentum",       sig["momentum"],        f"vs 4W avg: {sig['momentum_vs_4w']}%"),
            ("divergence",     sig["divergence"],      f"FBX={sig['fbx_rate']} WCI={sig['wci_rate']}"),
            ("stress",         sig["stress"],          f"{sig['stress_pct_above']}% above 12W avg"),
            ("inflation_score",sig["inflation_score"], f"Composite score: {sig['inflation_score']}"),
            (
                "inflation_breakdown",
                breakdown.get("composite_score"),
                (
                    f"bunker={breakdown.get('bunker_fuel_component')} "
                    f"crude={breakdown.get('crude_component')} "
                    f"rates={breakdown.get('rate_component')} "
                    f"bdi={breakdown.get('bdi_component')}"
                    + (f" | {breakdown['warning']}" if breakdown.get("warning") else "")
                ),
            ),
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
                    "route":       route,
                    "signal_type": signal_type,
                    "value":       value,
                    "week_ending": week_ending,
                    "notes":       notes,
                    **{k: sig[k] for k in sig if k != signal_type},
                }
            )

    logger.info("generate_weekly_signals: persisted signals for %d routes", len(signals_by_route))
    return flat

