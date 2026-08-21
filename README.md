# SignalDesk Workflow Health Check

## Track Chosen

Track A — Fictional Domain Packet.

## What I Built

A standard-library Python CLI that turns SignalDesk's messy workflow export into a compact weekly health brief. It validates the schema, records normalization and exclusions, compares human-facing outcomes before and after the August 4 prompt change, and isolates the mixed-policy August 7 incident. The report supports investigation; it does not claim the prompt caused observed changes.

## Who It Is For

A SignalDesk product manager or analyst deciding what to investigate before broader rollout.

## Data Or Source Used

The challenge's fictional `product_usage_events.csv` (41 daily aggregate rows, August 1–7, 2026). The included copy is unchanged.

## Run It

Requires Python 3.10+ and no third-party packages.

```bash
python signaldesk_health.py --output REPORT.md
python -m unittest discover -s tests -v
```

## Assumptions And Issues

Rates use ratios of summed counts. Acceptance and review rates use completed outputs as the denominator. Missing values are not imputed; missing rows are not zeros. Team casing is normalized for analysis. Both duplicate-key August 5 Lead summary/email records are excluded because the notes identify demo traffic plus a duplicate. August 7 is separated because coverage is incomplete and review policy changed mid-day. Confidence and estimated time saved are not treated as quality ground truth.

## Next

Confirm the policy-change timestamp and audit accepted, flagged, and heavily edited Reply draft outputs on each side of it. Add prompt/policy versions, timestamps, feedback definitions, and another comparable week before making a rollout decision.

