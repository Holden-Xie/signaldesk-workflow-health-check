# SignalDesk Weekly Workflow Health Check

Source: `product_usage_events.csv`  
Prompt-change comparison: baseline before 2026-08-04 vs. post-change through the day before a mixed-policy incident.  
This is descriptive monitoring, not a causal experiment.

## Can we trust this export?

- 41 input rows
- 1 inconsistent categorical value normalized
- 1 duplicate composite key detected
- 2 optional metric values missing; neither was imputed
- 1 day with source coverage different from the modal pattern
- 2 nonproduction/invalid rows excluded from comparisons

- **missing_value**: Row 5: user_rating is missing.
- **normalized_category**: Row 13: normalized team 'product' to 'Product'.
- **missing_value**: Row 32: median_confidence is missing.
- **duplicate_composite_key**: Rows (26, 27) share composite key (datetime.date(2026, 8, 5), 'Sales', 'Lead summary', 'email').
- **excluded_nonproduction**: Rows (26, 27) excluded: non-production demo traffic and duplicate export.
- **incomplete_daily_coverage**: 2026-08-07: source coverage differs from the modal daily pattern; missing [('Sales', 'Lead summary', 'manual'), ('Support', 'Reply draft', 'manual')].

## What happened?

Rates are ratios of summed counts. Deltas are percentage points.

| Workflow | Completed (base/post) | Completion delta | Acceptance delta | Review delta | Evidence |
|---|---:|---:|---:|---:|---|
| Feedback clustering | 45/67 | -3.3 pp | -1.0 pp | -2.1 pp | LOW SAMPLE |
| Lead summary | 154/147 | -0.8 pp | +1.0 pp | -1.5 pp | INCONCLUSIVE |
| Reply draft | 181/213 | -3.1 pp | +0.2 pp | +2.2 pp | INCONCLUSIVE |

## What looks suspicious?

### NEEDS INVESTIGATION - Reply draft / queue / 2026-08-07

- Completion: 56.7%
- Acceptance among completed: 47.1%
- Review flags per completed: 70.6%
- Estimated minutes saved per completed session: 1.5
- User rating: 2.1
- Model-reported confidence: 0.91
- Context: review policy changed mid-day

Human-facing signals deteriorated while model confidence remained high. The policy changed mid-day, so this is an investigation trigger, not proof of a model or prompt regression.

## Recommended next action

Pause broader **Reply draft** rollout until the August 7 policy transition is understood. Confirm the transition timestamp, then review a small stratified sample of accepted, flagged, and heavily edited outputs on each side of it. Collect at least one additional comparable week before making a prompt-performance claim.

## Interpretation limits

- Acceptance is a behavioral proxy, not correctness.
- Review flags may reflect quality, policy strictness, or careful users; overlap with acceptance is unknown.
- Estimated minutes saved are directional.
- Model confidence is diagnostic context only and never affects the evidence label.
- The short, aggregated, non-randomized dataset cannot establish causality or statistical significance.
