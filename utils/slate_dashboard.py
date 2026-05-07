"""Build slate-level dashboard metrics from saved report summaries."""

from __future__ import annotations

from typing import Any, Dict, List


def build_slate_dashboard(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return portfolio metrics for saved project reports."""
    recommendation_counts = {"GO": 0, "CONDITIONAL GO": 0, "NO-GO": 0, "UNKNOWN": 0}
    risk_counts: Dict[str, int] = {}
    platform_counts: Dict[str, int] = {}
    total_budget = 0.0
    total_exposure = 0.0
    roi_values = []
    confidence_values = []
    risk_scores = []

    scored_reports = []
    for report in reports:
        recommendation = _recommendation_bucket(report.get("recommendation"))
        recommendation_counts[recommendation] += 1
        platform = report.get("platform") or "n/a"
        platform_counts[platform] = platform_counts.get(platform, 0) + 1

        risk_level = report.get("risk_level") or "Risk n/a"
        risk_counts[risk_level] = risk_counts.get(risk_level, 0) + 1

        budget = _number(report.get("budget"))
        exposure = _number(report.get("total_exposure"))
        roi = _optional_number(report.get("moderate_roi"))
        confidence = _number(report.get("confidence"))
        risk_score = _optional_number(report.get("overall_risk_score"))

        total_budget += budget
        total_exposure += exposure
        if roi is not None:
            roi_values.append(roi)
        if confidence:
            confidence_values.append(confidence)
        if risk_score is not None:
            risk_scores.append(risk_score)

        scored_reports.append({
            **report,
            "slate_score": round(
                _recommendation_score(recommendation)
                + (confidence * 30)
                + _roi_score(roi)
                - _risk_penalty(risk_score),
                1,
            ),
        })

    ranked = sorted(scored_reports, key=lambda item: item["slate_score"], reverse=True)
    watchlist = sorted(
        scored_reports,
        key=lambda item: (
            _number(item.get("overall_risk_score")),
            -_optional_number(item.get("moderate_roi")) if _optional_number(item.get("moderate_roi")) is not None else 999,
        ),
        reverse=True,
    )

    return {
        "report_count": len(reports),
        "recommendation_counts": recommendation_counts,
        "risk_counts": risk_counts,
        "platform_counts": platform_counts,
        "total_budget": round(total_budget),
        "total_exposure": round(total_exposure),
        "average_roi": _average(roi_values),
        "average_confidence": _average(confidence_values),
        "average_risk_score": _average(risk_scores),
        "top_projects": _compact_rows(ranked[:5]),
        "watchlist": _compact_rows(watchlist[:5]),
    }


def _compact_rows(reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "id": report.get("id", ""),
            "project_name": report.get("project_name", ""),
            "recommendation": report.get("recommendation", ""),
            "confidence": report.get("confidence", 0),
            "budget": report.get("budget", 0),
            "moderate_roi": report.get("moderate_roi", ""),
            "risk_level": report.get("risk_level", ""),
            "overall_risk_score": report.get("overall_risk_score", ""),
            "slate_score": report.get("slate_score", 0),
        }
        for report in reports
    ]


def _recommendation_bucket(value: Any) -> str:
    recommendation = str(value or "").upper()
    if recommendation in {"GO", "CONDITIONAL GO", "NO-GO"}:
        return recommendation
    return "UNKNOWN"


def _recommendation_score(recommendation: str) -> float:
    return {
        "GO": 45,
        "CONDITIONAL GO": 25,
        "NO-GO": -20,
        "UNKNOWN": 0,
    }.get(recommendation, 0)


def _roi_score(value: Any) -> float:
    roi = _optional_number(value)
    if roi is None:
        return 0
    return max(-20, min(35, roi / 2))


def _risk_penalty(value: Any) -> float:
    risk = _optional_number(value)
    if risk is None:
        return 0
    return risk * 2.5


def _average(values: List[float]) -> float:
    if not values:
        return 0
    return round(sum(values) / len(values), 2)


def _optional_number(value: Any) -> float | None:
    if value in {"", None, "n/a"}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _number(value: Any) -> float:
    parsed = _optional_number(value)
    return parsed if parsed is not None else 0
