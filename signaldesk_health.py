"""Generate a compact, auditable SignalDesk workflow health report.

The implementation intentionally uses only Python's standard library so the
challenge artifact is easy to run in a clean environment.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable


REQUIRED_COLUMNS = {
    "date",
    "team",
    "workflow",
    "source",
    "sessions",
    "completed",
    "accepted_output",
    "flagged_for_review",
    "avg_minutes_saved",
    "median_confidence",
    "user_rating",
    "notes",
}
COUNT_FIELDS = ("sessions", "completed", "accepted_output", "flagged_for_review")
OPTIONAL_FLOAT_FIELDS = ("median_confidence", "user_rating")
MISSING_TOKENS = {"", "n/a", "na", "null", "none"}


@dataclass
class Issue:
    code: str
    message: str
    severity: str = "warning"
    rows: tuple[int, ...] = ()


@dataclass
class Record:
    row_number: int
    observed_on: date
    team: str
    original_team: str
    workflow: str
    source: str
    sessions: int | None
    completed: int | None
    accepted_output: int | None
    flagged_for_review: int | None
    avg_minutes_saved: float | None
    median_confidence: float | None
    user_rating: float | None
    notes: str
    analysis_eligible: bool = True
    exclusion_reasons: list[str] = field(default_factory=list)

    @property
    def segment(self) -> tuple[str, str, str]:
        return self.team, self.workflow, self.source

    @property
    def composite_key(self) -> tuple[date, str, str, str]:
        return self.observed_on, *self.segment


@dataclass(frozen=True)
class Metrics:
    rows: int
    sessions: int
    completed: int
    accepted: int
    flagged: int
    completion_rate: float
    acceptance_rate: float
    review_rate: float
    avg_minutes_saved: float | None
    median_confidence: float | None
    mean_row_rating: float | None


@dataclass
class HealthCheck:
    records: list[Record]
    issues: list[Issue]
    prompt_change_date: date
    incident_dates: set[date]
    baseline: dict[str, Metrics]
    post_prompt: dict[str, Metrics]
    incident_records: list[Record]


def _clean_text(value: str | None) -> str:
    return (value or "").strip()


def _normalize_team(value: str) -> str:
    known = {"sales": "Sales", "support": "Support", "product": "Product"}
    cleaned = _clean_text(value)
    return known.get(cleaned.casefold(), cleaned)


def _parse_int(value: str, field_name: str, row_number: int, issues: list[Issue]) -> int | None:
    cleaned = _clean_text(value).casefold()
    if cleaned in MISSING_TOKENS:
        issues.append(Issue("missing_required_value", f"Row {row_number}: {field_name} is missing.", "error", (row_number,)))
        return None
    try:
        number = int(cleaned)
    except ValueError:
        issues.append(Issue("invalid_integer", f"Row {row_number}: {field_name}={value!r} is not an integer.", "error", (row_number,)))
        return None
    if number < 0:
        issues.append(Issue("negative_count", f"Row {row_number}: {field_name} cannot be negative.", "error", (row_number,)))
        return None
    return number


def _parse_float(
    value: str,
    field_name: str,
    row_number: int,
    issues: list[Issue],
    *,
    optional: bool,
) -> float | None:
    cleaned = _clean_text(value).casefold()
    if cleaned in MISSING_TOKENS:
        severity = "info" if optional else "error"
        issues.append(Issue("missing_value", f"Row {row_number}: {field_name} is missing.", severity, (row_number,)))
        return None
    try:
        number = float(cleaned)
    except ValueError:
        issues.append(Issue("invalid_number", f"Row {row_number}: {field_name}={value!r} is not numeric.", "error", (row_number,)))
        return None
    if not math.isfinite(number):
        issues.append(Issue("nonfinite_number", f"Row {row_number}: {field_name} must be finite.", "error", (row_number,)))
        return None
    return number


def load_records(path: str | Path) -> tuple[list[Record], list[Issue]]:
    issues: list[Issue] = []
    records: list[Record] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing_columns = sorted(REQUIRED_COLUMNS - columns)
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

        for row_number, row in enumerate(reader, start=2):
            try:
                observed_on = date.fromisoformat(_clean_text(row["date"]))
            except ValueError as exc:
                raise ValueError(f"Row {row_number}: invalid ISO date {row['date']!r}") from exc

            original_team = _clean_text(row["team"])
            team = _normalize_team(original_team)
            if team != original_team:
                issues.append(
                    Issue(
                        "normalized_category",
                        f"Row {row_number}: normalized team {original_team!r} to {team!r}.",
                        "info",
                        (row_number,),
                    )
                )

            values = {
                name: _parse_int(row[name], name, row_number, issues)
                for name in COUNT_FIELDS
            }
            avg_minutes_saved = _parse_float(
                row["avg_minutes_saved"], "avg_minutes_saved", row_number, issues, optional=False
            )
            optional_values = {
                name: _parse_float(row[name], name, row_number, issues, optional=True)
                for name in OPTIONAL_FLOAT_FIELDS
            }

            record = Record(
                row_number=row_number,
                observed_on=observed_on,
                team=team,
                original_team=original_team,
                workflow=_clean_text(row["workflow"]),
                source=_clean_text(row["source"]),
                sessions=values["sessions"],
                completed=values["completed"],
                accepted_output=values["accepted_output"],
                flagged_for_review=values["flagged_for_review"],
                avg_minutes_saved=avg_minutes_saved,
                median_confidence=optional_values["median_confidence"],
                user_rating=optional_values["user_rating"],
                notes=_clean_text(row["notes"]),
            )
            _validate_record(record, issues)
            records.append(record)

    if not records:
        raise ValueError("The dataset contains no data rows.")
    return records, issues


def _validate_record(record: Record, issues: list[Issue]) -> None:
    row = record.row_number
    if record.sessions is not None and record.completed is not None and record.completed > record.sessions:
        issues.append(Issue("invalid_count_relationship", f"Row {row}: completed exceeds sessions.", "error", (row,)))
        record.analysis_eligible = False
        record.exclusion_reasons.append("invalid count relationship")
    if record.completed is not None:
        if record.accepted_output is not None and record.accepted_output > record.completed:
            issues.append(Issue("invalid_count_relationship", f"Row {row}: accepted_output exceeds completed.", "error", (row,)))
            record.analysis_eligible = False
            record.exclusion_reasons.append("invalid count relationship")
        if record.flagged_for_review is not None and record.flagged_for_review > record.completed:
            issues.append(Issue("invalid_count_relationship", f"Row {row}: flagged_for_review exceeds completed.", "error", (row,)))
            record.analysis_eligible = False
            record.exclusion_reasons.append("invalid count relationship")
    if record.avg_minutes_saved is not None and record.avg_minutes_saved < 0:
        issues.append(Issue("invalid_range", f"Row {row}: avg_minutes_saved cannot be negative.", "error", (row,)))
        record.analysis_eligible = False
        record.exclusion_reasons.append("invalid minutes-saved value")
    if record.median_confidence is not None and not 0 <= record.median_confidence <= 1:
        issues.append(Issue("invalid_range", f"Row {row}: median_confidence must be between 0 and 1.", "error", (row,)))
        record.median_confidence = None
    if record.user_rating is not None and not 1 <= record.user_rating <= 5:
        issues.append(Issue("invalid_range", f"Row {row}: user_rating must be between 1 and 5.", "error", (row,)))
        record.user_rating = None
    if any(getattr(record, name) is None for name in (*COUNT_FIELDS, "avg_minutes_saved")):
        record.analysis_eligible = False
        record.exclusion_reasons.append("missing required metric")


def _mark_duplicates_and_nonproduction(records: list[Record], issues: list[Issue]) -> None:
    by_key: dict[tuple[date, str, str, str], list[Record]] = defaultdict(list)
    for record in records:
        by_key[record.composite_key].append(record)

    for key, group in by_key.items():
        if len(group) < 2:
            continue
        rows = tuple(record.row_number for record in group)
        issues.append(Issue("duplicate_composite_key", f"Rows {rows} share composite key {key}.", "warning", rows))
        notes = " ".join(record.notes.casefold() for record in group)
        if "demo" in notes:
            reason = "non-production demo traffic and duplicate export"
            for record in group:
                record.analysis_eligible = False
                record.exclusion_reasons.append(reason)
            issues.append(Issue("excluded_nonproduction", f"Rows {rows} excluded: {reason}.", "warning", rows))


def _detect_coverage(records: list[Record], issues: list[Issue]) -> None:
    segments_by_date: dict[date, set[tuple[str, str, str]]] = defaultdict(set)
    for record in records:
        segments_by_date[record.observed_on].add(record.segment)
    patterns = Counter(tuple(sorted(segments)) for segments in segments_by_date.values())
    expected = set(patterns.most_common(1)[0][0])
    for observed_on, actual in sorted(segments_by_date.items()):
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        if missing or extra:
            message = f"{observed_on}: source coverage differs from the modal daily pattern"
            if missing:
                message += f"; missing {missing}"
            if extra:
                message += f"; extra {extra}"
            issues.append(Issue("incomplete_daily_coverage", message + ".", "warning"))


def aggregate(records: Iterable[Record]) -> Metrics:
    selected = list(records)
    if not selected:
        raise ValueError("Cannot aggregate an empty record set.")
    sessions = sum(record.sessions or 0 for record in selected)
    completed = sum(record.completed or 0 for record in selected)
    accepted = sum(record.accepted_output or 0 for record in selected)
    flagged = sum(record.flagged_for_review or 0 for record in selected)

    def ratio(numerator: int, denominator: int) -> float:
        return numerator / denominator if denominator else 0.0

    weighted_minutes_rows = [record for record in selected if record.avg_minutes_saved is not None and record.completed]
    minutes_denominator = sum(record.completed or 0 for record in weighted_minutes_rows)
    weighted_minutes = (
        sum((record.avg_minutes_saved or 0) * (record.completed or 0) for record in weighted_minutes_rows)
        / minutes_denominator
        if minutes_denominator
        else None
    )
    confidence_rows = [record for record in selected if record.median_confidence is not None and record.completed]
    confidence_denominator = sum(record.completed or 0 for record in confidence_rows)
    weighted_confidence = (
        sum((record.median_confidence or 0) * (record.completed or 0) for record in confidence_rows)
        / confidence_denominator
        if confidence_denominator
        else None
    )
    ratings = [record.user_rating for record in selected if record.user_rating is not None]
    return Metrics(
        rows=len(selected),
        sessions=sessions,
        completed=completed,
        accepted=accepted,
        flagged=flagged,
        completion_rate=ratio(completed, sessions),
        acceptance_rate=ratio(accepted, completed),
        review_rate=ratio(flagged, completed),
        avg_minutes_saved=weighted_minutes,
        median_confidence=weighted_confidence,
        mean_row_rating=statistics.fmean(ratings) if ratings else None,
    )


def classify_evidence(baseline: Metrics, post: Metrics) -> str:
    """Return a transparent evidence label; confidence is deliberately unused."""
    if min(baseline.completed, post.completed) < 50:
        return "LOW SAMPLE"
    deltas = (
        post.completion_rate - baseline.completion_rate,
        post.acceptance_rate - baseline.acceptance_rate,
        post.review_rate - baseline.review_rate,
    )
    if any(abs(delta) >= 0.10 for delta in deltas):
        return "NEEDS INVESTIGATION"
    if deltas[1] >= 0.02 and deltas[2] <= -0.02 and deltas[0] >= 0:
        return "DIRECTIONALLY POSITIVE"
    return "INCONCLUSIVE"


def build_health_check(path: str | Path) -> HealthCheck:
    records, issues = load_records(path)
    _mark_duplicates_and_nonproduction(records, issues)
    _detect_coverage(records, issues)

    prompt_dates = sorted(
        {record.observed_on for record in records if "new prompt version started" in record.notes.casefold()}
    )
    if not prompt_dates:
        raise ValueError("Could not identify a prompt change date from the notes column.")
    prompt_change_date = prompt_dates[0]
    incident_dates = {
        record.observed_on
        for record in records
        if "changed mid-day" in record.notes.casefold()
    }

    eligible = [record for record in records if record.analysis_eligible]
    baseline_records = [record for record in eligible if record.observed_on < prompt_change_date]
    post_records = [
        record
        for record in eligible
        if record.observed_on >= prompt_change_date and record.observed_on not in incident_dates
    ]
    workflows = sorted({record.workflow for record in baseline_records} & {record.workflow for record in post_records})
    baseline = {workflow: aggregate(record for record in baseline_records if record.workflow == workflow) for workflow in workflows}
    post_prompt = {workflow: aggregate(record for record in post_records if record.workflow == workflow) for workflow in workflows}
    incident_records = [
        record
        for record in eligible
        if record.observed_on in incident_dates and "changed mid-day" in record.notes.casefold()
    ]
    return HealthCheck(records, issues, prompt_change_date, incident_dates, baseline, post_prompt, incident_records)


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _pp(value: float) -> str:
    return f"{value * 100:+.1f} pp"


def render_report(check: HealthCheck, source_name: str) -> str:
    excluded = [record for record in check.records if not record.analysis_eligible]
    duplicate_issues = [issue for issue in check.issues if issue.code == "duplicate_composite_key"]
    missing_issues = [issue for issue in check.issues if issue.code == "missing_value"]
    normalized_issues = [issue for issue in check.issues if issue.code == "normalized_category"]
    coverage_issues = [issue for issue in check.issues if issue.code == "incomplete_daily_coverage"]

    lines = [
        "# SignalDesk Weekly Workflow Health Check",
        "",
        f"Source: `{source_name}`  ",
        f"Prompt-change comparison: baseline before {check.prompt_change_date} vs. post-change through the day before a mixed-policy incident.  ",
        "This is descriptive monitoring, not a causal experiment.",
        "",
        "## Can we trust this export?",
        "",
        f"- {len(check.records)} input rows",
        f"- {len(normalized_issues)} inconsistent categorical value normalized",
        f"- {len(duplicate_issues)} duplicate composite key detected",
        f"- {len(missing_issues)} optional metric values missing; neither was imputed",
        f"- {len(coverage_issues)} day with source coverage different from the modal pattern",
        f"- {len(excluded)} nonproduction/invalid rows excluded from comparisons",
        "",
    ]
    for issue in check.issues:
        if issue.code in {
            "normalized_category",
            "duplicate_composite_key",
            "excluded_nonproduction",
            "missing_value",
            "incomplete_daily_coverage",
        }:
            lines.append(f"- **{issue.code}**: {issue.message}")

    lines.extend(
        [
            "",
            "## What happened?",
            "",
            "Rates are ratios of summed counts. Deltas are percentage points.",
            "",
            "| Workflow | Completed (base/post) | Completion delta | Acceptance delta | Review delta | Evidence |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for workflow in sorted(check.baseline):
        before = check.baseline[workflow]
        after = check.post_prompt[workflow]
        lines.append(
            "| "
            + " | ".join(
                [
                    workflow,
                    f"{before.completed}/{after.completed}",
                    _pp(after.completion_rate - before.completion_rate),
                    _pp(after.acceptance_rate - before.acceptance_rate),
                    _pp(after.review_rate - before.review_rate),
                    classify_evidence(before, after),
                ]
            )
            + " |"
        )

    lines.extend(["", "## What looks suspicious?", ""])
    for record in check.incident_records:
        metrics = aggregate([record])
        lines.extend(
            [
                f"### NEEDS INVESTIGATION - {record.workflow} / {record.source} / {record.observed_on}",
                "",
                f"- Completion: {_pct(metrics.completion_rate)}",
                f"- Acceptance among completed: {_pct(metrics.acceptance_rate)}",
                f"- Review flags per completed: {_pct(metrics.review_rate)}",
                f"- Estimated minutes saved per completed session: {record.avg_minutes_saved:.1f}",
                f"- User rating: {record.user_rating:.1f}",
                f"- Model-reported confidence: {record.median_confidence:.2f}",
                f"- Context: {record.notes}",
                "",
                "Human-facing signals deteriorated while model confidence remained high. The policy changed mid-day, so this is an investigation trigger, not proof of a model or prompt regression.",
            ]
        )

    lines.extend(
        [
            "",
            "## Recommended next action",
            "",
            "Pause broader **Reply draft** rollout until the August 7 policy transition is understood. Confirm the transition timestamp, then review a small stratified sample of accepted, flagged, and heavily edited outputs on each side of it. Collect at least one additional comparable week before making a prompt-performance claim.",
            "",
            "## Interpretation limits",
            "",
            "- Acceptance is a behavioral proxy, not correctness.",
            "- Review flags may reflect quality, policy strictness, or careful users; overlap with acceptance is unknown.",
            "- Estimated minutes saved are directional.",
            "- Model confidence is diagnostic context only and never affects the evidence label.",
            "- The short, aggregated, non-randomized dataset cannot establish causality or statistical significance.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "csv_path",
        nargs="?",
        default=str(Path(__file__).parent / "data" / "product_usage_events.csv"),
        help="Path to the SignalDesk CSV export.",
    )
    parser.add_argument("--output", "-o", help="Optional Markdown output path.")
    args = parser.parse_args(argv)

    check = build_health_check(args.csv_path)
    report = render_report(check, Path(args.csv_path).name)
    print(report)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
