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

        metrics = self._calculate_basic_metrics(
            budget,
            genre,
            platform,
            comparable_evidence=comparable_evidence,
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
                },
            )
        
        user_message = f"""
Build a comprehensive financial model for this project:

**Project Description:** {description}

**Production Budget:** ${budget:,}
**Genre:** {genre}
**Distribution Platform:** {platform}

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
                "basic_metrics": metrics
            }
        )
    
    def _calculate_basic_metrics(
        self,
        budget: int,
        genre: str,
        platform: str,
        comparable_evidence: list = None,
    ) -> Dict[str, Any]:
        """Calculate basic financial benchmarks."""
        comparable_evidence = comparable_evidence or []

        if budget <= 0:
            return {
                "budget_warning": "Budget not provided; ROI calculations unavailable.",
                "conservative_revenue": 0,
                "moderate_revenue": 0,
                "optimistic_revenue": 0,
                "conservative_roi": 0,
                "moderate_roi": 0,
                "optimistic_roi": 0,
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
            conservative_revenue = budget * (multiplier * 0.7)
            moderate_revenue = budget * multiplier
            optimistic_revenue = budget * (multiplier * 1.5)
            if comparable_average:
                conservative_revenue = (conservative_revenue + comparable_average * 0.45) / 2
                moderate_revenue = (moderate_revenue + comparable_average * 0.65) / 2
                optimistic_revenue = (optimistic_revenue + comparable_average * 0.9) / 2
            
            return {
                "conservative_revenue": round(conservative_revenue),
                "moderate_revenue": round(moderate_revenue),
                "optimistic_revenue": round(optimistic_revenue),
                "conservative_roi": round((conservative_revenue / budget - 1) * 100, 2),
                "moderate_roi": round((moderate_revenue / budget - 1) * 100, 2),
                "optimistic_roi": round((optimistic_revenue / budget - 1) * 100, 2),
                "comparable_average_revenue": round(comparable_average),
                "platform_model": "theatrical upside with streaming downside protection"
                if platform == "hybrid"
                else "theatrical",
            }
        else:
            # Streaming model
            value_per_sub = 120
            est_subs = budget / 1_000_000 * 50
            lifetime_value = est_subs * value_per_sub
            
            return {
                "estimated_new_subscribers": round(est_subs),
                "subscriber_lifetime_value": round(lifetime_value),
                "cost_per_acquisition": round(budget / est_subs) if est_subs > 0 else 0,
                "estimated_roi": round((lifetime_value / budget - 1) * 100, 2),
                "comparable_average_revenue": round(comparable_average),
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
