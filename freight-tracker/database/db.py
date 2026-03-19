"""
SQLite database handler for the freight rate tracker.

Tables
------
- freight_rates     : raw scraped rate data
- rate_signals      : derived trading / alert signals
- alerts_log        : record of dispatched notifications
"""

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger(__name__)

# Default DB path — override via config or env var if needed
DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "freight.db"

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

DDL_FREIGHT_RATES = """
CREATE TABLE IF NOT EXISTS freight_rates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    index_name  TEXT    NOT NULL,
    route       TEXT    NOT NULL,
    rate_usd    REAL    NOT NULL,
    week_ending TEXT    NOT NULL,   -- ISO date YYYY-MM-DD
    scraped_at  TEXT    NOT NULL,   -- ISO datetime
    source      TEXT    NOT NULL
);
"""

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

DDL_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_fr_route       ON freight_rates (route);",
    "CREATE INDEX IF NOT EXISTS idx_fr_index_name  ON freight_rates (index_name);",
    "CREATE INDEX IF NOT EXISTS idx_fr_week_ending ON freight_rates (week_ending);",
    "CREATE INDEX IF NOT EXISTS idx_rs_route       ON rate_signals  (route);",
    "CREATE INDEX IF NOT EXISTS idx_al_route       ON alerts_log    (route);",
]


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
        for idx_sql in DDL_INDICES:
            conn.execute(idx_sql)
        conn.commit()

    logger.info("Database ready at %s", path.resolve())
    return path


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

    Skips duplicates (same index_name + route + week_ending).

    Parameters
    ----------
    rates : list[dict]
        Each dict must contain keys:
        index_name, route, rate_usd_per_feu, week_ending, source_url

    Returns
    -------
    int: Number of rows actually inserted.
    """
    if not rates:
        return 0

    scraped_at = datetime.now(timezone.utc).isoformat()
    inserted = 0

    with _connect(db_path) as conn:
        for r in rates:
            try:
                conn.execute(
                    """
                    INSERT INTO freight_rates
                        (index_name, route, rate_usd, week_ending, scraped_at, source)
                    SELECT ?, ?, ?, ?, ?, ?
                    WHERE NOT EXISTS (
                        SELECT 1 FROM freight_rates
                        WHERE index_name = ? AND route = ? AND week_ending = ?
                    )
                    """,
                    (
                        r["index_name"],
                        r["route"],
                        r["rate_usd_per_feu"],
                        r["week_ending"],
                        scraped_at,
                        r["source_url"],
                        r["index_name"],
                        r["route"],
                        r["week_ending"],
                    ),
                )
                inserted += conn.execute("SELECT changes()").fetchone()[0]
            except (KeyError, sqlite3.Error) as exc:
                logger.error("insert_rates: skipping row due to error: %s | row=%s", exc, r)

    logger.info("insert_rates: inserted %d / %d records", inserted, len(rates))
    return inserted


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
    Return the most-recent rate for every (index_name, route) pair.

    Parameters
    ----------
    index_name : str, optional
        Filter to a specific index (e.g. 'Drewry WCI').
    """
    with _connect(db_path) as conn:
        if index_name:
            rows = conn.execute(
                """
                SELECT fr.*
                FROM freight_rates fr
                INNER JOIN (
                    SELECT index_name, route, MAX(week_ending) AS max_week
                    FROM freight_rates
                    WHERE index_name = ?
                    GROUP BY index_name, route
                ) latest
                ON fr.index_name = latest.index_name
                AND fr.route      = latest.route
                AND fr.week_ending = latest.max_week
                ORDER BY fr.route
                """,
                (index_name,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT fr.*
                FROM freight_rates fr
                INNER JOIN (
                    SELECT index_name, route, MAX(week_ending) AS max_week
                    FROM freight_rates
                    GROUP BY index_name, route
                ) latest
                ON fr.index_name  = latest.index_name
                AND fr.route       = latest.route
                AND fr.week_ending = latest.max_week
                ORDER BY fr.index_name, fr.route
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
    Return up to *weeks* weeks of history for a given route.

    Parameters
    ----------
    route       : Exact route string (case-sensitive).
    weeks       : Number of most-recent distinct weeks to return.
    index_name  : Optional filter to a single index source.
    """
    with _connect(db_path) as conn:
        if index_name:
            rows = conn.execute(
                """
                SELECT * FROM freight_rates
                WHERE route = ? AND index_name = ?
                ORDER BY week_ending DESC
                LIMIT ?
                """,
                (route, index_name, weeks),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM freight_rates
                WHERE route = ?
                ORDER BY week_ending DESC
                LIMIT ?
                """,
                (route, weeks),
            ).fetchall()

    return [dict(r) for r in rows]


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
