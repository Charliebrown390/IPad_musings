"""
Canonical route registry and normaliser.

Problem
-------
Every scraper names the same physical lane differently:

    "Shanghai -> Rotterdam"                      (SCFI, ASCII arrow)
    "Shanghai → Rotterdam"                       (Drewry WCI, Unicode arrow)
    "China/East Asia → North Europe"             (Freightos FBX, region names)
    "FBX03 – China/East Asia → North Europe"     (Freightos FBX, code-prefixed)

Stored verbatim these become four distinct keys, so week-on-week maths runs
independently on four partial histories and the report shows the same lane
four times with contradictory numbers.

Solution
--------
Map every raw string to a canonical lane ID (``CN_NEUR``). The raw string is
still kept on the row for audit; the canonical ID drives all joins, WoW
calculations and signal generation.

Anything that fails to map returns an ``UNMAPPED:`` sentinel rather than
None, so that

  * unmapped lanes stay visible in the data instead of vanishing,
  * they never silently merge with each other, and
  * the UNIQUE constraint still applies to them (SQLite treats NULLs as
    distinct, so a NULL canonical ID would defeat the constraint).

Use :func:`validate_route_coverage` to surface unmapped strings as WARNINGs.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Prefix marking a raw string that no rule could resolve.
UNMAPPED_PREFIX = "UNMAPPED:"


# ---------------------------------------------------------------------------
# Canonical registry — one entry per physical lane
# ---------------------------------------------------------------------------

# Every ID is ORIGIN_DEST built from one region vocabulary, so direction is
# part of the identity. Without that, a backhaul lane and its headhaul twin
# resolve to the same ID and INSERT OR REPLACE destroys one of them.
#
# Region tokens: CN, USWC, USEC, NEUR, MED, SAM, OCE, PG.
# NEUR is the sole token for North Europe; an earlier EUR_USEC spelling used a
# second token for the same region and is renamed by _migrate_canonical_ids().
CANONICAL_ROUTES: dict[str, str] = {
    # Headhaul — Asia outbound
    "CN_USWC":   "China/East Asia → North America West Coast",
    "CN_USEC":   "China/East Asia → North America East Coast",
    "CN_NEUR":   "China/East Asia → North Europe",
    "CN_MED":    "China/East Asia → Mediterranean",
    "CN_SAM":    "China/East Asia → South America",
    "CN_OCE":    "China/East Asia → Oceania",
    "CN_PG":     "China/East Asia → Persian Gulf",
    # Headhaul — transatlantic
    "NEUR_USEC": "North Europe → North America East Coast",
    "USEC_NEUR": "North America East Coast → North Europe",
    # Backhaul — the return legs into Asia
    "USWC_CN":   "North America West Coast → China/East Asia",
    "USEC_CN":   "North America East Coast → China/East Asia",
    "NEUR_CN":   "North Europe → China/East Asia",
    "MED_CN":    "Mediterranean → China/East Asia",
    "SAM_CN":    "South America → China/East Asia",
    "OCE_CN":    "Oceania → China/East Asia",
}

# Lanes running *into* Asia are backhaul: carriers price the return leg near
# marginal cost to avoid repositioning empty boxes, so the rate reflects
# repositioning economics rather than demand. Low values on these lanes are
# legitimate, not corrupt.
BACKHAUL_ROUTES: frozenset[str] = frozenset({
    "USWC_CN", "USEC_CN", "NEUR_CN", "MED_CN", "SAM_CN", "OCE_CN",
})


def is_backhaul(canonical_route_id: str | None) -> bool:
    """
    True when the lane is a return leg.

    Derived from the registry rather than stored, so it cannot drift out of
    step with the ID it describes.
    """
    return bool(canonical_route_id) and canonical_route_id in BACKHAUL_ROUTES


# Canonical IDs superseded by the direction-aware vocabulary, old -> new.
RENAMED_CANONICAL_IDS: dict[str, str] = {
    "EUR_USEC": "NEUR_USEC",
}


# ---------------------------------------------------------------------------
# Region synonyms
# ---------------------------------------------------------------------------
# Each region token maps to the phrases that denote it. Matching is
# longest-phrase-first so "north america east coast" wins over "america",
# and "north europe" resolves the same as bare "europe".

_REGION_SYNONYMS: dict[str, list[str]] = {
    "CN": [
        "china/east asia", "east asia", "china", "shanghai", "ningbo",
        "shenzhen", "yantian", "asia", "cn",
    ],
    "USWC": [
        "north america west coast", "us west coast", "usa west coast",
        "west coast north america", "los angeles", "long beach",
        "uswc", "usw", "nawc",
    ],
    "USEC": [
        "north america east coast", "us east coast", "usa east coast",
        "east coast north america", "new york", "savannah", "norfolk",
        "usec", "use", "naec",
    ],
    "NEUR": [
        "north europe", "northern europe", "rotterdam", "hamburg",
        "antwerp", "felixstowe", "bremerhaven", "europe", "neur", "eur",
    ],
    "MED": [
        "mediterranean", "port said", "genoa", "barcelona", "valencia",
        "piraeus", "med",
    ],
    "SAM": [
        "south america east coast", "south america west coast",
        "south america", "santos", "sam",
    ],
    "OCE": [
        "australia/nz", "australia / nz", "new zealand", "australia",
        "oceania", "sydney", "melbourne", "anz", "oce",
    ],
    "PG": [
        "persian gulf & red sea", "persian gulf and red sea",
        "persian gulf", "arabian gulf", "middle east", "jebel ali",
        "red sea", "dubai", "pg",
    ],
}

# Flattened (phrase, region) pairs, longest phrase first.
_SYNONYM_INDEX: list[tuple[str, str]] = sorted(
    ((phrase, region)
     for region, phrases in _REGION_SYNONYMS.items()
     for phrase in phrases),
    key=lambda pair: len(pair[0]),
    reverse=True,
)


# ---------------------------------------------------------------------------
# Origin/destination pair → canonical ID
# ---------------------------------------------------------------------------
# Explicit rather than derived, so that adding a lane is a deliberate act and
# a region pair with no defined lane stays unmapped rather than inferred.

_LANE_IDS: dict[tuple[str, str], str] = {
    # Headhaul
    ("CN", "USWC"):   "CN_USWC",
    ("CN", "USEC"):   "CN_USEC",
    ("CN", "NEUR"):   "CN_NEUR",
    ("CN", "MED"):    "CN_MED",
    ("CN", "SAM"):    "CN_SAM",
    ("CN", "OCE"):    "CN_OCE",
    ("CN", "PG"):     "CN_PG",
    ("NEUR", "USEC"): "NEUR_USEC",
    ("USEC", "NEUR"): "USEC_NEUR",
    # Backhaul
    ("USWC", "CN"):   "USWC_CN",
    ("USEC", "CN"):   "USEC_CN",
    ("NEUR", "CN"):   "NEUR_CN",
    ("MED",  "CN"):   "MED_CN",
    ("SAM",  "CN"):   "SAM_CN",
    ("OCE",  "CN"):   "OCE_CN",
}


# ---------------------------------------------------------------------------
# FBX numeric code → canonical ID
# ---------------------------------------------------------------------------
# Derived from this project's own lane definitions in
# ``scrapers/freightos.py::KNOWN_ROUTES`` — that dict produced the labels
# already stored in the DB, so it is the authority for what these rows mean.
#
# NOTE: this project's numbering does not match the published Freightos FBX
# specification (e.g. real-world FBX11 is China→North Europe, whereas this
# project uses FBX03 for that lane). Codes the project never defined —
# FBX12, FBX14, FBX21, FBX22, FBX24, FBX26 — are deliberately left out
# rather than guessed from the public spec: assigning them a meaning we
# cannot verify would reintroduce exactly the silent corruption this module
# exists to prevent. They resolve to UNMAPPED: and are reported as WARNINGs.

_FBX_CODE_IDS: dict[str, str] = {
    "FBX01": "CN_USWC",    # China/East Asia → North America West Coast
    "FBX02": "CN_USEC",    # China/East Asia → North America East Coast
    "FBX03": "CN_NEUR",    # China/East Asia → North Europe
    "FBX04": "CN_MED",     # China/East Asia → Mediterranean
    "FBX05": "NEUR_USEC",  # Europe → North America East Coast
    "FBX06": "USEC_NEUR",  # North America East Coast → Europe
    "FBX11": "CN_SAM",     # China/East Asia → South America
    "FBX13": "CN_OCE",     # China/East Asia → Oceania
}

_FBX_CODE_RE = re.compile(r"\bFBX\s*(\d{2})\b", re.IGNORECASE)

# Separators that all mean "to": ASCII arrow, Unicode arrow, dashes, "to".
_SEPARATOR_RE = re.compile(
    r"\s*(?:->|-->|→|➔|=>|\bto\b|–|—|-)\s*"
)


# ---------------------------------------------------------------------------
# Index-name normalisation
# ---------------------------------------------------------------------------
# The index column suffers the same disease as the route column:
# "FBX" vs "Freightos FBX", "WCI" vs "Drewry WCI". Left alone, those variants
# defeat any UNIQUE constraint that includes index_name.

_INDEX_ALIASES: list[tuple[str, str]] = [
    ("freightos", "FBX"),
    ("fbx",       "FBX"),
    ("drewry",    "WCI"),
    ("wci",       "WCI"),
    ("scfi",      "SCFI"),
    ("bdi",       "BDI"),
]


def normalise_index(index_name: str | None) -> str:
    """
    Collapse index-name variants to a canonical code.

    >>> normalise_index("Freightos FBX")
    'FBX'
    >>> normalise_index("Drewry WCI")
    'WCI'
    """
    if not index_name:
        return "UNKNOWN"
    lowered = str(index_name).strip().lower()
    for needle, canonical in _INDEX_ALIASES:
        if needle in lowered:
            return canonical
    return str(index_name).strip().upper()


# ---------------------------------------------------------------------------
# Route normalisation
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    """Lowercase, collapse whitespace, drop punctuation noise."""
    text = str(text).strip().lower()
    text = text.replace("&amp;", "&")
    text = re.sub(r"\s+", " ", text)
    return text


def _strip_fbx_prefix(text: str) -> str:
    """Remove a leading ``FBX01 –`` style code prefix, keeping the label."""
    return re.sub(r"^\s*fbx\s*\d{2}\s*[–—\-:]\s*", "", text, flags=re.IGNORECASE)


def _match_region(fragment: str) -> str | None:
    """Return the region token for *fragment*, longest synonym first."""
    fragment = fragment.strip()
    if not fragment:
        return None
    for phrase, region in _SYNONYM_INDEX:
        if phrase in fragment:
            return region
    return None


def _split_endpoints(text: str) -> tuple[str, str] | None:
    """
    Split ``origin <sep> destination`` on the first separator that yields
    two non-empty halves.
    """
    parts = [p for p in _SEPARATOR_RE.split(text) if p and p.strip()]
    if len(parts) < 2:
        return None
    return parts[0].strip(), parts[-1].strip()


def normalise_route(raw_string: str | None, index_name: str | None = None) -> str:
    """
    Map a scraper's route string to a canonical lane ID.

    Resolution order:

    1. An explicit ``FBXnn`` code, looked up in :data:`_FBX_CODE_IDS`.
    2. Origin/destination regions parsed from the text and matched against
       :data:`_LANE_IDS`.

    Parameters
    ----------
    raw_string : str
        Route label as emitted by a scraper.
    index_name : str, optional
        Owning index. Only consulted to prefer the FBX code path.

    Returns
    -------
    str
        A canonical ID from :data:`CANONICAL_ROUTES`, or
        ``"UNMAPPED:<cleaned raw string>"`` when no rule applies.

    Examples
    --------
    >>> normalise_route("Shanghai -> Rotterdam", "SCFI")
    'CN_NEUR'
    >>> normalise_route("Shanghai → Rotterdam", "Drewry WCI")
    'CN_NEUR'
    >>> normalise_route("FBX03 – China/East Asia → North Europe", "Freightos FBX")
    'CN_NEUR'
    >>> normalise_route("New York → Rotterdam", "Drewry WCI")
    'USEC_NEUR'
    """
    if raw_string is None or not str(raw_string).strip():
        return f"{UNMAPPED_PREFIX}<blank>"

    cleaned = _clean(raw_string)
    # Whitespace-normalised but case-preserving, so an unmapped lane still
    # renders as the scraper wrote it ("FBX12", not "fbx12").
    original = re.sub(r"\s+", " ", str(raw_string).strip())

    # 1. Explicit FBX code wins — it is unambiguous where a label may not be.
    code_match = _FBX_CODE_RE.search(cleaned)
    if code_match:
        code = f"FBX{code_match.group(1)}"
        mapped = _FBX_CODE_IDS.get(code.upper())
        if mapped:
            return mapped
        # Known-shape code with no verified lane definition — fall through and
        # try the descriptive label, which may still resolve.

    # 2. Parse origin → destination from the descriptive text.
    label = _strip_fbx_prefix(cleaned)
    endpoints = _split_endpoints(label)
    if endpoints:
        origin = _match_region(endpoints[0])
        dest = _match_region(endpoints[1])
        if origin and dest:
            lane = _LANE_IDS.get((origin, dest))
            if lane:
                return lane

    return f"{UNMAPPED_PREFIX}{original}"


def is_unmapped(canonical_route_id: str | None) -> bool:
    """True when *canonical_route_id* is an UNMAPPED sentinel."""
    return bool(canonical_route_id) and str(canonical_route_id).startswith(UNMAPPED_PREFIX)


def display_name(canonical_route_id: str | None) -> str:
    """
    Human-readable label for a canonical ID, for report tables.

    Unmapped IDs fall back to the raw string they were built from, so nothing
    ever renders as an opaque sentinel.
    """
    if not canonical_route_id:
        return "Unknown route"
    if is_unmapped(canonical_route_id):
        return str(canonical_route_id)[len(UNMAPPED_PREFIX):].strip() or "Unknown route"
    return CANONICAL_ROUTES.get(canonical_route_id, canonical_route_id)


# ---------------------------------------------------------------------------
# Coverage validation
# ---------------------------------------------------------------------------

def validate_route_coverage(
    rows: list[dict[str, Any]] | None = None,
    db_path: Any = None,
) -> dict[str, Any]:
    """
    Check that every raw route string resolves to a canonical lane.

    Logs a WARNING per distinct unmapped string so new scraper output is
    visible instead of silently minting a new key.

    Parameters
    ----------
    rows : list[dict], optional
        Rows carrying ``route`` and ``index_name``. When omitted, every
        distinct pair in ``freight_rates`` is read from the database.

    Returns
    -------
    dict with keys: ``total``, ``mapped``, ``unmapped``, ``unmapped_details``,
    ``coverage_pct``.
    """
    if rows is None:
        # Imported lazily: database.db imports this module, so a top-level
        # import here would be circular.
        from database.db import _connect  # noqa: PLC0415

        with _connect(db_path) as conn:
            rows = [
                dict(r)
                for r in conn.execute(
                    "SELECT DISTINCT index_name, route FROM freight_rates"
                ).fetchall()
            ]

    seen: set[tuple[str, str]] = set()
    unmapped: list[dict[str, str]] = []
    mapped_count = 0

    for row in rows:
        raw = row.get("route") or row.get("raw_route_string")
        index_name = row.get("index_name")
        key = (str(index_name), str(raw))
        if key in seen:
            continue
        seen.add(key)

        canonical = normalise_route(raw, index_name)
        if is_unmapped(canonical):
            unmapped.append({"index_name": str(index_name), "route": str(raw)})
        else:
            mapped_count += 1

    total = len(seen)
    for item in unmapped:
        logger.warning(
            "validate_route_coverage: unmapped route '%s' (index=%s) — "
            "add a synonym or FBX code mapping in analysis/route_normaliser.py",
            item["route"], item["index_name"],
        )

    coverage = (mapped_count / total * 100) if total else 100.0
    logger.info(
        "validate_route_coverage: %d/%d distinct routes mapped (%.1f%%), %d unmapped",
        mapped_count, total, coverage, len(unmapped),
    )

    return {
        "total": total,
        "mapped": mapped_count,
        "unmapped": len(unmapped),
        "unmapped_details": unmapped,
        "coverage_pct": round(coverage, 1),
    }
