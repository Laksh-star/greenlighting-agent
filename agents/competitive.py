"""Competitive Analysis Agent - Assesses release-window and market-position risk."""

from typing import Dict, Any
from agents import BaseAgent


COMPETITIVE_ANALYSIS_PROMPT = """
You are a film and TV competitive strategy analyst.
Assess market saturation, positioning, comparable crowding, and release-window risk.
Be concise and focus on greenlight-relevant decisions.
"""


class CompetitiveAnalysisAgent(BaseAgent):
    """Agent specialized in competitive positioning."""

    def __init__(self):
        super().__init__(
            name="Competitive Analysis Agent",
            role="Maps competitive landscape, release timing, and market positioning",
            system_prompt=COMPETITIVE_ANALYSIS_PROMPT,
        )

    async def analyze(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        genre = project_data.get("genre", "Unknown")
        platform = project_data.get("platform", "theatrical")
        comparables = project_data.get("comparables", [])
        description = project_data.get("description", "")

        if project_data.get("demo_mode"):
            findings = (
                "The project should avoid direct competition with large-scale sci-fi "
                "tentpoles and instead position as elevated genre programming. "
                "The cleanest window is a counterprogramming slot or streamer-led launch "
                "where premium adult sci-fi can be marketed on concept and reviews rather "
                "than franchise scale."
            )
            confidence = 0.78
        else:
            user_message = f"""
Assess the competitive landscape for this project:

**Project Description:** {description}
**Genre:** {genre}
**Platform:** {platform}
**Comparable Titles:** {', '.join(comparables) if comparables else 'None provided'}

Cover:
1. Market saturation
2. Release-window risks
3. Positioning opportunities
4. White-space strategy
5. Competitive threats
"""
            self.add_to_history("user", user_message)
            response = self._call_claude(
                messages=self.conversation_history,
                temperature=0.6,
            )
            findings = response.content[0].text
            self.add_to_history("assistant", findings)
            confidence = 0.7 + (0.1 if comparables else 0)

        return self.format_result(
            findings=findings,
            confidence=min(confidence, 0.9),
            metadata={
                "genre": genre,
                "platform": platform,
                "comparables_count": len(comparables),
            },
        )
