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
        
        # Calculate basic financial metrics
        metrics = self._calculate_basic_metrics(budget, genre, platform)
        
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
        platform: str
    ) -> Dict[str, Any]:
        """Calculate basic financial benchmarks."""
        
        # Industry multipliers (simplified - real models are much more complex)
        theatrical_multipliers = {
            "Action": 2.5,
            "Comedy": 2.8,
            "Drama": 2.2,
            "Horror": 3.5,  # Horror typically has great ROI
            "Science Fiction": 2.4,
            "Unknown": 2.0
        }
        
        streaming_multipliers = {
            # Subscriber value metrics (simplified)
            "value_per_subscriber": 120,  # Annual value
            "estimated_new_subs": budget / 1_000_000 * 50  # Rough estimate
        }
        
        if platform == "theatrical":
            multiplier = theatrical_multipliers.get(genre, 2.0)
            conservative_revenue = budget * (multiplier * 0.7)
            moderate_revenue = budget * multiplier
            optimistic_revenue = budget * (multiplier * 1.5)
            
            return {
                "conservative_revenue": round(conservative_revenue),
                "moderate_revenue": round(moderate_revenue),
                "optimistic_revenue": round(optimistic_revenue),
                "conservative_roi": round((conservative_revenue / budget - 1) * 100, 2),
                "moderate_roi": round((moderate_revenue / budget - 1) * 100, 2),
                "optimistic_roi": round((optimistic_revenue / budget - 1) * 100, 2)
            }
        else:
            # Streaming model
            est_subs = streaming_multipliers["estimated_new_subs"]
            value_per_sub = streaming_multipliers["value_per_subscriber"]
            lifetime_value = est_subs * value_per_sub
            
            return {
                "estimated_new_subscribers": round(est_subs),
                "subscriber_lifetime_value": round(lifetime_value),
                "cost_per_acquisition": round(budget / est_subs) if est_subs > 0 else 0,
                "estimated_roi": round((lifetime_value / budget - 1) * 100, 2)
            }
