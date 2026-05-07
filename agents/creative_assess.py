"""Creative Assessment Agent - Reviews concept clarity and execution difficulty."""

from typing import Dict, Any
from agents import BaseAgent


CREATIVE_ASSESSMENT_PROMPT = """
You are a film and TV creative executive.
Evaluate the concept, execution difficulty, talent dependencies, genre promise, and
commercial/awards fit. Be direct and greenlight-oriented.
"""


class CreativeAssessmentAgent(BaseAgent):
    """Agent specialized in creative package assessment."""

    def __init__(self):
        super().__init__(
            name="Creative Assessment Agent",
            role="Assesses concept clarity, execution difficulty, and creative upside",
            system_prompt=CREATIVE_ASSESSMENT_PROMPT,
        )

    async def analyze(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        description = project_data.get("description", "")
        genre = project_data.get("genre", "Unknown")
        budget = project_data.get("budget", 0)
        source_material = project_data.get("source_material", {})
        source_excerpt = source_material.get("excerpt", "")

        if project_data.get("demo_mode"):
            if source_excerpt:
                findings = (
                    "The provided source material gives the creative assessment more "
                    "specificity than a logline alone. The opening signal is usable for "
                    "tone, concept clarity, and execution-risk review, but the project "
                    "still needs a focused human spine and clear visual grammar."
                )
            else:
                findings = (
                    "The creative hook is strong because it combines a contained location, "
                    "AI paranoia, and a mystery engine that can be sold quickly. The main "
                    "creative risk is familiarity: the script needs a human emotional spine "
                    "and a specific visual world to avoid feeling like generic AI anxiety."
                )
            confidence = 0.8
        else:
            user_message = f"""
Assess the creative package for this project:

**Project Description:** {description}
**Genre:** {genre}
**Budget:** ${budget:,}
**Source Material:** {source_material.get('name', 'not provided')}

**Source Material Excerpt:**
{source_excerpt or 'No source material provided.'}

Cover:
1. Concept clarity
2. Genre promise
3. Execution difficulty
4. Talent/casting dependencies
5. Commercial and awards upside
6. Main creative risks
"""
            self.add_to_history("user", user_message)
            response = self._call_claude(
                messages=self.conversation_history,
                temperature=0.7,
            )
            findings = response.content[0].text
            self.add_to_history("assistant", findings)
            confidence = 0.76 if description else 0.55

        return self.format_result(
            findings=findings,
            confidence=confidence,
            metadata={
                "genre": genre,
                "budget": budget,
                "execution_complexity": "moderate" if budget < 50_000_000 else "high",
                "source_material_name": source_material.get("name", ""),
                "source_material_word_count": source_material.get("word_count", 0),
            },
        )
