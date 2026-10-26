"""Schema conversion and local-only private-set release verification. No network."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

CATEGORIES = {"phantom": "phantom_vintage", "control": "control",
              "citation": "invented_score", "false_premise": "false_premise",
              "provenance": "provenance", "fact_or_fiction": "fact_or_fiction",
              "the_table": "the_table"}
BEHAVIOURS = {"phantom": "correct_the_premise", "control": "answer_correctly",
              "citation": "admit_unknown", "false_premise": "correct_the_premise",
              "provenance": "flag_provenance", "fact_or_fiction": "first_line_label",
              "the_table": "human_review"}


def map_item(item: dict, split: str) -> dict:
    if split not in {"dev", "test"}:
        raise ValueError("Unknown split")
    category = item["category"]
    sources = copy.deepcopy(item.get("sources", []))
    hosts = {urlsplit(url).hostname.removeprefix("www.") for url in sources
             if urlsplit(url).scheme == "https" and urlsplit(url).hostname}
    approval = re.fullmatch(r"approved_by_woody_(\d{4}-\d{2}-\d{2})", item.get("status", ""))
    ready = bool(approval) or len(hosts) >= 2
    mapped = {"id": "CT-v02-" + item["id"], "split": split,
              "trap": CATEGORIES[category], "question": item["prompt"],
              "expected_behaviour": BEHAVIOURS[category],
              "reference_answer": item.get("expected", item.get("rubric", {}).get("2", "")),
              "reference_answer_kind": "label" if category == "fact_or_fiction" else "rubric_criterion",
              "pass_if_any": [], "fail_if_any": [],
              "facts": ["See the preserved source item and rubric."] if sources else [],
              "sources": sources, "requires_sources": bool(sources),
              "fictional_entities": item.get("status") == "verified_fictional",
              "status": "confirmed" if ready else "draft", "scoring_tier": item["tier"],
              "source_id": item["id"], "source_status": item.get("status"),
              "source_item": copy.deepcopy(item), "notes": item.get("notes", "")}
    if "rubric" in item:
        mapped["rubric"] = copy.deepcopy(item["rubric"])
    if "expected" in item:
        mapped["expected"] = item["expected"]
    if approval:
        mapped.update(reviewed_by="Woody Wu", reviewed_on=approval.group(1), review_basis="recorded_owner_approval")
    elif ready:
        mapped.update(reviewed_by="Two-site source eligibility check, not owner review",
                      reviewed_on="2026-10-25", review_basis="two_source_sites")
    else:
        mapped["draft_reason"] = "No recorded owner approval and fewer than two distinct HTTPS source sites."
    return mapped


def _normal(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)


def public_leaks(root: Path, heldout: list[dict]) -> list[str]:
    """Check all candidate public files, including ignored build output, not .git."""
    needles = [(q["id"], _normal(q["question"])) for q in heldout]
    leaks = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file() or path.is_symlink() or any(p in {".git", "__pycache__"} for p in relative.parts) or path.name == ".env":
            continue
        text = path.read_bytes().decode("utf-8", errors="ignore")
        variants = [text]
        # Exported JSON may escape accents, punctuation and whitespace.
        for candidate in [text, *text.splitlines()]:
            try:
                variants.extend(_strings(json.loads(candidate)))
            except (ValueError, TypeError):
                pass
        normal = [_normal(v) for v in variants]
        if any(any(qid in v or (question and question in v) for v in normal)
               for qid, question in [(qid.casefold(), question) for qid, question in needles]):
            leaks.append(str(relative))
    return leaks


def verify_release(root: Path, heldout_path: Path) -> list[str]:
    root, heldout_path = root.resolve(), heldout_path.resolve()
    if heldout_path.is_relative_to(root):
        return ["Private questions must live outside the public repository."]
    manifest = json.loads((root / "data/split-manifest.json").read_text("utf-8"))
    raw = heldout_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["heldout_sha256"]:
        return ["Private set hash does not match the public commitment."]
    heldout = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    dev_path = root / "data/dev/questions.jsonl"
    dev = [json.loads(line) for line in dev_path.read_text("utf-8").splitlines() if line.strip()]
    problems = []
    if len(heldout) != manifest["test_count"] or len(dev) != manifest["dev_count"]:
        problems.append("Split counts do not match the commitment.")
    if len({q["id"] for q in heldout + dev}) != len(heldout) + len(dev):
        problems.append("Duplicate IDs within or between splits.")
    if manifest.get("dev_sha256") and hashlib.sha256(dev_path.read_bytes()).hexdigest() != manifest["dev_sha256"]:
        problems.append("Public dev hash does not match the commitment.")
    problems.extend("Private material in public file: " + p for p in public_leaks(root, heldout))
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--heldout", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    problems = verify_release(args.root, args.heldout)
    for problem in problems:
        print(problem)
    print("Private-set commitment and public-file leak check: " + ("FAIL" if problems else "PASS"))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
