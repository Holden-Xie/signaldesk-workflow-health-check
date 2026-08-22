import csv
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from signaldesk_health import build_health_check, choose_most_useful, load_records, render_report


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "product_usage_events.csv"


class SignalDeskUsefulnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.check = build_health_check(DATA)

    def test_uses_stable_post_change_window_for_current_answer(self):
        self.assertEqual(len(self.check.records), 41)
        self.assertEqual(self.check.prompt_change_date.isoformat(), "2026-08-04")
        self.assertEqual(self.check.current_start.isoformat(), "2026-08-04")
        self.assertEqual(self.check.current_end.isoformat(), "2026-08-06")
        self.assertNotIn(self.check.current_end, self.check.incident_dates)

    def test_normalizes_team_without_changing_raw_value(self):
        record = next(record for record in self.check.records if record.original_team == "product")
        self.assertEqual(record.team, "Product")
        self.assertIn("normalized_category", {issue.code for issue in self.check.issues})

    def test_missing_optional_values_are_not_imputed_or_excluded(self):
        missing = [issue for issue in self.check.issues if issue.code == "missing_value"]
        self.assertEqual(len(missing), 2)
        support = next(record for record in self.check.records if record.row_number == 5)
        feedback = next(record for record in self.check.records if record.row_number == 32)
        self.assertIsNone(support.user_rating)
        self.assertIsNone(feedback.median_confidence)
        self.assertTrue(support.analysis_eligible)
        self.assertTrue(feedback.analysis_eligible)

    def test_excludes_both_demo_and_duplicate_rows(self):
        excluded = {
            record.row_number
            for record in self.check.records
            if not record.analysis_eligible
        }
        self.assertEqual(excluded, {26, 27})
        duplicate = [issue for issue in self.check.issues if issue.code == "duplicate_composite_key"]
        self.assertEqual(len(duplicate), 1)
        self.assertEqual(set(duplicate[0].rows), {26, 27})

    def test_current_scorecards_match_independent_known_totals(self):
        expected = {
            "Lead summary": (191, 147, 115, 13),
            "Reply draft": (264, 213, 164, 33),
            "Feedback clustering": (100, 67, 44, 12),
        }
        for workflow, totals in expected.items():
            metrics = self.check.scorecards[workflow].metrics
            self.assertEqual(
                (metrics.sessions, metrics.completed, metrics.accepted, metrics.flagged),
                totals,
            )

    def test_ratio_of_sums_is_used(self):
        lead = self.check.scorecards["Lead summary"].metrics
        self.assertAlmostEqual(lead.completion_rate, 147 / 191)
        self.assertAlmostEqual(lead.acceptance_rate, 115 / 147)
        self.assertAlmostEqual(lead.review_rate, 13 / 147)

    def test_daily_impact_and_coverage_are_exact(self):
        lead = self.check.scorecards["Lead summary"]
        reply = self.check.scorecards["Reply draft"]
        feedback = self.check.scorecards["Feedback clustering"]

        self.assertAlmostEqual(lead.accepted_per_day, 115 / 3)
        self.assertAlmostEqual(reply.accepted_per_day, 164 / 3)
        self.assertAlmostEqual(feedback.accepted_per_day, 44 / 3)
        self.assertAlmostEqual(lead.estimated_minutes_per_day, 1167.5 / 3)
        self.assertAlmostEqual(reply.estimated_minutes_per_day, 851.0 / 3)
        self.assertAlmostEqual(feedback.estimated_minutes_per_day, 874.6 / 3)
        self.assertEqual((lead.observed_segment_days, lead.expected_segment_days), (5, 6))
        self.assertAlmostEqual(lead.coverage_rate, 5 / 6)
        self.assertEqual(reply.coverage_rate, 1.0)
        self.assertEqual(feedback.coverage_rate, 1.0)

    def test_decision_is_transparent_and_selects_lead_summary(self):
        decision = self.check.decision
        self.assertEqual(decision.winner, "Lead summary")
        self.assertEqual(decision.confidence, "TENTATIVE")
        self.assertEqual(decision.win_counts["Lead summary"], 2)
        self.assertEqual(decision.lens_winners["accepted outputs per day"], "Reply draft")
        self.assertEqual(decision.lens_winners["acceptance rate"], "Lead summary")
        self.assertEqual(decision.lens_winners["lowest review burden"], "Lead summary")
        self.assertNotIn("estimated minutes saved per day", decision.lens_winners)

    def test_model_confidence_cannot_change_usefulness_decision(self):
        original = self.check.scorecards
        changed = dict(original)
        reply = changed["Reply draft"]
        changed["Reply draft"] = replace(
            reply,
            metrics=replace(reply.metrics, median_confidence=1.0),
        )
        self.assertEqual(choose_most_useful(original).winner, choose_most_useful(changed).winner)

    def test_incident_day_is_not_mixed_into_current_reply_metrics(self):
        reply = self.check.scorecards["Reply draft"].metrics
        self.assertEqual(reply.sessions, 264)
        self.assertEqual(len(self.check.incident_records), 1)
        self.assertEqual(self.check.incident_records[0].observed_on.isoformat(), "2026-08-07")

    def test_report_answers_the_decision_question_and_discloses_limits(self):
        report = render_report(self.check, DATA.name)
        self.assertIn("Lead summary appears most useful right now, tentatively", report)
        self.assertIn("Reply draft leads accepted-output throughput", report)
        self.assertIn("83.3% current-window source coverage", report)
        self.assertIn("same Tuesday-Thursday window", report)
        self.assertIn("Three days is too short", report)

    def test_missing_required_columns_fail_clearly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["date", "team"])
                writer.writerow(["2026-08-01", "Sales"])
            with self.assertRaisesRegex(ValueError, "Missing required columns"):
                load_records(path)


if __name__ == "__main__":
    unittest.main()
