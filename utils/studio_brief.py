"""Generate compact studio decision briefs from structured report payloads."""

from __future__ import annotations

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
