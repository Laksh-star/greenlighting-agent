"""
Market Research Agent - Analyzes comparable titles, box office trends, and streaming performance.
"""

from typing import Dict, Any
from agents import BaseAgent
from utils.prompt_templates import MARKET_RESEARCH_PROMPT
from utils.sample_data import SAMPLE_COMPARABLE_EVIDENCE
from tools.tmdb_tools import tmdb_client


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
        comparable_evidence = project_data.get("comparable_evidence")

        if project_data.get("demo_mode"):
            comparable_evidence = comparable_evidence or self._demo_comparable_evidence(comparables)
            findings = self._demo_findings(genre, budget, comparable_evidence)
            return self.format_result(
                findings=findings,
                confidence=0.88,
                metadata={
                    "genre": genre,
                    "budget_category": self._categorize_budget(budget),
                    "comparables_count": len(comparable_evidence),
                    "comparable_evidence": comparable_evidence,
                },
            )

        if comparables and comparable_evidence is None:
            try:
                comparable_evidence = tmdb_client.enrich_comparable_titles(comparables)
            except Exception as exc:
                comparable_evidence = self._fallback_comparable_evidence(comparables)
                project_data["market_data_warning"] = f"TMDB enrichment unavailable: {exc}"

        comparable_evidence = comparable_evidence or self._fallback_comparable_evidence(comparables)

        project_data["comparable_evidence"] = comparable_evidence
        
        # Build analysis prompt
        user_message = f"""
Analyze the market viability for this project:

**Project Description:** {description}

**Genre:** {genre}
**Estimated Budget:** ${budget:,}
**Comparable Titles:** {', '.join(comparables) if comparables else 'None provided'}
**Comparable Evidence:** {self._format_comparable_evidence(comparable_evidence or [])}

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
        if comparable_evidence:
            confidence += 0.1
        if budget > 0:
            confidence += 0.1
        confidence = min(confidence, 1.0)
        
        return self.format_result(
            findings=findings,
            confidence=confidence,
            metadata={
                "genre": genre,
                "budget_category": self._categorize_budget(budget),
                "comparables_count": len(comparable_evidence or comparables),
                "comparable_evidence": comparable_evidence,
                "market_data_warning": project_data.get("market_data_warning", ""),
            }
        )

    def _fallback_comparable_evidence(self, comparables: list) -> list:
        """Create reportable fallback rows when live enrichment is unavailable."""
        return [
            {
                "title": title,
                "year": "n/a",
                "budget": 0,
                "revenue": 0,
                "roi": 0.0,
                "rating": 0,
                "popularity": 0,
                "similar_titles": [],
                "source": "input only",
            }
            for title in comparables
        ]

    def _demo_comparable_evidence(self, comparables: list) -> list:
        """Choose deterministic evidence for sample mode without mislabeling rows."""
        sample_titles = [item["title"] for item in SAMPLE_COMPARABLE_EVIDENCE]
        if not comparables or comparables == sample_titles:
            return SAMPLE_COMPARABLE_EVIDENCE
        return self._fallback_comparable_evidence(comparables)

    def _format_comparable_evidence(self, comparable_evidence: list) -> str:
        """Format comparable rows for the LLM prompt."""
        if not comparable_evidence:
            return "No comparable evidence available."

        rows = []
        for item in comparable_evidence:
            rows.append(
                f"- {item.get('title', 'Unknown')} ({item.get('year', 'n/a')}): "
                f"budget ${item.get('budget', 0):,}, revenue ${item.get('revenue', 0):,}, "
                f"ROI {item.get('roi', 0)}%, rating {item.get('rating', 0):.1f}, "
                f"popularity {item.get('popularity', 0):.1f}"
            )
        return "\n".join(rows)

    def _demo_findings(self, genre: str, budget: int, comparable_evidence: list) -> str:
        """Return deterministic market findings for sample mode."""
        revenue_rows = [
            item.get("revenue", 0)
            for item in comparable_evidence
            if item.get("revenue", 0) > 0
        ]
        if revenue_rows:
            comparable_note = (
                f"Comparable titles average about ${sum(revenue_rows) / len(revenue_rows):,.0f} "
                "in reported worldwide revenue"
            )
        else:
            comparable_note = (
                "Comparable titles were supplied as input-only rows, so live revenue "
                "benchmarks should be added before relying on the market estimate"
            )
        return (
            f"The {genre} package is viable as a contained, mid-budget genre project. "
            f"{comparable_note}, with strongest upside when the concept has a clean hook and premium "
            f"critical positioning. At a ${budget:,} budget, the project sits below the "
            f"largest comparable while keeping enough scale for theatrical marketing. "
            "Market risk is moderate: original sci-fi is selective, but contained AI and "
            "space-thriller concepts remain legible to adult audiences and stream well after "
            "release."
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
