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
    RENAMED_CANONICAL_IDS,
    is_unmapped,
    normalise_index,
    normalise_route,
    validate_route_coverage,
)
from database.db import (
    DDL_DROP_LEGACY_UNIQUE,
    DDL_UNIQUE_LANE,
    DEFAULT_DB_PATH,
    _migrate_schema,
    is_synthetic_source,
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


# Column additions and the week_ending -> observation_date rename are owned by
# database.db._migrate_schema(), so init_db() and this script cannot drift.


def _migrate_canonical_ids(conn: sqlite3.Connection) -> dict[str, int]:
    """
    Rename canonical IDs superseded by the direction-aware vocabulary.

    Currently EUR_USEC -> NEUR_USEC: the old spelling used a second token for
    a region the rest of the registry calls NEUR. Idempotent; a row already
    carrying the new ID is left alone.
    """
    renamed: dict[str, int] = {}
    for old_id, new_id in RENAMED_CANONICAL_IDS.items():
        n = conn.execute(
            "SELECT COUNT(*) FROM freight_rates WHERE canonical_route_id = ?",
            (old_id,),
        ).fetchone()[0]
        if not n:
            continue
        # The UNIQUE index spans (index_name, canonical_route_id,
        # observation_date, is_synthetic); a straight UPDATE would collide if
        # rows already exist under the new ID for the same lane-day.
        clash = conn.execute(
            """
            SELECT COUNT(*) FROM freight_rates a
            WHERE a.canonical_route_id = ?
              AND EXISTS (
                  SELECT 1 FROM freight_rates b
                  WHERE b.canonical_route_id = ?
                    AND b.index_name       = a.index_name
                    AND b.observation_date = a.observation_date
                    AND b.is_synthetic     = a.is_synthetic
              )
            """,
            (old_id, new_id),
        ).fetchone()[0]
        if clash:
            logger.error(
                "canonical ID rename %s -> %s blocked: %d row(s) would collide "
                "with existing %s rows; resolve manually",
                old_id, new_id, clash, new_id,
            )
            continue
        conn.execute(
            "UPDATE freight_rates SET canonical_route_id = ? WHERE canonical_route_id = ?",
            (new_id, old_id),
        )
        renamed[f"{old_id} -> {new_id}"] = n
        logger.info("Renamed canonical ID %s -> %s on %d row(s)", old_id, new_id, n)
    return renamed


def _flag_synthetic(conn: sqlite3.Connection) -> int:
    """
    Mark every row whose source denotes fabricated data as synthetic.

    Quarantine, not deletion: the rows stay queryable for audit but are
    filtered out of every historical statistic.
    """
    rows = conn.execute("SELECT id, source FROM freight_rates").fetchall()
    synthetic_ids = [(r[0],) for r in rows if is_synthetic_source(r[1])]
    if synthetic_ids:
        conn.executemany(
            "UPDATE freight_rates SET is_synthetic = 1 WHERE id = ?", synthetic_ids
        )
    conn.executemany(
        "UPDATE freight_rates SET is_synthetic = 0 WHERE id = ?",
        [(r[0],) for r in rows if not is_synthetic_source(r[1])],
    )
    return len(synthetic_ids)


def restore_displaced_real_rows(
    conn: sqlite3.Connection,
    backup_path: Path,
) -> list[dict]:
    """
    Re-insert real observations that a synthetic row displaced during the
    original de-duplication.

    Reads *backup_path*, finds every lane-day where the surviving row was
    synthetic and a discarded row was real, and restores the real row. The
    synthetic row is kept alongside it — the UNIQUE index includes
    is_synthetic, so both fit, and reads take the real one.
    """
    src = sqlite3.connect(backup_path)
    src.row_factory = sqlite3.Row
    try:
        rows = src.execute(
            "SELECT id, index_name, route, rate_usd, week_ending, scraped_at, source "
            "FROM freight_rates"
        ).fetchall()
    finally:
        src.close()

    groups: dict[tuple[str, str, str], list[dict]] = {}
    for r in rows:
        key = (
            normalise_index(r["index_name"]),
            normalise_route(r["route"], r["index_name"]),
            r["week_ending"],
        )
        groups.setdefault(key, []).append(dict(r))

    restored: list[dict] = []
    for (index_name, lane, obs_date), members in sorted(groups.items()):
        if len(members) < 2:
            continue
        ranked = sorted(members, key=lambda m: (m["scraped_at"], m["id"]), reverse=True)
        keeper, losers = ranked[0], ranked[1:]
        if not is_synthetic_source(keeper["source"]):
            continue   # a real row survived; nothing was lost
        for lost in losers:
            if is_synthetic_source(lost["source"]):
                continue   # synthetic displaced synthetic; no real data lost
            conn.execute(
                """
                INSERT OR REPLACE INTO freight_rates
                    (index_name, route, rate_usd, observation_date, scraped_at,
                     source, canonical_route_id, raw_route_string, is_synthetic)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    index_name, lost["route"], lost["rate_usd"], obs_date,
                    lost["scraped_at"], lost["source"], lane, lost["route"],
                ),
            )
            restored.append({
                "index_name": index_name, "lane": lane,
                "observation_date": obs_date, "rate": lost["rate_usd"],
                "route": lost["route"], "source": lost["source"],
                "displaced_by": keeper["rate_usd"],
            })
    return restored


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


def report_collisions(
    db_path: Path,
    threshold: float = 5.0,
    real_vs_seed_only: bool = False,
) -> int:
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

    def _displaces_real(members: list[dict]) -> bool:
        """True when a synthetic row survives and a real one is discarded."""
        ranked = sorted(members, key=lambda m: (m["scraped_at"], m["id"]), reverse=True)
        if not is_synthetic_source(ranked[0]["source"]):
            return False
        return any(not is_synthetic_source(m["source"]) for m in ranked[1:])

    if real_vs_seed_only:
        collisions = {k: v for k, v in collisions.items() if _displaces_real(v)}

    discarded = sum(len(v) - 1 for v in collisions.values())

    logger.info("=" * 78)
    logger.info("COLLISION REPORT (read-only) — %s", db_path.name)
    if real_vs_seed_only:
        logger.info("FILTER: only collisions where a SEED row displaced a REAL one")
    logger.info("=" * 78)
    logger.info("%d rows, %d colliding lane-day(s), %d rows would be discarded",
                len(rows), len(collisions), discarded)
    logger.info("Survivor rule: ORDER BY scraped_at DESC, id DESC (freshest observation)")
    logger.info("")

    if real_vs_seed_only and not collisions:
        logger.info("No real observation was displaced by a synthetic row.")
        logger.info("=" * 78)
        return 0

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
    Keep one row per (index_name, canonical_route_id, observation_date,
    is_synthetic).

    Real and synthetic rows for the same lane-day are deliberately *not*
    collapsed into each other: is_synthetic is part of the partition, so a
    seeded value can never again displace a real observation. Within a
    partition the survivor is the most recently scraped row, falling back to
    the highest rowid on a tie.
    """
    doomed = conn.execute(
        """
        SELECT id FROM freight_rates
        WHERE id NOT IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY index_name, canonical_route_id,
                                        observation_date, is_synthetic
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


def migrate(
    db_path: Path,
    dry_run: bool = False,
    restore_from: Path | None = None,
) -> int:
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

        # Renames week_ending -> observation_date, adds is_synthetic, and
        # re-adds week_ending as a generated column.
        _migrate_schema(conn)

        # Drop the legacy UNIQUE index before any write. It keys on
        # week_ending, which is now generated: a real row and the seed row it
        # should sit beside both derive the same week, so leaving it in place
        # would make the restore below silently overwrite the seed row instead
        # of adding alongside it.
        conn.execute(DDL_DROP_LEGACY_UNIQUE)

        updated, unmapped = _backfill(conn)
        logger.info("Backfilled canonical_route_id for %d rows", updated)

        renamed = _migrate_canonical_ids(conn)
        if renamed:
            logger.info("Canonical ID renames: %s", renamed)

        flagged = _flag_synthetic(conn)
        logger.info("Flagged %d row(s) as synthetic (quarantined, not deleted)", flagged)

        restored: list[dict] = []
        if restore_from is not None:
            if not restore_from.exists():
                logger.error("Restore source not found: %s", restore_from)
                conn.rollback()
                return 1
            restored = restore_displaced_real_rows(conn, restore_from)
            logger.info("Restored %d real observation(s) displaced by seed rows",
                        len(restored))
            for r in restored:
                logger.info(
                    "   RESTORED %s/%s %s: $%s (%s) — had been displaced by $%s",
                    r["index_name"], r["lane"], r["observation_date"],
                    f"{r['rate']:,.0f}", r["source"], f"{r['displaced_by']:,.0f}",
                )

        removed = _dedupe(conn)
        logger.info("Removed %d duplicate lane-day rows", removed)

        # Install the constraint only once the table can satisfy it.
        try:
            conn.execute(DDL_DROP_LEGACY_UNIQUE)
            conn.execute(DDL_UNIQUE_LANE)
            logger.info("UNIQUE index uq_fr_lane_obs installed")
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
    parser.add_argument("--real-vs-seed-only", action="store_true",
                        help="With --report-collisions, show only cases where a "
                             "synthetic row displaced a real observation")
    parser.add_argument("--restore-from", type=Path, default=None,
                        help="Pre-migration backup to recover real observations "
                             "that were displaced by synthetic rows")
    args = parser.parse_args()

    if args.report_collisions:
        return report_collisions(args.db, threshold=args.threshold,
                                 real_vs_seed_only=args.real_vs_seed_only)

    code = migrate(args.db, dry_run=args.dry_run, restore_from=args.restore_from)

    if code == 0:
        logger.info("Verifying route coverage ...")
        validate_route_coverage(db_path=args.db)
    return code


if __name__ == "__main__":
    sys.exit(main())
