"""
Financial Modeling Agent - Builds ROI projections, budget feasibility, and revenue forecasts.
"""

from typing import Dict, Any
from agents import BaseAgent
from utils.prompt_templates import FINANCIAL_MODELING_PROMPT


class FinancialModelingAgent(BaseAgent):
    """Agent specialized in financial analysis and projections."""
    
    def __init__(self):
        super().__init__(
            name="Financial Modeling Agent",
            role="Creates ROI projections, budget analysis, and revenue forecasts",
            system_prompt=FINANCIAL_MODELING_PROMPT
        )
    
    async def analyze(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Conduct financial modeling and analysis.
        
        Args:
            project_data: Dict with 'budget', 'genre', 'platform', 'comparable_revenues'
            
        Returns:
            Financial projections and ROI analysis
        """
        budget = project_data.get('budget', 0)
        genre = project_data.get('genre', 'Unknown')
        platform = project_data.get('platform', 'theatrical')  # theatrical, streaming, hybrid
        description = project_data.get('description', '')
        market_data = project_data.get('market_analysis', {})
        comparable_evidence = project_data.get("comparable_evidence", [])
        assumptions = normalize_financial_assumptions(
            project_data.get("financial_assumptions", {}),
            budget=budget,
            platform=platform,
        )

        metrics = self._calculate_basic_metrics(
            budget,
            genre,
            platform,
            comparable_evidence=comparable_evidence,
            assumptions=assumptions,
        )

        if project_data.get("demo_mode"):
            findings = self._demo_findings(budget, platform, metrics)
            return self.format_result(
                findings=findings,
                confidence=0.86,
                metadata={
                    "budget": budget,
                    "platform": platform,
                    "genre": genre,
                    "basic_metrics": metrics,
                    "assumptions": assumptions,
                },
            )
        
        user_message = f"""
Build a comprehensive financial model for this project:

**Project Description:** {description}

**Production Budget:** ${budget:,}
**Genre:** {genre}
**Distribution Platform:** {platform}
**Financial Assumptions:** {assumptions}

Based on the market analysis:
{market_data.get('findings', 'No market data available')}

Please provide:
1. Revenue projections (conservative, moderate, optimistic scenarios)
2. Break-even analysis
3. ROI estimates for each scenario
4. Marketing budget recommendations
5. Revenue timeline (opening weekend, domestic total, international, ancillary)
6. Risk factors affecting financial performance
7. Comparable title revenue benchmarks

For streaming projects, focus on subscriber acquisition value and retention metrics.
For theatrical, provide box office projections.
"""
        
        self.add_to_history("user", user_message)
        
        response = self._call_claude(
            messages=self.conversation_history,
            temperature=0.5  # Lower temperature for numerical analysis
        )
        
        findings = response.content[0].text
        self.add_to_history("assistant", findings)
        
        # Confidence is higher when we have budget and market data
        confidence = 0.6
        if budget > 0:
            confidence += 0.2
        if market_data:
            confidence += 0.2
        
        return self.format_result(
            findings=findings,
            confidence=confidence,
            metadata={
                "budget": budget,
                "platform": platform,
                "genre": genre,
                "basic_metrics": metrics,
                "assumptions": assumptions,
            }
        )
    
    def _calculate_basic_metrics(
        self,
        budget: int,
        genre: str,
        platform: str,
        comparable_evidence: list = None,
        assumptions: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Calculate basic financial benchmarks."""
        comparable_evidence = comparable_evidence or []
        assumptions = normalize_financial_assumptions(
            assumptions,
            budget=budget,
            platform=platform,
        )

        if budget <= 0:
            return {
                "budget_warning": "Budget not provided; ROI calculations unavailable.",
                "conservative_revenue": 0,
                "moderate_revenue": 0,
                "optimistic_revenue": 0,
                "conservative_roi": 0,
                "moderate_roi": 0,
                "optimistic_roi": 0,
                "break_even_revenue": 0,
                "total_exposure": 0,
                "assumptions": assumptions,
            }
        
        # Industry multipliers (simplified - real models are much more complex)
        theatrical_multipliers = {
            "Action": 2.5,
            "Comedy": 2.8,
            "Drama": 2.2,
            "Horror": 3.5,  # Horror typically has great ROI
            "Science Fiction": 2.4,
            "Unknown": 2.0
        }
        
        comparable_revenues = [
            item.get("revenue", 0)
            for item in comparable_evidence
            if item.get("revenue", 0) > 0
        ]
        comparable_average = (
            sum(comparable_revenues) / len(comparable_revenues)
            if comparable_revenues
            else 0
        )
        
        if platform in ("theatrical", "hybrid"):
            multiplier = theatrical_multipliers.get(genre, 2.0)
            downside_multiplier = assumptions["downside_revenue_multiplier"] or (multiplier * 0.7)
            base_multiplier = assumptions["base_revenue_multiplier"] or multiplier
            upside_multiplier = assumptions["upside_revenue_multiplier"] or (multiplier * 1.5)
            conservative_revenue = budget * downside_multiplier
            moderate_revenue = budget * base_multiplier
            optimistic_revenue = budget * upside_multiplier
            if comparable_average:
                conservative_revenue = (conservative_revenue + comparable_average * 0.45) / 2
                moderate_revenue = (moderate_revenue + comparable_average * 0.65) / 2
                optimistic_revenue = (optimistic_revenue + comparable_average * 0.9) / 2

            total_exposure = budget + assumptions["marketing_spend"]
            net_revenue_share = max(
                0.0,
                assumptions["theatrical_revenue_share"] * (1 - assumptions["distribution_fee_pct"]),
            )
            if platform == "hybrid":
                net_revenue_share += 0.15
            break_even_revenue = (
                total_exposure / net_revenue_share
                if net_revenue_share > 0
                else 0
            )
            scenarios = {
                "conservative": conservative_revenue,
                "moderate": moderate_revenue,
                "optimistic": optimistic_revenue,
            }
            net_scenarios = {
                name: gross * net_revenue_share + assumptions["streaming_license_value"]
                for name, gross in scenarios.items()
            }
            roi_scenarios = {
                name: round(((net - total_exposure) / total_exposure) * 100, 2)
                for name, net in net_scenarios.items()
            }
            
            return {
                "conservative_revenue": round(conservative_revenue),
                "moderate_revenue": round(moderate_revenue),
                "optimistic_revenue": round(optimistic_revenue),
                "conservative_net_revenue": round(net_scenarios["conservative"]),
                "moderate_net_revenue": round(net_scenarios["moderate"]),
                "optimistic_net_revenue": round(net_scenarios["optimistic"]),
                "conservative_roi": roi_scenarios["conservative"],
                "moderate_roi": roi_scenarios["moderate"],
                "optimistic_roi": roi_scenarios["optimistic"],
                "comparable_average_revenue": round(comparable_average),
                "total_exposure": round(total_exposure),
                "break_even_revenue": round(break_even_revenue),
                "net_revenue_share": round(net_revenue_share, 4),
                "sensitivity_table": build_sensitivity_table(
                    budget,
                    assumptions,
                    comparable_average=comparable_average,
                    genre_multiplier=multiplier,
                    platform=platform,
                ),
                "decision_thresholds": decision_thresholds(assumptions["risk_tolerance"]),
                "assumptions": assumptions,
                "platform_model": "theatrical upside with streaming downside protection"
                if platform == "hybrid"
                else "theatrical",
            }
        else:
            # Streaming model
            value_per_sub = assumptions["subscriber_lifetime_value"]
            est_subs = budget / 1_000_000 * 50
            lifetime_value = est_subs * value_per_sub + assumptions["streaming_license_value"]
            total_exposure = budget + assumptions["marketing_spend"]
            
            return {
                "estimated_new_subscribers": round(est_subs),
                "subscriber_lifetime_value": round(lifetime_value),
                "cost_per_acquisition": round(budget / est_subs) if est_subs > 0 else 0,
                "estimated_roi": round(((lifetime_value - total_exposure) / total_exposure) * 100, 2),
                "comparable_average_revenue": round(comparable_average),
                "total_exposure": round(total_exposure),
                "break_even_subscribers": round(total_exposure / value_per_sub) if value_per_sub > 0 else 0,
                "sensitivity_table": build_streaming_sensitivity_table(budget, assumptions),
                "decision_thresholds": decision_thresholds(assumptions["risk_tolerance"]),
                "assumptions": assumptions,
            }

    def _demo_findings(self, budget: int, platform: str, metrics: Dict[str, Any]) -> str:
        """Return deterministic financial findings for sample mode."""
        if platform == "theatrical":
            moderate = metrics.get("moderate_revenue", 0)
            roi = metrics.get("moderate_roi", 0)
            return (
                f"The deterministic moderate case projects ${moderate:,} in revenue, "
                f"or {roi}% ROI against a ${budget:,} production budget. The project "
                "should stay disciplined on marketing spend and avoid VFX scope creep."
            )

        return (
            f"For a {platform} release, the budget is manageable if packaged as premium "
            "genre programming with theatrical optionality. The financial model favors "
            "a conditional go: cap production exposure, pre-sell international rights "
            "where possible, and use streamer value as downside protection."
        )


DEFAULT_RISK_THRESHOLDS = {
    "conservative": {"go_roi": 60, "conditional_roi": 20},
    "balanced": {"go_roi": 35, "conditional_roi": 0},
    "aggressive": {"go_roi": 20, "conditional_roi": -15},
}


def normalize_financial_assumptions(
    assumptions: Dict[str, Any] = None,
    budget: int = 0,
    platform: str = "theatrical",
) -> Dict[str, Any]:
    """Return bounded, explicit financial assumptions for scenario modeling."""
    assumptions = assumptions or {}
    risk_tolerance = str(assumptions.get("risk_tolerance") or "balanced").lower()
    if risk_tolerance not in DEFAULT_RISK_THRESHOLDS:
        risk_tolerance = "balanced"

    default_marketing = 0
    if budget > 0 and platform in ("theatrical", "hybrid"):
        default_marketing = round(budget * 0.5)

    return {
        "marketing_spend": max(0, _as_int(assumptions.get("marketing_spend"), default_marketing)),
        "distribution_fee_pct": _clamp(_as_float(assumptions.get("distribution_fee_pct"), 0.12), 0, 0.5),
        "theatrical_revenue_share": _clamp(_as_float(assumptions.get("theatrical_revenue_share"), 0.5), 0, 1),
        "streaming_license_value": max(0, _as_int(assumptions.get("streaming_license_value"), 0)),
        "subscriber_lifetime_value": max(1, _as_int(assumptions.get("subscriber_lifetime_value"), 120)),
        "downside_revenue_multiplier": max(0, _as_float(assumptions.get("downside_revenue_multiplier"), 0)),
        "base_revenue_multiplier": max(0, _as_float(assumptions.get("base_revenue_multiplier"), 0)),
        "upside_revenue_multiplier": max(0, _as_float(assumptions.get("upside_revenue_multiplier"), 0)),
        "risk_tolerance": risk_tolerance,
    }


def build_sensitivity_table(
    budget: int,
    assumptions: Dict[str, Any],
    comparable_average: float = 0,
    genre_multiplier: float = 2.0,
    platform: str = "theatrical",
) -> list:
    """Calculate revenue/ROI scenarios under supplied assumptions."""
    total_exposure = budget + assumptions["marketing_spend"]
    if total_exposure <= 0:
        return []
    net_revenue_share = max(
        0.0,
        assumptions["theatrical_revenue_share"] * (1 - assumptions["distribution_fee_pct"]),
    )
    if platform == "hybrid":
        net_revenue_share += 0.15
    scenario_defs = [
        ("Downside", assumptions["downside_revenue_multiplier"] or genre_multiplier * 0.7, 0.45),
        ("Base", assumptions["base_revenue_multiplier"] or genre_multiplier, 0.65),
        ("Upside", assumptions["upside_revenue_multiplier"] or genre_multiplier * 1.5, 0.9),
    ]
    rows = []
    for label, multiplier, comparable_weight in scenario_defs:
        gross = budget * multiplier
        if comparable_average:
            gross = (gross + comparable_average * comparable_weight) / 2
        net = gross * net_revenue_share + assumptions["streaming_license_value"]
        rows.append({
            "scenario": label,
            "gross_revenue": round(gross),
            "net_revenue": round(net),
            "roi": round(((net - total_exposure) / total_exposure) * 100, 2),
        })
    return rows


def build_streaming_sensitivity_table(budget: int, assumptions: Dict[str, Any]) -> list:
    total_exposure = budget + assumptions["marketing_spend"]
    if total_exposure <= 0:
        return []
    base_subscribers = budget / 1_000_000 * 50
    rows = []
    for label, factor in [("Downside", 0.7), ("Base", 1.0), ("Upside", 1.4)]:
        subscribers = base_subscribers * factor
        net = subscribers * assumptions["subscriber_lifetime_value"] + assumptions["streaming_license_value"]
        rows.append({
            "scenario": label,
            "subscribers": round(subscribers),
            "net_revenue": round(net),
            "roi": round(((net - total_exposure) / total_exposure) * 100, 2),
        })
    return rows


def decision_thresholds(risk_tolerance: str) -> Dict[str, int]:
    return DEFAULT_RISK_THRESHOLDS.get(risk_tolerance, DEFAULT_RISK_THRESHOLDS["balanced"])


def _as_int(value: Any, default: int) -> int:
    if value in (None, ""):
        return default
    try:
        return int(float(str(value).replace(",", "").replace("$", "")))
    except ValueError:
        return default


def _as_float(value: Any, default: float) -> float:
    if value in (None, ""):
        return default
    try:
        return float(str(value).replace("%", "")) / (100 if "%" in str(value) else 1)
    except ValueError:
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
