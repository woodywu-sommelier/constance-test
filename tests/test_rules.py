"""House rules for everything published from this repository."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {".git", "dist", "__pycache__"}
REAL_PRODUCERS = ["Romanée-Conti", "Romanee-Conti", "Yquem", "Opus One", "Screaming Eagle",
                  "Penfolds", "Grange", "Ponsot"]


def text_files():
    for path in ROOT.rglob("*"):
        if path.is_file() and not any(part in SKIP for part in path.relative_to(ROOT).parts):
            if path.suffix in {".md", ".py", ".json", ".jsonl", ".cff", ""} or path.name.startswith("LICENSE"):
                yield path


class Rules(unittest.TestCase):
    def test_no_em_or_en_dashes(self):
        for path in text_files():
            text = path.read_text(encoding="utf-8")
            for ch in (chr(0x2014), chr(0x2013)):
                self.assertNotIn(ch, text, str(path.relative_to(ROOT)))

    def test_no_secrets(self):
        pattern = re.compile(r"sk-[A-Za-z0-9_-]{20,}|\bhf_[A-Za-z0-9]{20,}|\bghp_[A-Za-z0-9]{20,}|"
                             r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
        for path in text_files():
            self.assertIsNone(pattern.search(path.read_text(encoding="utf-8")), str(path))

    def test_real_producers_only_in_sourced_items(self):
        questions = [json.loads(l) for l in (ROOT / "data" / "dev" / "questions.jsonl").read_text("utf-8").splitlines() if l]
        sourced = {q["id"] for q in questions if q["facts"]}
        for q in questions:
            if q["id"] in sourced:
                continue
            for name in REAL_PRODUCERS:
                self.assertNotIn(name, q["question"] + q["reference_answer"], q["id"])
        for path in (ROOT / "examples").glob("answers-*.jsonl"):
            for line in path.read_text("utf-8").splitlines():
                row = json.loads(line)
                if row["id"] not in sourced:
                    for name in REAL_PRODUCERS:
                        self.assertNotIn(name, row["answer"], f"{path.name} {row['id']}")

    def test_no_real_critic_attributions_in_examples(self):
        for path in (ROOT / "examples").glob("answers-*.jsonl"):
            self.assertNotRegex(path.read_text("utf-8"), r"Parker|Robinson|Suckling|Galloni|Wine Advocate")

    def test_new_questions_start_as_drafts_or_are_reviewed(self):
        for line in (ROOT / "data" / "dev" / "questions.jsonl").read_text("utf-8").splitlines():
            q = json.loads(line)
            if q["status"] == "confirmed":
                self.assertTrue(q["reviewed_by"] and q["reviewed_on"], q["id"])


if __name__ == "__main__":
    unittest.main()
