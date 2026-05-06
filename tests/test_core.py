"""Core regression tests for the runnable demo path."""

import asyncio
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from agents import BaseAgent
from agents.financial_model import FinancialModelingAgent
from agents.market_research import MarketResearchAgent
from agents.master_agent import MasterOrchestratorAgent
from main import GreenlightingCLI, parse_comparables
from tools.tmdb_tools import TMDBClient


class FakeAgent(BaseAgent):
    def __init__(self, name, delay=0):
        super().__init__(name=name, role="fake", system_prompt="fake")
        self.delay = delay

    async def analyze(self, project_data):
        await asyncio.sleep(self.delay)
        return self.format_result(
            findings=f"{self.name} done",
            confidence=0.8,
            metadata={},
        )


class CoreTests(unittest.IsolatedAsyncioTestCase):
    def test_parse_comparables(self):
        self.assertEqual(
            parse_comparables("Arrival, Ex Machina,, Moon "),
            ["Arrival", "Ex Machina", "Moon"],
        )

    async def test_interactive_method_not_shadowed(self):
        cli = GreenlightingCLI()
        self.assertTrue(callable(cli.interactive_mode))
        self.assertFalse(cli.is_interactive)

    async def test_orchestrator_preserves_agent_names(self):
        orchestrator = MasterOrchestratorAgent()
        orchestrator.subagents = {
            "market_research": FakeAgent("market", delay=0.01),
            "financial_model": FakeAgent("finance", delay=0),
            "risk_analysis": FakeAgent("risk", delay=0.005),
        }

        results = await orchestrator._run_subagent_analyses({"demo_mode": True})

        self.assertEqual(
            set(results.keys()),
            {"market_research", "financial_model", "risk_analysis"},
        )
        self.assertEqual(results["financial_model"]["agent"], "finance")

    def test_recommendation_parser_prefers_explicit_headline(self):
        orchestrator = MasterOrchestratorAgent()
        text = """
# MASTER GREENLIGHT RECOMMENDATION

## RECOMMENDATION: **CONDITIONAL GO**

The no-go threshold is only triggered if VFX scope cannot be locked.
"""
        self.assertEqual(
            orchestrator._categorize_recommendation(text, {}),
            "CONDITIONAL GO",
        )

    def test_financial_model_handles_zero_budget(self):
        agent = FinancialModelingAgent()
        metrics = agent._calculate_basic_metrics(0, "Drama", "theatrical")
        self.assertEqual(metrics["moderate_roi"], 0)
        self.assertIn("Budget not provided", metrics["budget_warning"])

    def test_market_research_fallback_comparable_rows(self):
        agent = MarketResearchAgent()
        rows = agent._fallback_comparable_evidence(["Arrival", "Moon"])
        self.assertEqual([row["title"] for row in rows], ["Arrival", "Moon"])
        self.assertEqual(rows[0]["source"], "input only")

    def test_report_renders_fallback_comparable_rows(self):
        cli = GreenlightingCLI()
        results = {
            "project_data": {
                "description": "Test project",
                "budget": 1,
                "genre": "Drama",
                "platform": "theatrical",
                "target_audience": "general",
                "comparables": ["Arrival"],
            },
            "final_recommendation": {
                "recommendation": "CONDITIONAL GO",
                "confidence": 0.8,
                "summary": "Test summary",
                "analysis": "Test analysis",
                "decision_drivers": ["Test driver"],
            },
            "subagent_results": {
                "market_research": {
                    "agent": "Market Research Agent",
                    "confidence": 0.8,
                    "findings": "Market findings",
                    "metadata": {
                        "comparable_evidence": [
                            {
                                "title": "Arrival",
                                "year": "n/a",
                                "budget": 0,
                                "revenue": 0,
                                "roi": 0,
                                "rating": 0,
                                "similar_titles": [],
                                "source": "input only",
                            }
                        ],
                        "market_data_warning": "TMDB enrichment unavailable",
                    },
                }
            },
        }

        report = cli._format_report(results)

        self.assertIn("### Comparable Evidence", report)
        self.assertIn("TMDB enrichment unavailable", report)
        self.assertIn("| Arrival | n/a | $0 | $0 | 0% | 0.0 | input only |", report)

    def test_tmdb_comparable_enrichment_with_mocked_responses(self):
        client = TMDBClient()

        def fake_request(endpoint, params=None):
            if endpoint == "/search/movie":
                return {"results": [{"id": 1, "title": "Moon", "vote_average": 7.6}]}
            if endpoint == "/movie/1":
                return {
                    "title": "Moon",
                    "release_date": "2009-06-12",
                    "budget": 5_000_000,
                    "revenue": 9_800_000,
                    "vote_average": 7.6,
                    "popularity": 24.4,
                }
            if endpoint == "/movie/1/similar":
                return {"results": [{"title": "Sunshine"}]}
            return {}

        with patch.object(client, "_make_request", side_effect=fake_request):
            enriched = client.enrich_comparable_titles(["Moon"])

        self.assertEqual(enriched[0]["title"], "Moon")
        self.assertEqual(enriched[0]["roi"], 96.0)
        self.assertEqual(enriched[0]["similar_titles"], ["Sunshine"])

    def test_sample_generates_report_without_keys(self):
        repo = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "main.py", "--sample"],
            cwd=repo,
            text=True,
            capture_output=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("RECOMMENDATION", result.stdout)
        self.assertTrue(list((repo / "outputs" / "reports").glob("*.md")))


if __name__ == "__main__":
    unittest.main()
