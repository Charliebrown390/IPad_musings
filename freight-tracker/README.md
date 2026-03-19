# Container Freight Rate Tracker

An automated agent that scrapes global container shipping indices, detects
rate anomalies, and delivers a structured Telegram report — scheduled via
GitHub Actions so it runs reliably whether or not your Codespace is open.

---

## What the agent does

| Step | Description |
|------|-------------|
| **Scrape** | Pulls weekly rates from Drewry WCI, Freightos FBX, and SCFI |
| **Store** | Persists every reading to a SQLite database committed back to the repo |
| **Analyse** | Computes three signal categories across all monitored routes |
| **Report** | Builds a Markdown report, generates an AI executive summary via Claude, and sends the result to Telegram |
| **Alert** | Fires a targeted Telegram alert whenever a rate moves more than 10 % week-on-week |

---

## Signal categories

### 1. Momentum — `SPIKE / COOLING / STABLE`
Compares the latest rate to the 4-week rolling average for each route.

| Label | Condition |
|-------|-----------|
| `SPIKE` | Current rate ≥ 10 % above 4-week average |
| `COOLING` | Current rate ≤ 5 % below 4-week average |
| `STABLE` | Within the ±5–10 % band |

### 2. Cross-index divergence — `DIVERGENCE`
Flags a route when the Freightos FBX and Drewry WCI rates for the same
corridor diverge by more than **15 %** of their mean.
A large spread can indicate thin liquidity, data-source lag, or methodology
differences worth investigating before acting on either index in isolation.

### 3. Geopolitical stress proxy — `STRESS`
Monitors **Shanghai → Rotterdam** and **Shanghai → Genoa** (the primary
Suez / Red Sea corridors). A `STRESS` flag is raised when the current rate
exceeds the route's own 12-week average by more than **40 %**, consistent
with the rerouting premium observed during periods of elevated Red Sea risk.

---

## Project layout

```
freight-tracker/
├── main.py                        # CLI entry point
├── config.yaml                    # Thresholds, routes, timezone
├── requirements.txt
├── scrapers/
│   ├── drewry.py                  # httpx + BeautifulSoup
│   ├── freightos.py               # Playwright (async, JS-rendered)
│   └── scfi.py                    # httpx + BeautifulSoup
├── database/
│   └── db.py                      # SQLite schema + CRUD helpers
├── analysis/
│   └── signals.py                 # generate_signals(df) + DB orchestrator
├── reports/
│   ├── reporter.py                # Markdown report + Claude API + Telegram
│   └── output/                    # Generated reports (committed to repo)
├── data/
│   └── freight.db                 # SQLite DB (committed after each weekly run)
├── scraper.log                    # Rotating log (gitignored)
├── .devcontainer/
│   └── devcontainer.json          # Codespace auto-setup
└── .github/workflows/
    ├── weekly_report.yml          # Mon 00:00 UTC — full pipeline
    └── intraday_check.yml         # Daily 23:00 UTC — DB-only spike check
```

---

## Schedule

| Workflow | Cron (UTC) | Local time (SGT) | What it does |
|----------|-----------|-----------------|--------------|
| `weekly_report.yml` | `0 0 * * 1` | Mon 08:00 | Scrape all sources → store → compute signals → send full Telegram report → commit DB to repo |
| `intraday_check.yml` | `0 23 * * *` | Daily 07:00 | Read DB only → check WoW % moves → alert on routes that moved > 10 % |

---

## Quickstart (local / Codespace)

The dev container handles setup automatically when you open the repo in
GitHub Codespaces. For a local environment:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Install Playwright browser
playwright install chromium

# 3. Set environment variables (see "Adding secrets" below)
export ANTHROPIC_API_KEY="sk-ant-..."
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."

# 4. Run
python main.py --run-now          # full weekly pipeline
python main.py --intraday-check   # DB-only WoW check
python main.py --backfill         # scrape + store, no Telegram
```

---

## Adding secrets to GitHub

Secrets are used by both GitHub Actions workflows and, when set as
Codespace secrets, by your local dev environment.

### Repository secrets (for GitHub Actions)

1. Go to your repository on GitHub.
2. Click **Settings → Secrets and variables → Actions**.
3. Click **New repository secret** for each of the following:

| Secret name | Where to get it |
|-------------|----------------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/) → API Keys |
| `TELEGRAM_BOT_TOKEN` | Message [@BotFather](https://t.me/BotFather) on Telegram → `/newbot` |
| `TELEGRAM_CHAT_ID` | Message [@userinfobot](https://t.me/userinfobot) or use the Telegram API to find your chat ID |

### Codespace secrets (for local dev in Codespaces)

1. Go to **github.com/settings/codespaces**.
2. Under **Codespace secrets**, add the same three secrets and grant access to this repository.

The `devcontainer.json` will automatically inject them as environment
variables when your Codespace starts.

---

## Triggering a manual run via GitHub Actions

1. Go to your repository on GitHub.
2. Click the **Actions** tab.
3. Select **Weekly Freight Rate Report** (or **Intraday Freight Rate Check**).
4. Click **Run workflow** → choose the branch → click the green **Run workflow** button.

The weekly workflow also exposes a `debug` input: set it to `true` for
verbose Python output in the Actions log.

---

## Database persistence

The SQLite database (`data/freight.db`) is committed back to the repository
after every successful weekly run by the `weekly_report.yml` workflow. This
means:

- No external database or cloud storage is required.
- Each weekly run inherits the full rate history accumulated by previous runs.
- The intraday check reads the last-committed DB via a standard `checkout`.
- Commits from the workflow are tagged `[skip ci]` to prevent feedback loops.

---

## Configuration reference (`config.yaml`)

```yaml
alert_thresholds:
  wow_pct: 10        # WoW % that triggers an intraday alert
  stress_pct: 40     # % above 12-week avg that flags STRESS
  divergence_pct: 15 # FBX vs WCI spread that flags DIVERGENCE

routes_of_interest:   # Subset checked by --intraday-check
  - "Shanghai→Los Angeles"
  - "Shanghai→Rotterdam"
  - "New York→Rotterdam"
  - "Shanghai→Genoa"

timezone: "Asia/Singapore"  # Display label only; cron runs in UTC
```

Set `routes_of_interest` to `[]` to monitor every route currently in the DB.

---

## Logs

All runs append to `scraper.log` (rotating, 5 MB × 3 backups).
Each entry is timestamped in UTC ISO-8601 format:

```
2024-01-15T00:03:12Z INFO     __main__: === run-now: starting full pipeline ===
2024-01-15T00:03:12Z INFO     __main__: [2024-01-15T00:03:12Z] Starting scraper: drewry
2024-01-15T00:03:17Z INFO     __main__: Scraper 'drewry' returned 9 records
...
```

The log file is gitignored and is available as a GitHub Actions artifact
for 90 days (weekly) or 14 days (intraday, failures only).
