"""Create shareable pitch packages from saved analysis reports."""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from utils.studio_brief import build_studio_brief, build_studio_brief_html


def build_pitch_package(
    report_id: str,
    detail: Dict[str, Any],
    output_root: Path,
) -> Dict[str, str]:
    """Create a local folder and zip bundle for one saved report."""
    payload = detail["payload"]
    package_root = output_root / "packages"
    package_dir = package_root / _safe_name(report_id)
    zip_path = package_root / f"{_safe_name(report_id)}.zip"
    package_root.mkdir(parents=True, exist_ok=True)
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True, exist_ok=True)

    _write_text(package_dir / "PACKAGE_SUMMARY.md", _package_summary(report_id, payload))
    _write_text(package_dir / "FULL_REPORT.md", detail.get("markdown", ""))
    _write_json(package_dir / "analysis.json", payload)
    _write_text(package_dir / "STUDIO_BRIEF.md", build_studio_brief(payload))
    _write_text(package_dir / "STUDIO_BRIEF_PRINT.html", build_studio_brief_html(payload))
    _write_json(package_dir / "scenario_comparison.json", payload.get("scenario_comparison", []))
    _write_json(package_dir / "comparable_evidence.json", payload.get("comparable_evidence", []))
    _write_json(package_dir / "financial_assumptions.json", payload.get("financial_assumptions", {}))
    _write_json(package_dir / "source_material_summary.json", payload.get("source_material", {}))

    run_ledger = _load_run_ledger(payload)
    if run_ledger is not None:
        _write_json(package_dir / "run_ledger.json", run_ledger)

    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(package_dir.iterdir()):
            archive.write(file_path, arcname=f"{package_dir.name}/{file_path.name}")

    return {
        "package_dir": str(package_dir),
        "zip_path": str(zip_path),
        "zip_name": zip_path.name,
    }


def _package_summary(report_id: str, payload: Dict[str, Any]) -> str:
    project = payload.get("project", {})
    financial = payload.get("financial_scenarios", {})
    risk = payload.get("risk_matrix", {})
    lines = [
        "# Pitch Package",
        "",
        f"**Report ID:** {report_id}",
        f"**Generated:** {datetime.utcnow().isoformat()}Z",
        f"**Project:** {project.get('description', 'Untitled project')}",
        f"**Recommendation:** {payload.get('recommendation', 'n/a')}",
        f"**Confidence:** {float(payload.get('confidence') or 0):.0%}",
        f"**Budget:** {_money(project.get('budget', 0))}",
        f"**Platform:** {project.get('platform', 'n/a')}",
        f"**Moderate/Base ROI:** {financial.get('moderate_roi', financial.get('estimated_roi', 'n/a'))}%",
        f"**Risk:** {risk.get('risk_level', 'n/a')}",
        "",
        "## Contents",
        "",
        "- `FULL_REPORT.md`: complete generated analysis report",
        "- `analysis.json`: structured report payload",
        "- `STUDIO_BRIEF.md`: compact Markdown decision memo",
        "- `STUDIO_BRIEF_PRINT.html`: printable studio memo",
        "- `scenario_comparison.json`: conservative/base/aggressive case table",
        "- `comparable_evidence.json`: comparable title evidence",
        "- `financial_assumptions.json`: assumptions used in the finance model",
        "- `source_material_summary.json`: source material metadata and excerpt, if supplied",
        "- `run_ledger.json`: model usage and audit ledger, when available",
        "",
        "## Decision Drivers",
        "",
    ]
    drivers = payload.get("decision_drivers") or ["See full report for supporting rationale."]
    lines.extend(f"- {driver}" for driver in drivers[:3])
    return "\n".join(lines) + "\n"


def _load_run_ledger(payload: Dict[str, Any]) -> Dict[str, Any] | None:
    ledger_path = payload.get("run_ledger_path")
    if not ledger_path:
        return None
    path = Path(ledger_path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _write_text(path: Path, content: str) -> None:
    path.write_text(content or "")


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2))


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value).strip("_")


def _money(value: Any) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0
    if not number:
        return "$0"
    if abs(number) >= 1_000_000:
        return f"${number / 1_000_000:.1f}M"
    return f"${number:,.0f}"
