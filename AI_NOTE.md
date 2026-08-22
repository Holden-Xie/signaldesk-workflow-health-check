# AI Collaboration Note

## Did You Use AI?

Yes. I used Codex extensively for repository research, data inspection, implementation, test design, and documentation.

## How You Used It

AI helped inspect every challenge file and the full dataset, identify data-quality traps, calculate candidate metrics, write the CLI, and propose edge-case tests. I iteratively redirected it as the decision question became clearer.

## One Helpful Workflow

The first analysis was too broad. I narrowed it to “Which workflow seems most useful right now?”, challenged whether the result was actually conclusive, and raised day-of-week as a possible confounder. AI then rebuilt the analysis around a shared Tuesday–Thursday window and exposed each decision lens instead of hiding the judgment in a composite score.

## What I Verified Or Decided Myself

I decided that the answer should be tentative, that throughput alone could favor Reply draft, and that confidence and rating should not drive the recommendation. I required assumptions and limitations to be explicit. Important totals, denominators, exclusions, coverage, lens winners, and incident-day separation were independently reconciled and encoded in tests rather than accepted from a single AI calculation.
