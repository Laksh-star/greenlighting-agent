"""Report library helpers for browsing generated local reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def list_report_summaries(report_dir: Path, limit: int = 25) -> List[Dict[str, Any]]:
    """Return newest structured report summaries."""
    rows = []
    for json_path in sorted(report_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True):
        try:
            payload = json.loads(json_path.read_text())
        except json.JSONDecodeError:
            continue
        markdown_path = json_path.with_suffix(".md")
        rows.append(_summary_from_payload(payload, json_path, markdown_path))
        if len(rows) >= limit:
            break
    return rows


def load_report_detail(report_dir: Path, report_id: str) -> Dict[str, Any]:
    """Load one report detail by report id/stem."""
    json_path = safe_report_json_path(report_dir, report_id)
    payload = json.loads(json_path.read_text())
    markdown_path = json_path.with_suffix(".md")
    markdown = markdown_path.read_text() if markdown_path.exists() else ""
    return {
        "summary": _summary_from_payload(payload, json_path, markdown_path),
        "payload": payload,
        "markdown": markdown,
    }


def safe_report_json_path(report_dir: Path, report_id: str) -> Path:
    """Resolve a report id to a JSON path inside the report directory."""
    safe_id = Path(report_id).stem
    candidate = (report_dir / f"{safe_id}.json").resolve()
    root = report_dir.resolve()
    if root not in candidate.parents or candidate.suffix != ".json":
        raise ValueError("Invalid report id")
    if not candidate.exists():
        raise FileNotFoundError("Report not found")
    return candidate


def _summary_from_payload(payload: Dict[str, Any], json_path: Path, markdown_path: Path) -> Dict[str, Any]:
    project = payload.get("project", {})
    description = project.get("description", "Untitled project")
    financial = payload.get("financial_scenarios", {})
    risk = payload.get("risk_matrix", {})
    assumptions = payload.get("financial_assumptions", {})
    return {
        "id": json_path.stem,
        "generated_at": payload.get("generated_at", ""),
        "project_name": _project_name(description),
        "description": description,
        "budget": project.get("budget", 0),
        "genre": project.get("genre", "Unknown"),
        "platform": project.get("platform", ""),
        "target_audience": project.get("target_audience", ""),
        "recommendation": payload.get("recommendation", ""),
        "confidence": payload.get("confidence", 0),
        "moderate_roi": financial.get("moderate_roi", financial.get("estimated_roi", "")),
        "total_exposure": financial.get("total_exposure", ""),
        "break_even_revenue": financial.get("break_even_revenue", ""),
        "risk_tolerance": assumptions.get("risk_tolerance", ""),
        "risk_level": risk.get("risk_level", ""),
        "overall_risk_score": risk.get("overall_risk_score", ""),
        "markdown_path": str(markdown_path),
        "json_path": str(json_path),
        "has_markdown": markdown_path.exists(),
    }


def _project_name(description: str) -> str:
    words = str(description or "Untitled project").split()
    name = " ".join(words[:6])
    return f"{name}..." if len(words) > 6 else name
