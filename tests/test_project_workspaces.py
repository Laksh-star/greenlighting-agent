"""Workspace persistence, version isolation, and web integration regression tests."""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from utils.project_workspaces import ProjectWorkspaces, compare_versions
import web_app


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.reports = self.root / "reports"
        self.reports.mkdir()
        self.store = ProjectWorkspaces(self.root / "projects" / "index.sqlite3")
        self.client = TestClient(web_app.app)
        self.patches = [patch("web_app.workspaces", self.store), patch("web_app.OUTPUT_DIR", self.reports)]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def report(self, report_id, budget=100, roi=10, recommendation="CONDITIONAL GO"):
        payload = {"project": {"description": "A contained thriller about a stranded crew", "budget": budget,
                               "genre": "Thriller", "comparables": ["Moon"], "demo_mode": True},
                   "recommendation": recommendation, "confidence": .8,
                   "financial_scenarios": {"moderate_roi": roi, "total_exposure": budget * 1.5},
                   "financial_assumptions": {"marketing_spend": 0},
                   "risk_matrix": {"overall_risk_score": 4}}
        (self.reports / f"{report_id}.json").write_text(json.dumps(payload))
        (self.reports / f"{report_id}.md").write_text("Original report")
        return payload

    def test_adopt_is_idempotent_and_preserves_reports(self):
        self.report("Original..._report")
        response = self.client.post("/api/projects", json={"name": "Lunar", "report_id": "Original..._report"})
        self.assertEqual(response.status_code, 200)
        again = self.client.post("/api/projects", json={"name": "Renamed", "report_id": "Original..._report"})
        self.assertEqual(response.json()["id"], again.json()["id"])
        request = response.json()["versions"][0]["request"]
        self.assertEqual(request["marketing_spend"], 0)
        self.assertEqual(request["comparables"], "Moon")
        self.assertTrue(request["demo_mode"])
        self.assertEqual((self.reports / "Original..._report.md").read_text(), "Original report")

    def test_persistence_and_named_versions(self):
        project = self.store.create("Lunar", "first", {"budget": 100})
        self.store.add_version(project, "second", "Budget reduction", {"budget": 80})
        reopened = ProjectWorkspaces(self.store.database).get(project)
        self.assertEqual([v["number"] for v in reopened["versions"]], [2, 1])
        self.assertEqual(reopened["versions"][0]["label"], "Budget reduction")

    def test_slate_counts_project_once_and_keeps_legacy(self):
        self.report("first")
        self.report("second", 80, 30, "GO")
        self.report("legacy")
        project = self.store.create("Lunar", "first", {"budget": 100})
        self.store.add_version(project, "second", "Revision", {"budget": 80})
        response = self.client.get("/api/projects").json()
        self.assertEqual(len(response["reports"]), 2)
        row = next(r for r in response["reports"] if r.get("workspace_id") == project)
        self.assertEqual(row["id"], "second")
        self.assertEqual(row["version_count"], 2)
        self.assertEqual(response["dashboard"]["total_budget"], 180)

    def test_comparison_tracks_inputs_and_metrics(self):
        self.report("first")
        self.report("second", 80, 30, "GO")
        project = self.store.create("Lunar", "first", {"budget": 100, "source_material_text": "old"})
        self.store.add_version(project, "second", "New treatment", {"budget": 80, "source_material_text": "new"})
        response = self.client.get(f"/api/projects/{project}/compare?before=1&after=2")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual({r["field"] for r in data["inputs"]}, {"budget", "source_material_text"})
        self.assertEqual(next(r["delta"] for r in data["metrics"] if r["field"] == "moderate_roi"), 20)
        self.assertEqual(next(r["after"] for r in data["metrics"] if r["field"] == "recommendation"), "GO")

    def test_comparison_rejects_unrelated_version(self):
        project = self.store.create("One", "first", {})
        self.assertEqual(self.client.get(f"/api/projects/{project}/compare?before=1&after=2").status_code, 400)
        self.assertEqual(self.client.get("/api/projects/missing").status_code, 404)

    def test_unknown_workspace_rejected_before_job(self):
        response = self.client.post("/api/analyze", json={"description": "A sufficiently long logline", "workspace_id": "missing"})
        self.assertEqual(response.status_code, 404)

    def test_failed_analysis_does_not_add_version(self):
        project = self.store.create("Lunar", "first", {})
        job_id = "workspace-failed-test"
        web_app.JOBS[job_id] = {"events": []}
        self.addCleanup(web_app.JOBS.pop, job_id, None)
        async def fail(*args, **kwargs):
            raise RuntimeError("Provider unavailable")
        with patch("web_app.GreenlightingCLI.analyze_project", fail):
            asyncio.run(web_app._run_analysis(job_id, web_app.AnalysisRequest(
                description="A sufficiently long logline", workspace_id=project, demo_mode=True)))
        self.assertEqual(web_app.JOBS[job_id]["status"], "failed")
        self.assertEqual(len(self.store.get(project)["versions"]), 1)

    def test_completed_analysis_links_snapshot(self):
        project = self.store.create("Lunar", "first", {})
        self.report("second")
        job_id = "workspace-complete-test"
        web_app.JOBS[job_id] = {"events": []}
        self.addCleanup(web_app.JOBS.pop, job_id, None)
        async def complete(*args, **kwargs):
            return {"analysis_json_path": str(self.reports / "second.json")}
        with patch("web_app.GreenlightingCLI.analyze_project", complete):
            asyncio.run(web_app._run_analysis(job_id, web_app.AnalysisRequest(
                description="A sufficiently long logline", workspace_id=project, demo_mode=True,
                version_label="New treatment", source_material_text="Full confidential treatment")))
        version = self.store.get(project)["versions"][0]
        self.assertEqual(web_app.JOBS[job_id]["status"], "completed")
        self.assertEqual(version["request"]["source_material_text"], "Full confidential treatment")
        self.assertEqual(version["label"], "New treatment")

    def test_same_second_reports_have_unique_paths(self):
        from main import GreenlightingCLI
        with patch("main.OUTPUT_DIR", self.reports), patch("main.get_timestamp", return_value="fixed"), \
             patch("main.assert_report_quality", return_value={}), \
             patch.object(GreenlightingCLI, "_format_report", return_value="Report"):
            cli = GreenlightingCLI()
            results = {"project_data": {"description": "Same project"}}
            first = cli._save_report(results)
            second = cli._save_report(results)
        self.assertNotEqual(first, second)
        self.assertTrue(first.exists() and second.exists())
