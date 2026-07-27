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
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from database.db import (
    get_rate_history,
    get_cross_index_comparison,
    get_latest_rates,
    get_input_cost_history,
    insert_signal,
    log_data_quality_issue,
)
from analysis.route_normaliser import normalise_route

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
SPIKE_MOMENTUM_PCT = 10.0          # WoW % above this → SPIKE
COOLING_MOMENTUM_PCT = -5.0        # WoW % below this → COOLING
DIVERGENCE_THRESHOLD_PCT = 15.0    # FBX vs WCI spread → DIVERGENCE
STRESS_THRESHOLD_PCT = 40.0        # route above 12W avg → STRESS

# A rate whose week_ending is older than this is treated as stale: it is
# excluded from cross-index DIVERGENCE comparisons and from the inflationary
# pressure composite, and is flagged in the report. Without this, a dead
# scraper's last value silently masquerades as current — comparing a
# four-month-old WCI print against a live FBX print manufactures divergence.
STALE_THRESHOLD_DAYS = 14
# Key EU lanes watched for stress. Canonical IDs, so no spelling variants
# need listing — the normaliser resolves every scraper's wording to these.
STRESS_ROUTES = {
    "CN_NEUR",   # Shanghai → Rotterdam / North Europe
    "CN_MED",    # Shanghai → Genoa / Mediterranean
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
    Flag STRESS if the lane is a key EU lane AND its current rate is
    more than STRESS_THRESHOLD_PCT above its 12-week average.

    Parameters
    ----------
    route : Canonical lane ID (e.g. 'CN_NEUR').

    Returns
    -------
    ("STRESS", pct_above_avg) or (None, None)
    """
    if route not in STRESS_ROUTES:
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


def data_age_days(week_ending: Any, as_of: datetime | None = None) -> int | None:
    """
    Age in whole days of a rate dated *week_ending*, measured at report time.

    Returns None when the date cannot be parsed.
    """
    if week_ending is None:
        return None
    ts = pd.to_datetime(week_ending, errors="coerce")
    if pd.isna(ts):
        return None
    reference = as_of or datetime.now(timezone.utc)
    # Compare naive-to-naive; week_ending carries no timezone.
    ref_naive = reference.replace(tzinfo=None)
    return max(0, (ref_naive - ts.to_pydatetime().replace(tzinfo=None)).days)


def is_stale(week_ending: Any, as_of: datetime | None = None) -> bool:
    """True when a rate is older than STALE_THRESHOLD_DAYS."""
    age = data_age_days(week_ending, as_of)
    return age is not None and age > STALE_THRESHOLD_DAYS


def check_index_staleness(
    latest_rates: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Report every index whose freshest observation is stale, and record each
    one in ``data_quality_log`` so a scraper that dies is traceable to the run
    on which it first went quiet.

    Returns
    -------
    dict keyed by index name: {"last_week": str, "age_days": int}
    """
    if latest_rates is None:
        latest_rates = get_latest_rates()

    freshest: dict[str, str] = {}
    for row in latest_rates:
        idx, week = row.get("index_name"), row.get("week_ending")
        if not idx or not week:
            continue
        if idx not in freshest or str(week) > freshest[idx]:
            freshest[idx] = str(week)

    stale: dict[str, dict[str, Any]] = {}
    for idx, week in sorted(freshest.items()):
        age = data_age_days(week)
        if age is None or age <= STALE_THRESHOLD_DAYS:
            continue
        stale[idx] = {"last_week": week, "age_days": age}
        logger.warning(
            "STALE INDEX %s: no data since %s (%d days). Excluded from "
            "divergence checks and the inflation composite.", idx, week, age,
        )
        try:
            log_data_quality_issue(
                issue_type="stale_index",
                index_name=idx,
                week_ending=week,
                notes=(f"{idx} last reported {week} ({age} days ago); "
                       f"threshold is {STALE_THRESHOLD_DAYS} days"),
            )
        except Exception as exc:   # logging must never break the pipeline
            logger.debug("check_index_staleness: could not persist issue: %s", exc)

    if not stale:
        logger.info("check_index_staleness: all indices fresh")
    return stale


def _divergence_flag(
    route: str,
    df_all: pd.DataFrame,
    as_of: datetime | None = None,
) -> tuple[str | None, float | None, float | None, dict[str, int | None]]:
    """
    Compare the latest FBX and WCI rates for the canonical lane *route*.

    A rate older than STALE_THRESHOLD_DAYS is still returned for display but
    takes no part in the divergence test — a dead scraper's last print is not
    evidence that two live indices disagree.

    Returns
    -------
    (label, fbx_rate, wci_rate, ages)
        label : "DIVERGENCE" or None
        ages  : {"fbx": age_days|None, "wci": age_days|None}
    """
    route_df = df_all[df_all["canonical_route_id"] == route]

    fbx_rows = route_df[route_df["index_name"].str.contains("FBX|Freightos", case=False, na=False)]
    wci_rows = route_df[route_df["index_name"].str.contains("WCI|Drewry", case=False, na=False)]

    def _latest(rows: pd.DataFrame) -> tuple[float | None, Any]:
        if rows.empty:
            return None, None
        row = rows.sort_values("week_ending").iloc[-1]
        return row["rate_usd"], row["week_ending"]

    fbx_rate, fbx_week = _latest(fbx_rows)
    wci_rate, wci_week = _latest(wci_rows)

    ages = {
        "fbx": data_age_days(fbx_week, as_of),
        "wci": data_age_days(wci_week, as_of),
    }

    fbx_stale = fbx_rate is not None and is_stale(fbx_week, as_of)
    wci_stale = wci_rate is not None and is_stale(wci_week, as_of)

    rounded_fbx = round(fbx_rate, 2) if fbx_rate is not None else None
    rounded_wci = round(wci_rate, 2) if wci_rate is not None else None

    if fbx_rate is None or wci_rate is None:
        return None, rounded_fbx, rounded_wci, ages

    if fbx_stale or wci_stale:
        logger.debug(
            "divergence skipped for %s: stale input (fbx=%sd, wci=%sd)",
            route, ages["fbx"], ages["wci"],
        )
        return None, rounded_fbx, rounded_wci, ages

    mean_rate = (fbx_rate + wci_rate) / 2
    if mean_rate == 0:
        return None, rounded_fbx, rounded_wci, ages

    spread_pct = abs(fbx_rate - wci_rate) / mean_rate * 100
    label = "DIVERGENCE" if spread_pct >= DIVERGENCE_THRESHOLD_PCT else None
    return label, rounded_fbx, rounded_wci, ages


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

    routes = list({r["canonical_route_id"] for r in latest if r.get("canonical_route_id")})
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

    # Drop indices whose freshest print is stale. A dead scraper's last value
    # would otherwise be carried into the composite as if it were current,
    # anchoring the 4-week change against a months-old observation.
    if "index_name" in df.columns:
        freshest = df.groupby("index_name")["week_ending"].max()
        stale_indices = [idx for idx, wk in freshest.items() if is_stale(wk)]
        if stale_indices:
            kept = df[~df["index_name"].isin(stale_indices)]
            if kept.empty:
                logger.warning(
                    "inflation_score: every index is stale (%s); "
                    "retaining stale data rather than emptying the composite",
                    ", ".join(sorted(stale_indices)),
                )
            else:
                logger.warning(
                    "inflation_score: excluding stale index/indices from the "
                    "freight composite: %s",
                    ", ".join(f"{i} (last {freshest[i]:%Y-%m-%d})" for i in sorted(stale_indices)),
                )
                df = kept

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
        ``canonical_route_id`` is used when present and derived from ``route``
        otherwise, so lanes are grouped per physical lane rather than per
        scraper spelling.
        Typically covers 12 weeks of history per lane.

    Returns
    -------
    dict[canonical_route_id, signal_dict]

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

    # Group by physical lane, not by scraper spelling. Rows written before the
    # canonicalisation migration may lack the column, so derive it on the fly.
    if "canonical_route_id" not in df.columns:
        df["canonical_route_id"] = [
            normalise_route(r, i)
            for r, i in zip(df["route"], df.get("index_name", [None] * len(df)))
        ]
    else:
        df["canonical_route_id"] = df["canonical_route_id"].fillna(
            pd.Series(
                [normalise_route(r, i) for r, i in zip(df["route"], df["index_name"])],
                index=df.index,
            )
        )

    df = df.sort_values(["canonical_route_id", "index_name", "week_ending"])

    routes = df["canonical_route_id"].unique().tolist()
    results: dict[str, dict[str, Any]] = {}

    for route in routes:
        route_df = df[df["canonical_route_id"] == route]

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

        # 3. Cross-index divergence (FBX vs WCI); stale inputs are excluded
        div_label, fbx_rate, wci_rate, index_ages = _divergence_flag(route, df)

        # 4. Geopolitical stress proxy
        stress_label, stress_pct = _stress_flag(route, agg_series)

        # 5. Freshness of this lane's most recent observation
        lane_age = data_age_days(route_df["week_ending"].max())

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
            "data_age_days":    lane_age,
            "is_stale":         lane_age is not None and lane_age > STALE_THRESHOLD_DAYS,
            "fbx_age_days":     index_ages["fbx"],
            "wci_age_days":     index_ages["wci"],
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
    routes = list({r["canonical_route_id"] for r in latest if r.get("canonical_route_id")})
    logger.info("generate_weekly_signals: fetching history for %d lanes", len(routes))

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
        # Determine the most-recent week_ending for this lane
        route_rows = [r for r in all_rows if r.get("canonical_route_id") == route]
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

