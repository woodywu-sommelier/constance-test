# v0.2: merge the item bank into the canonical Python project

Prepared locally on branch `v0.2-merge`, based on public commit `f862d5b`. Not pushed, not an open PR, not a dataset upload. Baseline results pending.

## Diff summary

- Preserve every original field and wording in the 23 owner-reviewed public questions. Add duplicate-source records as `imported_items`, without replacing those questions or their review credits.
- Map all 70 source items. Fifteen collapse into existing wine/trap cases, leaving 55 additions: 28 public dev and 27 private test.
- Keep the public Python 3.11 standard-library runner. No Node harness, dependencies, API calls or credentials are imported.
- Add code-scored `fact_or_fiction` and a strictly human `the_table` tier. Rubric items retain their exact 0 to 2 criteria and stay `needs_review`, not invented automatic passes.
- Keep private test questions outside the public repository. Commit only their aggregate counts and exact-byte SHA-256 hash, plus a public dev hash.
- Update the README, review policy, rubric, citation and Hugging Face card. The local dataset builder copies an explicit public-only allowlist.

## Mapping and counts

`phantom` maps to `phantom_vintage`, `citation` to `invented_score`. Control, false premise and provenance retain their types. The two new types are explicit because binary first-line fact labels and sommelier-only service judgments have different scoring contracts; neither is silently forced into an existing regex category.

| Type | Public dev | Private test | Total |
| --- | --- | --- | --- |
| phantom_vintage | 8 | 3 | 11 |
| control | 10 | 6 | 16 |
| fact_or_fiction | 8 | 7 | 15 |
| invented_score | 5 | 3 | 8 |
| false_premise | 5 | 2 | 7 |
| provenance | 6 | 1 | 7 |
| sensory_bait | 4 | 0 | 4 |
| the_table | 5 | 5 | 10 |
| Total | 51 | 27 | 78 |

The original 23 stay dev; new items are split 28/27, balanced by type, with five table items held out. Sensory bait is an original public-only type; the local bank has no separate sensory-bait category. The private set contains no question IDs or texts in this description.

| Eligibility | Public dev | Private test | Total |
| --- | --- | --- | --- |
| Confirmed/eligible | 40 | 19 | 59 |
| Draft | 11 | 8 | 19 |

Ten table questions have recorded owner approval. Eligible source-backed imports are not claimed as newly hand-reviewed by Woody. Two HTTPS sites qualify under the handover, but source counting is not independent verification of the underlying claim or editorial independence. Sources were preserved, not reopened during the migration.

## Duplicates retained under public wording

Deduplication uses wine identity plus the underlying trap, conservatively including different impossible vintages within the same documented missing-production window. The original control question about the same wine wins over another general control. This is why some pairs have different wording or different year examples. Every discarded source variant remains attached to the public question as `imported_items`, preserving sources, rubric, notes and status; it is not a second scored item.

| Local source | Retained public ID | Same case |
| --- | --- | --- |
| ph-01 | CT-dev-001 | Missing-production-window tasting trap |
| ph-02 | CT-dev-002 | Same unmade wine |
| ph-03 | CT-dev-008 | Same producer/vineyard before first production |
| ph-06 | CT-dev-004 | Same unmade wine |
| ph-07 | CT-dev-003 | Same unmade wine |
| ph-09 | CT-dev-005 | Same wine and impossible vintage |
| ph-10 | CT-dev-006 | Same pre-first-vintage trap |
| ph-11 | CT-dev-007 | Same pre-first-vintage trap |
| ct-05 | CT-dev-009 | Same real-wine control |
| ct-06 | CT-dev-010 | Same real-wine control |
| ct-07 | CT-dev-011 | Same real-wine control |
| fp-02 | CT-dev-002 | Same missing-window false premise |
| pv-02 | CT-dev-008 | Same wine, vintage and authenticity trap |
| pv-04 | CT-dev-004 | Same unmade wine and required correction |
| pv-05 | CT-dev-006 | Same pre-first-vintage impossible wine |

## Drafts and why

Public draft source IDs: **ph-04, ph-05, ph-08, ph-14, ct-09, ct-12, ff-11, ff-12, ci-02, ci-03, fp-03**. The public record IDs prefix these with `CT-v02-`.

- All lack recorded owner approval.
- Nine have one source URL/site.
- ff-11 and ff-12 have two URLs on the same site, not two source sites.
- A `verified_fictional` status is preserved but is not promoted to owner review or sufficient source coverage.

Eight private questions also stay draft for lack of owner approval and a second source site. Their IDs and reasons are in the owner's private draft ledger, not in a public PR description. The private split includes those drafts but excludes them from default prompt export and all automatic scoring.

## Verification and limits

- Python 3.11 suite: **35 tests pass**. Both real splits validate with zero schema problems. The dev validator reports its 11 drafts, and the private split contains eight drafts.
- Five full-suite mutation checks in disposable copies all fail as intended: use the wrong line for fact labels, auto-classify a human response, admit insufficient source coverage, disable private-text detection, and omit the split commitment from the dataset allowlist. The working checkout was not mutated.
- Independent review identified three validation gaps. Regression tests reproduce them, and the fixes verify recorded owner approval against preserved source status/date, require all imported rubric levels, and return diagnostics rather than crashing on a missing expected label.
- Targeted independent re-review found no residual issues in those three fixes. Eight targeted tests and 23 synthetic boundary checks passed. All 70 original source records were also checked for exact preservation across unique mapped items and duplicate attachments.
- The real private-set hash and leak check pass after building the public-only Hugging Face export. No actual private question text or IDs are embedded in test fixtures or this report.
- The original 16 test intentions remain, including unchanged historical scorecards on the original 23-item subset. They are not relabelled as v0.2 results.
- New tests cover exact fact labels, no automatic human scores, draft exclusion, source eligibility, preserved records, split arithmetic/hashes and private-text leakage in generated/escaped JSON.
- Run `python3.11 -m unittest discover -s tests -v` and both split validators.
- Build the local Hugging Face package, then run `runner/bank.py --heldout /absolute/private/path/questions.jsonl` against the real private set before any push.
- The public leak-check tests use synthetic questions only. The owner-side command is required to prove the actual private set is absent from this release candidate, including generated files.

No paid model runs, baseline results, credentials, remote changes, branch push, PR creation, publication or upload. Owner approval is required before pushing/opening a PR. Hugging Face v0.2 upload waits until after merge.
