"""Budget cap arithmetic, safe suggestions, and incomplete evidence handling."""

import unittest
from utils.slate_planner import build_plan, number


def candidate(report_id, exposure=100, roi=20, genre="Drama", decision="Approved", ai="GO"):
    return {"id": report_id, "eligible": True, "exposure": exposure,
            "rois": {"Downside": -20, "Base": roi, "Upside": 60},
            "genre": genre, "producer_decision": decision, "recommendation": ai,
            "conditions": "", "platform": "theatrical", "overall_risk_score": 4}


class PlannerTests(unittest.TestCase):
    def test_weighted_roi_and_cap_include_total_exposure(self):
        rows = [candidate("a", 100, 20), candidate("b", 300, 40, "Horror")]
        plan = build_plan(rows, 500, ["a", "b"])
        self.assertEqual(plan["total_exposure"], 400)
        self.assertEqual(plan["remaining"], 100)
        self.assertEqual(plan["scenarios"][1]["modeled_profit"], 140)
        self.assertEqual(plan["scenarios"][1]["weighted_roi"], 35)
        self.assertEqual(plan["genre_mix"][0]["share"], 75)

    def test_over_cap_does_not_silently_drop_manual_selections(self):
        plan = build_plan([candidate("a", 100)], 80, ["a"])
        self.assertTrue(plan["over_cap"])
        self.assertEqual(plan["remaining"], -20)
        self.assertEqual(plan["selected_ids"], ["a"])

    def test_suggestion_stays_under_cap_and_excludes_blocked_decisions(self):
        rows = [candidate("a", 100), candidate("b", 50, decision="Hold"),
                candidate("c", 50, decision="Rework"), candidate("d", 50, decision="Passed"),
                candidate("e", 50, ai="NO-GO"), candidate("f", 70, roi=-1), candidate("g", 20)]
        plan = build_plan(rows, 110, suggest=True)
        self.assertLessEqual(plan["total_exposure"], 110)
        self.assertEqual(plan["selected_ids"], ["a"])
        self.assertIn("not an optimal", plan["method"])

    def test_approved_ranked_before_unreviewed(self):
        rows = [candidate("a", 100, roi=100, decision="Awaiting review"), candidate("b", 100, roi=10)]
        self.assertEqual(build_plan(rows, 100, suggest=True)["selected_ids"], ["b"])

    def test_missing_scenario_is_not_zero_or_partial_total(self):
        rows = [candidate("a"), candidate("b")]
        rows[1]["rois"]["Downside"] = None
        plan = build_plan(rows, 300, ["a", "b"])
        self.assertIsNone(plan["scenarios"][0]["modeled_profit"])
        self.assertEqual(plan["scenarios"][0]["coverage"], 1)
        self.assertIsNotNone(plan["scenarios"][1]["modeled_profit"])

    def test_empty_selection_has_no_scenario_forecast(self):
        plan = build_plan([], 100, [])
        self.assertEqual(plan["total_exposure"], 0)
        self.assertEqual(plan["remaining"], 100)
        self.assertIsNone(plan["scenarios"][1]["weighted_roi"])

    def test_rejects_invalid_selection(self):
        for ids in (["missing"], ["a", "a"]):
            with self.assertRaises(ValueError):
                build_plan([candidate("a")], 100, ids)
        row = candidate("a")
        row["eligible"] = False
        with self.assertRaises(ValueError):
            build_plan([row], 100, ["a"])

    def test_cap_must_be_positive_and_finite(self):
        for value in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                build_plan([], value)
        self.assertIsNone(number("n/a"))
        self.assertIsNone(number(float("nan")))

    def test_manual_no_go_and_conditions_warn_without_approval(self):
        row = candidate("a", ai="NO-GO", decision="Rework")
        row["conditions"] = "Budget cap"
        row["platform"] = "streaming"
        plan = build_plan([row], 200, ["a"])
        self.assertTrue(any("not approved" in warning for warning in plan["warnings"]))
        self.assertTrue(any("NO-GO" in warning for warning in plan["warnings"]))
        self.assertTrue(any("manual verification" in warning for warning in plan["warnings"]))
        self.assertTrue(any("not cash" in warning for warning in plan["warnings"]))

    def test_demo_selection_is_explicitly_labelled(self):
        row = candidate("demo")
        row["demo_mode"] = True
        self.assertTrue(any("demo sample" in warning for warning in build_plan([row], 200, ["demo"])["warnings"]))
