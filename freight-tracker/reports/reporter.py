"""
Report generation and alert dispatch for the freight rate tracker.

Outputs
-------
- Markdown weekly report (saved to reports/output/)
- Telegram message (if TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID are set)
- Claude AI narrative summary (via Anthropic SDK, if ANTHROPIC_API_KEY is set)
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anthropic
import pandas as pd
import yaml

from database.db import (
    get_latest_rates,
    get_rate_history,
    get_cross_index_comparison,
    insert_alert,
)

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"
CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


def _fmt_rate(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"${value:,.0f}"


def _pct_change(current: float, previous: float) -> str:
    if previous == 0:
        return "N/A"
    pct = (current - previous) / previous * 100
    arrow = "▲" if pct >= 0 else "▼"
    return f"{arrow} {abs(pct):.1f}%"


# ---------------------------------------------------------------------------
# Markdown report builder
# ---------------------------------------------------------------------------

def _build_markdown_report(
    latest_rates: list[dict],
    signals: list[dict],
    report_date: str,
) -> str:
    """Assemble a Markdown-formatted weekly report string."""
    lines = [
        f"# Freight Rate Weekly Report — {report_date}",
        "",
        "## Current Rates by Index",
        "",
    ]

    # Group rates by index
    df = pd.DataFrame(latest_rates)
    if df.empty:
        lines.append("_No rate data available._")
    else:
        for index_name, group in df.groupby("index_name"):
            lines.append(f"### {index_name}")
            lines.append("")
            lines.append("| Route | Rate (USD/FEU) | Week Ending |")
            lines.append("|-------|---------------|-------------|")
            for _, row in group.sort_values("route").iterrows():
                lines.append(
                    f"| {row['route']} | {_fmt_rate(row['rate_usd'])} | {row['week_ending']} |"
                )
            lines.append("")

    # Signals section
    if signals:
        lines += [
            "## Signals & Alerts",
            "",
            "| Route | Signal | Value | Week |",
            "|-------|--------|-------|------|",
        ]
        for sig in signals[:50]:  # cap at 50 rows for readability
            lines.append(
                f"| {sig.get('route','')} "
                f"| {sig.get('signal_type','')} "
                f"| {sig.get('value','')} "
                f"| {sig.get('week_ending','')} |"
            )
        lines.append("")

    lines += [
        "---",
        f"_Generated at {datetime.now(timezone.utc).isoformat()} UTC_",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Claude AI narrative
# ---------------------------------------------------------------------------

def _generate_ai_narrative(report_markdown: str) -> str | None:
    """
    Use the Anthropic API to generate a brief analyst-style narrative
    summarising the weekly freight rate movements.

    Returns None if ANTHROPIC_API_KEY is not set or the call fails.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.info("ANTHROPIC_API_KEY not set — skipping AI narrative")
        return None

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "You are a senior freight market analyst. "
                        "Based on the following weekly freight rate data, "
                        "write a concise 3-5 sentence market commentary "
                        "highlighting notable moves, trends, and any anomalies. "
                        "Be specific about routes and percentage changes.\n\n"
                        f"{report_markdown[:3000]}"
                    ),
                }
            ],
        )
        return message.content[0].text
    except Exception as exc:
        logger.error("AI narrative generation failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Telegram dispatch
# ---------------------------------------------------------------------------

def _send_telegram(text: str, config: dict) -> bool:
    """
    Send *text* via Telegram bot.

    Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from env vars (preferred)
    or config.yaml.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN") or config.get("telegram", {}).get("bot_token")
    chat_id = os.getenv("TELEGRAM_CHAT_ID") or config.get("telegram", {}).get("chat_id")

    if not token or not chat_id:
        logger.info("Telegram credentials not configured — skipping notification")
        return False

    try:
        import telegram  # python-telegram-bot

        import asyncio

        async def _send() -> None:
            bot = telegram.Bot(token=token)
            # Telegram message limit is 4096 chars
            for chunk_start in range(0, len(text), 4000):
                await bot.send_message(
                    chat_id=chat_id,
                    text=text[chunk_start : chunk_start + 4000],
                    parse_mode="Markdown",
                )

        asyncio.run(_send())
        logger.info("Telegram notification sent to chat_id=%s", chat_id)
        return True
    except Exception as exc:
        logger.error("Telegram send failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_weekly_report(
    signals: list[dict[str, Any]] | None = None,
) -> Path:
    """
    Build and save the weekly Markdown report, optionally including signals.
    Also sends a Telegram notification and AI narrative if configured.

    Parameters
    ----------
    signals : list[dict], optional
        Pre-computed signals (from analysis.generate_weekly_signals).

    Returns
    -------
    Path: Absolute path to the saved report file.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config = _load_config()
    report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    latest_rates = get_latest_rates()
    report_md = _build_markdown_report(
        latest_rates=latest_rates,
        signals=signals or [],
        report_date=report_date,
    )

    # Optionally prepend AI narrative
    ai_narrative = _generate_ai_narrative(report_md)
    if ai_narrative:
        report_md = f"## AI Market Commentary\n\n{ai_narrative}\n\n---\n\n" + report_md

    # Save file
    report_path = OUTPUT_DIR / f"weekly_report_{report_date}.md"
    report_path.write_text(report_md, encoding="utf-8")
    logger.info("Weekly report saved to %s", report_path)

    # Telegram notification — send a trimmed summary
    summary_lines = [f"*Freight Rate Report — {report_date}*", ""]
    for r in latest_rates[:10]:  # top 10 for brevity
        summary_lines.append(
            f"• {r['index_name']} | {r['route']}: {_fmt_rate(r['rate_usd'])}"
        )
    if ai_narrative:
        summary_lines += ["", ai_narrative[:600]]
    _send_telegram("\n".join(summary_lines), config)

    return report_path


def generate_intraday_alert(
    route: str,
    alert_type: str,
    message: str,
    notify: bool = True,
) -> None:
    """
    Log an intraday alert and optionally send a Telegram notification.

    Parameters
    ----------
    route       : The affected route.
    alert_type  : e.g. 'spike_up', 'threshold_breach'.
    message     : Human-readable alert message.
    notify      : Whether to send a Telegram message.
    """
    insert_alert(route=route, alert_type=alert_type, message=message)
    logger.warning("ALERT [%s] %s: %s", alert_type, route, message)

    if notify:
        config = _load_config()
        telegram_text = f"*FREIGHT ALERT*\nRoute: {route}\nType: {alert_type}\n\n{message}"
        _send_telegram(telegram_text, config)
