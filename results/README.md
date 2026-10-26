# Results

Model runs of The Constance Test. The benchmark and the scorer live in this repository; each run gets its own folder.

## Running a baseline

```
pip install anthropic openai google-genai
python3 results/runner/run_baseline.py dry-run        # plan, tokens and cost; no API calls
python3 results/runner/run_baseline.py check-models   # free: confirms each model id exists
python3 results/runner/run_baseline.py run            # paid; resumable; keeps partial results
python3 results/runner/run_baseline.py score          # re-score saved answers; no API calls
```

API keys come only from the environment (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`). Network access needed: `api.anthropic.com`, `api.openai.com`, `generativelanguage.googleapis.com`. Prices for estimates are in `results/runner/prices.json`.

The runner refuses to start unless `data/dev/questions.jsonl` matches the SHA-256 in `data/split-manifest.json`, and scores with `runner/constance.py` unchanged.

## A run folder

```
results/v0.2-baseline/
  answers/<provider>__<model>.jsonl   every raw answer, with timestamp, settings and token counts
  scorecards/<provider>__<model>.md   the scorer's output per model
  errors.jsonl                        questions that still failed after retries (if any)
  report.json                         machine-readable results (shape below)
  summary.md                          the write-up
results/the_table-for-woody.md        the_table replies for hand scoring, 0 to 2
```

## report.json

| Field | Meaning |
| --- | --- |
| `schema` | `constance-test-report/1` |
| `benchmark`, `version`, `split`, `dev_sha256` | What was run, pinned to the exact question bytes |
| `run_date`, `questions`, `auto_scored`, `human_tier` | When, and how many questions of each kind |
| `settings` | System text, output cap, defaults, fallbacks off, runs per question |
| `models[]` | One entry per model: `id` (`provider:model`), `provider`, `model`, `served_models` |
| `models[].overall` | Auto-scored questions: `n`, `pass`, `fail`, `needs_review`, `missing`, `refused`, and `pass_rate`, `fail_rate`, `needs_review_rate` over answered questions |
| `models[].by_type` | The same counts and rates for each question type |
| `models[].the_table` | `n`, `answered`, and `human_scores` (`"pending"` until Woody scores them) |
| `models[].tokens`, `models[].cost_usd` | Tokens used and cost at the list prices in `prices.json` |
| `models[].first_answer_at`, `last_answer_at` | UTC timestamps of the run |
| `errors_after_retries`, `total_cost_usd` | Run health and total cost |
| `limits` | Plain-language limits that must be shown with the numbers |

Rates are fractions from 0 to 1. `needs_review` is never counted as a pass.
