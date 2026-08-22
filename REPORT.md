# SignalDesk Current Usefulness Brief

Source: `product_usage_events.csv`
Current comparison window: 2026-08-04 through 2026-08-06.
Decision question: Which workflow seems most useful right now?

## Answer

**Lead summary appears most useful right now, tentatively.**

The recommendation uses three primary human-facing lenses: accepted-output throughput, acceptance rate, and review burden. Directional time impact is supporting context. Model confidence, rating, and hidden weights are not used.

## Current usefulness scorecard

| Workflow | Source coverage | Completion | Accepted/day | Acceptance | Review rate | Est. min/completion | Est. min/day |
|---|---:|---:|---:|---:|---:|---:|---:|
| Feedback clustering | 100.0% | 67.0% | 14.7 | 65.7% | 17.9% | 13.1 | 291.5 |
| Lead summary | 83.3% | 77.0% | 38.3 | 78.2% | 8.8% | 7.9 | 389.2 |
| Reply draft | 100.0% | 80.7% | 54.7 | 77.0% | 15.5% | 4.0 | 283.7 |

## Why this answer?

- **accepted outputs per day:** Reply draft
- **acceptance rate:** Lead summary
- **lowest review burden:** Lead summary
- **directional estimated minutes saved per day (supporting):** Lead summary

Lead summary leads two of the three primary decision lenses; directional time impact also supports it.
Reply draft leads accepted-output throughput, so it could be preferred if scale is the only objective. Feedback clustering leads minutes saved per completed run, but not estimated daily impact, and its human-facing outcomes are weaker.

## Data trust and exclusions

- 41 input rows; 2 rows excluded
- 1 category normalization, 1 duplicate key, 2 missing optional values
- 1 day with incomplete source coverage
- Both August 5 Lead summary/email rows were excluded because they describe demo traffic and its duplicate.
- August 7 was excluded because review policy changed mid-day and source coverage was incomplete.
- Lead summary has 83.3% current-window source coverage because normal August 5 email traffic is unavailable.

## Assumptions and limits

- Useful means a balance of realized adoption, accepted-output throughput, review burden, and time impact.
- Acceptance is a rough adoption/quality proxy; accepted and flagged outputs may overlap.
- Estimated minutes saved are directional and may not be comparable across tasks.
- All workflows use the same Tuesday-Thursday window, but team, task, and source mix still differ.
- Missing rows are unknown, not zero; model confidence is not a quality signal.
- Three days is too short for a definitive ROI or rollout decision.

## Recommended next decision

Continue **Lead summary** as the leading rollout candidate, but first recover or explain the missing August 5 production email segment and validate the minutes-saved estimate. Keep Reply draft under investigation until the August 7 policy incident is understood. Collect multiple matched weeks before treating this tentative recommendation as durable.
