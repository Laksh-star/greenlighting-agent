"""Evidence honesty and deterministic financial stress tests."""

import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.financial_model import FinancialModelingAgent
from utils.evidence_provenance import build_provenance
from utils.financial_stress import stress_report
from utils.analysis_report import build_analysis_payload
from tools.tmdb_tools import TMDBClient


def financial_payload(platform="theatrical", license_value=0):
    assumptions = {"marketing_spend": 500_000, "streaming_license_value": license_value}
    metrics = FinancialModelingAgent()._calculate_basic_metrics(1_000_000, "Horror", platform, assumptions=assumptions)
    return {"project": {"budget": 1_000_000, "platform": platform, "financial_assumptions": assumptions},
            "financial_scenarios": metrics, "financial_assumptions": metrics["assumptions"],
            "sensitivity_table": metrics["sensitivity_table"], "recommendation": "CONDITIONAL GO"}


class EvidenceStressTests(unittest.TestCase):
    def test_unknown_legacy_sources_have_no_invented_dates(self):
        result = build_provenance({"comparable_evidence": [{"title": "Unknown", "budget": 0}]})
        row = next(r for r in result["evidence"] if r["id"] == "comparable-1")
        self.assertEqual(row["source"], "unknown legacy source")
        self.assertIsNone(row["retrieved_at"])
        self.assertTrue(result["warnings"])

    def test_demo_does_not_relabel_private_evidence(self):
        result = build_provenance({"project": {"demo_mode": True}, "comparable_evidence": [
            {"title": "Sample", "budget": 1, "revenue": 2},
            {"title": "Private", "source": "private dataset", "dataset_id": "studio", "budget": 1, "revenue": 2}]})
        self.assertEqual(result["evidence"][1]["source"], "demo data")
        self.assertEqual(result["evidence"][2]["source"], "private dataset")

    def test_driver_links_are_exact_and_no_fake_narrative_citations(self):
        result = build_provenance({"financial_scenarios": {"moderate_roi": 20}, "decision_drivers": [
            "Moderate-case ROI: 20%.", "Strong audience demand will guarantee success."]})
        self.assertEqual(result["decision_drivers"][0]["evidence_ids"], ["financial-model"])
        self.assertEqual(result["decision_drivers"][1]["status"], "unsupported interpretation")
        self.assertEqual(result["decision_drivers"][1]["evidence_ids"], [])

    def test_user_assumption_is_distinct_from_model_default(self):
        result = build_provenance({"project": {"financial_assumptions": {"marketing_spend": 0}},
                                   "financial_assumptions": {"marketing_spend": 0, "distribution_fee_pct": .12}})
        rows = {r["id"]: r for r in result["evidence"]}
        self.assertEqual(rows["assumption-marketing_spend"]["source"], "user assumption")
        self.assertEqual(rows["assumption-distribution_fee_pct"]["source"], "model default")

    def test_structured_reports_embed_provenance(self):
        self.assertIn("evidence_provenance", build_analysis_payload({}, Path("report.md")))

    def test_tmdb_enrichment_records_source_and_actual_retrieval(self):
        client = TMDBClient()
        with patch.object(client, "search_movie", return_value=[{"id": 123, "title": "Movie"}]), \
             patch.object(client, "get_movie_details", return_value={"title": "Movie", "budget": 10, "revenue": 20}), \
             patch.object(client, "get_similar_movies", return_value=[]):
            row = client.enrich_comparable_titles(["Movie"])[0]
        self.assertEqual(row["source"], "TMDB")
        self.assertEqual(row["source_url"], "https://www.themoviedb.org/movie/123")
        self.assertTrue(row["retrieved_at"])

    def test_private_evidence_records_dataset_and_local_read_date(self):
        import tempfile
        from tools.private_dataset import PrivateDatasetStore
        with tempfile.TemporaryDirectory() as directory:
            store = PrivateDatasetStore(Path(directory))
            metadata = store.save_dataset("Studio", "title,budget,revenue\nMovie,100,200\n")
            row = store.comparable_evidence_for_titles(["Movie"], metadata["id"])[0]
        self.assertEqual(row["source"], "private dataset")
        self.assertEqual(row["dataset_id"], metadata["id"])
        self.assertTrue(row["retrieved_at"].endswith("Z"))

    def test_license_covering_cost_breaks_even_even_with_zero_share(self):
        payload = financial_payload(license_value=2_000_000)
        payload["financial_scenarios"]["net_revenue_share"] = 0
        self.assertEqual(stress_report(payload)["break_even_gross"], 0)

    def test_stress_baseline_matches_saved_model_for_all_platforms(self):
        for platform in ("theatrical", "hybrid", "streaming"):
            with self.subTest(platform=platform):
                payload = financial_payload(platform)
                result = stress_report(payload)
                saved = payload["financial_scenarios"].get("moderate_roi", payload["financial_scenarios"].get("estimated_roi"))
                self.assertAlmostEqual(result["scenarios"][1]["roi"], saved, places=2)

    def test_overrun_does_not_increase_forecast_demand(self):
        payload = financial_payload()
        base, overrun = stress_report(payload), stress_report(payload, overrun_pct=50)
        self.assertEqual(base["scenarios"][1]["gross_revenue"], overrun["scenarios"][1]["gross_revenue"])
        self.assertGreater(overrun["total_exposure"], base["total_exposure"])
        self.assertLess(overrun["scenarios"][1]["roi"], base["scenarios"][1]["roi"])

    def test_zero_revenue_keeps_contractual_license_value(self):
        result = stress_report(financial_payload(license_value=100), revenue_multiplier=0)
        self.assertEqual(result["scenarios"][1]["modeled_net_value"], 100)
        self.assertEqual(result["break_even_gross"], round((1_500_000 - 100) / .44))

    def test_financial_signal_can_change_without_mutating_ai(self):
        payload = financial_payload()
        original = copy.deepcopy(payload)
        result = stress_report(payload, revenue_multiplier=0, marketing_spend=0)
        self.assertEqual(result["scenarios"][1]["financial_signal"], "NO-GO")
        self.assertEqual(result["original_recommendation"], "CONDITIONAL GO")
        self.assertEqual(payload, original)

    def test_zero_share_break_even_is_unavailable(self):
        payload = financial_payload()
        payload["financial_scenarios"]["net_revenue_share"] = 0
        self.assertIsNone(stress_report(payload)["break_even_gross"])

    def test_stress_rejects_missing_budget_and_base_evidence(self):
        with self.assertRaises(ValueError):
            stress_report({"project": {"budget": 0}})
        with self.assertRaises(ValueError):
            stress_report({"project": {"budget": 100}})
        with self.assertRaises(ValueError):
            stress_report(financial_payload(), revenue_multiplier=float("nan"))
