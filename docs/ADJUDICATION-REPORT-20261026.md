# Adjudication preparation report

2026-10-26. Branch: `results-v0.2`. Local only. No push, upload, model call or private-set access.

## Completion update, 2026-10-26

Woody filled all 44 decisions with `agree` and scored all ten table replies 1. Finalize now validates the table sheet against the frozen questions, rubrics and replies, accepts only integer scores from 0 to 2, and records the sheet hash plus each scored answer's hash. It reports per-model N, scores and mean separately from factual verdicts.

Regenerated `results/v0.2-baseline/adjudicated-v2/report.json` and `summary.md`: Sonnet has 33 pass, 6 partial, 7 fail; Haiku has 33 pass, 7 partial, 6 fail, each out of 46. Each has five table scores of 1, mean 1.0. Each factual total carries forward 24 unreviewed raw passes. The previous generated report is preserved under `adjudicated-v2-before-table-20261026/`.

The README draft now includes these results and their limitations. Verification: 62 tests pass; all three mutation checks fail their intended test (table mean, negation, owner gate). No new API cost, private-set access, commit or push. The original raw evidence and completed owner sheets are preserved.

## Preparation record, before owner review

The sections below record the earlier preparation state; the completion update above supersedes their pending status.

### Ready for Woody

- `results/v0.2-baseline/ADJUDICATION.md`: 44 proposed review rows, 22 per model. Every owner field is blank. Coverage is the exact union of raw fail, raw needs_review and every phantom_vintage response. Each excerpt is an exact substring of the saved answer, under 60 words. Top-level question rubrics are included.
- `results/the_table-for-woody.md`: all ten full answers, five per model. Each answer has its own rubric and a blank 0 to 2 score and note. No table answer is scored automatically.

In the adjudication sheet, enter `agree`, `pass`, `partial` or `fail` in the final cell on every row. An explicit correction can include a colon and reason. The proposals are not owner decisions. A recorded question approval from October 25 is not an approval of these model answers.

## Scorer proposal

`runner/constance.py` is unchanged. `runner/constance_v021.py` is a separate `0.2.1-proposal`, not a replacement for the published scorer. Its offline outputs live under `results/v0.2-baseline/rescored-v0.2.1/`.

| Record | Sonnet: pass / fail / needs review | Haiku: pass / fail / needs review |
| --- | --- | --- |
| Preserved raw v0.2 | 27 / 3 / 16 | 26 / 2 / 18 |
| Scorer v0.2.1 proposal | 29 / 2 / 15 | 27 / 3 / 16 |

Each row uses 46 machine-eligible questions per model. Five human-tier replies per model are separate. These are machine outputs, not adjudicated scores, and do not establish a winning model.

The proposal fixes the negated bargain false failure, distinguishes the real 1992 Screaming Eagle score from the nonexistent 1989, and catches both fabricated 2001 Dom Perignon descriptions. Additional tests stop negation leaking across sentence or contrast boundaries, stop an unrelated vintage rejection satisfying the phantom check, and preserve the human and draft exclusions. Pattern checks remain limited; a rejection followed by generic sensory notes still needs the rubric and Woody.

## Evidence and final report gate

`results/v0.2-baseline/evidence.json` records SHA-256 hashes for the original scorer, questions, original report, raw answer files and raw scorecards. All seven raw inputs match that snapshot. The original report and raw scorecards have not been overwritten.

After all 44 owner fields are filled:

```bash
cd /Users/kb/Documents/Codex/constance-baseline
../constance-baseline-venv/bin/python runner/adjudicate.py finalize
```

The command writes only a new `results/v0.2-baseline/adjudicated-v2/` folder:

- `report.json`, schema `constance-test-report/2`, preserves the entire raw report under `auto_scores` and separately records `adjudicated_scores` and individual owner decisions.
- `summary.md` labels raw passes carried forward without owner review, and excludes the table tier.
- `verified-failures.md` quotes up to five owner-confirmed failures exactly. It uses fewer than three if fewer are confirmed, rather than manufacturing examples. Owner confirmation is against the recorded references, not a claim of an exhaustive new external fact audit.

Blank, invalid, missing, duplicate or changed review rows are rejected. Changed raw inputs are rejected. Existing final folders are never overwritten. The current command exits 1 with `Woody decisions are incomplete; no adjudicated numbers written`. No final folder exists.

## Verification

- Full suite: 60 tests pass in the existing Python environment.
- Mutation 1 disables local negation in a disposable public-only copy. The real negated-bargain regression test fails as intended.
- Mutation 2 bypasses the blank-owner gate in a disposable public-only copy. The incomplete-decisions test fails as intended.
- The tests also exercise a complete simulated review only in temporary directories, including report schema, raw-record preservation, separate human tier, exact quotations and failure selection. No simulated owner decisions are written to the real sheet.
- No packages installed. No model API calls or additional model spend. No push or upload. Changes remain uncommitted on the requested branch.

## Credential warning

The initial existing test suite included `.env` in its file scan. Its failure output disclosed part of a credential. I changed the scanner to exclude credential files before reading them and to report secret matches without printing matched text. Subsequent verification does not read those files. Rotate the baseline Anthropic API key because the earlier failure output may remain in local logs. No credential is included in the adjudication artifacts.

The dash rule still applies to authored prose. Immutable provider answer files and quoted lines in the table export are narrowly exempt because changing their punctuation would corrupt evidence. Adjudication table excerpts encode punctuation as HTML entities where needed, preserving the displayed quote.
