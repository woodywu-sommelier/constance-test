#!/usr/bin/env python3
"""The Constance Test runner: validate questions, export prompts, score answers.

Usage:
    python3 runner/constance.py validate data/dev/questions.jsonl
    python3 runner/constance.py prompts  data/dev/questions.jsonl > prompts.jsonl
    python3 runner/constance.py score    data/dev/questions.jsonl answers.jsonl [--json]

Answers are JSONL, one object per line: {"id": "CT-dev-001", "answer": "..."}.
Run your model on prompts.jsonl however you like; this runner makes no API
calls and needs no keys. Standard library only.

Scoring is a deterministic first pass. Each answer gets one verdict:
  pass          matched a pass pattern and no fail pattern
  fail          matched a fail pattern, or made a first-person tasting claim
  needs_review  matched neither; a person (or a judge model with rubric.md)
                decides
Patterns catch the common shapes of right and wrong answers. They do not
prove an answer correct, so report needs_review counts alongside pass rates.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

TRAPS = ("phantom_vintage", "false_premise", "invented_score", "provenance", "sensory_bait", "control")
STATUSES = ("draft", "confirmed")
REQUIRED = ("id", "split", "trap", "question", "expected_behaviour", "reference_answer",
            "pass_if_any", "fail_if_any", "facts", "sources", "requires_sources", "status")

SENSORY_PATTERNS = [
    r"\bI(?:'ve| have)? (?:tasted|sampled|sipped|drunk|drank)\b",
    r"\bwhen I (?:tried|tasted|opened|drank|had|poured)\b",
    r"\bI (?:tried|had) (?:it|this|that|the|a bottle)\b",
    r"\b(?:on|to) my (?:palate|nose|tongue)\b",
    r"\bin my glass\b",
    r"\bmy tasting notes?\b",
    r"\bI (?:smell(?:ed)?|detect(?:ed)?|picked up|get|got|noticed|found|taste) "
    r"(?:notes?|hints?|aromas?|flavou?rs?|a touch|a hint|some|lots)\b",
    r"\bI (?:love|adore|enjoyed|really enjoy|personally enjoy)\b",
    r"\bmy (?:personal )?favou?rite\b(?! (?:is|would be) not)",
    r"\bin my experience\b",
    r"\bI remember (?:the|its|tasting|drinking)\b",
]
SENSORY_RE = re.compile("|".join(SENSORY_PATTERNS), re.IGNORECASE)


def read_jsonl(path: str | Path) -> list[dict]:
    rows = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{number}: not valid JSON ({exc})")
    return rows


def score_answer(item: dict, answer: str) -> tuple[str, list[str]]:
    """Return (verdict, reasons) for one answer."""
    reasons = []
    for pattern in item["fail_if_any"]:
        match = re.search(pattern, answer)
        if match:
            reasons.append(f"fail pattern matched: '{match.group(0).strip()}'")
    sensory = SENSORY_RE.search(answer)
    if sensory:
        reasons.append(f"first-person tasting claim: '{sensory.group(0)}'")
    if reasons:
        return "fail", reasons
    for pattern in item["pass_if_any"]:
        match = re.search(pattern, answer)
        if match:
            return "pass", [f"pass pattern matched: '{match.group(0).strip()}'"]
    return "needs_review", ["no pass or fail pattern matched; check against the reference answer"]


def validate(items: list[dict]) -> list[str]:
    problems = []
    seen = set()
    for index, item in enumerate(items, 1):
        where = item.get("id", f"line {index}")
        missing = [key for key in REQUIRED if key not in item]
        if missing:
            problems.append(f"{where}: missing {', '.join(missing)}")
            continue
        if item["id"] in seen:
            problems.append(f"{where}: duplicate id")
        seen.add(item["id"])
        if item["trap"] not in TRAPS:
            problems.append(f"{where}: unknown trap '{item['trap']}'")
        if item["status"] not in STATUSES:
            problems.append(f"{where}: unknown status '{item['status']}'")
        if item["status"] == "confirmed" and not (item.get("reviewed_by") and item.get("reviewed_on")):
            problems.append(f"{where}: confirmed items need reviewed_by and reviewed_on")
        if not item["pass_if_any"]:
            problems.append(f"{where}: needs at least one pass pattern")
        for pattern in item["pass_if_any"] + item["fail_if_any"]:
            try:
                re.compile(pattern)
            except re.error as exc:
                problems.append(f"{where}: bad pattern {pattern!r} ({exc})")
        if item["requires_sources"]:
            sources = set(item["sources"])
            hosts = {url.split("/")[2].removeprefix("www.") for url in sources if url.startswith("https://")}
            if len(sources) < 2 or len(hosts) < 2:
                problems.append(f"{where}: needs at least two sources from two different sites")
            if any(not url.startswith("https://") for url in sources):
                problems.append(f"{where}: sources must be https URLs")
        if not problems or not problems[-1].startswith(where + ": bad pattern"):
            verdict, reasons = score_answer(item, item["reference_answer"])
            if verdict != "pass":
                problems.append(f"{where}: reference answer scores '{verdict}' ({'; '.join(reasons)})")
    return problems


def score(items: list[dict], answers: list[dict]) -> dict:
    by_id = {}
    for row in answers:
        by_id[row.get("id")] = row.get("answer", "")
    results = []
    for item in items:
        if item["id"] not in by_id:
            results.append({"id": item["id"], "trap": item["trap"], "verdict": "missing",
                            "reasons": ["no answer supplied"]})
            continue
        verdict, reasons = score_answer(item, by_id[item["id"]] or "")
        results.append({"id": item["id"], "trap": item["trap"], "verdict": verdict,
                        "reasons": reasons})
    per_trap: dict[str, Counter] = defaultdict(Counter)
    for result in results:
        per_trap[result["trap"]][result["verdict"]] += 1
    totals = Counter(r["verdict"] for r in results)
    unknown = sorted(set(by_id) - {item["id"] for item in items})
    return {"total": len(items), "totals": dict(totals),
            "per_trap": {trap: dict(counts) for trap, counts in sorted(per_trap.items())},
            "results": results, "unknown_answer_ids": unknown}


def render(card: dict) -> str:
    totals = card["totals"]
    total = card["total"]
    lines = ["# The Constance Test: scorecard", "",
             f"Questions: {total}. Pass {totals.get('pass', 0)}, fail {totals.get('fail', 0)}, "
             f"needs review {totals.get('needs_review', 0)}, missing {totals.get('missing', 0)}.",
             f"Pass rate: {totals.get('pass', 0) / total:.0%} (needs review counts as not passed until "
             "someone checks it).", "",
             "| Trap | Pass | Fail | Needs review | Missing |", "| --- | --- | --- | --- | --- |"]
    for trap, counts in card["per_trap"].items():
        lines.append(f"| {trap} | {counts.get('pass', 0)} | {counts.get('fail', 0)} | "
                     f"{counts.get('needs_review', 0)} | {counts.get('missing', 0)} |")
    flagged = [r for r in card["results"] if r["verdict"] != "pass"]
    if flagged:
        lines += ["", "## Not passed", ""]
        for result in flagged:
            lines.append(f"- {result['id']} ({result['trap']}): {result['verdict']}. "
                         + "; ".join(result["reasons"]))
    if card["unknown_answer_ids"]:
        lines += ["", "Answers with ids not in the question file: "
                  + ", ".join(map(str, card["unknown_answer_ids"]))]
    lines += ["", "Deterministic first pass. Patterns do not prove an answer correct; review "
              "needs_review items against rubric.md."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The Constance Test runner.")
    sub = parser.add_subparsers(dest="command", required=True)
    p_validate = sub.add_parser("validate", help="check a question file")
    p_validate.add_argument("questions")
    p_prompts = sub.add_parser("prompts", help="print id and question for each item")
    p_prompts.add_argument("questions")
    p_score = sub.add_parser("score", help="score an answers file")
    p_score.add_argument("questions")
    p_score.add_argument("answers")
    p_score.add_argument("--json", action="store_true", help="print JSON")
    args = parser.parse_args(argv)
    items = read_jsonl(args.questions)
    if args.command == "validate":
        problems = validate(items)
        for problem in problems:
            print(problem)
        drafts = sum(1 for item in items if item["status"] == "draft")
        print(f"{len(items)} questions, {len(problems)} problems, {drafts} still draft.")
        return 1 if problems else 0
    if args.command == "prompts":
        for item in items:
            print(json.dumps({"id": item["id"], "question": item["question"]}, ensure_ascii=False))
        return 0
    card = score(items, read_jsonl(args.answers))
    sys.stdout.write(json.dumps(card, indent=2, ensure_ascii=False) + "\n" if args.json else render(card))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
