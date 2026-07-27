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

# observation_date is the date the rate was actually observed. Indices do not
# share a publication cadence: FBX prints daily, SCFI/WCI weekly. Storing the
# true observation date and deriving the week from it keeps daily fidelity
# while letting weekly statistics be computed correctly.
#
# week_ending is a VIRTUAL generated column: the Sunday on or after
# observation_date (Mon–Sun weeks). It is derived, never written, so it can
# never drift out of step with observation_date.
WEEK_ENDING_EXPR = "date(observation_date, 'weekday 0')"

DDL_FREIGHT_RATES = f"""
CREATE TABLE IF NOT EXISTS freight_rates (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    index_name        TEXT    NOT NULL,
    route             TEXT    NOT NULL,
    rate_usd          REAL    NOT NULL,
    observation_date  TEXT    NOT NULL,   -- ISO date YYYY-MM-DD, as observed
    scraped_at        TEXT    NOT NULL,   -- ISO datetime
    source            TEXT    NOT NULL,
    canonical_route_id TEXT,              -- e.g. 'CN_NEUR'; drives ALL joins/WoW
    raw_route_string   TEXT,              -- scraper's original label, audit only
    is_synthetic      INTEGER NOT NULL DEFAULT 0,  -- 1 = seeded/fabricated
    week_ending       TEXT GENERATED ALWAYS AS ({WEEK_ENDING_EXPR}) VIRTUAL
);
"""

# Columns added after the table's first release. SQLite cannot express these
# in CREATE TABLE IF NOT EXISTS for an existing table, so they are applied
# idempotently by _migrate_schema().
MIGRATIONS_FREIGHT_RATES = [
    ("canonical_route_id", "ALTER TABLE freight_rates ADD COLUMN canonical_route_id TEXT"),
    ("raw_route_string",   "ALTER TABLE freight_rates ADD COLUMN raw_route_string TEXT"),
    ("is_synthetic",
     "ALTER TABLE freight_rates ADD COLUMN is_synthetic INTEGER NOT NULL DEFAULT 0"),
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

DDL_DATA_QUALITY_LOG = """
CREATE TABLE IF NOT EXISTS data_quality_log (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    detected_at        TEXT    NOT NULL,   -- ISO datetime UTC
    issue_type         TEXT    NOT NULL,   -- 'rate_collision' | 'stale_index'
    index_name         TEXT,
    canonical_route_id TEXT,
    week_ending        TEXT,
    existing_value     REAL,               -- value already in the DB
    incoming_value     REAL,               -- value being written
    pct_difference     REAL,               -- relative gap, % of the smaller
    existing_raw_route TEXT,               -- raw string behind existing_value
    incoming_raw_route TEXT,               -- raw string behind incoming_value
    winner             TEXT,               -- 'incoming' | 'existing'
    notes              TEXT
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
    "CREATE INDEX IF NOT EXISTS idx_dq_type        ON data_quality_log (issue_type);",
    "CREATE INDEX IF NOT EXISTS idx_dq_detected    ON data_quality_log (detected_at);",
]

# A collision below this threshold is treated as ordinary index noise and is
# not logged; above it, the two sources genuinely disagree about the lane.
COLLISION_PCT_THRESHOLD = 5.0

# One physical lane may have exactly one rate per index per observation date.
#
# Keyed on observation_date rather than week_ending because FBX publishes
# daily: keying on the derived week would make six of every seven daily prints
# a constraint violation. Keyed on is_synthetic as well so a quarantined seed
# row and the real observation it once displaced can coexist — the real row is
# what statistics read, the synthetic one stays for audit.
#
# Created separately from DDL_INDICES because it fails on a table that still
# holds pre-normalisation duplicates — see _ensure_unique_lane_index().
DDL_UNIQUE_LANE = (
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_fr_lane_obs "
    "ON freight_rates (index_name, canonical_route_id, observation_date, is_synthetic);"
)

# The pre-rename index; dropped during migration so it cannot conflict.
DDL_DROP_LEGACY_UNIQUE = "DROP INDEX IF EXISTS uq_fr_lane_week;"


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
        conn.execute(DDL_DATA_QUALITY_LOG)
        _migrate_schema(conn)
        for idx_sql in DDL_INDICES:
            conn.execute(idx_sql)
        _ensure_unique_lane_index(conn)
        conn.commit()

    logger.info("Database ready at %s", path.resolve())
    return path


def _columns(conn: sqlite3.Connection) -> set[str]:
    """
    All column names on freight_rates, generated columns included.

    table_xinfo, not table_info: the latter omits VIRTUAL generated columns,
    so a guard built on it would try to re-add week_ending on every run.
    """
    return {row[1] for row in conn.execute("PRAGMA table_xinfo(freight_rates)")}


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """Bring an existing freight_rates table up to the current shape."""
    existing = _columns(conn)

    # week_ending used to be a stored column holding whatever date the scraper
    # supplied — daily for FBX, weekly for others. Rename it to the honest
    # name and re-expose week_ending as a derived value.
    if "observation_date" not in existing:
        if "week_ending" in existing:
            conn.execute(
                "ALTER TABLE freight_rates RENAME COLUMN week_ending TO observation_date"
            )
            logger.info(
                "_migrate_schema: renamed freight_rates.week_ending -> observation_date"
            )
        else:
            conn.execute(
                "ALTER TABLE freight_rates ADD COLUMN observation_date TEXT"
            )
            logger.info("_migrate_schema: added freight_rates.observation_date")
        existing = _columns(conn)

    for column, ddl in MIGRATIONS_FREIGHT_RATES:
        if column not in existing:
            conn.execute(ddl)
            logger.info("_migrate_schema: added freight_rates.%s", column)

    # Re-add week_ending as a derived column. SQLite permits adding a VIRTUAL
    # generated column via ALTER TABLE (a STORED one it does not), which suits
    # us: computed on read, so it can never disagree with observation_date.
    existing = _columns(conn)
    if "week_ending" not in existing:
        conn.execute(
            f"ALTER TABLE freight_rates ADD COLUMN week_ending TEXT "
            f"GENERATED ALWAYS AS ({WEEK_ENDING_EXPR}) VIRTUAL"
        )
        logger.info("_migrate_schema: added generated freight_rates.week_ending")


def _ensure_unique_lane_index(conn: sqlite3.Connection) -> bool:
    """
    Create the (index_name, canonical_route_id, observation_date, is_synthetic)
    UNIQUE index, dropping the superseded week_ending-keyed one first.

    Returns False without raising when the table still holds pre-normalisation
    duplicates — the caller is told to run ``migrate_routes.py``, which
    de-duplicates and then installs the index.
    """
    try:
        conn.execute(DDL_DROP_LEGACY_UNIQUE)
        conn.execute(DDL_UNIQUE_LANE)
        return True
    except sqlite3.IntegrityError:
        logger.warning(
            "UNIQUE lane index not created: freight_rates still contains "
            "duplicate (index_name, canonical_route_id, observation_date, "
            "is_synthetic) rows. "
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

# Substrings that mark a source as fabricated rather than observed.
SYNTHETIC_SOURCE_MARKERS = ("seed", "synthetic", "fixture", "sample-data")


def is_synthetic_source(source: str | None) -> bool:
    """
    True when *source* denotes fabricated data rather than a real observation.

    Seed rows exist to bootstrap a demo; they must never reach a statistic.
    """
    if not source:
        return False
    lowered = str(source).lower()
    return any(marker in lowered for marker in SYNTHETIC_SOURCE_MARKERS)


def count_synthetic_rows(db_path: Path | None = None) -> dict[str, Any]:
    """
    Summarise quarantined synthetic rows, for the report header.

    Returns
    -------
    dict: {"synthetic": int, "real": int, "total": int, "by_source": {...}}
    """
    with _connect(db_path) as conn:
        synthetic = conn.execute(
            "SELECT COUNT(*) FROM freight_rates WHERE is_synthetic = 1"
        ).fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM freight_rates").fetchone()[0]
        by_source = {
            row["source"]: row["n"]
            for row in conn.execute(
                "SELECT source, COUNT(*) AS n FROM freight_rates "
                "WHERE is_synthetic = 1 GROUP BY source ORDER BY n DESC"
            )
        }
    return {
        "synthetic": synthetic,
        "real": total - synthetic,
        "total": total,
        "by_source": by_source,
    }


def get_index_data_status(db_path: Path | None = None) -> dict[str, dict[str, Any]]:
    """
    Per-index provenance: how much real data each index has, and how recent.

    Includes indices whose rows are *entirely* synthetic. Those would otherwise
    vanish from every real-data query — an index with no genuine observations
    is the most broken state there is, and must not be the quietest.

    Returns
    -------
    dict keyed by index_name, each:
        {"real": int, "synthetic": int, "last_real": str|None}
    """
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT index_name,
                   SUM(CASE WHEN is_synthetic = 0 THEN 1 ELSE 0 END) AS real_n,
                   SUM(CASE WHEN is_synthetic = 1 THEN 1 ELSE 0 END) AS synth_n,
                   MAX(CASE WHEN is_synthetic = 0 THEN observation_date END) AS last_real
            FROM freight_rates
            GROUP BY index_name
            ORDER BY index_name
            """
        ).fetchall()

    return {
        r["index_name"]: {
            "real": r["real_n"] or 0,
            "synthetic": r["synth_n"] or 0,
            "last_real": r["last_real"],
        }
        for r in rows
    }


def _pct_difference(a: float, b: float) -> float:
    """
    Relative gap between two rates, as a percentage of the smaller.

    Symmetric and expressed against the smaller value so a doubling reads as
    100% rather than 50%.
    """
    lo, hi = sorted((abs(a), abs(b)))
    if lo == 0:
        return 0.0 if hi == 0 else float("inf")
    return (hi - lo) / lo * 100.0


def _record_collisions(
    conn: sqlite3.Connection,
    collisions: list[dict[str, Any]],
) -> None:
    """Log each collision as a WARNING and persist it to data_quality_log."""
    detected_at = datetime.now(timezone.utc).isoformat()

    for c in collisions:
        logger.warning(
            "RATE COLLISION %s/%s week=%s: stored $%s (%s) vs incoming "
            "$%s (%s) — %.1f%% apart; incoming wins (last-write-wins)",
            c["index_name"], c["canonical_route_id"], c["week_ending"],
            f"{c['existing_value']:,.0f}", c["existing_raw_route"],
            f"{c['incoming_value']:,.0f}", c["incoming_raw_route"],
            c["pct_difference"],
        )

    conn.executemany(
        """
        INSERT INTO data_quality_log
            (detected_at, issue_type, index_name, canonical_route_id,
             week_ending, existing_value, incoming_value, pct_difference,
             existing_raw_route, incoming_raw_route, winner, notes)
        VALUES (?, 'rate_collision', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                detected_at, c["index_name"], c["canonical_route_id"],
                c["week_ending"], c["existing_value"], c["incoming_value"],
                round(c["pct_difference"], 2), c["existing_raw_route"],
                c["incoming_raw_route"], c["winner"], c["notes"],
            )
            for c in collisions
        ],
    )
    logger.warning(
        "insert_rates: %d rate collision(s) >%.0f%% recorded in data_quality_log",
        len(collisions), COLLISION_PCT_THRESHOLD,
    )


def log_data_quality_issue(
    issue_type: str,
    notes: str,
    index_name: str | None = None,
    canonical_route_id: str | None = None,
    week_ending: str | None = None,
    existing_value: float | None = None,
    incoming_value: float | None = None,
    db_path: Path | None = None,
) -> None:
    """Record a non-collision data-quality issue (e.g. a stale index)."""
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO data_quality_log
                (detected_at, issue_type, index_name, canonical_route_id,
                 week_ending, existing_value, incoming_value, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(), issue_type, index_name,
                canonical_route_id, week_ending, existing_value,
                incoming_value, notes,
            ),
        )


def insert_rates(
    rates: list[dict[str, Any]],
    db_path: Path | None = None,
) -> int:
    """
    Insert a batch of rate dicts into *freight_rates*.

    Each row's raw route string is resolved to a canonical lane ID, and both
    the canonical ID and the original string are stored. Writes use
    INSERT OR REPLACE keyed on the UNIQUE (index_name, canonical_route_id,
    observation_date, is_synthetic) index, so re-running a scrape updates the
    existing row for that lane and day rather than appending a duplicate.

    Because INSERT OR REPLACE resolves collisions by last-write-wins, any
    replacement where the incoming rate differs from the stored rate by more
    than COLLISION_PCT_THRESHOLD is logged as a WARNING and recorded in
    ``data_quality_log`` — two sources disagreeing about the same lane-day is
    a data-quality signal, not something to silently overwrite.

    Rows whose source is marked as seeded are flagged ``is_synthetic = 1`` and
    are excluded from every historical statistic.

    Parameters
    ----------
    rates : list[dict]
        Each dict must contain keys:
        index_name, route, rate_usd_per_feu, source_url, and either
        observation_date or (legacy) week_ending.

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
    collisions: list[dict[str, Any]] = []

    with _connect(db_path) as conn:
        for r in rates:
            try:
                raw_route = r["route"]
                canonical = normalise_route(raw_route, r.get("index_name"))
                index_name = normalise_index(r["index_name"])

                if is_unmapped(canonical):
                    unmapped_seen.add(str(raw_route))

                # Accept the new key, falling back to the legacy one so
                # scrapers not yet updated keep working.
                observation_date = r.get("observation_date") or r["week_ending"]
                source = r.get("source_url")
                synthetic = 1 if is_synthetic_source(source) else 0

                # Inspect the row this write is about to replace, so a
                # material disagreement is recorded rather than lost.
                existing = conn.execute(
                    """
                    SELECT rate_usd, raw_route_string, route, source
                    FROM freight_rates
                    WHERE index_name = ? AND canonical_route_id = ?
                      AND observation_date = ? AND is_synthetic = ?
                    """,
                    (index_name, canonical, observation_date, synthetic),
                ).fetchone()

                if existing is not None:
                    incoming_rate = float(r["rate_usd_per_feu"])
                    existing_rate = float(existing["rate_usd"])
                    pct = _pct_difference(existing_rate, incoming_rate)
                    if pct > COLLISION_PCT_THRESHOLD:
                        collisions.append({
                            "index_name": index_name,
                            "canonical_route_id": canonical,
                            "week_ending": observation_date,
                            "existing_value": existing_rate,
                            "incoming_value": incoming_rate,
                            "pct_difference": pct,
                            "existing_raw_route": (
                                existing["raw_route_string"] or existing["route"]
                            ),
                            "incoming_raw_route": str(raw_route),
                            "winner": "incoming",
                            "notes": (
                                f"INSERT OR REPLACE last-write-wins; "
                                f"existing source={existing['source']}, "
                                f"incoming source={source}"
                            ),
                        })

                conn.execute(
                    """
                    INSERT OR REPLACE INTO freight_rates
                        (index_name, route, rate_usd, observation_date, scraped_at,
                         source, canonical_route_id, raw_route_string, is_synthetic)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        index_name,
                        raw_route,
                        r["rate_usd_per_feu"],
                        observation_date,
                        scraped_at,
                        source,
                        canonical,
                        raw_route,
                        synthetic,
                    ),
                )
                written += conn.execute("SELECT changes()").fetchone()[0]
            except (KeyError, sqlite3.Error) as exc:
                logger.error("insert_rates: skipping row due to error: %s | row=%s", exc, r)

        if collisions:
            _record_collisions(conn, collisions)

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
    include_synthetic: bool = False,
) -> list[dict[str, Any]]:
    """
    Return the most-recent rate for every (index_name, canonical_route_id) lane.

    Grouping is by canonical lane, not by raw route string, so a lane that
    several scrapers spell differently yields one row rather than several.

    Synthetic rows are excluded unless *include_synthetic* is set — a seeded
    value must never be presented as the latest observation.

    Parameters
    ----------
    index_name : str, optional
        Filter to a specific index (e.g. 'WCI'). Normalised before matching.
    include_synthetic : bool
        Include quarantined seed rows. For audit tooling only.
    """
    from analysis.route_normaliser import normalise_index  # noqa: PLC0415

    synth_filter = "" if include_synthetic else "AND is_synthetic = 0"
    outer_filter = "" if include_synthetic else "WHERE fr.is_synthetic = 0"

    with _connect(db_path) as conn:
        if index_name:
            rows = conn.execute(
                f"""
                SELECT fr.*
                FROM freight_rates fr
                INNER JOIN (
                    SELECT index_name, canonical_route_id,
                           MAX(observation_date) AS max_obs
                    FROM freight_rates
                    WHERE index_name = ? {synth_filter}
                    GROUP BY index_name, canonical_route_id
                ) latest
                ON fr.index_name          = latest.index_name
                AND fr.canonical_route_id = latest.canonical_route_id
                AND fr.observation_date   = latest.max_obs
                {outer_filter}
                ORDER BY fr.canonical_route_id
                """,
                (normalise_index(index_name),),
            ).fetchall()
        else:
            rows = conn.execute(
                f"""
                SELECT fr.*
                FROM freight_rates fr
                INNER JOIN (
                    SELECT index_name, canonical_route_id,
                           MAX(observation_date) AS max_obs
                    FROM freight_rates
                    WHERE 1=1 {synth_filter}
                    GROUP BY index_name, canonical_route_id
                ) latest
                ON fr.index_name          = latest.index_name
                AND fr.canonical_route_id = latest.canonical_route_id
                AND fr.observation_date   = latest.max_obs
                {outer_filter}
                ORDER BY fr.index_name, fr.canonical_route_id
                """,
            ).fetchall()

    return [dict(r) for r in rows]


def get_rate_history(
    route: str,
    weeks: int = 12,
    index_name: str | None = None,
    db_path: Path | None = None,
    include_synthetic: bool = False,
) -> list[dict[str, Any]]:
    """
    Return *weeks* calendar weeks of history for one canonical lane.

    The window is bounded by **time**, not by row count or by a count of
    distinct dates: every observation on or after
    ``max(observation_date) - weeks*7 days`` is returned. With FBX publishing
    daily and other indices weekly, a row-bounded window would silently mean a
    different span per index.

    Synthetic rows are excluded unless *include_synthetic* is set, so no
    seeded value can reach a historical statistic.

    Parameters
    ----------
    route       : Canonical lane ID (e.g. 'CN_NEUR'). A raw scraper string is
                  also accepted and normalised, so older callers keep working.
    weeks       : Width of the window in calendar weeks.
    index_name  : Optional filter to a single index source.
    include_synthetic : Include quarantined seed rows. Audit tooling only.
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

    synth_filter = "" if include_synthetic else "AND is_synthetic = 0"
    days = int(weeks) * 7

    with _connect(db_path) as conn:
        if index_name:
            params: tuple[Any, ...] = (
                canonical, normalise_index(index_name),
                canonical, normalise_index(index_name),
            )
            index_clause = "AND index_name = ?"
        else:
            params = (canonical, canonical)
            index_clause = ""

        rows = conn.execute(
            f"""
            SELECT * FROM freight_rates
            WHERE canonical_route_id = ? {index_clause} {synth_filter}
              AND observation_date >= (
                  SELECT date(MAX(observation_date), '-{days} days')
                  FROM freight_rates
                  WHERE canonical_route_id = ? {index_clause} {synth_filter}
              )
            ORDER BY observation_date DESC
            """,
            params,
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
