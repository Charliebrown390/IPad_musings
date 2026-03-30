"""
Build a static GitHub Pages site from the weekly Markdown reports.

Usage (from freight-tracker/ directory):
    python -m pages.builder

Output layout written to <repo_root>/docs/:
    docs/
        index.html              — latest weekly report
        .nojekyll               — disables Jekyll processing
        reports/
            archive.html        — index of all historical reports
            YYYY-MM-DD.html     — one page per weekly report
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import markdown as md_lib

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

FREIGHT_TRACKER_DIR = Path(__file__).parent.parent          # freight-tracker/
REPO_ROOT           = FREIGHT_TRACKER_DIR.parent            # repo root
REPORTS_DIR         = FREIGHT_TRACKER_DIR / "reports" / "output"
DOCS_DIR            = REPO_ROOT / "docs"
DOCS_REPORTS_DIR    = DOCS_DIR / "reports"

# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  background: #0d1117;
  color: #c9d1d9;
  line-height: 1.6;
  font-size: 16px;
}
nav {
  background: #161b22;
  border-bottom: 1px solid #30363d;
  padding: 0.85rem 1.5rem;
  display: flex;
  gap: 1.5rem;
  align-items: center;
}
nav .brand { font-weight: 700; font-size: 1rem; color: #e6edf3; text-decoration: none; }
nav a { color: #58a6ff; text-decoration: none; font-size: 0.9rem; }
nav a:hover { text-decoration: underline; }
main {
  max-width: 960px;
  margin: 2rem auto;
  padding: 0 1.25rem;
}
h1 { font-size: 1.4rem; margin-bottom: 1rem; color: #e6edf3; }
h2 { font-size: 1.1rem; margin: 1.75rem 0 0.6rem; color: #e6edf3; }
p  { margin-bottom: 0.9rem; }
strong { color: #e6edf3; }
em { color: #8b949e; font-size: 0.85rem; }
hr { border: none; border-top: 1px solid #30363d; margin: 1.5rem 0; }
a  { color: #58a6ff; }
.table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
  white-space: nowrap;
}
th {
  background: #161b22;
  border: 1px solid #30363d;
  padding: 0.55rem 0.9rem;
  text-align: left;
  color: #8b949e;
  font-weight: 600;
}
td {
  border: 1px solid #21262d;
  padding: 0.55rem 0.9rem;
}
tr:nth-child(even) td { background: #161b22; }
.alert-banner {
  background: #3d1a1a;
  border: 1px solid #f85149;
  border-radius: 6px;
  padding: 0.75rem 1rem;
  margin-bottom: 1.25rem;
  color: #f85149;
  font-weight: 600;
}
.archive-list { list-style: none; padding: 0; }
.archive-list li {
  padding: 0.6rem 0;
  border-bottom: 1px solid #21262d;
  font-size: 0.95rem;
}
.archive-list li:last-child { border-bottom: none; }
.report-nav {
  display: flex;
  gap: 1rem;
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 1px solid #30363d;
  font-size: 0.875rem;
}
footer {
  text-align: center;
  padding: 2rem 1rem;
  color: #8b949e;
  font-size: 0.8rem;
  border-top: 1px solid #21262d;
  margin-top: 3rem;
}
@media (max-width: 600px) {
  h1 { font-size: 1.2rem; }
  nav { gap: 1rem; }
}
"""

_PAGE_TMPL = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<nav>
  <a class="brand" href="{root}index.html">📦 Freight Tracker</a>
  <a href="{root}reports/archive.html">Archive</a>
</nav>
<main>
{content}
</main>
<footer>
  Published via GitHub Pages &mdash; updated {generated}
</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Markdown → HTML conversion
# ---------------------------------------------------------------------------

_MD = md_lib.Markdown(extensions=["tables", "extra"])


def _md_to_html(text: str) -> str:
    _MD.reset()
    raw = _MD.convert(text)
    # Wrap every <table> so it horizontally scrolls on mobile
    raw = raw.replace("<table>", '<div class="table-wrap"><table>').replace(
        "</table>", "</table></div>"
    )
    return raw


def _is_alert(md_text: str) -> bool:
    return "🚨" in md_text.split("\n", 1)[0]


# ---------------------------------------------------------------------------
# Report discovery
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(r"weekly_report_(\d{4}-\d{2}-\d{2})\.md$")


def _find_reports() -> list[tuple[str, Path]]:
    """Return [(date_str, path), ...] sorted newest-first."""
    results = []
    for p in REPORTS_DIR.glob("weekly_report_*.md"):
        m = _DATE_RE.search(p.name)
        if m:
            results.append((m.group(1), p))
    results.sort(key=lambda x: x[0], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Page builders
# ---------------------------------------------------------------------------

def _render_page(*, title: str, content_html: str, root: str = "../") -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return _PAGE_TMPL.format(
        title=title,
        css=_CSS,
        root=root,
        content=content_html,
        generated=generated,
    )


def _build_report_page(date_str: str, md_text: str, *, prev_date: str | None, next_date: str | None) -> str:
    alert = _is_alert(md_text)
    body_html = _md_to_html(md_text)

    nav_links = []
    if next_date:
        nav_links.append(f'<a href="{next_date}.html">← Older: {next_date}</a>')
    nav_links.append('<a href="archive.html">All reports</a>')
    if prev_date:
        nav_links.append(f'<a href="{prev_date}.html">Newer: {prev_date} →</a>')

    content = ""
    if alert:
        content += '<div class="alert-banner">🚨 Urgent signals detected — review route table below</div>\n'
    content += body_html
    content += f'\n<div class="report-nav">{" &nbsp;|&nbsp; ".join(nav_links)}</div>'

    return _render_page(title=f"Freight Report — {date_str}", content_html=content)


def _build_archive_page(reports: list[tuple[str, Path]]) -> str:
    items = "\n".join(
        f'  <li><a href="{date}.html">Weekly Report — {date}</a></li>'
        for date, _ in reports
    )
    content = f"""\
<h1>Report Archive</h1>
<p>All weekly freight rate reports, newest first.</p>
<ul class="archive-list">
{items}
</ul>
"""
    return _render_page(title="Freight Report Archive", content_html=content)


def _build_index_page(latest_date: str, latest_md: str) -> str:
    alert = _is_alert(latest_md)
    body_html = _md_to_html(latest_md)

    content = ""
    if alert:
        content += '<div class="alert-banner">🚨 Urgent signals detected — review route table below</div>\n'
    content += body_html
    content += '\n<div class="report-nav"><a href="reports/archive.html">View all historical reports →</a></div>'

    return _render_page(
        title="Freight Tracker — Latest Report",
        content_html=content,
        root="",
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build() -> None:
    reports = _find_reports()
    if not reports:
        print("No weekly reports found in", REPORTS_DIR)
        return

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / ".nojekyll").touch()

    # index.html — latest report
    latest_date, latest_path = reports[0]
    latest_md = latest_path.read_text(encoding="utf-8")
    (DOCS_DIR / "index.html").write_text(
        _build_index_page(latest_date, latest_md), encoding="utf-8"
    )
    print(f"  index.html  ← {latest_path.name}")

    # archive.html
    (DOCS_REPORTS_DIR / "archive.html").write_text(
        _build_archive_page(reports), encoding="utf-8"
    )
    print(f"  reports/archive.html  ({len(reports)} reports)")

    # individual report pages
    for i, (date_str, path) in enumerate(reports):
        md_text = path.read_text(encoding="utf-8")
        prev_date = reports[i - 1][0] if i > 0 else None           # newer
        next_date = reports[i + 1][0] if i < len(reports) - 1 else None  # older
        html = _build_report_page(date_str, md_text, prev_date=prev_date, next_date=next_date)
        out = DOCS_REPORTS_DIR / f"{date_str}.html"
        out.write_text(html, encoding="utf-8")
        print(f"  reports/{date_str}.html")

    print(f"\nSite written to {DOCS_DIR}")


if __name__ == "__main__":
    build()
