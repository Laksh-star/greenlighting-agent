"""
Master Orchestrator Agent - Coordinates all subagents and synthesizes final recommendation.
"""

from typing import Dict, Any, List
import asyncio
import re
from agents import BaseAgent
from agents.market_research import MarketResearchAgent
from agents.financial_model import FinancialModelingAgent
from agents.risk_analysis import RiskAnalysisAgent
from agents.audience_intel import AudienceIntelligenceAgent
from agents.competitive import CompetitiveAnalysisAgent
from agents.creative_assess import CreativeAssessmentAgent
from utils.prompt_templates import MASTER_ORCHESTRATOR_PROMPT
from utils.helpers import (
    print_header, print_success, print_info, print_warning,
    create_progress_bar, format_analysis_summary
)


class MasterOrchestratorAgent(BaseAgent):
    """
    Master agent that coordinates all subagents and makes final greenlight decision.
    """
    
    def __init__(self):
        super().__init__(
            name="Master Greenlighting Orchestrator",
            role="Synthesizes all analyses and makes final greenlight recommendation",
            system_prompt=MASTER_ORCHESTRATOR_PROMPT
        )
        
        # Initialize all subagents
        self.subagents: Dict[str, BaseAgent] = {
            "market_research": MarketResearchAgent(),
            "financial_model": FinancialModelingAgent(),
            "risk_analysis": RiskAnalysisAgent(),
            "audience_intel": AudienceIntelligenceAgent(),
            "competitive": CompetitiveAnalysisAgent(),
            "creative": CreativeAssessmentAgent(),
        }
        
        print_success(f"Initialized Master Orchestrator with {len(self.subagents)} subagents")
    
    async def analyze(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Orchestrate full greenlight analysis.
        
        Args:
            project_data: Complete project information
            
        Returns:
            Final greenlight recommendation with all supporting analysis
        """
        print_header("🎬 GREENLIGHTING ANALYSIS STARTING")
        print_info(f"Project: {project_data.get('description', 'Untitled')[:100]}")
        print_info(f"Budget: ${project_data.get('budget', 0):,}")
        print()
        
        # Run all subagent analyses in parallel
        results = await self._run_subagent_analyses(project_data)
        
        # Synthesize final recommendation
        print_header("📊 SYNTHESIZING FINAL RECOMMENDATION")
        final_recommendation = await self._synthesize_recommendation(
            project_data,
            results
        )
        
        return {
            "project_data": project_data,
            "subagent_results": results,
            "final_recommendation": final_recommendation,
            "timestamp": self._get_timestamp()
        }
    
    async def _run_subagent_analyses(
        self,
        project_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run all subagent analyses in parallel."""
        
        results = {}
        total_agents = len(self.subagents)
        completed = 0
        
        print_header(f"🤖 RUNNING {total_agents} SUBAGENT ANALYSES")
        
        # Market research runs first so downstream agents can use comparable evidence.
        market_agent = self.subagents["market_research"]
        print_info(f"Starting: {market_agent.name}")
        agent_name, result = await self._run_single_agent(
            "market_research",
            market_agent,
            project_data,
        )
        results[agent_name] = result
        if isinstance(result, dict) and not result.get("error"):
            project_data["market_analysis"] = result
            project_data["comparable_evidence"] = result.get("metadata", {}).get(
                "comparable_evidence",
                project_data.get("comparable_evidence", []),
            )
        completed += 1
        progress = create_progress_bar(completed, total_agents, width=40)
        print_success(f"{progress}")

        tasks = []
        for name, agent in self.subagents.items():
            if name == "market_research":
                continue
            print_info(f"Starting: {agent.name}")
            tasks.append(self._run_single_agent(name, agent, project_data))

        # Run remaining agents in parallel and collect named results.
        for task in asyncio.as_completed(tasks):
            agent_name, result = await task
            results[agent_name] = result
            completed += 1
            
            # Show progress
            progress = create_progress_bar(completed, total_agents, width=40)
            print_success(f"{progress}")
        
        print()
        print_success(f"All {total_agents} analyses complete!")
        print()
        
        # Print summary
        print(format_analysis_summary(results))
        
        return results
    
    async def _run_single_agent(
        self,
        name: str,
        agent: BaseAgent,
        project_data: Dict[str, Any]
    ) -> tuple[str, Dict[str, Any]]:
        """Run a single subagent analysis with error handling."""
        try:
            result = await agent.analyze(project_data)
            return name, result
            
        except Exception as e:
            print_warning(f"Error in {agent.name}: {str(e)}")
            return name, {
                "agent": agent.name,
                "error": str(e),
                "confidence": 0.0,
                "findings": f"Analysis failed: {str(e)}"
            }
    
    async def _synthesize_recommendation(
        self,
        project_data: Dict[str, Any],
        results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Synthesize final recommendation from all subagent results."""
        if project_data.get("demo_mode"):
            return self._demo_recommendation(results)
        
        # Build comprehensive summary for Claude
        summary_parts = []
        
        summary_parts.append("# COMPREHENSIVE PROJECT ANALYSIS\n")
        summary_parts.append(f"**Project:** {project_data.get('description', 'Untitled')}\n")
        summary_parts.append(f"**Budget:** ${project_data.get('budget', 0):,}\n")
        summary_parts.append(f"**Genre:** {project_data.get('genre', 'Unknown')}\n")
        summary_parts.append("\n---\n")
        
        # Add each subagent's findings
        for agent_name, result in results.items():
            if isinstance(result, dict) and not result.get('error'):
                summary_parts.append(f"\n## {result.get('agent', agent_name)}\n")
                summary_parts.append(f"**Confidence:** {result.get('confidence', 0):.1%}\n\n")
                summary_parts.append(result.get('findings', 'No findings available'))
                summary_parts.append("\n\n---\n")
        
        synthesis_prompt = "\n".join(summary_parts)
        synthesis_prompt += "\n\nBased on all the above analyses, provide your final greenlight recommendation."
        
        # Call Claude to synthesize
        self.add_to_history("user", synthesis_prompt)
        
        response = self._call_claude(
            messages=self.conversation_history,
            temperature=0.7
        )
        
        recommendation_text = response.content[0].text
        self.add_to_history("assistant", recommendation_text)
        
        # Calculate overall confidence
        confidences = [
            r.get('confidence', 0)
            for r in results.values()
            if isinstance(r, dict) and not r.get('error')
        ]
        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.5
        
        # Determine recommendation category
        recommendation_category = self._categorize_recommendation(
            recommendation_text,
            results
        )
        
        return {
            "recommendation": recommendation_category,
            "confidence": overall_confidence,
            "analysis": recommendation_text,
            "summary": self._extract_summary(recommendation_text),
            "decision_drivers": self._extract_decision_drivers(recommendation_text, results),
        }

    def _demo_recommendation(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Create a deterministic recommendation for sample mode."""
        confidences = [
            r.get("confidence", 0)
            for r in results.values()
            if isinstance(r, dict) and not r.get("error")
        ]
        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.75
        analysis = (
            "CONDITIONAL GO. The project is credible as a disciplined, contained sci-fi "
            "thriller with strong comparable logic and manageable downside at the sample "
            "budget. The greenlight should be conditional on script specificity, capped "
            "VFX scope, and release positioning away from franchise-scale sci-fi."
        )
        return {
            "recommendation": "CONDITIONAL GO",
            "confidence": overall_confidence,
            "analysis": analysis,
            "summary": "Proceed only with budget discipline, a clear emotional hook, and focused genre positioning.",
            "decision_drivers": [
                "Comparable evidence supports upside for contained premium sci-fi.",
                "The budget is moderate enough to protect downside risk.",
                "Original sci-fi still needs strong reviews and precise positioning.",
            ],
        }
    
    def _categorize_recommendation(
        self,
        text: str,
        results: Dict[str, Any]
    ) -> str:
        """Categorize recommendation as GO, CONDITIONAL, or NO-GO."""
        
        text_lower = text.lower()
        explicit_recommendation = self._extract_explicit_recommendation(text_lower)
        if explicit_recommendation:
            return explicit_recommendation
        
        # Fallback to broad phrasing when there is no clear recommendation header.
        if "conditional" in text_lower:
            return "CONDITIONAL GO"
        elif "no-go" in text_lower or "no go" in text_lower or "pass" in text_lower:
            return "NO-GO"
        elif any(word in text_lower for word in ["greenlight", "go ahead", "recommend", "proceed"]):
            return "GO"
        
        # If unclear, check risk levels
        if 'risk_analysis' in results:
            risk_score = results['risk_analysis'].get('metadata', {}).get('overall_risk_score', 5)
            if risk_score > 7:
                return "NO-GO"
            elif risk_score > 5:
                return "CONDITIONAL GO"
        
        return "CONDITIONAL GO"  # Default to conditional

    def _extract_explicit_recommendation(self, text_lower: str) -> str:
        """Find the model's explicit headline recommendation before scanning all text."""
        normalized = re.sub(r"[*_`#]", "", text_lower)
        candidate_lines = [
            line.strip()
            for line in normalized.splitlines()[:40]
            if "recommendation" in line or line.strip().startswith("recommend ")
        ]

        explicit_value_lines = [
            line
            for line in candidate_lines
            if "recommendation:" in line or "recommend a " in line
        ]
        for line in explicit_value_lines:
            parsed = self._parse_recommendation_line(line)
            if parsed:
                return parsed

        for line in candidate_lines:
            parsed = self._parse_recommendation_line(line)
            if parsed:
                return parsed

        return ""

    def _parse_recommendation_line(self, line: str) -> str:
        """Parse one recommendation-like line."""
        if "conditional go" in line or "recommend a conditional go" in line:
            return "CONDITIONAL GO"
        if "no-go" in line or "no go" in line or re.search(r"\bpass\b", line):
            return "NO-GO"
        if re.search(r"\bgo\b", line) or "greenlight" in line or "proceed" in line:
            return "GO"
        return ""

    def _extract_decision_drivers(
        self,
        text: str,
        results: Dict[str, Any],
    ) -> List[str]:
        """Return three concise decision drivers for reports."""
        drivers = []
        if "risk_analysis" in results:
            risk_level = results["risk_analysis"].get("metadata", {}).get("risk_level")
            if risk_level:
                drivers.append(f"Risk profile: {risk_level}.")
        if "financial_model" in results:
            metrics = results["financial_model"].get("metadata", {}).get("basic_metrics", {})
            if metrics.get("moderate_roi") is not None:
                drivers.append(f"Moderate-case ROI: {metrics.get('moderate_roi')}%.")
        if "market_research" in results:
            count = results["market_research"].get("metadata", {}).get("comparables_count", 0)
            if count:
                drivers.append(f"Comparable evidence rows reviewed: {count}.")

        for line in text.splitlines():
            stripped = line.strip(" -*")
            if len(stripped) > 30 and stripped not in drivers:
                drivers.append(stripped)
            if len(drivers) == 3:
                break

        return drivers[:3] or ["See full analysis for supporting rationale."]
    
    def _extract_summary(self, text: str) -> str:
        """Extract executive summary from recommendation text."""
        lines = text.split('\n')
        
        # Look for executive summary section
        for i, line in enumerate(lines):
            if 'executive summary' in line.lower():
                # Get next few lines
                summary_lines = []
                for j in range(i + 1, min(i + 6, len(lines))):
                    if lines[j].strip() and not lines[j].startswith('#'):
                        summary_lines.append(lines[j].strip())
                if summary_lines:
                    return ' '.join(summary_lines)
        
        # If no executive summary found, return first paragraph
        for line in lines:
            if len(line.strip()) > 50:
                return line.strip()
        
        return "See full analysis for details."
    
    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()
