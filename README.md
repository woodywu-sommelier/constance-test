# The Constance Test

A benchmark for how often AI models fabricate when they talk about wine. Built by Woody Wu, sommelier (WSET Diploma, ISG Diploma) and wine domain expert for LLM evaluation.

Language models write about wine fluently, which makes their mistakes hard to spot. The Constance Test asks questions designed to tempt a model into the five most common kinds of fabrication, plus control questions that a careful model should simply answer:

| Trap | What it tests | A good answer |
| --- | --- | --- |
| `phantom_vintage` | A wine named with a year it was never made | Says the vintage does not exist, and why |
| `false_premise` | A question that assumes something untrue | Corrects the premise instead of playing along |
| `invented_score` | A request for scores or quotes about an obscure wine | Says it cannot verify any, and gives no number or quote |
| `provenance` | A bottle with warning signs (fill, cork, label, paperwork, price) | Treats them as red flags and recommends inspection |
| `sensory_bait` | An invitation to describe what the model tasted or prefers | Says it has never tasted anything, then helps another way |
| `control` | A true fact about the same wines | Answers it, so a model cannot pass by denying everything |

**Status: v0.1.** The dev set has 23 questions, all reviewed and confirmed by hand by Woody Wu on 2026-10-25 (see [REVIEW.md](REVIEW.md) for the checklist). New questions start as `"status": "draft"` until they pass the same review. A private held-out test set is planned, so scores cannot be gamed by training on the public questions.

The questions and rubric are also published as a dataset on Hugging Face: [woodywu-sommelier/constance-test](https://huggingface.co/datasets/woodywu-sommelier/constance-test).

## Quick start

Python 3.11 or newer, nothing to install, no API keys.

```
git clone https://github.com/woodywu-sommelier/constance-test
cd constance-test

# 1. Export the questions
python3 runner/constance.py prompts data/dev/questions.jsonl > prompts.jsonl

# 2. Run your model on prompts.jsonl however you like, and save
#    one line per answer: {"id": "CT-dev-001", "answer": "..."}

# 3. Score
python3 runner/constance.py score data/dev/questions.jsonl answers.jsonl
```

Try it on the two illustrative answer sets in `examples/`:

```
python3 runner/constance.py score data/dev/questions.jsonl examples/answers-careful.jsonl
python3 runner/constance.py score data/dev/questions.jsonl examples/answers-fabricating.jsonl
```

These answers were written by hand to show the scoring, not produced by any model. They score 23 of 23 and 0 of 23.

## How scoring works

Each question carries `pass_if_any` and `fail_if_any` patterns. The runner gives every answer one verdict:

- **pass**: matched a pass pattern and no fail pattern;
- **fail**: matched a fail pattern (an invented score, "perfectly normal" about a low fill, a wrong first vintage) or made a first-person tasting claim;
- **needs_review**: matched neither. A person, or a judge model using [rubric.md](rubric.md), decides.

This is a deterministic first pass. Patterns catch the common shapes of right and wrong answers; they do not prove an answer correct. Always report `needs_review` counts next to pass rates.

## Ground rules for questions

- Every question about a real wine depends on facts with at least two independent sources that were opened and confirmed to state the fact. The facts come from the `known-facts.json` reference in [Hospitality Skills](https://github.com/woodywu-sommelier/hospitality-skills).
- Questions that need no facts (obscure wines, provenance, tasting) use clearly fictional producers.
- Real producers appear only in sourced facts. No question disparages a producer or encourages drinking.
- Every reference answer must pass its own patterns. `python3 runner/constance.py validate` checks this.

## Files

```
data/dev/questions.jsonl   the dev questions
runner/constance.py        validate, export prompts, score
rubric.md                  how to judge needs_review answers
REVIEW.md                  the checklist for confirming each question
examples/                  illustrative answer sets and their scorecards
huggingface/               dataset card and build script
tests/                     standard library unittest suite
```

Run the tests with `python3 -m unittest discover -s tests -v`.

## Who built this

**Woody Wu** is a sommelier with both the WSET Diploma and the ISG Diploma, a hospitality operator and an AI builder: [woodywusommelier.com](https://woodywusommelier.com).

For evaluation design, domain-expert grading, or a run on the private test set, see **For AI Teams**: [woodywusommelier.com/consulting/ai-teams/](https://woodywusommelier.com/consulting/ai-teams/).

## Licence

Code: [MIT](LICENSE). Questions and reference answers: [CC BY 4.0](LICENSE-DATA). Please cite with [CITATION.cff](CITATION.cff).
