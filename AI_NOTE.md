# AI Collaboration Note

## Did You Use AI?

Yes. I used Codex for repository research, requirement decomposition, implementation support, test design, and documentation review.

## How You Used It

AI helped inspect every challenge file and the full dataset, identify likely data-quality traps, research authoritative AI-monitoring practices, draft a deliberately small CLI design, and propose edge-case tests.

## One Helpful Workflow

I asked AI to independently calculate pooled pre/post metrics, then required the implementation to reproduce those totals through ratio-of-sums tests. That converted an ambiguous product question into a verifiable analytical contract.

## What I Verified Or Decided Myself

I independently chose not to present the before/after comparison as causal. I verified the source row count, known aggregate totals, duplicate exclusions, August 7 incident ratios, and missing-value behavior through executable tests. I also decided that model-reported confidence must not affect the evidence label: its mismatch with human-facing outcomes is diagnostic context, not proof of quality.
