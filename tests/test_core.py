"""Core regression tests for the runnable demo path."""

import asyncio
import json
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
from utils.analysis_report import build_analysis_payload
from utils.batch import build_batch_summary_row, load_batch_projects
from utils.run_ledger import build_run_ledger, summarize_model_usage


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

    def test_demo_comparable_evidence_uses_fallback_for_non_sample_titles(self):
        agent = MarketResearchAgent()
        rows = agent._demo_comparable_evidence(["Paranormal Activity", "Host"])
        self.assertEqual(
            [row["title"] for row in rows],
            ["Paranormal Activity", "Host"],
        )
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

    def test_structured_analysis_payload_has_core_fields(self):
        results = {
            "requested_project_data": {"description": "Test project"},
            "project_data": {"description": "Mutated project"},
            "final_recommendation": {
                "recommendation": "CONDITIONAL GO",
                "confidence": 0.8,
                "summary": "Test summary",
                "analysis": "Test analysis",
                "decision_drivers": ["Driver"],
            },
            "subagent_results": {
                "market_research": {
                    "agent": "Market Research Agent",
                    "role": "market",
                    "confidence": 0.8,
                    "findings": "Market findings",
                    "metadata": {
                        "comparable_evidence": [{"title": "Arrival"}],
                    },
                },
                "financial_model": {
                    "agent": "Financial Modeling Agent",
                    "confidence": 0.8,
                    "findings": "Finance findings",
                    "metadata": {
                        "basic_metrics": {"moderate_roi": 42},
                    },
                },
                "risk_analysis": {
                    "agent": "Risk Analysis Agent",
                    "confidence": 0.8,
                    "findings": "Risk findings",
                    "metadata": {
                        "overall_risk_score": 5.5,
                        "risk_level": "Medium Risk",
                        "risk_factors": {"budget_risk": 5},
                    },
                },
            },
        }

        payload = build_analysis_payload(
            results,
            Path("outputs/reports/test.md"),
            Path("outputs/runs/test_run.json"),
        )

        self.assertEqual(payload["project"]["description"], "Test project")
        self.assertEqual(payload["recommendation"], "CONDITIONAL GO")
        self.assertEqual(payload["comparable_evidence"][0]["title"], "Arrival")
        self.assertEqual(payload["financial_scenarios"]["moderate_roi"], 42)
        self.assertEqual(payload["risk_matrix"]["risk_level"], "Medium Risk")
        self.assertEqual(payload["run_ledger_path"], "outputs/runs/test_run.json")

    def test_run_ledger_summarizes_usage_and_cost(self):
        results = {
            "project_data": {
                "description": "Test",
                "demo_mode": False,
                "market_analysis": {"large": "derived"},
            },
            "requested_project_data": {"description": "Test", "demo_mode": False},
            "final_recommendation": {
                "recommendation": "GO",
                "confidence": 0.9,
            },
            "usage_summary": {
                "master_orchestrator": {
                    "call_count": 1,
                    "models": ["claude-sonnet-4-5-20250929"],
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                    "events": [],
                },
                "subagents": {
                    "market_research": {
                        "call_count": 1,
                        "models": ["claude-sonnet-4-5-20250929"],
                        "input_tokens": 200,
                        "output_tokens": 75,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 0,
                        "events": [],
                    }
                },
            },
        }

        usage = summarize_model_usage(results)
        ledger = build_run_ledger(results, Path("outputs/reports/test.md"))

        self.assertEqual(usage["totals"]["call_count"], 2)
        self.assertEqual(usage["totals"]["input_tokens"], 300)
        self.assertEqual(usage["totals"]["output_tokens"], 125)
        self.assertEqual(ledger["estimated_anthropic_cost"]["billable_input_tokens"], 300)
        self.assertEqual(ledger["report_path"], "outputs/reports/test.md")
        self.assertNotIn("market_analysis", ledger["project"])

    def test_load_batch_projects(self):
        projects = load_batch_projects(Path("examples/projects.csv"))

        self.assertEqual(len(projects), 2)
        self.assertEqual(projects[0]["budget"], 18_000_000)
        self.assertEqual(projects[0]["comparables"], ["Ex Machina", "Moon", "Arrival"])

    def test_batch_summary_row_extracts_metrics(self):
        results = {
            "requested_project_data": {
                "description": "A test project with a long title",
            },
            "final_recommendation": {
                "recommendation": "CONDITIONAL GO",
                "confidence": 0.81234,
            },
            "subagent_results": {
                "financial_model": {
                    "metadata": {
                        "basic_metrics": {
                            "moderate_roi": 42,
                        }
                    }
                },
                "risk_analysis": {
                    "metadata": {
                        "risk_level": "Medium Risk",
                        "overall_risk_score": 5.5,
                    }
                },
            },
            "report_path": "outputs/reports/test.md",
            "analysis_json_path": "outputs/reports/test.json",
            "run_ledger_path": "outputs/runs/test_run.json",
        }

        row = build_batch_summary_row(results)

        self.assertEqual(row["recommendation"], "CONDITIONAL GO")
        self.assertEqual(row["confidence"], 0.8123)
        self.assertEqual(row["moderate_roi"], 42)
        self.assertEqual(row["risk_level"], "Medium Risk")

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
        self.assertIn("Structured JSON saved to", result.stdout)
        self.assertIn("Run ledger saved to", result.stdout)
        self.assertTrue(list((repo / "outputs" / "reports").glob("*.md")))
        json_reports = list((repo / "outputs" / "reports").glob("*.json"))
        self.assertTrue(json_reports)
        with open(json_reports[-1], "r") as f:
            payload = json.load(f)
        self.assertIn("recommendation", payload)
        self.assertIn("run_ledger_path", payload)
        self.assertTrue(list((repo / "outputs" / "runs").glob("*.json")))

    def test_batch_sample_generates_summaries(self):
        repo = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "main.py", "--batch", "examples/projects.csv", "--sample"],
            cwd=repo,
            text=True,
            capture_output=True,
            timeout=60,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("BATCH ANALYSIS COMPLETE", result.stdout)
        self.assertTrue(list((repo / "outputs" / "batches").glob("*_summary.csv")))
        self.assertTrue(list((repo / "outputs" / "batches").glob("*_summary.json")))


if __name__ == "__main__":
    unittest.main()
