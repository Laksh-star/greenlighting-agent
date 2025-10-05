"""
Market Research Agent - Analyzes comparable titles, box office trends, and streaming performance.
"""

from typing import Dict, Any
from agents import BaseAgent
from utils.prompt_templates import MARKET_RESEARCH_PROMPT


class MarketResearchAgent(BaseAgent):
    """Agent specialized in market analysis for film/TV projects."""
    
    def __init__(self):
        super().__init__(
            name="Market Research Agent",
            role="Analyzes comparable titles, box office performance, and market trends",
            system_prompt=MARKET_RESEARCH_PROMPT
        )
    
    async def analyze(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Conduct market research analysis.
        
        Args:
            project_data: Dict with keys like 'genre', 'budget', 'description', 'comparables'
            
        Returns:
            Analysis results including market trends, comparable performance, and insights
        """
        genre = project_data.get('genre', 'Unknown')
        budget = project_data.get('budget', 0)
        description = project_data.get('description', '')
        comparables = project_data.get('comparables', [])
        
        # Build analysis prompt
        user_message = f"""
Analyze the market viability for this project:

**Project Description:** {description}

**Genre:** {genre}
**Estimated Budget:** ${budget:,}
**Comparable Titles:** {', '.join(comparables) if comparables else 'None provided'}

Please provide:
1. Current market trends for this genre
2. Performance analysis of comparable titles (if provided)
3. Box office/streaming potential based on recent similar releases
4. Audience demand indicators
5. Market saturation assessment
6. Recommended release timing considerations

Base your analysis on recent industry data and trends.
"""
        
        # Call Claude for analysis
        self.add_to_history("user", user_message)
        
        response = self._call_claude(
            messages=self.conversation_history,
            temperature=0.7
        )
        
        findings = response.content[0].text
        self.add_to_history("assistant", findings)
        
        # Calculate confidence based on data availability
        confidence = 0.7  # Base confidence
        if comparables:
            confidence += 0.2
        if budget > 0:
            confidence += 0.1
        confidence = min(confidence, 1.0)
        
        return self.format_result(
            findings=findings,
            confidence=confidence,
            metadata={
                "genre": genre,
                "budget_category": self._categorize_budget(budget),
                "comparables_count": len(comparables)
            }
        )
    
    def _categorize_budget(self, budget: int) -> str:
        """Categorize budget into industry-standard tiers."""
        if budget < 1_000_000:
            return "Micro Budget"
        elif budget < 5_000_000:
            return "Low Budget"
        elif budget < 25_000_000:
            return "Medium Budget"
        elif budget < 75_000_000:
            return "High Budget"
        elif budget < 200_000_000:
            return "Blockbuster"
        else:
            return "Tentpole"
