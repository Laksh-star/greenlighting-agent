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
from fastapi.testclient import TestClient
from main import GreenlightingCLI, parse_comparables
from tools.tmdb_tools import TMDBClient
from tools.private_dataset import PrivateDatasetStore, PRIVATE_DATASET_SAMPLE, parse_private_dataset_csv
from utils.analysis_report import build_analysis_payload
from utils.batch import build_batch_summary_row, load_batch_projects, load_batch_projects_from_text
from utils.report_quality import validate_report_quality
from utils.run_ledger import build_run_ledger, summarize_model_usage
from web_app import JOBS, app


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

    def _quality_results(self, recommendation="CONDITIONAL GO", analysis=None):
        return {
            "requested_project_data": {
                "description": "Quality test",
                "budget": 10_000_000,
                "genre": "Science Fiction",
                "platform": "theatrical",
                "comparables": ["Arrival"],
            },
            "project_data": {
                "description": "Quality test",
                "budget": 10_000_000,
                "genre": "Science Fiction",
                "platform": "theatrical",
                "target_audience": "general",
                "comparables": ["Arrival"],
            },
            "final_recommendation": {
                "recommendation": recommendation,
                "confidence": 0.8,
                "summary": "Quality summary",
                "analysis": analysis or "Recommendation: CONDITIONAL GO\nProceed with guardrails.",
                "decision_drivers": ["Driver"],
            },
            "subagent_results": {
                "market_research": {
                    "agent": "Market Research Agent",
                    "confidence": 0.8,
                    "findings": "Market findings",
                    "metadata": {
                        "comparable_evidence": [{"title": "Arrival", "source": "tmdb"}],
                    },
                },
                "financial_model": {
                    "agent": "Financial Modeling Agent",
                    "confidence": 0.8,
                    "findings": "Finance findings",
                    "metadata": {
                        "basic_metrics": {
                            "conservative_revenue": 12_000_000,
                            "moderate_revenue": 20_000_000,
                            "optimistic_revenue": 30_000_000,
                        },
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

    def _quality_markdown(self):
        return "\n".join([
            "### Comparable Evidence",
            "| Title | Year | Budget | Revenue | ROI | Rating | Similar Signals |",
            "### Financial Scenario Snapshot",
            "### Risk Matrix",
        ])

    def test_report_quality_accepts_complete_report(self):
        quality = validate_report_quality(self._quality_results(), self._quality_markdown())

        self.assertTrue(quality["passed"])
        self.assertEqual(quality["errors"], [])
        self.assertEqual(quality["warnings"], [])

    def test_report_quality_rejects_recommendation_mismatch(self):
        quality = validate_report_quality(
            self._quality_results(
                recommendation="GO",
                analysis="Recommendation: NO-GO\nDo not proceed.",
            ),
            self._quality_markdown(),
        )

        self.assertFalse(quality["passed"])
        self.assertIn("does not match synthesis text", quality["errors"][0])

    def test_report_quality_requires_comparables_finance_and_risk(self):
        results = self._quality_results()
        results["subagent_results"]["market_research"]["metadata"]["comparable_evidence"] = []
        results["subagent_results"]["financial_model"]["metadata"]["basic_metrics"] = {}
        results["subagent_results"]["risk_analysis"]["metadata"] = {}

        quality = validate_report_quality(results, "Recommendation: CONDITIONAL GO")

        self.assertFalse(quality["passed"])
        self.assertIn("Comparable evidence is missing", "\n".join(quality["errors"]))
        self.assertIn("Financial scenarios are missing", "\n".join(quality["errors"]))
        self.assertIn("Risk matrix metadata is missing", "\n".join(quality["errors"]))

    def test_report_quality_warns_on_tmdb_fallback(self):
        results = self._quality_results()
        results["subagent_results"]["market_research"]["metadata"][
            "market_data_warning"
        ] = "TMDB enrichment unavailable"

        quality = validate_report_quality(results, self._quality_markdown())

        self.assertTrue(quality["passed"])
        self.assertEqual(quality["warnings"], ["TMDB enrichment unavailable"])

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

    def test_load_batch_projects_from_text(self):
        csv_text = (
            "description,budget,genre,platform,comparables,target_audience\n"
            "\"Small horror\",2500000,Horror,theatrical,\"Host,Paranormal Activity\",fans\n"
        )

        projects = load_batch_projects_from_text(csv_text)

        self.assertEqual(projects[0]["description"], "Small horror")
        self.assertEqual(projects[0]["budget"], 2_500_000)
        self.assertEqual(projects[0]["comparables"], ["Host", "Paranormal Activity"])

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

    def test_private_dataset_parses_comparable_evidence(self):
        rows = parse_private_dataset_csv(PRIVATE_DATASET_SAMPLE)

        self.assertEqual(rows[0]["title"], "Lunar Signal")
        self.assertEqual(rows[0]["source"], "private dataset")
        self.assertEqual(rows[0]["roi"], 250.0)

    def test_private_dataset_store_searches_saved_rows(self):
        temp_dir = Path("outputs/test_private_data")
        store = PrivateDatasetStore(temp_dir)
        metadata = store.save_dataset("Studio Test", PRIVATE_DATASET_SAMPLE)

        rows = store.search("lunar", dataset_id=metadata["id"])

        self.assertEqual(metadata["row_count"], 3)
        self.assertEqual(rows[0]["title"], "Lunar Signal")

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

    def test_web_sample_endpoint_returns_form_payload(self):
        client = TestClient(app)
        response = client.get("/api/sample")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("description", payload)
        self.assertIsInstance(payload["comparables"], str)

    def test_web_sample_batch_endpoint_returns_csv(self):
        client = TestClient(app)
        response = client.get("/api/sample-batch")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("description,budget,genre,platform", payload["csv_text"])

    def test_web_comparable_search_with_mocked_tmdb(self):
        client = TestClient(app)
        with patch("web_app.tmdb_client.search_movie") as search_movie, patch(
            "web_app.tmdb_client.get_movie_details"
        ) as get_movie_details:
            search_movie.return_value = [{
                "id": 1,
                "title": "Arrival",
                "release_date": "2016-11-11",
                "vote_average": 7.6,
                "popularity": 51.6,
            }]
            get_movie_details.return_value = {
                "id": 1,
                "title": "Arrival",
                "release_date": "2016-11-11",
                "vote_average": 7.6,
                "popularity": 51.6,
                "budget": 47_000_000,
                "revenue": 203_400_000,
                "poster_path": "/poster.jpg",
            }

            response = client.get("/api/comparables/search?q=Arrival")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"], "tmdb")
        self.assertEqual(payload["results"][0]["title"], "Arrival")
        self.assertEqual(payload["results"][0]["budget"], 47_000_000)
        self.assertIn("image.tmdb.org", payload["results"][0]["poster_url"])

    def test_web_comparable_search_falls_back_without_tmdb(self):
        client = TestClient(app)
        with patch("web_app.tmdb_client.search_movie", side_effect=Exception("no key")):
            response = client.get("/api/comparables/search?q=Moon")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"], "demo fallback")
        self.assertEqual(payload["results"][0]["title"], "Moon")
        self.assertIn("TMDB search unavailable", payload["warning"])

    def test_web_private_dataset_endpoints_and_search(self):
        client = TestClient(app)
        response = client.post(
            "/api/private-datasets",
            json={
                "name": "Unit Studio",
                "csv_text": PRIVATE_DATASET_SAMPLE,
            },
        )

        self.assertEqual(response.status_code, 200)
        dataset = response.json()["dataset"]

        list_response = client.get("/api/private-datasets")
        self.assertEqual(list_response.status_code, 200)
        self.assertTrue(
            any(item["id"] == dataset["id"] for item in list_response.json()["datasets"])
        )

        search_response = client.get(
            f"/api/comparables/search?q=Lunar&source=private&dataset_id={dataset['id']}"
        )
        self.assertEqual(search_response.status_code, 200)
        payload = search_response.json()
        self.assertEqual(payload["source"], "private dataset")
        self.assertEqual(payload["results"][0]["title"], "Lunar Signal")

    def test_web_batch_analyze_starts_job(self):
        client = TestClient(app)
        response = client.post(
            "/api/batch-analyze",
            json={
                "csv_text": (
                    "description,budget,genre,platform,comparables,target_audience\n"
                    "\"Small horror\",2500000,Horror,theatrical,\"Host\",fans\n"
                ),
                "demo_mode": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("job_id", payload)
        self.assertEqual(JOBS[payload["job_id"]]["kind"], "batch")

    def test_web_events_stream_job_progress(self):
        client = TestClient(app)
        job_id = "test-job"
        JOBS[job_id] = {
            "id": job_id,
            "status": "completed",
            "created_at": "test",
            "events": [
                {
                    "timestamp": "test",
                    "stage": "agent",
                    "name": "market_research",
                    "status": "completed",
                }
            ],
            "result": {},
            "error": "",
        }

        response = client.get(f"/api/jobs/{job_id}/events")

        self.assertEqual(response.status_code, 200)
        self.assertIn("market_research", response.text)
        JOBS.pop(job_id, None)


if __name__ == "__main__":
    unittest.main()
