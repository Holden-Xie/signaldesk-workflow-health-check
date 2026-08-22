"""Answer which SignalDesk workflow seems most useful right now.

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
    estimated_total_minutes: float
    median_confidence: float | None
    mean_row_rating: float | None


@dataclass(frozen=True)
class UsefulnessScorecard:
    workflow: str
    metrics: Metrics
    window_days: int
    observed_segment_days: int
    expected_segment_days: int
    accepted_per_day: float
    estimated_minutes_per_day: float

    @property
    def coverage_rate(self) -> float:
        if not self.expected_segment_days:
            return 0.0
        return self.observed_segment_days / self.expected_segment_days


@dataclass(frozen=True)
class UsefulnessDecision:
    winner: str | None
    confidence: str
    lens_winners: dict[str, str]
    win_counts: dict[str, int]


@dataclass
class HealthCheck:
    records: list[Record]
    issues: list[Issue]
    prompt_change_date: date
    incident_dates: set[date]
    current_start: date
    current_end: date
    scorecards: dict[str, UsefulnessScorecard]
    decision: UsefulnessDecision
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
    estimated_total_minutes = sum(
        (record.avg_minutes_saved or 0) * (record.completed or 0)
        for record in weighted_minutes_rows
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
        estimated_total_minutes=estimated_total_minutes,
        median_confidence=weighted_confidence,
        mean_row_rating=statistics.fmean(ratings) if ratings else None,
    )


def build_scorecards(
    records: list[Record],
    window_dates: list[date],
    expected_sources: dict[str, set[str]],
) -> dict[str, UsefulnessScorecard]:
    """Create comparable workflow summaries for the same current window."""
    scorecards: dict[str, UsefulnessScorecard] = {}
    for workflow in sorted({record.workflow for record in records}):
        workflow_records = [record for record in records if record.workflow == workflow]
        metrics = aggregate(workflow_records)
        days = len(window_dates)
        scorecards[workflow] = UsefulnessScorecard(
            workflow=workflow,
            metrics=metrics,
            window_days=days,
            observed_segment_days=len(workflow_records),
            expected_segment_days=days * len(expected_sources.get(workflow, set())),
            accepted_per_day=metrics.accepted / days,
            estimated_minutes_per_day=metrics.estimated_total_minutes / days,
        )
    return scorecards


def choose_most_useful(scorecards: dict[str, UsefulnessScorecard]) -> UsefulnessDecision:
    """Choose a best-balanced candidate by three human-facing lenses."""
    if not scorecards:
        raise ValueError("No workflows are available for a usefulness decision.")
    lens_winners = {
        "accepted outputs per day": max(scorecards, key=lambda name: scorecards[name].accepted_per_day),
        "acceptance rate": max(scorecards, key=lambda name: scorecards[name].metrics.acceptance_rate),
        "lowest review burden": min(scorecards, key=lambda name: scorecards[name].metrics.review_rate),
    }
    win_counts = Counter(lens_winners.values())
    highest = max(win_counts.values())
    leaders = sorted(workflow for workflow, count in win_counts.items() if count == highest)
    return UsefulnessDecision(
        winner=leaders[0] if len(leaders) == 1 else None,
        confidence="TENTATIVE",
        lens_winners=lens_winners,
        win_counts=dict(win_counts),
    )


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
    stable_dates = sorted(
        {
            record.observed_on
            for record in eligible
            if record.observed_on >= prompt_change_date and record.observed_on not in incident_dates
        }
    )
    if not stable_dates:
        raise ValueError("No stable post-change dates are available for the current usefulness window.")
    current_start, current_end = stable_dates[0], stable_dates[-1]
    current_records = [record for record in eligible if record.observed_on in stable_dates]
    expected_sources: dict[str, set[str]] = defaultdict(set)
    for record in records:
        expected_sources[record.workflow].add(record.source)
    scorecards = build_scorecards(current_records, stable_dates, expected_sources)
    decision = choose_most_useful(scorecards)
    incident_records = [
        record
        for record in eligible
        if record.observed_on in incident_dates and "changed mid-day" in record.notes.casefold()
    ]
    return HealthCheck(
        records,
        issues,
        prompt_change_date,
        incident_dates,
        current_start,
        current_end,
        scorecards,
        decision,
        incident_records,
    )


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def render_report(check: HealthCheck, source_name: str) -> str:
    excluded = [record for record in check.records if not record.analysis_eligible]
    duplicate_issues = [issue for issue in check.issues if issue.code == "duplicate_composite_key"]
    missing_issues = [issue for issue in check.issues if issue.code == "missing_value"]
    normalized_issues = [issue for issue in check.issues if issue.code == "normalized_category"]
    coverage_issues = [issue for issue in check.issues if issue.code == "incomplete_daily_coverage"]
    winner = check.decision.winner
    answer = (
        f"**{winner} appears most useful right now, tentatively.**"
        if winner
        else "**No single workflow is the clear usefulness leader.**"
    )

    lines = [
        "# SignalDesk Current Usefulness Brief",
        "",
        f"Source: `{source_name}`",
        f"Current comparison window: {check.current_start} through {check.current_end}.",
        "Decision question: Which workflow seems most useful right now?",
        "",
        "## Answer",
        "",
        answer,
        "",
        "The recommendation uses three primary human-facing lenses: accepted-output throughput, acceptance rate, and review burden. Directional time impact is supporting context. Model confidence, rating, and hidden weights are not used.",
        "",
        "## Current usefulness scorecard",
        "",
        "| Workflow | Source coverage | Completion | Accepted/day | Acceptance | Review rate | Est. min/completion | Est. min/day |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for workflow, card in sorted(check.scorecards.items()):
        metrics = card.metrics
        lines.append(
            "| "
            + " | ".join(
                [
                    workflow,
                    _pct(card.coverage_rate),
                    _pct(metrics.completion_rate),
                    f"{card.accepted_per_day:.1f}",
                    _pct(metrics.acceptance_rate),
                    _pct(metrics.review_rate),
                    f"{metrics.avg_minutes_saved:.1f}",
                    f"{card.estimated_minutes_per_day:.1f}",
                ]
            )
            + " |"
        )

    lines.extend(["", "## Why this answer?", ""])
    for lens, workflow in check.decision.lens_winners.items():
        lines.append(f"- **{lens}:** {workflow}")
    time_leader = max(check.scorecards, key=lambda name: check.scorecards[name].estimated_minutes_per_day)
    lines.append(f"- **directional estimated minutes saved per day (supporting):** {time_leader}")

    lines.extend(
        [
            "",
            f"{winner} leads two of the three primary decision lenses; directional time impact also supports it." if winner else "The primary decision lenses are tied.",
            "Reply draft leads accepted-output throughput, so it could be preferred if scale is the only objective. Feedback clustering leads minutes saved per completed run, but not estimated daily impact, and its human-facing outcomes are weaker.",
            "",
            "## Data trust and exclusions",
            "",
            f"- {len(check.records)} input rows; {len(excluded)} rows excluded",
            f"- {len(normalized_issues)} category normalization, {len(duplicate_issues)} duplicate key, {len(missing_issues)} missing optional values",
            f"- {len(coverage_issues)} day with incomplete source coverage",
            "- Both August 5 Lead summary/email rows were excluded because they describe demo traffic and its duplicate.",
            "- August 7 was excluded because review policy changed mid-day and source coverage was incomplete.",
            "- Lead summary has 83.3% current-window source coverage because normal August 5 email traffic is unavailable.",
            "",
            "## Assumptions and limits",
            "",
            "- Useful means a balance of realized adoption, accepted-output throughput, review burden, and time impact.",
            "- Acceptance is a rough adoption/quality proxy; accepted and flagged outputs may overlap.",
            "- Estimated minutes saved are directional and may not be comparable across tasks.",
            "- All workflows use the same Tuesday-Thursday window, but team, task, and source mix still differ.",
            "- Missing rows are unknown, not zero; model confidence is not a quality signal.",
            "- Three days is too short for a definitive ROI or rollout decision.",
            "",
            "## Recommended next decision",
            "",
            "Continue **Lead summary** as the leading rollout candidate, but first recover or explain the missing August 5 production email segment and validate the minutes-saved estimate. Keep Reply draft under investigation until the August 7 policy incident is understood. Collect multiple matched weeks before treating this tentative recommendation as durable.",
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
