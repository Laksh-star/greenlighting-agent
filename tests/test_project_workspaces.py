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

    def test_producer_decision_persists_without_changing_ai_report(self):
        self.report("first", recommendation="NO-GO")
        original = (self.reports / "first.json").read_text()
        project = self.store.create("Lunar", "first", {})
        response = self.client.post(f"/api/projects/{project}/decisions", json={
            "version": 1, "status": "Approved", "reviewer": "Producer",
            "notes": "Proceed with attached financing", "conditions": "Budget below $12M"})
        self.assertEqual(response.status_code, 201)
        reopened = ProjectWorkspaces(self.store.database).get(project)
        self.assertEqual(reopened["decisions"][0]["conditions"], "Budget below $12M")
        self.assertTrue(reopened["decisions"][0]["created_at"].endswith("Z"))
        self.assertEqual((self.reports / "first.json").read_text(), original)
        row = self.store.slate(self.reports)[0]
        self.assertEqual(row["human_decision"]["status"], "Approved")
        self.assertEqual(row["recommendation"], "NO-GO")

    def test_producer_decisions_are_append_only(self):
        project = self.store.create("Lunar", "first", {})
        first = self.store.record_decision(project, 1, "Hold", "A", "Await financing")
        second = self.store.record_decision(project, 1, "Approved", "B", "Financing confirmed")
        decisions = self.store.get(project)["decisions"]
        self.assertEqual([d["id"] for d in decisions], [second["id"], first["id"]])
        self.assertEqual(decisions[1]["status"], "Hold")

    def test_new_version_does_not_inherit_approval(self):
        self.report("first")
        self.report("second")
        project = self.store.create("Lunar", "first", {})
        self.store.record_decision(project, 1, "Approved", "A", "Approved original")
        self.store.add_version(project, "second", "Revised budget", {})
        row = self.store.slate(self.reports)[0]
        self.assertIsNone(row["human_decision"])
        self.assertEqual(row["previous_decision"]["version"], 1)

    def test_old_version_decision_does_not_override_current_review(self):
        self.report("first")
        self.report("second")
        project = self.store.create("Lunar", "first", {})
        self.store.add_version(project, "second", "Revised", {})
        self.store.record_decision(project, 2, "Rework", "A", "Revise treatment")
        self.store.record_decision(project, 1, "Approved", "B", "Original still approved")
        self.assertEqual(self.store.slate(self.reports)[0]["human_decision"]["status"], "Rework")

    def test_decision_rejects_foreign_version_and_missing_project(self):
        project = self.store.create("Lunar", "first", {})
        self.store.create("Other", "other", {})
        body = {"version": 2, "status": "Hold", "reviewer": "A", "notes": "Review"}
        self.assertEqual(self.client.post(f"/api/projects/{project}/decisions", json=body).status_code, 400)
        self.assertEqual(self.client.post("/api/projects/missing/decisions", json=body).status_code, 404)
        self.assertEqual(self.store.get(project)["decisions"], [])

    def test_decision_rejects_invalid_status_and_blank_fields(self):
        project = self.store.create("Lunar", "first", {})
        base = {"version": 1, "status": "Hold", "reviewer": "A", "notes": "Review"}
        for update, code in [({"status": "GO"}, 422), ({"reviewer": " "}, 400),
                             ({"notes": "\n "}, 400), ({"notes": "x" * 5001}, 422)]:
            with self.subTest(update=update):
                response = self.client.post(f"/api/projects/{project}/decisions", json={**base, **update})
                self.assertEqual(response.status_code, code)
        self.assertEqual(self.store.get(project)["decisions"], [])

    def test_decision_table_migrates_existing_workspace_database(self):
        import sqlite3
        project = self.store.create("Lunar", "first", {})
        with sqlite3.connect(self.store.database) as db:
            db.execute("DROP TABLE decisions")
        self.store.record_decision(project, 1, "Passed", "Producer", "Not a slate fit")
        workspace = self.store.get(project)
        self.assertEqual(len(workspace["versions"]), 1)
        self.assertEqual(workspace["decisions"][0]["status"], "Passed")

    def test_planner_endpoints_use_latest_version_only(self):
        self.report("first", 100, 20)
        self.report("second", 80, 30)
        project = self.store.create("Lunar", "first", {})
        self.store.add_version(project, "second", "Lean", {})
        candidates = self.client.get("/api/slate-planner").json()["projects"]
        self.assertEqual([p["id"] for p in candidates], ["second"])
        plan = self.client.post("/api/slate-planner/plan", json={"funding_cap": 200, "selected_ids": ["second"]})
        self.assertEqual(plan.status_code, 200)
        self.assertEqual(plan.json()["total_exposure"], 120)
        self.assertEqual(plan.json()["scenarios"][0]["modeled_profit"], None)
        stale = self.client.post("/api/slate-planner/plan", json={"funding_cap": 200, "selected_ids": ["first"]})
        self.assertEqual(stale.status_code, 400)

    def test_planner_page_and_assets(self):
        self.assertEqual(self.client.get("/slate-planner").status_code, 200)
        for asset in ("slate-planner.js", "slate-planner.css"):
            self.assertEqual(self.client.get(f"/static/{asset}").status_code, 200)
        self.assertEqual(self.client.post("/api/slate-planner/plan", json={"funding_cap": 0}).status_code, 422)

    def test_milestones_default_and_append_history(self):
        project = self.store.create("Lunar", "first", {})
        self.assertEqual(len(self.store.get(project)["milestones"]), 5)
        for status in ("In progress", "Complete"):
            response = self.client.post(f"/api/projects/{project}/milestones", json={
                "version": 1, "milestone": "Script", "status": status, "owner": "Writer",
                "due_date": "2026-11-01", "notes": "Recorded development update"})
            self.assertEqual(response.status_code, 201)
        workspace = self.store.get(project)
        self.assertEqual(len(workspace["milestone_history"]), 2)
        self.assertEqual(next(m for m in workspace["milestones"] if m["milestone"] == "Script")["status"], "Complete")
        self.store.add_version(project, "second", "Revision", {})
        self.assertEqual(self.store.get(project)["milestone_history"][0]["version"], 1)
        self.assertEqual(self.store.get(project)["decisions"], [])

    def test_milestone_validation_and_version_isolation(self):
        project = self.store.create("Lunar", "first", {})
        body = {"version": 1, "milestone": "Financing", "status": "Blocked", "notes": "Pending commitment"}
        for update, status in [({"milestone": "Unknown"}, 422), ({"status": "Ready"}, 422),
                               ({"due_date": "not-a-date"}, 422), ({"version": 2}, 400), ({"notes": " "}, 400)]:
            with self.subTest(update=update):
                self.assertEqual(self.client.post(f"/api/projects/{project}/milestones", json={**body, **update}).status_code, status)
        self.assertEqual(self.client.post("/api/projects/missing/milestones", json=body).status_code, 404)
        self.assertEqual(self.store.get(project)["milestone_history"], [])

    def test_milestone_storage_survives_reopening(self):
        project = self.store.create("Lunar", "first", {})
        self.store.update_milestone(project, 1, "Treatment", "Complete", "Producer", "", "Treatment signed off")
        reopened = ProjectWorkspaces(self.store.database).get(project)
        self.assertEqual(reopened["milestones"][0]["status"], "Complete")

    def test_evidence_endpoint_supports_legacy_without_mutating_report(self):
        self.report("legacy")
        original = (self.reports / "legacy.json").read_text()
        response = self.client.get("/api/reports/legacy/evidence")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["evidence"])
        self.assertEqual((self.reports / "legacy.json").read_text(), original)
        self.assertEqual(self.client.get("/api/reports/missing/evidence").status_code, 404)

    def test_stress_endpoint_does_not_call_ai_or_change_report(self):
        from test_evidence_stress import financial_payload
        (self.reports / "stress.json").write_text(json.dumps(financial_payload()))
        original = (self.reports / "stress.json").read_text()
        with patch("web_app.GreenlightingCLI.analyze_project") as analyze, patch("web_app.tmdb_client.enrich_comparable_titles") as tmdb:
            response = self.client.post("/api/reports/stress/stress", json={"revenue_multiplier": .5, "overrun_pct": 20})
            self.assertEqual(response.status_code, 200)
            analyze.assert_not_called()
            tmdb.assert_not_called()
        self.assertEqual((self.reports / "stress.json").read_text(), original)
        self.assertEqual(self.client.post("/api/reports/stress/stress", json={"overrun_pct": 200}).status_code, 422)
