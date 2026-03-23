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

from database.db import get_latest_rates, get_rate_history, insert_alert

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
    One row per unique route, merging FBX and WCI columns.
    """
    # Index latest rates by (route, index_name) for O(1) lookup
    rate_lookup: dict[tuple[str, str], float] = {}
    for row in latest_rates:
        key = (row["route"], row["index_name"])
        rate_lookup[key] = row["rate_usd"]

    routes = sorted({r["route"] for r in latest_rates})

    header = "| Route | FBX Rate | WCI Rate | WoW % | 4W Avg | Signal |"
    sep    = "|-------|----------|----------|-------|--------|--------|"
    rows = [header, sep]

    for route in routes:
        # FBX: match Freightos
        fbx = next(
            (v for (r, idx), v in rate_lookup.items()
             if r == route and ("FBX" in idx or "Freightos" in idx)),
            None,
        )
        # WCI: match Drewry
        wci = next(
            (v for (r, idx), v in rate_lookup.items()
             if r == route and ("WCI" in idx or "Drewry" in idx)),
            None,
        )

        sig = signals_by_route.get(route, {})
        wow = _fmt_pct(sig.get("wow_pct"))
        avg4w = _fmt_rate(sig.get("four_week_avg"))
        label = _signal_label(sig)

        rows.append(
            f"| {route} | {_fmt_rate(fbx)} | {_fmt_rate(wci)} "
            f"| {wow} | {avg4w} | {label} |"
        )

    return "\n".join(rows)


def _build_markdown_report(
    latest_rates: list[dict],
    signals_by_route: dict[str, dict[str, Any]],
    ai_summary: str | None,
    report_date: str,
) -> str:
    urgent = _has_urgent_signal(signals_by_route)
    header_flag = "🚨 " if urgent else ""

    lines = [
        f"# {header_flag}Freight Rate Weekly Report — {report_date}",
        "",
    ]

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
    if inflation_score is not None:
        lines += [
            f"**Inflationary Pressure Score: {inflation_score:.0f} / 100**",
            "",
        ]

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


def _generate_executive_summary(signals_by_route: dict[str, dict[str, Any]]) -> str | None:
    """
    Call claude-haiku-4-5-20251001 to produce a 3-sentence executive summary.
    Returns None if ANTHROPIC_API_KEY is unset or the call fails.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.info("ANTHROPIC_API_KEY not set — skipping executive summary")
        return None

    signal_text = _build_signal_summary_text(signals_by_route)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system="You are a freight market analyst writing for an insurance investment team.",
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Given these shipping rate signals:\n\n{signal_text}\n\n"
                        "Write a 3-sentence executive summary covering: "
                        "(1) demand trends, "
                        "(2) inflationary cost pressures from fuel and logistics, "
                        "(3) geopolitical route risk."
                    ),
                }
            ],
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

    Returns
    -------
    Path: Absolute path to the saved report file.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if latest_rates is None:
        latest_rates = get_latest_rates()

    if signals_by_route is None:
        signals_by_route = {}

    report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 1. AI executive summary
    ai_summary = _generate_executive_summary(signals_by_route)

    # 2. Markdown report
    report_md = _build_markdown_report(
        latest_rates=latest_rates,
        signals_by_route=signals_by_route,
        ai_summary=ai_summary,
        report_date=report_date,
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
