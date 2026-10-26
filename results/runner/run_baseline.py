#!/usr/bin/env python3
"""Run a Constance Test baseline on models from Anthropic, OpenAI and Google.

Usage (from the repository root):
    pip install anthropic openai google-genai
    # keys come only from the environment: ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY

    python3 results/runner/run_baseline.py dry-run        # plan, tokens and cost; no API calls
    python3 results/runner/run_baseline.py check-models   # free: confirms each model id exists
    python3 results/runner/run_baseline.py run            # the paid run (resumable)
    python3 results/runner/run_baseline.py score          # score saved answers; no API calls

Models are written provider:model-id. The defaults are the four models of the
v0.2 baseline; pass --models to change them.

Each model gets the question as one user message with the provider's default
settings. The only system text is the question's own instruction_to_agent,
when it has one. Output is capped at the same MAX_OUTPUT_TOKENS for every
provider so no answer is cut short by a provider default. Refusal fallbacks
are off, so every answer comes from the model named; refusals and blocked
responses are counted in their own column.

Retries happen only on transient errors (timeouts, rate limits, server
errors), handled by each SDK. A question that still fails is written to
errors.jsonl and the run moves on, so partial results are kept and a re-run
asks only what is missing.

Scoring uses the repository's own runner/constance.py, unchanged.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
QUESTIONS = REPO / "data" / "dev" / "questions.jsonl"
MANIFEST = REPO / "data" / "split-manifest.json"
OUT = REPO / "results" / "v0.2-baseline"
TABLE_EXPORT = REPO / "results" / "the_table-for-woody.md"
DEFAULT_MODELS = ["anthropic:claude-sonnet-5-5", "anthropic:claude-haiku-5-5",
                  "openai:gpt-6-astra", "google:gemini-4-argon"]
PROVIDERS = ("anthropic", "openai", "google")
MAX_OUTPUT_TOKENS = 16000
TRANSIENT_HTTP = [408, 429, 500, 502, 503, 504]
# Output-token range for the dry-run estimate; reasoning models bill thinking as output.
EST_OUTPUT_LOW, EST_OUTPUT_HIGH = 300, 4000


def load_constance():
    spec = importlib.util.spec_from_file_location("constance", REPO / "runner" / "constance.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["constance"] = module
    spec.loader.exec_module(module)
    return module


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


def parse_model(spec: str) -> tuple[str, str]:
    provider, _, model = spec.partition(":")
    if provider not in PROVIDERS or not model:
        raise SystemExit(f"Write models as provider:model-id with provider in {PROVIDERS} (got {spec!r}).")
    return provider, model


def answers_file(spec: str, out: Path = OUT) -> Path:
    provider, model = parse_model(spec)
    return out / "answers" / f"{provider}__{model}.jsonl"


def check_split() -> str:
    """Refuse to run unless the dev file matches the published manifest hash."""
    digest = hashlib.sha256(QUESTIONS.read_bytes()).hexdigest()
    expected = json.loads(MANIFEST.read_text("utf-8"))["dev_sha256"]
    if digest != expected:
        raise SystemExit(f"Dev split hash {digest} does not match the manifest ({expected}).")
    return digest


def eligible_items(constance) -> list[dict]:
    items = constance.read_jsonl(QUESTIONS)
    problems = constance.validate(items)
    if problems:
        raise SystemExit("The question file has problems:\n" + "\n".join(problems))
    return [item for item in items if item["status"] != "draft"]


# Providers -------------------------------------------------------------------

class FatalProviderError(Exception):
    """Authentication, permission or unknown model: stop this model, keep its results."""


def make_client(provider: str):
    if provider == "anthropic":
        import anthropic
        return anthropic.Anthropic(max_retries=4)
    if provider == "openai":
        import openai
        return openai.OpenAI(max_retries=4)
    from google import genai
    from google.genai import types
    return genai.Client(http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(
        attempts=5, http_status_codes=TRANSIENT_HTTP)))


def fatal_errors(provider: str) -> tuple:
    if provider == "anthropic":
        import anthropic
        return (anthropic.AuthenticationError, anthropic.PermissionDeniedError, anthropic.NotFoundError)
    if provider == "openai":
        import openai
        return (openai.AuthenticationError, openai.PermissionDeniedError, openai.NotFoundError)
    from google.genai import errors
    return (errors.ClientError,)  # 4xx after retries: bad key, unknown model, bad request


def ask(provider: str, client, model: str, question: str, system: str | None) -> dict:
    if provider == "anthropic":
        kwargs = {"system": system} if system else {}
        r = client.messages.create(model=model, max_tokens=MAX_OUTPUT_TOKENS,
                                   messages=[{"role": "user", "content": question}], **kwargs)
        record = {"answer": "".join(b.text for b in r.content if b.type == "text"),
                  "served_model": r.model, "stop_reason": r.stop_reason,
                  "refused": r.stop_reason == "refusal",
                  "input_tokens": r.usage.input_tokens, "output_tokens": r.usage.output_tokens,
                  "request_id": getattr(r, "_request_id", None)}
        if record["refused"] and getattr(r, "stop_details", None):
            record["refusal_category"] = r.stop_details.category
        return record
    if provider == "openai":
        kwargs = {"instructions": system} if system else {}
        r = client.responses.create(model=model, input=question,
                                    max_output_tokens=MAX_OUTPUT_TOKENS, **kwargs)
        reason = r.incomplete_details.reason if r.incomplete_details else None
        return {"answer": r.output_text or "", "served_model": r.model,
                "stop_reason": reason or r.status, "refused": reason == "content_filter",
                "input_tokens": r.usage.input_tokens if r.usage else 0,
                "output_tokens": r.usage.output_tokens if r.usage else 0,  # includes reasoning
                "request_id": getattr(r, "_request_id", None) or r.id}
    config = {"max_output_tokens": MAX_OUTPUT_TOKENS}
    if system:
        config["system_instruction"] = system
    r = client.models.generate_content(model=model, contents=question, config=config)
    candidate = r.candidates[0] if r.candidates else None
    finish = getattr(candidate.finish_reason, "name", "") if candidate and candidate.finish_reason else ""
    blocked = bool(r.prompt_feedback and r.prompt_feedback.block_reason)
    try:
        text = r.text or ""
    except ValueError:
        text = ""
    usage = r.usage_metadata
    return {"answer": text, "served_model": r.model_version or model,
            "stop_reason": "blocked" if blocked else finish,
            "refused": blocked or finish in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII"),
            "input_tokens": (usage.prompt_token_count or 0) if usage else 0,
            "output_tokens": ((usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0))
            if usage else 0,  # thinking tokens are billed as output
            "request_id": getattr(r, "response_id", None)}


def list_models(provider: str, client) -> set[str]:
    """Model ids available to the key. Listing models is free."""
    if provider == "google":
        return {m.name.removeprefix("models/") for m in client.models.list()}
    return {m.id for m in client.models.list()}


# Commands --------------------------------------------------------------------

def load_prices() -> dict:
    return json.loads((HERE / "prices.json").read_text("utf-8"))


def money(value: float) -> str:
    return f"${value:,.2f}" if value >= 0.005 else "under $0.01"


def dry_run(specs: list[str], items: list[dict], out: Path = OUT) -> str:
    prices = load_prices()["models"]
    est_in = {i["id"]: (len(i["question"]) + len(i.get("instruction_to_agent") or "")) // 4 + 10
              for i in items}
    table = sum(1 for i in items if i["trap"] == "the_table")
    lines = [f"Plan: {len(items)} questions x {len(specs)} models = {len(items) * len(specs)} calls "
             f"({len(items) - table} auto-scored, {table} the_table for hand scoring).", "",
             "| Model | Calls | Input tokens (est.) | Output tokens (est.) | Cost (est.) | Price per 1M in / out |",
             "| --- | --- | --- | --- | --- | --- |"]
    total_low = total_high = 0.0
    for spec in specs:
        done = {r["id"] for r in read_jsonl(answers_file(spec, out))}
        todo = [i for i in items if i["id"] not in done]
        tin = sum(est_in[i["id"]] for i in todo)
        out_low, out_high = len(todo) * EST_OUTPUT_LOW, len(todo) * EST_OUTPUT_HIGH
        price = prices.get(spec)
        if price:
            low = tin / 1e6 * price["input"] + out_low / 1e6 * price["output"]
            high = tin / 1e6 * price["input"] + out_high / 1e6 * price["output"]
            total_low, total_high = total_low + low, total_high + high
            cost_cell = f"{money(low)} to {money(high)}"
            price_cell = f"${price['input']:g} / ${price['output']:g}"
        else:
            cost_cell, price_cell = "unknown", "not on file"
        lines.append(f"| {spec} | {len(todo)} | {tin:,} | {out_low:,} to {out_high:,} | {cost_cell} | {price_cell} |")
    lines += ["", f"Estimated total: {money(total_low)} to {money(total_high)}.",
              f"Output assumes {EST_OUTPUT_LOW} to {EST_OUTPUT_HIGH} tokens per answer; the high end "
              "allows for reasoning tokens, which all three providers bill as output.",
              "No API calls were made."]
    return "\n".join(lines)


def check_models(specs: list[str]) -> list[str]:
    problems = []
    for provider in sorted({parse_model(s)[0] for s in specs}):
        try:
            available = list_models(provider, make_client(provider))
        except Exception as exc:
            problems.append(f"{provider}: could not list models ({type(exc).__name__})")
            continue
        for spec in specs:
            p, model = parse_model(spec)
            if p == provider and model not in available:
                problems.append(f"{spec} is not available to this key")
    return problems


def run_model(spec: str, client, items: list[dict], out: Path = OUT, log=print,
              fatal: tuple = ()) -> None:
    provider, model = parse_model(spec)
    path = answers_file(spec, out)
    done = {r["id"] for r in read_jsonl(path)}
    todo = [i for i in items if i["id"] not in done]
    log(f"{spec}: {len(done)} already answered, {len(todo)} to ask")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for item in todo:
            system = item.get("instruction_to_agent") or None
            started = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
            try:
                result = ask(provider, client, model, item["question"], system)
            except fatal as exc:
                write_error(out, spec, item["id"], started, exc)
                log(f"  {item['id']}: stopped this model ({type(exc).__name__}); results so far are kept")
                return
            except Exception as exc:  # transient errors already retried by the SDK
                write_error(out, spec, item["id"], started, exc)
                log(f"  {item['id']}: failed after retries ({type(exc).__name__}); moving on")
                continue
            record = {"id": item["id"], "provider": provider, "model": model, "timestamp": started,
                      "settings": {"system": system, "max_output_tokens": MAX_OUTPUT_TOKENS,
                                   "other": "provider defaults"},
                      **result}
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            log(f"  {item['id']}: {record['stop_reason']}")


def write_error(out: Path, spec: str, qid: str, when: str, exc: Exception) -> None:
    out.mkdir(parents=True, exist_ok=True)
    row = {"model": spec, "id": qid, "timestamp": when, "error": type(exc).__name__,
           "status": getattr(exc, "status_code", getattr(exc, "code", None))}
    with (out / "errors.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def cost_of(spec: str, answers: list[dict]) -> float | None:
    price = load_prices()["models"].get(spec)
    if not price:
        return None
    return (sum(a.get("input_tokens", 0) for a in answers) / 1e6 * price["input"]
            + sum(a.get("output_tokens", 0) for a in answers) / 1e6 * price["output"])


def score_all(constance, specs: list[str], items: list[dict], dev_sha: str, out: Path = OUT,
              table_export: Path = TABLE_EXPORT, run_date: str | None = None) -> dict:
    """Score every model, write scorecards, report.json and the table export; return the report."""
    run_date = run_date or datetime.date.today().isoformat()
    traps = sorted({i["trap"] for i in items if i["trap"] != "the_table"})
    (out / "scorecards").mkdir(parents=True, exist_ok=True)
    models, table_rows = [], {}
    for spec in specs:
        provider, model = parse_model(spec)
        answers = read_jsonl(answers_file(spec, out))
        card = constance.score(items, answers)
        (out / "scorecards" / f"{provider}__{model}.md").write_text(constance.render(card), "utf-8")
        by_id = {a["id"]: a for a in answers}
        auto = [r for r in card["results"] if r["trap"] != "the_table"]
        refused = sum(1 for r in auto if by_id.get(r["id"], {}).get("refused"))

        def counts(rows):
            c = {"n": len(rows)}
            for v in ("pass", "fail", "needs_review", "missing"):
                c[v] = sum(1 for r in rows if r["verdict"] == v)
            answered = c["n"] - c["missing"]
            c["pass_rate"] = round(c["pass"] / answered, 4) if answered else None
            c["fail_rate"] = round(c["fail"] / answered, 4) if answered else None
            c["needs_review_rate"] = round(c["needs_review"] / answered, 4) if answered else None
            return c

        overall = counts(auto)
        overall["refused"] = refused
        human = [r for r in card["results"] if r["trap"] == "the_table"]
        served = sorted({a.get("served_model") for a in answers if a.get("served_model")})
        cost = cost_of(spec, answers)
        models.append({
            "id": spec, "provider": provider, "model": model, "served_models": served,
            "overall": overall,
            "by_type": {t: counts([r for r in auto if r["trap"] == t]) for t in traps},
            "the_table": {"n": len(human), "answered": sum(1 for r in human if r["verdict"] != "missing"),
                          "human_scores": "pending"},
            "tokens": {"input": sum(a.get("input_tokens", 0) for a in answers),
                       "output": sum(a.get("output_tokens", 0) for a in answers)},
            "cost_usd": round(cost, 4) if cost is not None else None,
            "first_answer_at": min((a["timestamp"] for a in answers), default=None),
            "last_answer_at": max((a["timestamp"] for a in answers), default=None),
        })
        for item in items:
            if item["trap"] == "the_table":
                table_rows.setdefault(item["id"], []).append((spec, by_id.get(item["id"], {}).get("answer")))
    errors = read_jsonl(out / "errors.jsonl")
    report = {
        "schema": "constance-test-report/1",
        "benchmark": "The Constance Test", "version": "0.2.0", "split": "dev",
        "dev_sha256": dev_sha, "run_date": run_date,
        "questions": len(items), "auto_scored": sum(1 for i in items if i["trap"] != "the_table"),
        "human_tier": sum(1 for i in items if i["trap"] == "the_table"),
        "settings": {"system": "only the question's instruction_to_agent, when present",
                     "max_output_tokens": MAX_OUTPUT_TOKENS, "other": "provider defaults",
                     "refusal_fallbacks": False, "runs_per_question": 1},
        "scorer": "runner/constance.py (deterministic patterns; needs_review is not a pass)",
        "models": models,
        "errors_after_retries": len(errors),
        "total_cost_usd": round(sum(m["cost_usd"] or 0 for m in models), 4),
        "limits": [
            "Pattern scoring flags risk; it does not prove an answer true or false.",
            "One run per question at default settings; results can vary between runs.",
            "Human-tier (the_table) scores are pending and not included in any rate.",
            "The dev set is public, so these are not unseen-question results.",
        ],
    }
    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", "utf-8")
    write_table_export(items, table_rows, table_export)
    return report


def write_table_export(items, rows, path: Path) -> None:
    lines = ["# the_table: replies for Woody to score", "",
             "Score each reply 0, 1 or 2 against the rubric under its question, and add a short note. "
             "These replies are never auto-scored. Answers are quoted exactly.", ""]
    for item in items:
        if item["trap"] != "the_table":
            continue
        lines += [f"## {item['id']}", "", f"**Question:** {item['question']}", ""]
        if item.get("instruction_to_agent"):
            lines += [f"**Instruction sent as system text:** {item['instruction_to_agent']}", ""]
        lines += ["**Rubric:**", ""] + [f"- {k}: {v}" for k, v in sorted(item["rubric"].items())] + [""]
        for spec, answer in rows.get(item["id"], []):
            quoted = "\n".join("> " + line if line else ">" for line in (answer or "(no answer)").splitlines())
            lines += [f"### {spec}", "", quoted, "", "Score (0 to 2): ", "", "Note: ", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a Constance Test baseline.")
    parser.add_argument("command", choices=["dry-run", "check-models", "run", "score"])
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    args = parser.parse_args(argv)
    for spec in args.models:
        parse_model(spec)
    dev_sha = check_split()
    constance = load_constance()
    items = eligible_items(constance)
    if args.command == "dry-run":
        print(dry_run(args.models, items))
        return 0
    if args.command == "check-models":
        problems = check_models(args.models)
        print("\n".join(problems) if problems else "All models are available to these keys.")
        return 1 if problems else 0
    if args.command == "run":
        for spec in args.models:
            provider = parse_model(spec)[0]
            run_model(spec, make_client(provider), items, fatal=fatal_errors(provider))
    report = score_all(constance, args.models, items, dev_sha)
    print(json.dumps({m["id"]: m["overall"] for m in report["models"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
