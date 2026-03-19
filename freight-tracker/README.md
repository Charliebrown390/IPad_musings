# Container Freight Rate Tracker

Automated agent that scrapes, stores, analyses, and reports on global container
shipping rates from three major indices:

| Index | Source | Method |
|-------|--------|--------|
| **Drewry WCI** | drewry.co.uk | httpx + BeautifulSoup |
| **Freightos FBX** | fbx.freightos.com | Playwright (async, JS-rendered) |
| **SCFI** | en.sse.net.cn | httpx + BeautifulSoup |

---

## Project Layout

```
freight-tracker/
├── main.py                   # CLI entry point
├── config.yaml               # Runtime configuration
├── requirements.txt
├── scrapers/
│   ├── drewry.py             # Drewry WCI scraper
│   ├── freightos.py          # Freightos FBX scraper (Playwright)
│   └── scfi.py               # SCFI scraper
├── database/
│   └── db.py                 # SQLite schema + CRUD helpers
├── analysis/
│   └── signals.py            # Spike / trend / crossover detection
├── reports/
│   ├── reporter.py           # Markdown reports + Telegram + Claude AI
│   └── output/               # Generated report files (gitignored)
├── data/
│   └── freight.db            # SQLite database (gitignored)
├── scraper.log               # Rotating log file (gitignored)
└── .github/workflows/
    ├── weekly_report.yml     # Weekly full pipeline (Sundays 06:00 UTC)
    └── intraday_check.yml    # Intraday spike check (Mon–Fri, every 4 h)
```

---

## Quickstart

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure secrets (optional)

```bash
export ANTHROPIC_API_KEY="sk-ant-..."      # AI narrative in reports
export TELEGRAM_BOT_TOKEN="..."            # Telegram notifications
export TELEGRAM_CHAT_ID="..."
```

### 3. Run

```bash
# Full weekly pipeline (scrape → store → signals → report)
python main.py

# Intraday scrape + spike-alert check only
python main.py --mode intraday

# Scrape and store without analysis
python main.py --mode scrape-only

# Re-generate report from existing DB data
python main.py --mode report-only
```

---

## Database Schema

### `freight_rates`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| index_name | TEXT | e.g. "Drewry WCI" |
| route | TEXT | e.g. "Shanghai → Europe" |
| rate_usd | REAL | USD per FEU |
| week_ending | TEXT | ISO date YYYY-MM-DD |
| scraped_at | TEXT | ISO datetime (UTC) |
| source | TEXT | Source URL |

### `rate_signals`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| route | TEXT | Affected route |
| signal_type | TEXT | spike_up / trend_up / crossover_up / … |
| value | REAL | Numeric signal value |
| week_ending | TEXT | ISO date |
| notes | TEXT | Human-readable explanation |

### `alerts_log`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| route | TEXT | Affected route |
| alert_type | TEXT | e.g. "threshold_breach" |
| triggered_at | TEXT | ISO datetime (UTC) |
| message | TEXT | Full alert message |

---

## Signals

| Signal | Logic |
|--------|-------|
| `spike_up` / `spike_down` | Weekly % change ≥ threshold (default 10 %) |
| `trend_up` / `trend_down` | Sign of linear regression slope over 4-week window |
| `crossover_up` / `crossover_down` | MA4 crosses MA12 |
| `multi_index_divergence` | Spread between highest/lowest current index rate > 20 % |

---

## GitHub Actions

### `weekly_report.yml`
- **Trigger**: Sunday at 06:00 UTC (+ manual dispatch)
- **Steps**: install deps → install Playwright browsers → run full pipeline → upload report as artifact

### `intraday_check.yml`
- **Trigger**: Mon–Fri at 06:00, 10:00, 14:00, 18:00 UTC (+ manual dispatch)
- **Steps**: install deps → install Playwright browsers → run intraday check

Both workflows read secrets `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, and
`TELEGRAM_CHAT_ID` from the repository's Actions secrets.

---

## Logging

All scrapers log failures with ISO-8601 timestamps to `scraper.log` (rotating,
5 MB × 3 backups). HTTP errors, parse failures, and signal anomalies are all
captured. Set `PYTHONUNBUFFERED=1` to see logs in real time in Actions.
