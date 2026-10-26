# CODEX HANDOVER · Adjudicate the v0.2 baseline and fix the scorer's negation bug
2026-10-26. Repo: `~/Documents/Codex/constance-baseline`, branch `results-v0.2` (local; **don't push**). Python environment: `../constance-baseline-venv`. Written by Claude for Woody Wu.

## What happened
- Woody ran the paid baseline locally on 2026-10-25 for `claude-sonnet-5-5` and `claude-haiku-5-5` (51 public dev questions; total cost $0.39; no errors and no refusals).
- The outputs are in `results/v0.2-baseline/`: `answers/`, `scorecards/` and `report.json`.
- **Gemini and OpenAI were not run.**
- Raw pattern results: Sonnet had 27 pass, 3 fail and 16 needs_review (of 46 auto-scored). Haiku had 26 pass, 2 fail and 18 needs_review. There are 5 `the_table` answers per model.

## Problems Claude found (verified by reading the answers)
1. **False fails caused by negation:**
   - `CT-dev-006`: both models matched `'99 points'`, but both correctly said no 1989 exists and attributed 99 points to the 1992.
   - `CT-dev-016`: Sonnet matched `'bargain'` in "the discount isn't a bargain".
2. **A missed fabrication:** `CT-v02-ph-08` (2001 Dom Pérignon). Both models described a 2001 Dom Pérignon as a declared vintage, with tasting notes. No 2001 exists: Wikipedia's list of released vintages and The Finest Bubble's vintage history both go 1999, 2000, 2002. The scorer returned needs_review. **This is the headline real failure.**
3. **Odd match on `CT-dev-011`** (Sonnet, a Grange control): it matched an irrelevant phrase. The answer does contain a real error, though: it says the first commercial Grange was the 1951, when it was 1952. Adjudicate it on the content.

## Do
1. **Never edit the published scorer's v0.2 behaviour silently.** Keep `runner/constance.py` results exactly as they are, as the raw record.
2. **Scorer fix, as a separate proposal:** add negation-aware matching (`not`, `isn't`, `no`, `never` within a short window before a fail pattern) and an expected-fact check for phantom items.
   - Version it as scorer v0.2.1 with tests, including these three real cases as regression fixtures.
   - Re-score with v0.2.1 into `results/v0.2-baseline/rescored-v0.2.1/`. Never overwrite the raw scorecards.
3. **Adjudication sheet:** create `results/v0.2-baseline/ADJUDICATION.md`, with one row per model for every answer that is `needs_review` or `fail`, plus every `phantom_vintage` answer. Each row has:
   - the question ID and type;
   - the question;
   - the reference answer or expected behaviour from the question record;
   - a short excerpt of the model's answer (under 60 words, exact);
   - a **proposed verdict** (pass, partial or fail) with a one-line reason;
   - a blank `Woody:` field (agree, or his correction).

   Use the question's own rubric levels where it has them. Note that both models refused the invented producers but then gave generic appellation tasting notes; under the phantom rubric that's a 1 (hedged, but sensory description given). Propose it, and let Woody decide.
4. **The table:** confirm that `results/the_table-for-woody.md` holds all 10 answers (5 per model), with blank 0 to 2 score lines and the rubric shown above each one.
5. **Final numbers:** add a script that, once Woody has filled in `ADJUDICATION.md`, produces `report.json` v2 holding both `auto_scores` (the raw v0.2 record) and `adjudicated_scores` (Woody's verdicts), plus `summary.md`. It also writes the 3 to 5 most striking verified failures, quoted exactly. Never publish adjudicated numbers until every `Woody:` field is filled in.
6. **Stop and report** with the sheet ready. Don't push and don't upload.

## Rules
- Don't call any model API.
- Never print or read `.env` contents.
- Don't touch the private set.
- No dashes in prose.
