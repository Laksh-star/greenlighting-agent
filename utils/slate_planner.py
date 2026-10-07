"""Budget-fit planning using latest project versions, never automatic approvals."""

import math
from collections import defaultdict
from utils.report_library import load_report_detail


def number(value):
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def planner_candidates(workspaces, report_dir):
    candidates = []
    for row in workspaces.slate(report_dir):
        payload = load_report_detail(report_dir, row["id"])["payload"]
        finance = payload.get("financial_scenarios", {})
        sensitivity = {s.get("scenario"): s.get("roi") for s in payload.get("sensitivity_table", [])}
        rois = {
            "Downside": number(finance.get("conservative_roi", sensitivity.get("Downside"))),
            "Base": number(finance.get("moderate_roi", finance.get("estimated_roi", sensitivity.get("Base")))),
            "Upside": number(finance.get("optimistic_roi", sensitivity.get("Upside"))),
        }
        exposure = number(row.get("total_exposure"))
        decision = row.get("human_decision") or {}
        candidates.append({key: row.get(key) for key in (
            "id", "workspace_id", "project_name", "description", "genre", "platform",
            "version_label", "recommendation", "overall_risk_score", "budget") } | {
            "exposure": exposure, "rois": rois,
            "producer_decision": decision.get("status", "Awaiting review"),
            "conditions": decision.get("conditions", ""),
            "demo_mode": bool(payload.get("project", {}).get("demo_mode", False)),
            "eligible": exposure is not None and exposure > 0 and rois["Base"] is not None,
        })
    return candidates


def build_plan(candidates, funding_cap, selected_ids=None, suggest=False):
    if number(funding_cap) is None or funding_cap <= 0:
        raise ValueError("Funding cap must be greater than zero")
    if suggest:
        # This is a transparent ranked greedy basket, not portfolio optimization.
        eligible = [r for r in candidates if r["eligible"] and r["rois"]["Base"] >= 0
                    and r["recommendation"] in ("GO", "CONDITIONAL GO")
                    and r["producer_decision"] not in ("Hold", "Rework", "Passed")]
        eligible.sort(key=lambda r: (
            r["producer_decision"] != "Approved", r["recommendation"] != "GO",
            -r["rois"]["Base"], number(r["overall_risk_score"]) if number(r["overall_risk_score"]) is not None else 10,
            r["id"]))
        selected_ids, remaining = [], funding_cap
        for row in eligible:
            if row["exposure"] <= remaining:
                selected_ids.append(row["id"])
                remaining -= row["exposure"]
    selected_ids = selected_ids or []
    if len(set(selected_ids)) != len(selected_ids):
        raise ValueError("A project can only be selected once")
    by_id = {row["id"]: row for row in candidates}
    if any(report_id not in by_id for report_id in selected_ids):
        raise ValueError("Selection contains a missing or superseded version; refresh the planner")
    selected = [by_id[report_id] for report_id in selected_ids]
    if any(not row["eligible"] for row in selected):
        raise ValueError("Selected projects require positive exposure and a valid base ROI")
    exposure = sum(row["exposure"] for row in selected)
    mix = defaultdict(float)
    for row in selected:
        mix[row["genre"] or "Unknown"] += row["exposure"]
    scenarios = []
    for name in ("Downside", "Base", "Upside"):
        covered = [row for row in selected if row["rois"][name] is not None]
        complete = len(covered) == len(selected) and bool(selected)
        profit = sum(row["exposure"] * row["rois"][name] / 100 for row in covered)
        scenarios.append({"scenario": name, "coverage": len(covered), "total": len(selected),
                          "modeled_profit": round(profit, 2) if complete else None,
                          "weighted_roi": round(profit / exposure * 100, 2) if complete and exposure else None})
    warnings = []
    if any(row.get("demo_mode") for row in selected):
        warnings.append("Selection includes demo sample analyses, not live AI assessments.")
    if exposure > funding_cap:
        warnings.append("Selection exceeds the funding cap.")
    if any(row["producer_decision"] != "Approved" for row in selected):
        warnings.append("Some selected projects are not approved on their current version.")
    if any(row["conditions"] for row in selected):
        warnings.append("Producer conditions require manual verification; they are not enforced by this planner.")
    if any(row["recommendation"] == "NO-GO" for row in selected):
        warnings.append("Selection includes an AI NO-GO recommendation.")
    if any(row["platform"] == "streaming" for row in selected):
        warnings.append("Streaming modeled value may include subscriber lifetime value, not cash receipts.")
    if any(s["coverage"] != s["total"] for s in scenarios):
        warnings.append("Incomplete scenario data: unavailable totals are not treated as zero.")
    if exposure and mix and max(mix.values()) / exposure > .6:
        warnings.append("More than 60% of exposure is concentrated in one genre.")
    return {"funding_cap": funding_cap, "selected_ids": selected_ids, "projects": selected,
            "total_exposure": round(exposure, 2), "remaining": round(funding_cap - exposure, 2),
            "over_cap": exposure > funding_cap, "scenarios": scenarios,
            "genre_mix": [{"genre": key, "exposure": round(value, 2), "share": round(value / exposure * 100, 2)}
                          for key, value in sorted(mix.items(), key=lambda pair: -pair[1])],
            "warnings": warnings,
            "method": "Ranked budget-fit suggestion; not an optimal portfolio" if suggest else "Manual selection",
            "assumption": "Independent project estimates summed without diversification, correlation, or timing adjustments; not a cash-flow forecast."}
