"""Stress saved forecast volumes without rerunning AI or inflating demand with costs."""

from agents.financial_model import decision_thresholds, normalize_financial_assumptions
from utils.slate_planner import number


def stress_report(payload, revenue_multiplier=1.0, overrun_pct=0.0, marketing_spend=None):
    if number(revenue_multiplier) is None or not 0 <= revenue_multiplier <= 3:
        raise ValueError("Revenue multiplier must be between 0 and 3")
    if number(overrun_pct) is None or not 0 <= overrun_pct <= 100:
        raise ValueError("Overrun must be between 0 and 100 percent")
    project = payload.get("project", {})
    budget = number(project.get("budget"))
    if budget is None or budget <= 0:
        raise ValueError("A positive saved budget is required for stress testing")
    platform = project.get("platform", "theatrical")
    if platform not in ("theatrical", "hybrid", "streaming"):
        raise ValueError("Unsupported distribution platform")
    assumptions = normalize_financial_assumptions(payload.get("financial_assumptions", {}), budget=int(budget), platform=platform)
    if marketing_spend is not None:
        if number(marketing_spend) is None or marketing_spend < 0:
            raise ValueError("Marketing spend cannot be negative")
        assumptions["marketing_spend"] = marketing_spend
    stressed_budget = budget * (1 + overrun_pct / 100)
    exposure = stressed_budget + assumptions["marketing_spend"]
    finance = payload.get("financial_scenarios", {})
    license_value = assumptions["streaming_license_value"]
    thresholds = decision_thresholds(assumptions["risk_tolerance"])
    scenarios = []
    for label, key in (("Downside", "conservative"), ("Base", "moderate"), ("Upside", "optimistic")):
        if platform == "streaming":
            rows = {r.get("scenario"): r for r in payload.get("sensitivity_table", [])}
            row = rows.get(label, {})
            net = number(row.get("net_revenue"))
            if net is None and label == "Base":
                net = number(finance.get("subscriber_lifetime_value"))
            net = max(0, net - license_value) * revenue_multiplier + license_value if net is not None else None
            gross = None
        else:
            gross = number(finance.get(f"{key}_revenue"))
            share = number(finance.get("net_revenue_share"))
            if share is None:
                share = assumptions["theatrical_revenue_share"] * (1 - assumptions["distribution_fee_pct"]) + (.15 if platform == "hybrid" else 0)
            gross = gross * revenue_multiplier if gross is not None else None
            net = gross * share + license_value if gross is not None else None
        roi = (net - exposure) / exposure * 100 if net is not None else None
        signal = None if roi is None else "GO" if roi >= thresholds["go_roi"] else "CONDITIONAL GO" if roi >= thresholds["conditional_roi"] else "NO-GO"
        scenarios.append({"scenario": label, "gross_revenue": round(gross) if gross is not None else None,
                          "modeled_net_value": round(net) if net is not None else None,
                          "profit": round(net - exposure) if net is not None else None,
                          "roi": round(roi, 2) if roi is not None else None, "financial_signal": signal})
    if scenarios[1]["roi"] is None:
        raise ValueError("Saved base scenario data is unavailable; rerun the analysis first")
    share = number(finance.get("net_revenue_share"))
    if share is None:
        share = assumptions["theatrical_revenue_share"] * (1 - assumptions["distribution_fee_pct"]) + (.15 if platform == "hybrid" else 0)
    remaining_cost = max(0, exposure - license_value)
    break_even = (0 if remaining_cost == 0 else remaining_cost / share if share > 0 else None) if platform != "streaming" else None
    return {"original_recommendation": payload.get("recommendation"), "production_budget": round(stressed_budget),
            "total_exposure": round(exposure), "marketing_spend": assumptions["marketing_spend"],
            "revenue_multiplier": revenue_multiplier, "overrun_pct": overrun_pct,
            "break_even_gross": round(break_even) if break_even is not None else None,
            "break_even_subscribers": round(max(0, exposure - license_value) / assumptions["subscriber_lifetime_value"]) if platform == "streaming" else None,
            "thresholds": thresholds, "scenarios": scenarios,
            "note": "Financial threshold signal only, not a revised AI or producer decision. Saved demand stays fixed when costs rise; license value stays fixed. Streaming modeled value is not cash receipts."}
