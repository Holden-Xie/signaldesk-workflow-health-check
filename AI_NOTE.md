# AI Collaboration Note

## Did You Use AI?

Yes. I used Codex for repository research, data inspection, implementation, test design, and documentation.

## How You Used It

AI helped inspect the challenge files and dataset, identify data-quality traps, calculate candidate metrics, write the CLI, and propose edge-case tests. I reviewed and redirected the work as the decision question became clearer.

## One Helpful Workflow

The first analysis was too broad. I narrowed it to “Which workflow seems most useful right now?”, challenged whether the result was actually conclusive, and raised day-of-week as a possible confounder. AI then rebuilt the analysis around a shared Tuesday–Thursday window and exposed each decision lens instead of hiding the judgment in a composite score.

## What I Verified Or Decided Myself

I decided that the answer should be tentative, that throughput alone could favor Reply draft, and that confidence and rating should not drive the recommendation. I chose the scope: answer the current-usefulness question with transparent metric lenses rather than a hidden composite score. I verified important totals, denominators, exclusions, coverage, lens winners, and incident-day separation independently and encoded them in tests.

I also identified weekday as a possible confounder. The implementation aligns workflows on the shared Tuesday-Thursday window, but I did not claim that this removes weekday effects because three days cannot estimate them. I decided that the report must state this limitation, along with task mix, source mix, team/user mix, missing coverage, aggregation, and policy-change confounding. A stronger follow-up would collect multiple matched weeks with those fields and test whether the ranking is stable by weekday and workflow context.
