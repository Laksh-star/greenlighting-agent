"""Structured report payloads for downstream tools."""

from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import json


def _agent_metadata(results: Dict[str, Any], agent_name: str) -> Dict[str, Any]:
    result = results.get("subagent_results", {}).get(agent_name, {})
    return result.get("metadata", {}) if isinstance(result, dict) else {}


def build_analysis_payload(
    results: Dict[str, Any],
    markdown_report_path: Path,
    run_ledger_path: Path = None,
) -> Dict[str, Any]:
    """Build a stable JSON analysis payload next to the Markdown report."""
    final = results.get("final_recommendation", {})
    subagents = {}

    for name, result in results.get("subagent_results", {}).items():
        if not isinstance(result, dict):
            continue
        subagents[name] = {
            "agent": result.get("agent", name),
            "role": result.get("role"),
            "confidence": result.get("confidence"),
            "findings": result.get("findings"),
            "error": result.get("error", ""),
            "metadata": result.get("metadata", {}),
        }

    return {
        "schema_version": "1.0",
        "generated_at": datetime.utcnow().isoformat(),
        "project": results.get("requested_project_data", results.get("project_data", {})),
        "source_material": _source_material_summary(
            results.get("requested_project_data", results.get("project_data", {})).get(
                "source_material",
                {},
            )
        ),
        "recommendation": final.get("recommendation"),
        "confidence": final.get("confidence"),
        "summary": final.get("summary"),
        "decision_drivers": final.get("decision_drivers", []),
        "analysis": final.get("analysis"),
        "comparable_evidence": _agent_metadata(results, "market_research").get(
            "comparable_evidence",
            [],
        ),
        "financial_scenarios": _agent_metadata(results, "financial_model").get(
            "basic_metrics",
            {},
        ),
        "financial_assumptions": _agent_metadata(results, "financial_model").get(
            "assumptions",
            {},
        ),
        "scenario_comparison": _agent_metadata(results, "financial_model").get(
            "scenario_comparison",
            [],
        ),
        "sensitivity_table": _agent_metadata(results, "financial_model")
        .get("basic_metrics", {})
        .get("sensitivity_table", []),
        "risk_matrix": {
            "overall_risk_score": _agent_metadata(results, "risk_analysis").get(
                "overall_risk_score",
            ),
            "risk_level": _agent_metadata(results, "risk_analysis").get("risk_level"),
            "risk_factors": _agent_metadata(results, "risk_analysis").get(
                "risk_factors",
                {},
            ),
        },
        "report_quality": results.get("report_quality", {}),
        "subagent_results": subagents,
        "markdown_report_path": str(markdown_report_path),
        "run_ledger_path": str(run_ledger_path) if run_ledger_path else "",
}


def _source_material_summary(source_material: Dict[str, Any]) -> Dict[str, Any]:
    if not source_material:
        return {}
    return {
        "name": source_material.get("name", ""),
        "word_count": source_material.get("word_count", 0),
        "character_count": source_material.get("character_count", 0),
        "line_count": source_material.get("line_count", 0),
        "excerpt": source_material.get("excerpt", ""),
    }


def save_analysis_json(
    results: Dict[str, Any],
    markdown_report_path: Path,
    run_ledger_path: Path = None,
) -> Path:
    """Save the structured JSON report beside the Markdown report."""
    payload = build_analysis_payload(results, markdown_report_path, run_ledger_path)
    json_path = Path(markdown_report_path).with_suffix(".json")
    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2)
    return json_path
