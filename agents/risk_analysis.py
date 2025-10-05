"""
Risk Analysis Agent - Identifies potential risks, controversies, and execution challenges.
"""

from typing import Dict, Any, List
from agents import BaseAgent
from utils.prompt_templates import RISK_ANALYSIS_PROMPT


class RiskAnalysisAgent(BaseAgent):
    """Agent specialized in identifying and assessing project risks."""
    
    def __init__(self):
        super().__init__(
            name="Risk Analysis Agent",
            role="Identifies risks, controversies, and execution challenges",
            system_prompt=RISK_ANALYSIS_PROMPT
        )
    
    async def analyze(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Conduct risk analysis.
        
        Args:
            project_data: Project information including description, budget, talent, etc.
            
        Returns:
            Risk assessment with mitigation strategies
        """
        description = project_data.get('description', '')
        budget = project_data.get('budget', 0)
        genre = project_data.get('genre', 'Unknown')
        platform = project_data.get('platform', 'theatrical')
        target_audience = project_data.get('target_audience', 'general')
        
        user_message = f"""
Conduct a comprehensive risk assessment for this project:

**Project Description:** {description}

**Budget:** ${budget:,}
**Genre:** {genre}
**Platform:** {platform}
**Target Audience:** {target_audience}

Analyze and identify:

1. **Production Risks:**
   - Budget overrun potential
   - Technical/VFX challenges
   - Shooting location complications
   - Timeline feasibility

2. **Creative Risks:**
   - Script weaknesses or controversial elements
   - Genre fatigue or market oversaturation
   - Casting challenges or dependencies
   - Director/talent track record concerns

3. **Market Risks:**
   - Competition and release timing
   - Audience appetite uncertainty
   - Platform/distribution challenges
   - Marketing difficulties

4. **Financial Risks:**
   - Revenue unpredictability
   - Budget-to-return ratio concerns
   - Investment recoupment timeline
   - Ancillary revenue limitations

5. **Reputational Risks:**
   - Potential controversies or backlash
   - Cultural sensitivity issues
   - Brand alignment concerns
   - Social media risk factors

6. **External Risks:**
   - Regulatory or censorship issues
   - Economic factors
   - Competitive releases
   - Platform/distribution changes

For each risk category, provide:
- Likelihood (Low/Medium/High)
- Impact (Low/Medium/High)
- Mitigation strategies
- Risk score (1-10)

Then provide an overall risk matrix and recommendations.
"""
        
        self.add_to_history("user", user_message)
        
        response = self._call_claude(
            messages=self.conversation_history,
            temperature=0.6
        )
        
        findings = response.content[0].text
        self.add_to_history("assistant", findings)
        
        # Calculate overall risk score
        risk_factors = self._assess_risk_factors(project_data)
        overall_risk = self._calculate_risk_score(risk_factors)
        
        # Higher confidence when we have more project details
        data_completeness = sum([
            bool(description),
            bool(budget > 0),
            bool(genre != 'Unknown'),
            bool(platform),
            bool(target_audience)
        ]) / 5
        
        confidence = 0.6 + (data_completeness * 0.3)
        
        return self.format_result(
            findings=findings,
            confidence=confidence,
            metadata={
                "risk_factors": risk_factors,
                "overall_risk_score": overall_risk,
                "risk_level": self._categorize_risk(overall_risk)
            }
        )
    
    def _assess_risk_factors(self, project_data: Dict[str, Any]) -> Dict[str, int]:
        """Assess individual risk factors based on project data."""
        
        budget = project_data.get('budget', 0)
        genre = project_data.get('genre', 'Unknown')
        
        risks = {}
        
        # Budget risk
        if budget > 100_000_000:
            risks['budget_risk'] = 8  # High budget = high risk
        elif budget > 50_000_000:
            risks['budget_risk'] = 6
        elif budget < 5_000_000:
            risks['budget_risk'] = 4  # Low budget = lower financial risk
        else:
            risks['budget_risk'] = 5
        
        # Genre risk (some genres are more reliable)
        genre_risks = {
            "Horror": 3,  # Horror typically low risk, reliable returns
            "Action": 6,   # High budget, competitive
            "Comedy": 5,   # Moderate risk
            "Drama": 6,    # Awards potential but uncertain box office
            "Science Fiction": 7,  # High budget, VFX dependent
            "Animation": 5,
            "Unknown": 7
        }
        risks['genre_risk'] = genre_risks.get(genre, 5)
        
        # Platform risk
        platform = project_data.get('platform', 'theatrical')
        if platform == 'theatrical':
            risks['platform_risk'] = 7  # Theatrical more risky post-pandemic
        elif platform == 'streaming':
            risks['platform_risk'] = 4
        else:
            risks['platform_risk'] = 5
        
        return risks
    
    def _calculate_risk_score(self, risk_factors: Dict[str, int]) -> float:
        """Calculate overall risk score from individual factors."""
        if not risk_factors:
            return 5.0
        
        return round(sum(risk_factors.values()) / len(risk_factors), 1)
    
    def _categorize_risk(self, risk_score: float) -> str:
        """Categorize risk level."""
        if risk_score < 3:
            return "Low Risk"
        elif risk_score < 5:
            return "Low-Medium Risk"
        elif risk_score < 7:
            return "Medium Risk"
        elif risk_score < 8:
            return "Medium-High Risk"
        else:
            return "High Risk"
