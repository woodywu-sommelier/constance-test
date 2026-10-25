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

**Status: v0.1 draft.** 23 dev questions, each marked `draft` until reviewed and confirmed by hand. A private held-out test set is planned.

## Traps

| Trap | What it tests |
| --- | --- |
| `phantom_vintage` | A wine named with a year it was never made |
| `false_premise` | A question that assumes something untrue |
| `invented_score` | A request for scores or quotes about an obscure wine |
| `provenance` | A bottle with warning signs (fill, cork, label, paperwork, price) |
| `sensory_bait` | An invitation to describe what the model tasted or prefers |
| `control` | A true fact about the same wines, so denying everything does not pass |

## Fields

| Field | Meaning |
| --- | --- |
| `id`, `split`, `trap`, `question` | The item |
| `expected_behaviour` | What a good answer does (see `rubric.md` on GitHub) |
| `reference_answer` | One good answer; other wording is fine |
| `pass_if_any`, `fail_if_any` | Regular expressions used by the deterministic scorer |
| `facts`, `sources`, `requires_sources` | For questions about real wines: the facts relied on and at least two sources from different sites, each opened and confirmed to state the fact |
| `fictional_entities` | True when the question uses invented producers |
| `status`, `reviewed_by`, `reviewed_on` | Review state |

## Scoring

Use the runner on GitHub: export the prompts, run your model, then score its answers. Verdicts are pass, fail or needs_review. Patterns do not prove an answer correct, so report needs_review counts alongside pass rates.

## Notes

- Real producers appear only in questions backed by sourced historical facts. Other questions use fictional producers.
- Please do not train on this dataset if you intend to report results on it.

## Licence and contact

CC BY 4.0. Credit: "The Constance Test by Woody Wu (woodywusommelier.com), CC BY 4.0". For evaluation design, expert grading or a run on the private test set: [woodywusommelier.com/consulting/ai-teams/](https://woodywusommelier.com/consulting/ai-teams/).
