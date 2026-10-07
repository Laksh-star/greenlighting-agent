"""Actuals precision, forecast isolation and manual constraint audit tests."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
import web_app
from utils.project_workspaces import ProjectWorkspaces
from utils.production_tracking import (
    ACTUALS_CSV, cents, normalize_snapshot, parse_actuals_csv,
    production_detail, save_actuals, save_constraint,
)


class ProductionTrackingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = ProjectWorkspaces(self.root / "workspaces.sqlite3")
        self.reports = self.root / "reports"
        self.reports.mkdir()
        for name, budget, platform in (("first", 100, "theatrical"), ("second", 200, "streaming")):
            payload = {"project": {"budget": budget, "platform": platform},
                       "financial_assumptions": {"marketing_spend": 20},
                       "financial_scenarios": {"moderate_revenue": 300, "moderate_net_revenue": 150}}
            (self.reports / f"{name}.json").write_text(json.dumps(payload))
            (self.reports / f"{name}.md").write_text("Immutable forecast")
        self.project = self.store.create("Film", "first", {})
        self.store.add_version(self.project, "second", "Streaming revision", {})
        self.client = TestClient(web_app.app)
        for name, value in (("workspaces", self.store), ("OUTPUT_DIR", self.reports)):
            item = patch(f"web_app.{name}", value)
            item.start()
            self.addCleanup(item.stop)

    def snapshot(self, **changes):
        return normalize_snapshot({"version": 1, "as_of": "2026-10-07", "phase": "Interim",
                                   "production_spend": "80.01", "marketing_spend": "10",
                                   "gross_revenue": "250", "studio_receipts": "120",
                                   "notes": "Finance reconciliation", **changes})

    def detail(self, **kwargs):
        return production_detail(self.store, self.project, self.reports, **kwargs)

    def constraint(self, **changes):
        return {"version": 1, "category": "Location", "title": "Soundstage booking",
                "status": "Blocked", "owner": "Producer", "start_date": "2026-11-01",
                "end_date": "2026-11-07", "notes": "Awaiting contract", **changes}

    def test_amount_precision_and_unknown(self):
        self.assertEqual(cents("80.01"), 8001)
        self.assertEqual(cents("0"), 0)
        self.assertIsNone(cents(""))
        for value in ("-1", "NaN", "Infinity", "1.001", "not money"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cents(value)

    def test_duplicate_snapshot_is_not_double_counted(self):
        row = self.snapshot()
        self.assertEqual(save_actuals(self.store, self.project, [row, row]),
                         {"imported": 1, "skipped_duplicates": 1})
        self.assertEqual(len(self.detail()["actual_snapshots"]), 1)

    def test_correction_appends_and_older_date_does_not_replace_latest(self):
        save_actuals(self.store, self.project, [self.snapshot(), self.snapshot(production_spend="90"),
                                               self.snapshot(as_of="2026-10-01", production_spend="10")])
        detail = self.detail()
        self.assertEqual(len(detail["actual_snapshots"]), 3)
        self.assertEqual(detail["comparison"]["snapshot"]["production_spend"], 90)

    def test_comparison_uses_selected_version_and_cash_receipts(self):
        save_actuals(self.store, self.project, [self.snapshot()])
        comparison = self.detail()["comparison"]
        self.assertEqual(comparison["report_id"], "first")
        self.assertEqual(comparison["rows"][0]["forecast"], 100)
        self.assertEqual(comparison["cash_profit"], 29.99)
        self.assertTrue(comparison["warnings"])
        self.assertEqual((self.reports / "first.md").read_text(), "Immutable forecast")

    def test_unknown_costs_or_receipts_do_not_generate_profit(self):
        for changes in ({"marketing_spend": None}, {"studio_receipts": None},
                        {"production_spend": "0", "marketing_spend": "0"}):
            save_actuals(self.store, self.project, [self.snapshot(**changes)])
            self.assertIsNone(self.detail()["comparison"]["cash_roi"])

    def test_streaming_ltv_is_not_a_cash_forecast(self):
        save_actuals(self.store, self.project, [self.snapshot(version=2, phase="Final")])
        comparison = self.detail()["comparison"]
        self.assertIsNone(comparison["rows"][2]["forecast"])
        self.assertIsNone(comparison["rows"][3]["forecast"])
        self.assertIn("lifetime value", comparison["warnings"][0])

    def test_snapshot_selection_and_project_isolation(self):
        save_actuals(self.store, self.project, [self.snapshot(), self.snapshot(version=2)])
        first = self.detail()["actual_snapshots"][-1]
        self.assertEqual(self.detail(snapshot_id=first["id"])["comparison"]["report_id"], "first")
        other = self.store.create("Other", "unrelated-report", {})
        with self.assertRaises(ValueError):
            production_detail(self.store, other, self.reports, snapshot_id=first["id"])

    def test_csv_validation_and_atomic_version_rejection(self):
        rows = parse_actuals_csv(ACTUALS_CSV)
        self.assertEqual(len(rows), 1)
        with self.assertRaises(ValueError):
            parse_actuals_csv(ACTUALS_CSV + "1,invalid,Interim,1,1,1,1,Invalid date\n")
        with self.assertRaises(ValueError):
            save_actuals(self.store, self.project, [rows[0], self.snapshot(version=9)])
        self.assertEqual(self.detail()["actual_snapshots"], [])

    def test_constraint_updates_keep_history_and_resolve_blocker(self):
        first = save_constraint(self.store, self.project, self.constraint())
        self.assertEqual(self.detail()["blocker_count"], 1)
        save_constraint(self.store, self.project, self.constraint(
            constraint_id=first["constraint_id"], version=2, status="Confirmed", notes="Contract signed"))
        detail = self.detail()
        self.assertEqual(detail["blocker_count"], 0)
        self.assertEqual(len(detail["constraints"]), 1)
        self.assertEqual(len(detail["constraint_history"]), 2)

    def test_constraint_rejects_foreign_id_version_and_invalid_window(self):
        first = save_constraint(self.store, self.project, self.constraint())
        other = self.store.create("Other", "unrelated-report", {})
        with self.assertRaises(ValueError):
            save_constraint(self.store, other, self.constraint(constraint_id=first["constraint_id"]))
        for changes in ({"version": 9}, {"end_date": "2026-10-01"}, {"status": "Approved"}, {"notes": " "}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                save_constraint(self.store, self.project, self.constraint(**changes))

    def test_api_snapshot_validation_and_persistence(self):
        url = f"/api/projects/{self.project}/actuals"
        body = {"version": 1, "as_of": "2026-10-07", "production_spend": "1.01", "notes": "Manual ledger"}
        self.assertEqual(self.client.post(url, json=body).status_code, 201)
        self.assertEqual(self.client.post(url, json={**body, "production_spend": "1.001"}).status_code, 422)
        result = self.client.get(f"/api/projects/{self.project}/production").json()
        self.assertEqual(result["comparison"]["snapshot"]["production_spend"], 1.01)
        reopened = ProjectWorkspaces(self.store.database)
        self.assertEqual(len(production_detail(reopened, self.project, self.reports)["actual_snapshots"]), 1)

    def test_api_csv_duplicate_and_constraint_routes(self):
        url = f"/api/projects/{self.project}"
        for expected in (1, 0):
            response = self.client.post(url + "/actuals/import", json={"csv_text": ACTUALS_CSV})
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json()["imported"], expected)
        self.assertEqual(self.client.post(url + "/constraints", json=self.constraint()).status_code, 201)
        self.assertEqual(self.client.get("/api/projects/missing/production").status_code, 404)
        self.assertEqual(self.client.get("/api/actuals/template").status_code, 200)
        self.assertEqual(self.client.get("/static/production-tools.js").status_code, 200)
