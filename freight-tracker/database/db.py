"""
SQLite database handler for the freight rate tracker.

Tables
------
- freight_rates     : raw scraped rate data
- rate_signals      : derived trading / alert signals
- alerts_log        : record of dispatched notifications
- input_costs       : daily bunker fuel and crude oil prices
- news_signals      : weekly news sentiment risk scores
"""

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger(__name__)

# NOTE: analysis.route_normaliser is imported inside the functions that need
# it rather than at module scope. Importing `analysis.*` executes
# analysis/__init__.py, which pulls in analysis.signals, which imports this
# module — a cycle. route_normaliser itself is a leaf with no project
# imports, so a deferred import resolves cleanly.

# Default DB path — override via config or env var if needed
DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "freight.db"

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

DDL_FREIGHT_RATES = """
CREATE TABLE IF NOT EXISTS freight_rates (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    index_name        TEXT    NOT NULL,
    route             TEXT    NOT NULL,
    rate_usd          REAL    NOT NULL,
    week_ending       TEXT    NOT NULL,   -- ISO date YYYY-MM-DD
    scraped_at        TEXT    NOT NULL,   -- ISO datetime
    source            TEXT    NOT NULL,
    canonical_route_id TEXT,              -- e.g. 'CN_NEUR'; drives ALL joins/WoW
    raw_route_string   TEXT               -- scraper's original label, audit only
);
"""

# Columns added after the table's first release. SQLite cannot express these
# in CREATE TABLE IF NOT EXISTS for an existing table, so they are applied
# idempotently by _migrate_schema().
MIGRATIONS_FREIGHT_RATES = [
    ("canonical_route_id", "ALTER TABLE freight_rates ADD COLUMN canonical_route_id TEXT"),
    ("raw_route_string",   "ALTER TABLE freight_rates ADD COLUMN raw_route_string TEXT"),
]

DDL_RATE_SIGNALS = """
CREATE TABLE IF NOT EXISTS rate_signals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    route       TEXT    NOT NULL,
    signal_type TEXT    NOT NULL,   -- e.g. 'trend_up', 'spike', 'crossover'
    value       REAL,
    week_ending TEXT    NOT NULL,
    notes       TEXT
);
"""

DDL_ALERTS_LOG = """
CREATE TABLE IF NOT EXISTS alerts_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    route        TEXT    NOT NULL,
    alert_type   TEXT    NOT NULL,
    triggered_at TEXT    NOT NULL,   -- ISO datetime
    message      TEXT    NOT NULL
);
"""

DDL_INPUT_COSTS = """
CREATE TABLE IF NOT EXISTS input_costs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    indicator_name TEXT    NOT NULL,   -- e.g. 'VLSFO 0.5% - Rotterdam', 'Brent Crude'
    value          REAL    NOT NULL,
    unit           TEXT    NOT NULL,   -- e.g. 'USD/MT', 'USD/bbl'
    date           TEXT    NOT NULL,   -- ISO date YYYY-MM-DD
    source         TEXT    NOT NULL
);
"""

DDL_NEWS_SIGNALS = """
CREATE TABLE IF NOT EXISTS news_signals (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    date                 TEXT    NOT NULL,   -- ISO date YYYY-MM-DD
    geopolitical_score   REAL    NOT NULL,   -- 0-100
    labour_score         REAL    NOT NULL,   -- 0-100
    port_score           REAL    NOT NULL,   -- 0-100
    key_events_json      TEXT    NOT NULL,   -- JSON array of strings
    affected_routes_json TEXT    NOT NULL,   -- JSON array of strings
    scraped_at           TEXT    NOT NULL    -- ISO datetime UTC
);
"""

DDL_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_fr_route       ON freight_rates (route);",
    "CREATE INDEX IF NOT EXISTS idx_fr_index_name  ON freight_rates (index_name);",
    "CREATE INDEX IF NOT EXISTS idx_fr_week_ending ON freight_rates (week_ending);",
    "CREATE INDEX IF NOT EXISTS idx_fr_canonical   ON freight_rates (canonical_route_id);",
    "CREATE INDEX IF NOT EXISTS idx_rs_route       ON rate_signals  (route);",
    "CREATE INDEX IF NOT EXISTS idx_al_route       ON alerts_log    (route);",
    "CREATE INDEX IF NOT EXISTS idx_ic_indicator   ON input_costs   (indicator_name);",
    "CREATE INDEX IF NOT EXISTS idx_ic_date        ON input_costs   (date);",
    "CREATE INDEX IF NOT EXISTS idx_ns_date        ON news_signals  (date);",
]

# One physical lane may have exactly one rate per index per week.
# Created separately from DDL_INDICES because it fails on a table that still
# holds pre-normalisation duplicates — see _ensure_unique_lane_index().
DDL_UNIQUE_LANE = (
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_fr_lane_week "
    "ON freight_rates (index_name, canonical_route_id, week_ending);"
)


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _get_db_path() -> Path:
    return DEFAULT_DB_PATH


def init_db(db_path: Path | None = None) -> Path:
    """
    Create the database file and all tables if they do not yet exist.

    Parameters
    ----------
    db_path : Path, optional
        Override the default database location.

    Returns
    -------
    Path: Absolute path to the database file.
    """
    path = db_path or _get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute(DDL_FREIGHT_RATES)
        conn.execute(DDL_RATE_SIGNALS)
        conn.execute(DDL_ALERTS_LOG)
        conn.execute(DDL_INPUT_COSTS)
        conn.execute(DDL_NEWS_SIGNALS)
        _migrate_schema(conn)
        for idx_sql in DDL_INDICES:
            conn.execute(idx_sql)
        _ensure_unique_lane_index(conn)
        conn.commit()

    logger.info("Database ready at %s", path.resolve())
    return path


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """Add columns introduced after the table's first release, idempotently."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(freight_rates)")}
    for column, ddl in MIGRATIONS_FREIGHT_RATES:
        if column not in existing:
            conn.execute(ddl)
            logger.info("_migrate_schema: added freight_rates.%s", column)


def _ensure_unique_lane_index(conn: sqlite3.Connection) -> bool:
    """
    Create the (index_name, canonical_route_id, week_ending) UNIQUE index.

    Returns False without raising when the table still holds pre-normalisation
    duplicates — the caller is told to run ``migrate_routes.py``, which
    de-duplicates and then installs the index.
    """
    try:
        conn.execute(DDL_UNIQUE_LANE)
        return True
    except sqlite3.IntegrityError:
        logger.warning(
            "UNIQUE lane index not created: freight_rates still contains "
            "duplicate (index_name, canonical_route_id, week_ending) rows. "
            "Run `python migrate_routes.py` to backfill and de-duplicate."
        )
        return False


@contextmanager
def _connect(db_path: Path | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager that yields a row-factory-enabled connection."""
    path = db_path or _get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

def insert_rates(
    rates: list[dict[str, Any]],
    db_path: Path | None = None,
) -> int:
    """
    Insert a batch of rate dicts into *freight_rates*.

    Each row's raw route string is resolved to a canonical lane ID, and both
    the canonical ID and the original string are stored. Writes use
    INSERT OR REPLACE keyed on the UNIQUE (index_name, canonical_route_id,
    week_ending) index, so re-running a scrape updates the existing row for
    that lane and week rather than appending a near-duplicate.

    Parameters
    ----------
    rates : list[dict]
        Each dict must contain keys:
        index_name, route, rate_usd_per_feu, week_ending, source_url

    Returns
    -------
    int: Number of rows written (inserted or updated in place).
    """
    if not rates:
        return 0

    from analysis.route_normaliser import (  # noqa: PLC0415 — breaks import cycle
        is_unmapped,
        normalise_index,
        normalise_route,
    )

    scraped_at = datetime.now(timezone.utc).isoformat()
    written = 0
    unmapped_seen: set[str] = set()

    with _connect(db_path) as conn:
        for r in rates:
            try:
                raw_route = r["route"]
                canonical = normalise_route(raw_route, r.get("index_name"))
                index_name = normalise_index(r["index_name"])

                if is_unmapped(canonical):
                    unmapped_seen.add(str(raw_route))

                conn.execute(
                    """
                    INSERT OR REPLACE INTO freight_rates
                        (index_name, route, rate_usd, week_ending, scraped_at,
                         source, canonical_route_id, raw_route_string)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        index_name,
                        raw_route,
                        r["rate_usd_per_feu"],
                        r["week_ending"],
                        scraped_at,
                        r["source_url"],
                        canonical,
                        raw_route,
                    ),
                )
                written += conn.execute("SELECT changes()").fetchone()[0]
            except (KeyError, sqlite3.Error) as exc:
                logger.error("insert_rates: skipping row due to error: %s | row=%s", exc, r)

    for raw in sorted(unmapped_seen):
        logger.warning(
            "insert_rates: route '%s' did not map to a canonical lane — "
            "stored as UNMAPPED. Add a mapping in analysis/route_normaliser.py",
            raw,
        )

    logger.info("insert_rates: wrote %d / %d records", written, len(rates))
    return written


def insert_signal(
    route: str,
    signal_type: str,
    value: float | None,
    week_ending: str,
    notes: str = "",
    db_path: Path | None = None,
) -> None:
    """Append a derived signal to *rate_signals*."""
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO rate_signals (route, signal_type, value, week_ending, notes) VALUES (?,?,?,?,?)",
            (route, signal_type, value, week_ending, notes),
        )


def insert_alert(
    route: str,
    alert_type: str,
    message: str,
    db_path: Path | None = None,
) -> None:
    """Append a dispatched alert record to *alerts_log*."""
    triggered_at = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO alerts_log (route, alert_type, triggered_at, message) VALUES (?,?,?,?)",
            (route, alert_type, triggered_at, message),
        )


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

def get_latest_rates(
    index_name: str | None = None,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Return the most-recent rate for every (index_name, canonical_route_id) lane.

    Grouping is by canonical lane, not by raw route string, so a lane that
    several scrapers spell differently yields one row rather than several.

    Parameters
    ----------
    index_name : str, optional
        Filter to a specific index (e.g. 'WCI'). Normalised before matching.
    """
    from analysis.route_normaliser import normalise_index  # noqa: PLC0415

    with _connect(db_path) as conn:
        if index_name:
            rows = conn.execute(
                """
                SELECT fr.*
                FROM freight_rates fr
                INNER JOIN (
                    SELECT index_name, canonical_route_id, MAX(week_ending) AS max_week
                    FROM freight_rates
                    WHERE index_name = ?
                    GROUP BY index_name, canonical_route_id
                ) latest
                ON fr.index_name         = latest.index_name
                AND fr.canonical_route_id = latest.canonical_route_id
                AND fr.week_ending        = latest.max_week
                ORDER BY fr.canonical_route_id
                """,
                (normalise_index(index_name),),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT fr.*
                FROM freight_rates fr
                INNER JOIN (
                    SELECT index_name, canonical_route_id, MAX(week_ending) AS max_week
                    FROM freight_rates
                    GROUP BY index_name, canonical_route_id
                ) latest
                ON fr.index_name         = latest.index_name
                AND fr.canonical_route_id = latest.canonical_route_id
                AND fr.week_ending        = latest.max_week
                ORDER BY fr.index_name, fr.canonical_route_id
                """,
            ).fetchall()

    return [dict(r) for r in rows]


def get_rate_history(
    route: str,
    weeks: int = 12,
    index_name: str | None = None,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Return up to *weeks* weeks of history for one canonical lane.

    Parameters
    ----------
    route       : Canonical lane ID (e.g. 'CN_NEUR'). A raw scraper string is
                  also accepted and normalised, so older callers keep working.
    weeks       : Number of most-recent distinct weeks to return. Every index's
                  rows for those weeks are returned — a lane now spans several
                  indices, so limiting by row count would silently drop one
                  index's history in favour of whichever reports most often.
    index_name  : Optional filter to a single index source.
    """
    from analysis.route_normaliser import (  # noqa: PLC0415
        CANONICAL_ROUTES,
        normalise_index,
        normalise_route,
        is_unmapped,
    )

    # Accept either a canonical ID or a raw route string.
    if route in CANONICAL_ROUTES or is_unmapped(route):
        canonical = route
    else:
        canonical = normalise_route(route, index_name)

    with _connect(db_path) as conn:
        if index_name:
            rows = conn.execute(
                """
                SELECT * FROM freight_rates
                WHERE canonical_route_id = ? AND index_name = ?
                  AND week_ending IN (
                      SELECT week_ending FROM freight_rates
                      WHERE canonical_route_id = ? AND index_name = ?
                      GROUP BY week_ending
                      ORDER BY week_ending DESC
                      LIMIT ?
                  )
                ORDER BY week_ending DESC
                """,
                (canonical, normalise_index(index_name),
                 canonical, normalise_index(index_name), weeks),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM freight_rates
                WHERE canonical_route_id = ?
                  AND week_ending IN (
                      SELECT week_ending FROM freight_rates
                      WHERE canonical_route_id = ?
                      GROUP BY week_ending
                      ORDER BY week_ending DESC
                      LIMIT ?
                  )
                ORDER BY week_ending DESC
                """,
                (canonical, canonical, weeks),
            ).fetchall()

    return [dict(r) for r in rows]


def insert_input_costs(
    costs: list[dict[str, Any]],
    db_path: Path | None = None,
) -> int:
    """
    Insert a batch of input cost records into *input_costs*.

    Skips duplicates (same indicator_name + date).

    Parameters
    ----------
    costs : list[dict]
        Each dict must contain keys:
        indicator_name, value, unit, date, source

    Returns
    -------
    int: Number of rows actually inserted.
    """
    if not costs:
        return 0

    inserted = 0

    with _connect(db_path) as conn:
        for c in costs:
            try:
                conn.execute(
                    """
                    INSERT INTO input_costs
                        (indicator_name, value, unit, date, source)
                    SELECT ?, ?, ?, ?, ?
                    WHERE NOT EXISTS (
                        SELECT 1 FROM input_costs
                        WHERE indicator_name = ? AND date = ?
                    )
                    """,
                    (
                        c["indicator_name"],
                        c["value"],
                        c["unit"],
                        c["date"],
                        c["source"],
                        c["indicator_name"],
                        c["date"],
                    ),
                )
                inserted += conn.execute("SELECT changes()").fetchone()[0]
            except (KeyError, sqlite3.Error) as exc:
                logger.error("insert_input_costs: skipping row due to error: %s | row=%s", exc, c)

    logger.info("insert_input_costs: inserted %d / %d records", inserted, len(costs))
    return inserted


def get_input_cost_history(
    indicator: str,
    weeks: int = 12,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Return up to *weeks* weeks of daily history for an input cost indicator.

    Parameters
    ----------
    indicator : str
        Exact indicator_name string (case-sensitive).
    weeks     : int
        Number of weeks of history to return (converted to days).
    """
    days = weeks * 7
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM input_costs
            WHERE indicator_name = ?
            ORDER BY date DESC
            LIMIT ?
            """,
            (indicator, days),
        ).fetchall()

    return [dict(r) for r in rows]


def insert_news_signal(
    record: dict[str, Any],
    db_path: Path | None = None,
) -> bool:
    """
    Insert a news sentiment record into *news_signals*.

    Skips if a row already exists for the same date (one record per day).

    Parameters
    ----------
    record : dict
        Must contain keys matching the scraper output:
        date, geopolitical_score, labour_score, port_score,
        key_events (list), affected_routes (list), scraped_at

    Returns
    -------
    bool: True when a new row was inserted, False when skipped.
    """
    import json as _json

    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO news_signals
                (date, geopolitical_score, labour_score, port_score,
                 key_events_json, affected_routes_json, scraped_at)
            SELECT ?, ?, ?, ?, ?, ?, ?
            WHERE NOT EXISTS (
                SELECT 1 FROM news_signals WHERE date = ?
            )
            """,
            (
                record["date"],
                record["geopolitical_score"],
                record["labour_score"],
                record["port_score"],
                _json.dumps(record.get("key_events") or []),
                _json.dumps(record.get("affected_routes") or []),
                record["scraped_at"],
                record["date"],
            ),
        )
        inserted = conn.execute("SELECT changes()").fetchone()[0]

    if inserted:
        logger.info("insert_news_signal: inserted record for date=%s", record["date"])
    else:
        logger.info("insert_news_signal: skipped duplicate for date=%s", record["date"])
    return bool(inserted)


def get_latest_news_signal(
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    """
    Return the most-recent news sentiment record, with JSON columns
    decoded back to Python lists.

    Returns None when the table is empty.
    """
    import json as _json

    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM news_signals ORDER BY date DESC, id DESC LIMIT 1"
        ).fetchone()

    if row is None:
        return None

    result = dict(row)
    result["key_events"]      = _json.loads(result.pop("key_events_json",      "[]"))
    result["affected_routes"] = _json.loads(result.pop("affected_routes_json", "[]"))
    return result


def get_cross_index_comparison(
    route: str,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Return the latest rate from every index for a given route,
    enabling direct cross-index comparison.

    Parameters
    ----------
    route : Partial or exact route string (LIKE match).
    """
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT fr.index_name, fr.route, fr.rate_usd, fr.week_ending, fr.source
            FROM freight_rates fr
            INNER JOIN (
                SELECT index_name, route, MAX(week_ending) AS max_week
                FROM freight_rates
                WHERE route LIKE ?
                GROUP BY index_name, route
            ) latest
            ON fr.index_name   = latest.index_name
            AND fr.route        = latest.route
            AND fr.week_ending  = latest.max_week
            ORDER BY fr.index_name
            """,
            (f"%{route}%",),
        ).fetchall()

    return [dict(r) for r in rows]
