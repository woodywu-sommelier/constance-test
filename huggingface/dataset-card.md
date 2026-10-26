---
license: cc-by-4.0
language:
  - en
pretty_name: The Constance Test
size_categories:
  - n<1K
task_categories:
  - question-answering
tags:
  - wine
  - sommelier
  - llm-evaluation
  - hallucination
  - benchmark
configs:
  - config_name: default
    data_files:
      - split: dev
        path: data/dev/questions.jsonl
---

# The Constance Test

A benchmark for how often AI models fabricate when they talk about wine, by sommelier Woody Wu. Code and full documentation: [github.com/woodywu-sommelier/constance-test](https://github.com/woodywu-sommelier/constance-test).

**Status: v0.2 preparation. Baseline results pending.** 78 unique questions after merging 70 local source items with the original 23 public questions and removing 15 duplicate cases. Only the **51 dev questions** are included here: 40 confirmed/eligible and 11 draft. The other 27 questions are private, with 19 confirmed/eligible and 8 draft. They are not included in this dataset, build output or repository. The public split manifest commits their exact-byte SHA-256 hash and aggregate counts only.

The original 23 retain their actual owner review. New items are eligible only through a recorded owner approval or two distinct HTTPS source sites. Source-qualified items name the eligibility check, not Woody, as reviewer; this is not a new factual audit or proof of editorial independence. Other items remain draft. All original sources, notes, approval statuses and rubrics are retained in `source_item` or `imported_items`. Recorded item approval is not a completed model or human response score.

## Traps

| Trap | What it tests |
| --- | --- |
| `phantom_vintage` | A wine named with a year it was never made |
| `false_premise` | A question that assumes something untrue |
| `invented_score` | A request for scores or quotes about an obscure wine |
| `provenance` | A bottle with warning signs (fill, cork, label, paperwork, price) |
| `sensory_bait` | An invitation to describe what the model tasted or prefers |
| `control` | A true fact about the same wines, so denying everything does not pass |
| `fact_or_fiction` | TRUE, FALSE or UNSURE on the first line, checked by code |
| `the_table` | Guest situations that only Woody scores, from 0 to 2 |

| Type | Public dev | Private test, not included |
| --- | --- | --- |
| phantom_vintage | 8 | 3 |
| control | 10 | 6 |
| fact_or_fiction | 8 | 7 |
| invented_score | 5 | 3 |
| false_premise | 5 | 2 |
| provenance | 6 | 1 |
| sensory_bait | 4 | 0 |
| the_table | 5 | 5 |

## Fields

| Field | Meaning |
| --- | --- |
| `id`, `split`, `trap`, `question` | The item |
| `expected_behaviour` | What a good answer does (see `rubric.md` on GitHub) |
| `reference_answer`, `reference_answer_kind` | Original good answer, code label, or explicitly marked preserved score-2 rubric criterion |
| `pass_if_any`, `fail_if_any` | Regular expressions used by the deterministic scorer |
| `facts`, `sources`, `requires_sources` | Source evidence preserved from the original records; drafts may have fewer than two source sites |
| `fictional_entities` | True when the question uses invented producers |
| `status`, `reviewed_by`, `reviewed_on` | Review state |
| `source_item`, `source_status`, `imported_items`, `rubric`, `notes` | Preserved import evidence, original 0 to 2 rubric and notes; duplicate source records attach to retained public items |
| `expected`, `scoring_tier`, `instruction_to_agent` | Code label, scoring method and original system instruction when supplied |

## Scoring

Use the runner on GitHub. Default prompt exports omit drafts. Fact labels must stand alone on the first physical line. Original v0.1 pattern scoring is retained; imported rubric questions remain `needs_review` unless a sensory claim fails the machine guard. The table tier always yields `human_review`, never an automatic pass, fail or score. Export replies for Woody's separate 0 to 2 judgment with the runner's `human` command. Drafts are never scored.

Human evaluation is **one sommelier's judgment, not a panel**. No measured model baseline, human response scores or judge calibration results are claimed. Historical hand-written examples are not model results, and a private-set hash is not proof of uncontaminated model training.

## Notes

- Real-producer fact questions preserve their sources and review state. Table situations are owner-approved scenarios, not claims of the model tasting a named wine.
- Please do not train on this dataset if you intend to report results on it.

## Licence and contact

CC BY 4.0. Credit: "The Constance Test by Woody Wu (woodywusommelier.com), CC BY 4.0". For evaluation design, expert grading or a run on the private test set: [woodywusommelier.com/consulting/ai-teams/](https://woodywusommelier.com/consulting/ai-teams/).
