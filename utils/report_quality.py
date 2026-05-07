"""Report quality checks for saved greenlighting outputs."""

import re
from typing import Any, Dict, List


RECOMMENDATIONS = ("CONDITIONAL GO", "NO-GO", "GO")


class ReportQualityError(ValueError):
    """Raised when a report fails mandatory quality checks."""

    def __init__(self, errors: List[str], warnings: List[str] = None):
        self.errors = errors
        self.warnings = warnings or []
        super().__init__("Report quality checks failed: " + "; ".join(errors))


def validate_report_quality(
    results: Dict[str, Any],
    markdown_report: str,
) -> Dict[str, Any]:
    """Validate a report before it is saved."""
    errors = []
    warnings = []
    project = results.get("requested_project_data") or results.get("project_data", {})
    final = results.get("final_recommendation", {})

    _check_recommendation_consistency(final, errors)
    _check_comparable_evidence(project, markdown_report, results, errors)
    _check_financial_scenarios(project, markdown_report, results, errors)
    _check_risk_matrix(markdown_report, results, errors)
    _check_tmdb_warnings(project, results, warnings)

    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
    }


def assert_report_quality(
    results: Dict[str, Any],
    markdown_report: str,
) -> Dict[str, Any]:
    """Return quality metadata or raise when mandatory checks fail."""
    quality = validate_report_quality(results, markdown_report)
    if quality["errors"]:
        raise ReportQualityError(quality["errors"], quality["warnings"])
    return quality


def _check_recommendation_consistency(final: Dict[str, Any], errors: List[str]):
    expected = final.get("recommendation", "")
    analysis = final.get("analysis", "")
    inferred = infer_recommendation_from_text(analysis)

    if expected not in RECOMMENDATIONS:
        errors.append("Final recommendation is missing or unsupported.")
        return

    if not inferred:
        errors.append("Synthesis text does not state a final recommendation.")
        return

    if inferred != expected:
        errors.append(
            f"Final recommendation '{expected}' does not match synthesis text '{inferred}'."
        )


def _check_comparable_evidence(
    project: Dict[str, Any],
    markdown_report: str,
    results: Dict[str, Any],
    errors: List[str],
):
    if not project.get("comparables"):
        return

    evidence = _agent_metadata(results, "market_research").get("comparable_evidence", [])
    if not evidence:
        errors.append("Comparable evidence is missing despite supplied comparables.")
        return

    if "### Comparable Evidence" not in markdown_report or "| Title | Year |" not in markdown_report:
        errors.append("Comparable table is missing from the Markdown report.")


def _check_financial_scenarios(
    project: Dict[str, Any],
    markdown_report: str,
    results: Dict[str, Any],
    errors: List[str],
):
    if project.get("budget", 0) <= 0:
        return

    metrics = _agent_metadata(results, "financial_model").get("basic_metrics", {})
    if not metrics:
        errors.append("Financial scenarios are missing despite a positive budget.")
        return

    platform = project.get("platform", "theatrical")
    theatrical_keys = {
        "conservative_revenue",
        "moderate_revenue",
        "optimistic_revenue",
    }
    streaming_keys = {"estimated_roi", "subscriber_lifetime_value"}
    has_required_metrics = (
        theatrical_keys.issubset(metrics)
        if platform in ("theatrical", "hybrid")
        else bool(streaming_keys.intersection(metrics))
    )
    if not has_required_metrics:
        errors.append("Financial scenario metrics are incomplete for this platform.")

    if "### Financial Scenario Snapshot" not in markdown_report:
        errors.append("Financial scenario section is missing from the Markdown report.")

    if "### Model Assumptions" not in markdown_report:
        errors.append("Model assumptions section is missing from the Markdown report.")

    if "### Break-even Analysis" not in markdown_report:
        errors.append("Break-even analysis section is missing from the Markdown report.")


def _check_risk_matrix(
    markdown_report: str,
    results: Dict[str, Any],
    errors: List[str],
):
    risk = _agent_metadata(results, "risk_analysis")
    if not risk.get("risk_factors") or risk.get("overall_risk_score") is None:
        errors.append("Risk matrix metadata is missing.")

    if "### Risk Matrix" not in markdown_report:
        errors.append("Risk matrix section is missing from the Markdown report.")


def _check_tmdb_warnings(
    project: Dict[str, Any],
    results: Dict[str, Any],
    warnings: List[str],
):
    if not project.get("comparables"):
        return

    metadata = _agent_metadata(results, "market_research")
    market_warning = metadata.get("market_data_warning")
    if market_warning:
        warnings.append(market_warning)
        return

    evidence = metadata.get("comparable_evidence", [])
    if evidence and all(item.get("source") == "input only" for item in evidence):
        warnings.append("TMDB enrichment unavailable; comparable rows are input-only fallback data.")


def _agent_metadata(results: Dict[str, Any], agent_name: str) -> Dict[str, Any]:
    result = results.get("subagent_results", {}).get(agent_name, {})
    return result.get("metadata", {}) if isinstance(result, dict) else {}


def infer_recommendation_from_text(text: str) -> str:
    """Infer a recommendation from synthesis text using headline-first parsing."""
    normalized = re.sub(r"[*_`#]", "", text or "").lower()
    candidate_lines = [
        line.strip()
        for line in normalized.splitlines()[:40]
        if "recommendation" in line or line.strip().startswith("recommend ")
    ]

    explicit_lines = [
        line for line in candidate_lines if "recommendation:" in line or "recommend a " in line
    ]
    for line in explicit_lines + candidate_lines:
        parsed = _parse_recommendation_line(line)
        if parsed:
            return parsed

    if "conditional go" in normalized or "conditional" in normalized:
        return "CONDITIONAL GO"
    if "no-go" in normalized or "no go" in normalized or re.search(r"\bpass\b", normalized):
        return "NO-GO"
    if any(word in normalized for word in ["greenlight", "go ahead", "recommend", "proceed"]):
        return "GO"
    return ""


def _parse_recommendation_line(line: str) -> str:
    if "conditional go" in line or "recommend a conditional go" in line:
        return "CONDITIONAL GO"
    if "no-go" in line or "no go" in line or re.search(r"\bpass\b", line):
        return "NO-GO"
    if re.search(r"\bgo\b", line) or "greenlight" in line or "proceed" in line:
        return "GO"
    return ""
