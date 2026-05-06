"""Audience Intelligence Agent - Evaluates target-audience and platform fit."""

from typing import Dict, Any
from agents import BaseAgent


AUDIENCE_INTEL_PROMPT = """
You are an audience intelligence analyst for film and TV greenlighting.
Evaluate demographic fit, audience demand, platform fit, and fan/community assumptions.
Be concise, practical, and explicit about uncertainty.
"""


class AudienceIntelligenceAgent(BaseAgent):
    """Agent specialized in audience and platform fit."""

    def __init__(self):
        super().__init__(
            name="Audience Intelligence Agent",
            role="Assesses target demographic fit, platform fit, and audience demand",
            system_prompt=AUDIENCE_INTEL_PROMPT,
        )

    async def analyze(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        target_audience = project_data.get("target_audience", "general")
        platform = project_data.get("platform", "theatrical")
        genre = project_data.get("genre", "Unknown")
        description = project_data.get("description", "")

        if project_data.get("demo_mode"):
            findings = (
                f"The project has a clear audience lane: {target_audience}. "
                f"{genre} concepts with a contained mystery hook can serve both "
                f"{platform} discovery and long-tail streaming if the trailer explains "
                "the premise in one sentence. Audience risk is moderate because original "
                "sci-fi depends on reviews and word of mouth."
            )
            confidence = 0.82
        else:
            user_message = f"""
Evaluate audience fit for this project:

**Project Description:** {description}
**Genre:** {genre}
**Platform:** {platform}
**Target Audience:** {target_audience}

Cover:
1. Core audience segments
2. Platform fit
3. Social/community hooks
4. Audience expansion potential
5. Main audience risks
"""
            self.add_to_history("user", user_message)
            response = self._call_claude(
                messages=self.conversation_history,
                temperature=0.6,
            )
            findings = response.content[0].text
            self.add_to_history("assistant", findings)
            confidence = 0.72 if target_audience == "general" else 0.82

        return self.format_result(
            findings=findings,
            confidence=confidence,
            metadata={
                "target_audience": target_audience,
                "platform": platform,
                "audience_fit": "focused" if target_audience != "general" else "broad",
            },
        )
