import csv
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from signaldesk_health import (
    Metrics,
    build_health_check,
    classify_evidence,
    load_records,
    render_report,
)


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "product_usage_events.csv"


class SignalDeskHealthCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.check = build_health_check(DATA)

    def test_loads_all_source_rows_and_finds_prompt_change(self):
        self.assertEqual(len(self.check.records), 41)
        self.assertEqual(self.check.prompt_change_date.isoformat(), "2026-08-04")

    def test_normalizes_team_without_changing_raw_value(self):
        record = next(record for record in self.check.records if record.original_team == "product")
        self.assertEqual(record.team, "Product")
        self.assertIn("normalized_category", {issue.code for issue in self.check.issues})

    def test_detects_missing_values_without_imputation(self):
        missing = [issue for issue in self.check.issues if issue.code == "missing_value"]
        self.assertEqual(len(missing), 2)
        support = next(record for record in self.check.records if record.row_number == 5)
        feedback = next(record for record in self.check.records if record.row_number == 32)
        self.assertIsNone(support.user_rating)
        self.assertIsNone(feedback.median_confidence)
        self.assertTrue(support.analysis_eligible)
        self.assertTrue(feedback.analysis_eligible)

    def test_excludes_both_demo_and_duplicate_rows(self):
        excluded_rows = {
            record.row_number
            for record in self.check.records
            if not record.analysis_eligible
        }
        self.assertEqual(excluded_rows, {26, 27})
        duplicate = [issue for issue in self.check.issues if issue.code == "duplicate_composite_key"]
        self.assertEqual(len(duplicate), 1)
        self.assertEqual(set(duplicate[0].rows), {26, 27})

    def test_detects_august_7_as_incomplete_not_zero_usage(self):
        coverage = [issue for issue in self.check.issues if issue.code == "incomplete_daily_coverage"]
        self.assertEqual(len(coverage), 1)
        self.assertIn("2026-08-07", coverage[0].message)
        lead_incident_day = [
            record
            for record in self.check.records
            if record.observed_on.isoformat() == "2026-08-07" and record.workflow == "Lead summary"
        ]
        self.assertEqual(sum(record.sessions or 0 for record in lead_incident_day), 61)

    def test_ratio_of_sums_matches_independent_known_totals(self):
        lead_before = self.check.baseline["Lead summary"]
        self.assertEqual((lead_before.sessions, lead_before.completed, lead_before.accepted, lead_before.flagged), (198, 154, 119, 16))
        self.assertAlmostEqual(lead_before.completion_rate, 154 / 198)
        self.assertAlmostEqual(lead_before.acceptance_rate, 119 / 154)
        self.assertAlmostEqual(lead_before.review_rate, 16 / 154)

        reply_after = self.check.post_prompt["Reply draft"]
        self.assertEqual((reply_after.sessions, reply_after.completed, reply_after.accepted, reply_after.flagged), (264, 213, 164, 33))

    def test_incident_metrics_and_context_are_exact(self):
        self.assertEqual(len(self.check.incident_records), 1)
        incident = self.check.incident_records[0]
        self.assertEqual(incident.workflow, "Reply draft")
        self.assertEqual((incident.sessions, incident.completed, incident.accepted_output, incident.flagged_for_review), (30, 17, 8, 12))
        report = render_report(self.check, DATA.name)
        self.assertIn("Completion: 56.7%", report)
        self.assertIn("Acceptance among completed: 47.1%", report)
        self.assertIn("Review flags per completed: 70.6%", report)
        self.assertIn("Model-reported confidence: 0.91", report)

    def test_confidence_cannot_change_evidence_label(self):
        baseline = Metrics(1, 100, 80, 64, 8, 0.8, 0.8, 0.1, 5.0, 0.1, 4.0)
        post = Metrics(1, 100, 80, 65, 8, 0.8, 0.8125, 0.1, 5.0, 0.1, 4.0)
        high_confidence_post = replace(post, median_confidence=0.99)
        self.assertEqual(classify_evidence(baseline, post), classify_evidence(baseline, high_confidence_post))

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
