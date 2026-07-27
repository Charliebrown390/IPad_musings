"""
One-off migration: backfill canonical route IDs and de-duplicate lanes.

The same physical lane was historically stored under several different
strings ("Shanghai -> Rotterdam", "Shanghai → Rotterdam",
"FBX03 – China/East Asia → North Europe"), producing duplicate rows whose
week-on-week maths disagreed with each other.

This script:

  1. Adds the ``canonical_route_id`` / ``raw_route_string`` columns if absent.
  2. Backfills both for every existing row.
  3. Normalises ``index_name`` variants ("Freightos FBX" → "FBX",
     "Drewry WCI" → "WCI"), which otherwise defeat the UNIQUE constraint.
  4. Collapses duplicate (index_name, canonical_route_id, week_ending) rows,
     keeping the most recently scraped row for each lane-week.
  5. Installs the UNIQUE index that stops duplicates recurring.
  6. Reports any route string that failed to map.

Safe to re-run: every step is idempotent. A timestamped backup of the
database file is written before anything is modified.

Usage
-----
    python migrate_routes.py             # migrate the default DB
    python migrate_routes.py --dry-run   # report only, change nothing
    python migrate_routes.py --db PATH   # migrate a specific file
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from analysis.route_normaliser import (
    is_unmapped,
    normalise_index,
    normalise_route,
    validate_route_coverage,
)
from database.db import (
    DDL_UNIQUE_LANE,
    DEFAULT_DB_PATH,
    MIGRATIONS_FREIGHT_RATES,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(message)s",
)
logger = logging.getLogger("migrate_routes")


def _backup(db_path: Path) -> Path:
    """Copy the database beside itself with a UTC timestamp suffix."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = db_path.with_name(f"{db_path.stem}.pre-migration-{stamp}{db_path.suffix}")
    shutil.copy2(db_path, backup_path)
    logger.info("Backup written to %s", backup_path.name)
    return backup_path


def _add_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(freight_rates)")}
    for column, ddl in MIGRATIONS_FREIGHT_RATES:
        if column in existing:
            logger.info("Column freight_rates.%s already present", column)
        else:
            conn.execute(ddl)
            logger.info("Added column freight_rates.%s", column)


def _backfill(conn: sqlite3.Connection) -> tuple[int, list[tuple[str, str]]]:
    """
    Populate canonical_route_id / raw_route_string and normalise index_name.

    Returns (rows_updated, unmapped_pairs).
    """
    rows = conn.execute(
        "SELECT id, index_name, route FROM freight_rates"
    ).fetchall()

    updated = 0
    unmapped: set[tuple[str, str]] = set()

    for row_id, index_name, route in rows:
        canonical = normalise_route(route, index_name)
        canonical_index = normalise_index(index_name)

        if is_unmapped(canonical):
            unmapped.add((str(index_name), str(route)))

        conn.execute(
            """
            UPDATE freight_rates
            SET canonical_route_id = ?,
                raw_route_string   = COALESCE(raw_route_string, route),
                index_name         = ?
            WHERE id = ?
            """,
            (canonical, canonical_index, row_id),
        )
        updated += 1

    return updated, sorted(unmapped)


def report_collisions(db_path: Path, threshold: float = 5.0) -> int:
    """
    List every lane-week collision without modifying anything.

    Groups rows the way the migration does — by (normalised index, canonical
    lane, week) — and shows which row would survive the
    ``ORDER BY scraped_at DESC, id DESC`` tie-break and what would be
    discarded, so the choice can be audited after the fact.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, index_name, route, rate_usd, week_ending, scraped_at, source "
            "FROM freight_rates"
        ).fetchall()
    finally:
        conn.close()

    groups: dict[tuple[str, str, str], list[dict]] = {}
    for r in rows:
        key = (
            normalise_index(r["index_name"]),
            normalise_route(r["route"], r["index_name"]),
            r["week_ending"],
        )
        groups.setdefault(key, []).append(dict(r))

    collisions = {k: v for k, v in groups.items() if len(v) > 1}
    discarded = sum(len(v) - 1 for v in collisions.values())

    logger.info("=" * 78)
    logger.info("COLLISION REPORT (read-only) — %s", db_path.name)
    logger.info("=" * 78)
    logger.info("%d rows, %d colliding lane-weeks, %d rows would be discarded",
                len(rows), len(collisions), discarded)
    logger.info("Survivor rule: ORDER BY scraped_at DESC, id DESC (freshest observation)")
    logger.info("")

    material = 0
    by_lane: dict[tuple[str, str], list] = {}
    for key, members in collisions.items():
        by_lane.setdefault((key[0], key[1]), []).append((key[2], members))

    for (index_name, lane), weeks in sorted(by_lane.items()):
        logger.info("-" * 78)
        logger.info("%s / %s  — %d colliding week(s)", index_name, lane, len(weeks))
        for week, members in sorted(weeks):
            ranked = sorted(
                members, key=lambda m: (m["scraped_at"], m["id"]), reverse=True
            )
            keeper, losers = ranked[0], ranked[1:]
            worst = max(
                (_pct_gap(keeper["rate_usd"], l["rate_usd"]) for l in losers),
                default=0.0,
            )
            flag = "  <<< MATERIAL" if worst > threshold else ""
            if worst > threshold:
                material += 1
            logger.info("  week %s   spread %.0f%%%s", week, worst, flag)
            logger.info("     KEPT     $%9s  %-52s  src=%s",
                        f"{keeper['rate_usd']:,.0f}",
                        (keeper["route"] or "")[:52], keeper["source"])
            for l in losers:
                logger.info("     DISCARD  $%9s  %-52s  src=%s",
                            f"{l['rate_usd']:,.0f}",
                            (l["route"] or "")[:52], l["source"])
        logger.info("")

    logger.info("=" * 78)
    logger.info("%d of %d collisions exceeded the %.0f%% materiality threshold",
                material, len(collisions), threshold)
    logger.info("=" * 78)
    return 0


def _pct_gap(a: float, b: float) -> float:
    lo, hi = sorted((abs(float(a)), abs(float(b))))
    if lo == 0:
        return 0.0 if hi == 0 else float("inf")
    return (hi - lo) / lo * 100.0


def _dedupe(conn: sqlite3.Connection) -> int:
    """
    Keep one row per (index_name, canonical_route_id, week_ending).

    The survivor is the most recently scraped row, falling back to the highest
    rowid when scraped_at ties — the freshest observation of that lane-week.
    """
    doomed = conn.execute(
        """
        SELECT id FROM freight_rates
        WHERE id NOT IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY index_name, canonical_route_id, week_ending
                           ORDER BY scraped_at DESC, id DESC
                       ) AS rn
                FROM freight_rates
            )
            WHERE rn = 1
        )
        """
    ).fetchall()

    if not doomed:
        return 0

    conn.executemany(
        "DELETE FROM freight_rates WHERE id = ?", [(r[0],) for r in doomed]
    )
    return len(doomed)


def migrate(db_path: Path, dry_run: bool = False) -> int:
    if not db_path.exists():
        logger.error("Database not found: %s", db_path)
        return 1

    logger.info("=" * 68)
    logger.info("Route canonicalisation migration%s", "  [DRY RUN]" if dry_run else "")
    logger.info("Database: %s", db_path)
    logger.info("=" * 68)

    if not dry_run:
        _backup(db_path)

    conn = sqlite3.connect(db_path)
    try:
        before = conn.execute("SELECT COUNT(*) FROM freight_rates").fetchone()[0]
        distinct_before = conn.execute(
            "SELECT COUNT(*) FROM (SELECT DISTINCT index_name, route FROM freight_rates)"
        ).fetchone()[0]
        logger.info("Before: %d rows across %d distinct (index, route) keys",
                    before, distinct_before)

        _add_columns(conn)

        updated, unmapped = _backfill(conn)
        logger.info("Backfilled canonical_route_id for %d rows", updated)

        removed = _dedupe(conn)
        logger.info("Removed %d duplicate lane-week rows", removed)

        # Install the constraint only once the table can satisfy it.
        try:
            conn.execute(DDL_UNIQUE_LANE)
            logger.info("UNIQUE index uq_fr_lane_week installed")
        except sqlite3.IntegrityError as exc:
            logger.error("Could not install UNIQUE index: %s", exc)
            conn.rollback()
            return 1

        after = conn.execute("SELECT COUNT(*) FROM freight_rates").fetchone()[0]
        distinct_after = conn.execute(
            "SELECT COUNT(*) FROM (SELECT DISTINCT index_name, canonical_route_id FROM freight_rates)"
        ).fetchone()[0]
        logger.info("After:  %d rows across %d distinct canonical lanes",
                    after, distinct_after)

        if unmapped:
            logger.warning("-" * 68)
            logger.warning("%d route string(s) did not map to a canonical lane:", len(unmapped))
            for index_name, route in unmapped:
                logger.warning("    %-16s | %s", index_name, route)
            logger.warning("These are stored with an UNMAPPED: prefix and are excluded")
            logger.warning("from canonical aggregation. Add mappings in")
            logger.warning("analysis/route_normaliser.py if they are real lanes.")
            logger.warning("-" * 68)

        if dry_run:
            conn.rollback()
            logger.info("DRY RUN — all changes rolled back")
        else:
            conn.commit()
            logger.info("Migration committed")

        return 0
    except Exception:
        conn.rollback()
        logger.exception("Migration failed — database rolled back")
        return 1
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH,
                        help="Path to the SQLite database")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would change without writing")
    parser.add_argument("--report-collisions", action="store_true",
                        help="List every colliding lane-week and what would be "
                             "discarded, then exit. Never modifies the database.")
    parser.add_argument("--threshold", type=float, default=5.0,
                        help="Materiality threshold for collisions, %% (default 5)")
    args = parser.parse_args()

    if args.report_collisions:
        return report_collisions(args.db, threshold=args.threshold)

    code = migrate(args.db, dry_run=args.dry_run)

    if code == 0:
        logger.info("Verifying route coverage ...")
        validate_route_coverage(db_path=args.db)
    return code


if __name__ == "__main__":
    sys.exit(main())
