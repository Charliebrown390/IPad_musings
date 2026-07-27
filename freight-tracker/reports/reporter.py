"""
Report generation and alert dispatch for the freight rate tracker.

Outputs
-------
1. Markdown weekly report
   - Summary table: Route | FBX Rate | WCI Rate | WoW % | 4W Avg | Signal
   - 3-sentence executive summary via claude-haiku-4-5-20251001

2. Telegram delivery
   - Prepends 🚨 alert header if any route carries a SPIKE or STRESS signal
   - Falls back to saving reports/output/latest_report.md on send failure

All credentials are read exclusively from environment variables:
    ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anthropic
import httpx
import pandas as pd
import yaml

from database.db import get_latest_rates, get_rate_history, insert_alert, get_latest_news_signal
from analysis.route_normaliser import display_name
from analysis.signals import STALE_THRESHOLD_DAYS, data_age_days, is_stale

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"
CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
FALLBACK_REPORT = OUTPUT_DIR / "latest_report.md"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_rate(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"${value:,.0f}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    arrow = "▲" if value >= 0 else "▼"
    return f"{arrow} {abs(value):.1f}%"


def _signal_label(sig: dict[str, Any]) -> str:
    """
    Produce a single display label from a route's signal dict.
    Priority: STRESS > SPIKE/COOLING > DIVERGENCE > STABLE
    """
    if sig.get("stress") == "STRESS":
        return "🔴 STRESS"
    momentum = sig.get("momentum", "STABLE")
    if momentum == "SPIKE":
        return "🟠 SPIKE"
    if momentum == "COOLING":
        return "🔵 COOLING"
    if sig.get("divergence") == "DIVERGENCE":
        return "🟡 DIVERGENCE"
    return "🟢 STABLE"


def _has_urgent_signal(signals_by_route: dict[str, dict]) -> bool:
    """Return True if any route is SPIKE or STRESS."""
    for sig in signals_by_route.values():
        if sig.get("momentum") == "SPIKE" or sig.get("stress") == "STRESS":
            return True
    return False


# ---------------------------------------------------------------------------
# Markdown report builder
# ---------------------------------------------------------------------------

def _build_summary_table(
    latest_rates: list[dict],
    signals_by_route: dict[str, dict[str, Any]],
) -> str:
    """
    Build the Route | FBX Rate | WCI Rate | WoW % | 4W Avg | Signal table.
    One row per canonical lane, merging FBX and WCI columns.
    """
    # Index latest rates by (canonical lane, index_name), keeping the
    # as-of week so staleness can be shown alongside the value.
    rate_lookup: dict[tuple[str, str], tuple[float, Any]] = {}
    for row in latest_rates:
        key = (row.get("canonical_route_id") or row["route"], row["index_name"])
        rate_lookup[key] = (row["rate_usd"], row.get("week_ending"))

    routes = sorted({r.get("canonical_route_id") or r["route"] for r in latest_rates})

    header = "| Route | FBX Rate | WCI Rate | WoW % | 4W Avg | Signal |"
    sep    = "|-------|----------|----------|-------|--------|--------|"
    rows = [header, sep]

    def _pick(route: str, *needles: str) -> tuple[float | None, Any]:
        for (r, idx), (value, week) in rate_lookup.items():
            if r == route and any(n in idx for n in needles):
                return value, week
        return None, None

    def _fmt_with_age(value: float | None, week: Any) -> str:
        """Render a rate, marking it ⚠ with its as-of date when stale."""
        if value is None:
            return "N/A"
        if week is not None and is_stale(week):
            # Plain inline form: renders identically as Markdown, as HTML on
            # the Pages site, and as plain text in a Telegram message.
            return f"⚠ {_fmt_rate(value)} (as of {str(week)[:10]})"
        return _fmt_rate(value)

    for route in routes:
        fbx, fbx_week = _pick(route, "FBX", "Freightos")
        wci, wci_week = _pick(route, "WCI", "Drewry")

        sig = signals_by_route.get(route, {})
        wow = _fmt_pct(sig.get("wow_pct"))
        avg4w = _fmt_rate(sig.get("four_week_avg"))
        label = _signal_label(sig)

        rows.append(
            f"| {display_name(route)} | {_fmt_with_age(fbx, fbx_week)} "
            f"| {_fmt_with_age(wci, wci_week)} | {wow} | {avg4w} | {label} |"
        )

    return "\n".join(rows)


def _build_staleness_header(latest_rates: list[dict]) -> list[str]:
    """
    Warn about any index whose freshest data is older than the threshold.

    Rendered on every report so a scraper that has quietly started failing is
    visible immediately, rather than being discovered months later.
    """
    freshest: dict[str, str] = {}
    for row in latest_rates:
        idx = row.get("index_name")
        week = row.get("week_ending")
        if not idx or not week:
            continue
        if idx not in freshest or str(week) > freshest[idx]:
            freshest[idx] = str(week)

    stale = {
        idx: week for idx, week in freshest.items() if is_stale(week)
    }
    if not stale:
        return []

    noun = "index has" if len(stale) == 1 else "indices have"
    # Every line is prefixed with '>' including the separator, otherwise a
    # bare blank line would terminate the blockquote.
    lines = [
        f"> ⚠ **STALE DATA WARNING** — {len(stale)} {noun} not reported "
        f"in over {STALE_THRESHOLD_DAYS} days:",
        ">",
    ]
    for idx, week in sorted(stale.items()):
        age = data_age_days(week)
        lines.append(
            f"> - **{idx}** — last data {week} ({age} days old). "
            f"Excluded from divergence checks and the inflation composite."
        )
    lines += [">", ""]
    return lines


def _build_news_sentiment_section(news: dict[str, Any]) -> list[str]:
    """
    Build the News Sentiment Risk markdown block from a news_signals record.
    Returns a list of lines (no trailing blank line — caller adds spacing).
    """
    geo   = news.get("geopolitical_score",  0.0)
    lab   = news.get("labour_score",         0.0)
    port  = news.get("port_score",           0.0)
    events         = news.get("key_events",      []) or []
    affected_routes = news.get("affected_routes", []) or []

    def _risk_label(score: float) -> str:
        if score >= 70:
            return "🔴 HIGH"
        if score >= 40:
            return "🟠 MODERATE"
        return "🟢 LOW"

    lines = [
        "## News Sentiment Risk",
        "",
        "| Risk Category | Score (0–100) | Level |",
        "|---------------|:-------------:|-------|",
        f"| Geopolitical Risk      | {geo:.0f} | {_risk_label(geo)} |",
        f"| Labour Disruption Risk | {lab:.0f} | {_risk_label(lab)} |",
        f"| Port Congestion Risk   | {port:.0f} | {_risk_label(port)} |",
        "",
    ]

    def _as_text(item: object) -> str:
        if isinstance(item, dict):
            return str(
                item.get("event")
                or item.get("route")
                or item.get("description")
                or item.get("title")
                or item.get("name")
                or item
            )
        return str(item)

    if events:
        lines.append("**Key Events Detected:**")
        lines.extend(f"- {_as_text(e)}" for e in events[:3])
        lines.append("")

    if affected_routes:
        lines.append(
            "**Routes at Risk:** " + " · ".join(_as_text(r) for r in affected_routes)
        )
        lines.append("")

    return lines


def _build_markdown_report(
    latest_rates: list[dict],
    signals_by_route: dict[str, dict[str, Any]],
    ai_summary: str | None,
    report_date: str,
    news_signal: dict[str, Any] | None = None,
) -> str:
    urgent = _has_urgent_signal(signals_by_route)
    header_flag = "🚨 " if urgent else ""

    lines = [
        f"# {header_flag}Freight Rate Weekly Report — {report_date}",
        "",
    ]

    # Surface dead scrapers before anything else — every number below is only
    # as trustworthy as the freshness of the index behind it.
    lines += _build_staleness_header(latest_rates)

    if ai_summary:
        lines += [
            "## Executive Summary",
            "",
            ai_summary,
            "",
            "---",
            "",
        ]

    inflation_score = next(
        (s.get("inflation_score") for s in signals_by_route.values() if s.get("inflation_score") is not None),
        None,
    )
    breakdown = next(
        (s.get("inflationary_pressure_breakdown") for s in signals_by_route.values()
         if s.get("inflationary_pressure_breakdown")),
        None,
    )
    if inflation_score is not None:
        lines += [f"**Inflationary Pressure Score: {inflation_score:.0f} / 100**", ""]

    if breakdown:
        warning = breakdown.get("warning")
        if warning:
            lines += [f"⚠️ **{warning}** — input costs rising faster than freight rates", ""]

        def _fmt_component(val: float | None) -> str:
            return f"{val:.0f}" if val is not None else "N/A"

        lines += [
            "| Component | Score (0–100) | Weight |",
            "|-----------|--------------|--------|",
            f"| Bunker Fuel (VLSFO Singapore 4W Δ) | {_fmt_component(breakdown.get('bunker_fuel_component'))} | 35% |",
            f"| Brent Crude (4W Δ)                 | {_fmt_component(breakdown.get('crude_component'))} | 20% |",
            f"| Freight Rate Composite (4W Δ)       | {_fmt_component(breakdown.get('rate_component'))} | 25% |",
            f"| Baltic Dry Index (4W Δ)             | {_fmt_component(breakdown.get('bdi_component'))} | 20% |",
            "",
        ]

    if news_signal:
        lines += _build_news_sentiment_section(news_signal)
        lines += ["---", ""]

    lines += [
        "## Rate Summary",
        "",
        _build_summary_table(latest_rates, signals_by_route),
        "",
        "---",
        f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC_",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Anthropic executive summary
# ---------------------------------------------------------------------------

def _build_signal_summary_text(signals_by_route: dict[str, dict[str, Any]]) -> str:
    """Serialise signals to a compact text block for the LLM prompt."""
    lines = []
    for route, sig in signals_by_route.items():
        parts = [f"Route: {route}"]
        if sig.get("wow_pct") is not None:
            parts.append(f"WoW={sig['wow_pct']:+.1f}%")
        parts.append(f"momentum={sig.get('momentum','STABLE')}")
        if sig.get("divergence"):
            parts.append(f"divergence=FBX${sig.get('fbx_rate','?')} vs WCI${sig.get('wci_rate','?')}")
        if sig.get("stress"):
            parts.append(f"STRESS({sig.get('stress_pct_above',0):.0f}% above 12W avg)")
        lines.append(" | ".join(parts))
    score = next((s["inflation_score"] for s in signals_by_route.values() if s.get("inflation_score")), 0)
    lines.append(f"Composite inflationary pressure score: {score:.0f}/100")
    return "\n".join(lines)


def _generate_executive_summary(
    signals_by_route: dict[str, dict[str, Any]],
    news_signal: dict[str, Any] | None = None,
) -> str | None:
    """
    Call claude-haiku-4-5-20251001 to produce a detailed executive summary.
    Returns None if ANTHROPIC_API_KEY is unset or the call fails.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.info("ANTHROPIC_API_KEY not set — skipping executive summary")
        return None

    # --- {signals} block ---
    signals_text = _build_signal_summary_text(signals_by_route)

    # --- {inflation_breakdown} block ---
    breakdown = next(
        (s.get("inflationary_pressure_breakdown")
         for s in signals_by_route.values()
         if s.get("inflationary_pressure_breakdown")),
        {},
    )

    def _fmt(v: float | None) -> str:
        return f"{v:.1f}" if v is not None else "N/A"

    inflation_breakdown_text = (
        f"bunker_fuel_component={_fmt(breakdown.get('bunker_fuel_component'))}/100  "
        f"crude_component={_fmt(breakdown.get('crude_component'))}/100  "
        f"rate_component={_fmt(breakdown.get('rate_component'))}/100  "
        f"bdi_component={_fmt(breakdown.get('bdi_component'))}/100  "
        f"composite={_fmt(breakdown.get('composite_score'))}/100"
    )

    # --- {bunker_change} ---
    # Normalised 0-100 pressure score for bunker (higher = more pressure)
    bunker_change = _fmt(breakdown.get("bunker_fuel_component"))

    # --- {news_signals} block ---
    if news_signal:
        def _event_str(item: object) -> str:
            if isinstance(item, dict):
                return str(item.get("event") or item.get("description") or item.get("title") or item)
            return str(item)
        key_events = "; ".join(_event_str(e) for e in (news_signal.get("key_events") or [])) or "none detected"
        news_text = (
            f"geopolitical_risk={_fmt(news_signal.get('geopolitical_score'))}/100  "
            f"labour_disruption={_fmt(news_signal.get('labour_score'))}/100  "
            f"port_congestion={_fmt(news_signal.get('port_score'))}/100  "
            f"key_events=[{key_events}]"
        )
    else:
        news_text = "not available"

    # --- {cost_squeeze_flag} ---
    cost_squeeze_flag = bool(breakdown.get("warning") == "COST SQUEEZE INCOMING")

    prompt = (
        "You are a freight market analyst writing for an insurance investment "
        "team managing fixed income and multi-asset portfolios.\n\n"
        "Given:\n"
        f"- Freight rate signals: {signals_text}\n"
        f"- Inflationary pressure breakdown: {inflation_breakdown_text}\n"
        f"- Bunker fuel 4W change: {bunker_change}%\n"
        f"- News sentiment scores: {news_text}\n"
        f"- COST SQUEEZE WARNING active: {cost_squeeze_flag}\n\n"
        "Write a detailed executive summary covering:\n"
        "(1) demand trends by region,\n"
        "(2) inflationary cost pressures distinguishing between input costs "
        "already materialised vs those not yet passed through to rates,\n"
        "(3) geopolitical and labour route risk,\n"
        "(4) one actionable implication for an insurance investment portfolio "
        "(e.g. implications for inflation assumptions, credit exposure to "
        "shipping sector, or reinsurance cost outlook)."
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except anthropic.APIStatusError as exc:
        logger.error("Anthropic API error %s: %s", exc.status_code, exc.message)
        return None
    except Exception as exc:
        logger.error("Executive summary generation failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Telegram delivery
# ---------------------------------------------------------------------------

def _escape_html(text: str) -> str:
    """Escape the three characters reserved in Telegram HTML mode."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def _send_telegram_async(text: str, token: str, chat_id: str) -> None:
    """
    Send *text* in ≤4 096-char chunks via the Telegram Bot API using HTML
    parse mode, driven by httpx (already a project dependency — avoids the
    python-telegram-bot cryptography/cffi C-extension requirement).
    """
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient(timeout=30) as client:
        for start in range(0, len(text), 4096):
            chunk = text[start : start + 4096]
            resp = await client.post(
                url,
                json={"chat_id": chat_id, "text": chunk, "parse_mode": "HTML"},
            )
            resp.raise_for_status()


def _send_telegram(text: str) -> bool:
    """
    Dispatch *text* via Telegram. Reads credentials from env vars only.
    Returns True on success, False on failure (caller handles fallback).
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        logger.info("Telegram credentials not set — skipping notification")
        return False

    try:
        asyncio.run(_send_telegram_async(text, token, chat_id))
        logger.info("Telegram notification sent to chat_id=%s", chat_id)
        return True
    except Exception as exc:
        logger.error("Telegram send failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_weekly_report(
    signals_by_route: dict[str, dict[str, Any]] | None = None,
    latest_rates: list[dict] | None = None,
    news_signal: dict[str, Any] | None = None,
) -> Path:
    """
    Build the weekly Markdown report, call the Anthropic API for an executive
    summary, and deliver via Telegram (with local fallback).

    Parameters
    ----------
    signals_by_route : dict, optional
        Output of analysis.generate_signals(df). If None, an empty dict
        is used (report will have N/A signal columns).
    latest_rates : list[dict], optional
        Pre-fetched latest rates. If None, fetched from the DB.
    news_signal : dict, optional
        Output of scrape_news_sentiment() (or get_latest_news_signal()).
        If None, the News Sentiment Risk section is omitted from the report.

    Returns
    -------
    Path: Absolute path to the saved report file.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if latest_rates is None:
        latest_rates = get_latest_rates()

    if signals_by_route is None:
        signals_by_route = {}

    # Fall back to the most-recent stored signal when none is passed in
    if news_signal is None:
        try:
            news_signal = get_latest_news_signal()
        except Exception as exc:
            logger.warning("generate_weekly_report: could not fetch news signal: %s", exc)

    report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 1. AI executive summary
    ai_summary = _generate_executive_summary(signals_by_route, news_signal=news_signal)

    # 2. Markdown report
    report_md = _build_markdown_report(
        latest_rates=latest_rates,
        signals_by_route=signals_by_route,
        ai_summary=ai_summary,
        report_date=report_date,
        news_signal=news_signal,
    )

    # 3. Save dated copy
    dated_path = OUTPUT_DIR / f"weekly_report_{report_date}.md"
    dated_path.write_text(report_md, encoding="utf-8")
    logger.info("Weekly report saved to %s", dated_path)

    # 4. Telegram — use HTML parse mode (only &, <, > need escaping)
    urgent = _has_urgent_signal(signals_by_route)
    tg_header = "🚨 <b>FREIGHT ALERT</b> — urgent signals detected\n\n" if urgent else ""

    tg_lines = [f"{tg_header}<b>Freight Rate Report — {_escape_html(report_date)}</b>", ""]
    if ai_summary:
        tg_lines += [_escape_html(ai_summary), ""]
    tg_lines.append("<b>Route Signals:</b>")
    for route, sig in signals_by_route.items():
        label = _signal_label(sig)
        wow_str = f"{sig['wow_pct']:+.1f}%" if sig.get("wow_pct") is not None else "N/A"
        tg_lines.append(
            f"• {_escape_html(route)}: {_escape_html(label)} ({_escape_html(wow_str)} WoW)"
        )

    tg_text = "\n".join(tg_lines)

    if not _send_telegram(tg_text):
        # Fallback: persist a copy at the well-known path
        FALLBACK_REPORT.write_text(report_md, encoding="utf-8")
        logger.info("Telegram unavailable — report saved to %s", FALLBACK_REPORT)

    return dated_path


def generate_intraday_alert(
    route: str,
    alert_type: str,
    message: str,
    notify: bool = True,
) -> None:
    """
    Log an intraday alert to the DB and optionally send a Telegram notification.

    Parameters
    ----------
    route       : Affected route label.
    alert_type  : e.g. 'spike_up', 'threshold_breach', 'stress'.
    message     : Human-readable alert message.
    notify      : Set False to skip Telegram dispatch.
    """
    insert_alert(route=route, alert_type=alert_type, message=message)
    logger.warning("ALERT [%s] %s: %s", alert_type, route, message)

    if notify:
        tg_text = (
            f"🚨 <b>FREIGHT ALERT</b>\n"
            f"Route: {_escape_html(route)}\n"
            f"Type: {_escape_html(alert_type)}\n\n"
            f"{_escape_html(message)}"
        )
        _send_telegram(tg_text)
