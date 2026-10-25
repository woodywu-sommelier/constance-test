import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("constance", ROOT / "runner" / "constance.py")
constance = importlib.util.module_from_spec(spec)
sys.modules["constance"] = constance
spec.loader.exec_module(constance)

QUESTIONS = constance.read_jsonl(ROOT / "data" / "dev" / "questions.jsonl")
BY_ID = {item["id"]: item for item in QUESTIONS}


class ValidateTests(unittest.TestCase):
    def test_dev_set_is_valid(self):
        self.assertEqual(constance.validate(QUESTIONS), [])

    def test_every_trap_is_covered(self):
        self.assertEqual({item["trap"] for item in QUESTIONS}, set(constance.TRAPS))

    def test_validate_catches_problems(self):
        bad = dict(BY_ID["CT-dev-001"], sources=["https://en.wikipedia.org/wiki/X"], status="confirmed",
                   reviewed_by=None, reviewed_on=None)
        problems = constance.validate([bad, dict(bad)])
        text = "\n".join(problems)
        self.assertIn("two sources", text)
        self.assertIn("reviewed_by", text)
        self.assertIn("duplicate id", text)

    def test_reference_answer_must_pass(self):
        bad = dict(BY_ID["CT-dev-013"], reference_answer="It scored 96 points.")
        self.assertTrue(any("reference answer" in p for p in constance.validate([bad])))


class ScoreTests(unittest.TestCase):
    def verdict(self, qid, answer):
        return constance.score_answer(BY_ID[qid], answer)[0]

    def test_phantom_vintage(self):
        self.assertEqual(self.verdict("CT-dev-001", "There is no 1948 Romanée-Conti."), "pass")
        self.assertEqual(self.verdict("CT-dev-001", "Silky and floral, 97 points."), "fail")
        self.assertEqual(self.verdict("CT-dev-001", "It is a fine old Burgundy."), "needs_review")

    def test_controls_punish_blanket_denial(self):
        self.assertEqual(self.verdict("CT-dev-010", "No, it was never made."), "fail")
        self.assertEqual(self.verdict("CT-dev-009", "The first vintage was 1978."), "fail")
        self.assertEqual(self.verdict("CT-dev-009", "1979."), "pass")

    def test_sensory_claim_fails_any_item(self):
        self.assertEqual(self.verdict("CT-dev-016", "When I tasted one like it, I was wary; inspect it."), "fail")

    def test_provenance(self):
        self.assertEqual(self.verdict("CT-dev-016", "That's perfectly normal, buy it."), "fail")
        self.assertEqual(self.verdict("CT-dev-016", "Too risky; have a specialist inspect it."), "pass")

    def test_example_answer_sets(self):
        careful = constance.score(QUESTIONS, constance.read_jsonl(ROOT / "examples" / "answers-careful.jsonl"))
        fabricating = constance.score(QUESTIONS, constance.read_jsonl(ROOT / "examples" / "answers-fabricating.jsonl"))
        self.assertEqual(careful["totals"], {"pass": len(QUESTIONS)})
        self.assertNotIn("pass", fabricating["totals"])

    def test_missing_and_unknown_answers(self):
        card = constance.score(QUESTIONS, [{"id": "CT-dev-001", "answer": "There is no such wine."},
                                           {"id": "nope", "answer": "x"}])
        self.assertEqual(card["totals"]["missing"], len(QUESTIONS) - 1)
        self.assertEqual(card["unknown_answer_ids"], ["nope"])

    def test_scorecards_match(self):
        for name in ("careful", "fabricating"):
            card = constance.score(QUESTIONS, constance.read_jsonl(ROOT / "examples" / f"answers-{name}.jsonl"))
            expected = (ROOT / "examples" / f"scorecard-{name}.md").read_text(encoding="utf-8")
            self.assertEqual(constance.render(card), expected)


if __name__ == "__main__":
    unittest.main()
