"""Generate compact studio decision briefs from structured report payloads."""

from __future__ import annotations

from html import escape
from typing import Any, Dict, List


def build_studio_brief(payload: Dict[str, Any]) -> str:
    """Return a concise Markdown studio brief from a structured report payload."""
    project = payload.get("project", {})
    financial = payload.get("financial_scenarios", {})
    assumptions = payload.get("financial_assumptions", {})
    risk = payload.get("risk_matrix", {})
    source_material = payload.get("source_material", {})

    lines = [
        "# Studio Greenlight Brief",
        "",
        f"**Project:** {project.get('description', 'Untitled project')}",
        f"**Recommendation:** {payload.get('recommendation', 'n/a')}",
        f"**Confidence:** {_percent(payload.get('confidence', 0))}",
        f"**Genre / Platform:** {project.get('genre', 'Unknown')} / {project.get('platform', 'n/a')}",
        f"**Budget:** {_money(project.get('budget', 0))}",
        "",
        "## Decision Drivers",
        "",
    ]
    drivers = payload.get("decision_drivers") or []
    lines.extend(_bullet_lines(drivers[:3] or ["See full report for supporting rationale."]))

    lines.extend([
        "",
        "## Comparable Evidence",
        "",
    ])
    lines.extend(_comparable_summary(payload.get("comparable_evidence", [])))

    lines.extend([
        "",
        "## Financial Snapshot",
        "",
        f"- **Moderate ROI:** {financial.get('moderate_roi', financial.get('estimated_roi', 'n/a'))}%",
        f"- **Total exposure:** {_money(financial.get('total_exposure', 0))}",
        f"- **Break-even revenue:** {_money(financial.get('break_even_revenue', 0))}",
        f"- **Risk tolerance:** {assumptions.get('risk_tolerance', 'n/a')}",
    ])

    lines.extend([
        "",
        "## Risk Snapshot",
        "",
        f"- **Overall risk:** {risk.get('risk_level', 'n/a')} ({risk.get('overall_risk_score', 'n/a')}/10)",
    ])
    for key, value in (risk.get("risk_factors") or {}).items():
        lines.append(f"- **{key.replace('_', ' ').title()}:** {value}/10")

    if source_material:
        lines.extend([
            "",
            "## Source Material",
            "",
            f"- **Name:** {source_material.get('name', 'source material')}",
            f"- **Words:** {source_material.get('word_count', 0):,}",
        ])

    summary = payload.get("summary")
    if summary:
        lines.extend([
            "",
            "## Executive Note",
            "",
            summary,
        ])

    lines.extend([
        "",
        "---",
        "",
        "*Generated from the Greenlighting Agent structured report. Use as a decision memo, not a substitute for full due diligence.*",
    ])
    return "\n".join(lines)


def build_studio_brief_html(payload: Dict[str, Any]) -> str:
    """Return standalone printable HTML for a studio brief."""
    project = payload.get("project", {})
    financial = payload.get("financial_scenarios", {})
    assumptions = payload.get("financial_assumptions", {})
    risk = payload.get("risk_matrix", {})
    source_material = payload.get("source_material", {})
    drivers = payload.get("decision_drivers") or ["See full report for supporting rationale."]
    comparables = payload.get("comparable_evidence", [])
    summary = payload.get("summary", "")

    return "\n".join([
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        f"  <title>{escape(_project_title(project))} - Studio Brief</title>",
        "  <style>",
        _print_css(),
        "  </style>",
        "</head>",
        "<body>",
        '  <main class="brief-page">',
        '    <header class="brief-header">',
        "      <div>",
        "        <p>Studio Greenlight Brief</p>",
        f"        <h1>{escape(_project_title(project))}</h1>",
        "      </div>",
        '      <button class="print-button" type="button" onclick="window.print()">Print / Save PDF</button>',
        "    </header>",
        '    <section class="summary-grid">',
        _summary_item("Recommendation", payload.get("recommendation", "n/a")),
        _summary_item("Confidence", _percent(payload.get("confidence", 0))),
        _summary_item("Genre / Platform", f"{project.get('genre', 'Unknown')} / {project.get('platform', 'n/a')}"),
        _summary_item("Budget", _money(project.get("budget", 0))),
        "    </section>",
        _section("Decision Drivers", _html_list(drivers[:3])),
        _section("Comparable Evidence", _comparables_table(comparables)),
        _section("Financial Snapshot", _html_list([
            f"Moderate ROI: {financial.get('moderate_roi', financial.get('estimated_roi', 'n/a'))}%",
            f"Total exposure: {_money(financial.get('total_exposure', 0))}",
            f"Break-even revenue: {_money(financial.get('break_even_revenue', 0))}",
            f"Risk tolerance: {assumptions.get('risk_tolerance', 'n/a')}",
        ])),
        _section("Risk Snapshot", _risk_snapshot(risk)),
        _source_material_section(source_material),
        _section("Executive Note", f"<p>{escape(str(summary))}</p>") if summary else "",
        '    <footer>Generated from the Greenlighting Agent structured report. Use as a decision memo, not a substitute for full due diligence.</footer>',
        "  </main>",
        "</body>",
        "</html>",
    ])


def _comparable_summary(comparables: List[Dict[str, Any]]) -> List[str]:
    if not comparables:
        return ["- No comparable evidence supplied."]
    rows = []
    for item in comparables[:5]:
        rows.append(
            "- "
            f"**{item.get('title', 'Unknown')}** "
            f"({_money(item.get('budget', 0))} budget, "
            f"{_money(item.get('revenue', 0))} revenue, "
            f"{item.get('roi', 0)}% ROI)"
        )
    return rows


def _project_title(project: Dict[str, Any]) -> str:
    return str(project.get("description") or "Untitled project")


def _summary_item(label: str, value: Any) -> str:
    return (
        '      <article class="summary-item">'
        f"<span>{escape(label)}</span>"
        f"<strong>{escape(str(value))}</strong>"
        "</article>"
    )


def _section(title: str, body: str) -> str:
    return "\n".join([
        '    <section class="brief-section">',
        f"      <h2>{escape(title)}</h2>",
        f"      {body}",
        "    </section>",
    ])


def _html_list(items: List[Any]) -> str:
    return "<ul>" + "".join(f"<li>{escape(str(item))}</li>" for item in items) + "</ul>"


def _comparables_table(comparables: List[Dict[str, Any]]) -> str:
    if not comparables:
        return "<p>No comparable evidence supplied.</p>"
    rows = []
    for item in comparables[:5]:
        rows.append(
            "<tr>"
            f"<td>{escape(str(item.get('title', 'Unknown')))}</td>"
            f"<td>{escape(str(item.get('year', 'n/a')))}</td>"
            f"<td>{escape(_money(item.get('budget', 0)))}</td>"
            f"<td>{escape(_money(item.get('revenue', 0)))}</td>"
            f"<td>{escape(str(item.get('roi', 0)))}%</td>"
            "</tr>"
        )
    return (
        "<table>"
        "<thead><tr><th>Title</th><th>Year</th><th>Budget</th><th>Revenue</th><th>ROI</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


def _risk_snapshot(risk: Dict[str, Any]) -> str:
    items = [
        f"Overall risk: {risk.get('risk_level', 'n/a')} ({risk.get('overall_risk_score', 'n/a')}/10)"
    ]
    for key, value in (risk.get("risk_factors") or {}).items():
        items.append(f"{key.replace('_', ' ').title()}: {value}/10")
    return _html_list(items)


def _source_material_section(source_material: Dict[str, Any]) -> str:
    if not source_material:
        return ""
    return _section("Source Material", _html_list([
        f"Name: {source_material.get('name', 'source material')}",
        f"Words: {source_material.get('word_count', 0):,}",
    ]))


def _print_css() -> str:
    return """
      :root {
        color-scheme: light;
        --text: #1f2428;
        --muted: #687078;
        --line: #d9d5cd;
        --accent: #236b5d;
        --paper: #ffffff;
        --bg: #f6f5f2;
      }
      * { box-sizing: border-box; }
      body {
        background: var(--bg);
        color: var(--text);
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        line-height: 1.5;
        margin: 0;
      }
      .brief-page {
        background: var(--paper);
        border: 1px solid var(--line);
        margin: 28px auto;
        max-width: 920px;
        padding: 38px;
      }
      .brief-header {
        align-items: flex-start;
        border-bottom: 2px solid var(--text);
        display: flex;
        gap: 20px;
        justify-content: space-between;
        padding-bottom: 20px;
      }
      .brief-header p,
      .summary-item span {
        color: var(--muted);
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 0;
        margin: 0 0 8px;
        text-transform: uppercase;
      }
      h1 {
        font-size: 30px;
        letter-spacing: 0;
        line-height: 1.15;
        margin: 0;
      }
      h2 {
        border-bottom: 1px solid var(--line);
        font-size: 16px;
        letter-spacing: 0;
        margin: 0 0 12px;
        padding-bottom: 7px;
      }
      .print-button {
        background: var(--accent);
        border: 0;
        border-radius: 6px;
        color: #ffffff;
        cursor: pointer;
        font: inherit;
        font-weight: 800;
        min-height: 40px;
        padding: 0 14px;
        white-space: nowrap;
      }
      .summary-grid {
        display: grid;
        gap: 12px;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        margin: 20px 0;
      }
      .summary-item {
        border: 1px solid var(--line);
        border-radius: 6px;
        padding: 12px;
      }
      .summary-item strong {
        display: block;
        font-size: 15px;
      }
      .brief-section {
        margin-top: 22px;
      }
      ul {
        margin: 0;
        padding-left: 20px;
      }
      li {
        margin: 6px 0;
      }
      p {
        margin: 0;
      }
      table {
        border-collapse: collapse;
        font-size: 13px;
        width: 100%;
      }
      th,
      td {
        border-bottom: 1px solid var(--line);
        padding: 8px;
        text-align: left;
      }
      th {
        color: var(--muted);
        font-size: 11px;
        text-transform: uppercase;
      }
      footer {
        border-top: 1px solid var(--line);
        color: var(--muted);
        font-size: 12px;
        margin-top: 26px;
        padding-top: 14px;
      }
      @media print {
        body { background: #ffffff; }
        .brief-page {
          border: 0;
          margin: 0;
          max-width: none;
          padding: 0;
        }
        .print-button { display: none; }
      }
      @media (max-width: 760px) {
        .brief-page {
          margin: 0;
          padding: 22px;
        }
        .brief-header,
        .summary-grid {
          display: block;
        }
        .summary-item,
        .print-button {
          margin-top: 10px;
          width: 100%;
        }
      }
    """.strip()


def _bullet_lines(items: List[str]) -> List[str]:
    return [f"- {item}" for item in items]


def _money(value: Any) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0
    if not number:
        return "$0"
    if abs(number) >= 1_000_000_000:
        return f"${number / 1_000_000_000:.1f}B"
    if abs(number) >= 1_000_000:
        return f"${number / 1_000_000:.1f}M"
    return f"${number:,.0f}"


def _percent(value: Any) -> str:
    try:
        return f"{float(value or 0) * 100:.0f}%"
    except (TypeError, ValueError):
        return "0%"
