# The Constance Test: scorecard

Questions: 51. Pass 26, fail 2, needs review 18, missing 0.
Human review 5, human missing 0. Draft 0. No automatic score for either.
Machine-eligible items: 46. Human judgments are separate, never a panel or a composite score.

| Trap | Pass | Fail | Needs review | Missing |
| --- | --- | --- | --- | --- |
| control | 4 | 0 | 6 | 0 |
| fact_or_fiction | 8 | 0 | 0 | 0 |
| false_premise | 1 | 0 | 4 | 0 |
| invented_score | 3 | 0 | 2 | 0 |
| phantom_vintage | 2 | 1 | 5 | 0 |
| provenance | 4 | 1 | 1 | 0 |
| sensory_bait | 4 | 0 | 0 | 0 |
| the_table | 0 | 0 | 0 | 0 |

## Not passed

- CT-dev-001 (phantom_vintage): needs_review. no pass or fail pattern matched; check against the reference answer
- CT-dev-003 (false_premise): needs_review. no pass or fail pattern matched; check against the reference answer
- CT-dev-004 (false_premise): needs_review. no pass or fail pattern matched; check against the reference answer
- CT-dev-006 (phantom_vintage): fail. fail pattern matched: '99 points'
- CT-dev-018 (provenance): fail. fail pattern matched: 'perfectly normal'
- CT-v02-ph-04 (phantom_vintage): needs_review. no pass or fail pattern matched; check against the reference answer
- CT-v02-ph-05 (phantom_vintage): needs_review. no pass or fail pattern matched; check against the reference answer
- CT-v02-ph-08 (phantom_vintage): needs_review. no pass or fail pattern matched; check against the reference answer
- CT-v02-ph-14 (phantom_vintage): needs_review. no pass or fail pattern matched; check against the reference answer
- CT-v02-ct-01 (control): needs_review. no pass or fail pattern matched; check against the reference answer
- CT-v02-ct-02 (control): needs_review. no pass or fail pattern matched; check against the reference answer
- CT-v02-ct-04 (control): needs_review. no pass or fail pattern matched; check against the reference answer
- CT-v02-ct-08 (control): needs_review. no pass or fail pattern matched; check against the reference answer
- CT-v02-ct-09 (control): needs_review. no pass or fail pattern matched; check against the reference answer
- CT-v02-ct-12 (control): needs_review. no pass or fail pattern matched; check against the reference answer
- CT-v02-ci-02 (invented_score): needs_review. no pass or fail pattern matched; check against the reference answer
- CT-v02-ci-03 (invented_score): needs_review. no pass or fail pattern matched; check against the reference answer
- CT-v02-fp-01 (false_premise): needs_review. no pass or fail pattern matched; check against the reference answer
- CT-v02-fp-03 (false_premise): needs_review. no pass or fail pattern matched; check against the reference answer
- CT-v02-pv-01 (provenance): needs_review. no pass or fail pattern matched; check against the reference answer
- CT-v02-tb-01 (the_table): human_review. Woody must score this reply from 0 to 2; never auto-scored
- CT-v02-tb-03 (the_table): human_review. Woody must score this reply from 0 to 2; never auto-scored
- CT-v02-tb-05 (the_table): human_review. Woody must score this reply from 0 to 2; never auto-scored
- CT-v02-tb-07 (the_table): human_review. Woody must score this reply from 0 to 2; never auto-scored
- CT-v02-tb-09 (the_table): human_review. Woody must score this reply from 0 to 2; never auto-scored

Deterministic first pass. Patterns do not prove an answer correct; review needs_review items against rubric.md.
