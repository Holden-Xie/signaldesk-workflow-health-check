# SignalDesk Current Usefulness Brief

## Track Chosen

Track A — Fictional Domain Packet.

## What I Built

A standard-library Python CLI focused on one decision: **Which workflow seems most useful right now?** It validates the messy export, selects the stable August 4–6 window, and compares accepted outputs per day, acceptance rate, and review burden. Directional minutes saved is supporting context; no opaque score is used.

## Decision

**Lead summary is the tentative best-balanced candidate.** It leads acceptance and review burden; Reply draft leads throughput and would be the choice if scale were the only objective. This is a prioritization signal, not a causal ROI claim.

## Who It Is For

A SignalDesk product manager choosing which workflow to prioritize for continued rollout.

## Data Or Source Used

The challenge's fictional [`product_usage_events.csv`](https://github.com/vyuan2037/ds-intern-challenge/blob/main/sample-data/product_usage_events.csv) (41 daily aggregate rows, August 1–7, 2026). The included copy is unchanged.

## Run It

Requires Python 3.10+ and no third-party packages.

```bash
python signaldesk_health.py --output REPORT.md
python -m unittest discover -s tests -v
```

## Assumptions And Issues

"Useful" means a balance of adoption, throughput, review burden, and time impact. Rates use ratios of summed counts. Missing values are not imputed and missing rows are not zeros. Both August 5 Lead summary/email records are excluded as demo traffic plus its duplicate. August 7 is excluded because policy changed mid-day. Lead summary therefore has 83.3% source coverage. Confidence and rating do not affect the recommendation; minutes saved are directional. Cross-workflow task differences and the three-day window make the answer tentative.

## Next

Recover the missing Lead summary segment, validate minutes saved, investigate the Reply draft policy incident, and collect multiple matched weeks with explicit prompt/policy versions before making a durable rollout decision.
