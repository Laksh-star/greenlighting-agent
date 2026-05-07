"""Batch analysis helpers."""

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import csv
import io
import json

from config import BATCHES_DIR
from utils.helpers import extract_project_name, sanitize_filename


BATCH_COLUMNS = [
    "project_name",
    "recommendation",
    "confidence",
    "moderate_roi",
    "risk_level",
    "overall_risk_score",
    "report_path",
    "json_path",
    "ledger_path",
]


def load_batch_projects(csv_path: Path) -> List[Dict[str, Any]]:
    """Load batch project rows from a CSV file."""
    with open(csv_path, newline="") as f:
        return load_batch_projects_from_text(f.read())


def load_batch_projects_from_text(csv_text: str) -> List[Dict[str, Any]]:
    """Load batch project rows from CSV text."""
    rows = list(csv.DictReader(io.StringIO(csv_text)))

    projects = []
    for index, row in enumerate(rows, start=1):
        description = (row.get("description") or "").strip()
        if not description:
            raise ValueError(f"Row {index} is missing required description")
        projects.append({
            "description": description,
            "budget": parse_int(row.get("budget"), default=0),
            "genre": (row.get("genre") or "Unknown").strip() or "Unknown",
            "platform": (row.get("platform") or "theatrical").strip() or "theatrical",
            "comparables": parse_comparables(row.get("comparables") or ""),
            "target_audience": (row.get("target_audience") or "general").strip() or "general",
        })
    return projects


def parse_int(value: Any, default: int = 0) -> int:
    """Parse integer-ish CSV values."""
    if value in (None, ""):
        return default
    try:
        return int(float(str(value).replace(",", "").strip()))
    except ValueError:
        return default


def parse_comparables(value: str) -> List[str]:
    """Parse comma-separated comparable titles."""
    return [item.strip() for item in value.split(",") if item.strip()]


def build_batch_summary_row(results: Dict[str, Any]) -> Dict[str, Any]:
    """Build one summary row from analysis results."""
    project = results.get("requested_project_data", results.get("project_data", {}))
    financial = agent_metadata(results, "financial_model").get("basic_metrics", {})
    risk = agent_metadata(results, "risk_analysis")
    final = results.get("final_recommendation", {})
    description = project.get("description", "Untitled")

    return {
        "project_name": sanitize_filename(extract_project_name(description)),
        "recommendation": final.get("recommendation", ""),
        "confidence": round(final.get("confidence", 0), 4),
        "moderate_roi": financial.get("moderate_roi", financial.get("estimated_roi", "")),
        "risk_level": risk.get("risk_level", ""),
        "overall_risk_score": risk.get("overall_risk_score", ""),
        "report_path": results.get("report_path", ""),
        "json_path": results.get("analysis_json_path", ""),
        "ledger_path": results.get("run_ledger_path", ""),
    }


def agent_metadata(results: Dict[str, Any], agent_name: str) -> Dict[str, Any]:
    """Return agent metadata safely."""
    result = results.get("subagent_results", {}).get(agent_name, {})
    return result.get("metadata", {}) if isinstance(result, dict) else {}


def save_batch_summary(rows: List[Dict[str, Any]]) -> Dict[str, str]:
    """Save batch summary CSV and JSON artifacts."""
    BATCHES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = BATCHES_DIR / f"{timestamp}_summary.csv"
    json_path = BATCHES_DIR / f"{timestamp}_summary.json"

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=BATCH_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    with open(json_path, "w") as f:
        json.dump(rows, f, indent=2)

    return {
        "csv_path": str(csv_path),
        "json_path": str(json_path),
    }
