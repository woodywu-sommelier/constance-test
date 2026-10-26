"""Tests for results/runner/run_baseline.py with fake clients: no network, no SDKs, no keys."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("run_baseline", ROOT / "results" / "runner" / "run_baseline.py")
rb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rb)


class Boom(Exception):
    pass


class Fatal(Exception):
    pass


def fake(provider, seen, refuse=(), fail=(), fatal_on=()):
    """A client whose answers echo the question id; records system text it was given."""
    def reply(question, system):
        seen.append((question, system))
        if question in fatal_on:
            raise Fatal()
        if question in fail:
            raise Boom()
        return None if question in refuse else "TRUE\nThere is no such wine."

    if provider == "anthropic":
        def create(model, max_tokens, messages, system=None):
            t = reply(messages[0]["content"], system)
            return NS(content=[NS(type="text", text=t)] if t else [], model=model,
                      stop_reason="end_turn" if t else "refusal", stop_details=NS(category="other"),
                      usage=NS(input_tokens=50, output_tokens=200), _request_id="req")
        return NS(messages=NS(create=create))
    if provider == "openai":
        def create(model, input, max_output_tokens, instructions=None):
            t = reply(input, instructions)
            return NS(output_text=t or "", model=model, status="completed" if t else "incomplete",
                      incomplete_details=None if t else NS(reason="content_filter"),
                      usage=NS(input_tokens=50, output_tokens=200), id="resp")
        return NS(responses=NS(create=create))

    def generate_content(model, contents, config):
        t = reply(contents, config.get("system_instruction"))
        return NS(text=t or "", candidates=[NS(finish_reason=NS(name="STOP" if t else "SAFETY"))],
                  prompt_feedback=None, model_version=model, response_id="g",
                  usage_metadata=NS(prompt_token_count=50, candidates_token_count=50,
                                    thoughts_token_count=150))
    return NS(models=NS(generate_content=generate_content))


class BaselineRunnerTests(unittest.TestCase):
    def setUp(self):
        self.constance = rb.load_constance()
        self.items = rb.eligible_items(self.constance)
        self.out = Path(tempfile.mkdtemp()) / "v0.2-baseline"
        self.log = lambda *_: None

    def test_split_hash_matches_manifest(self):
        self.assertEqual(len(rb.check_split()), 64)
        self.assertEqual(len(self.items), 51)

    def test_instruction_to_agent_is_the_only_system_text(self):
        with_instr = next(i for i in self.items if i.get("instruction_to_agent"))
        without = next(i for i in self.items if not i.get("instruction_to_agent"))
        for provider in rb.PROVIDERS:
            seen = []
            rb.run_model(f"{provider}:m", fake(provider, seen), [with_instr, without], self.out, self.log)
            self.assertEqual(seen, [(with_instr["question"], with_instr["instruction_to_agent"]),
                                    (without["question"], None)], provider)

    def test_records_carry_metadata_and_resume(self):
        seen = []
        client = fake("google", seen, refuse={self.items[0]["question"]})
        rb.run_model("google:m", client, self.items[:3], self.out, self.log)
        rb.run_model("google:m", client, self.items, self.out, self.log)
        self.assertEqual(len(seen), len(self.items))
        rows = rb.read_jsonl(rb.answers_file("google:m", self.out))
        first, second = rows[0], rows[1]
        self.assertTrue(first["refused"])
        for key in ("id", "provider", "model", "timestamp", "settings", "served_model",
                    "input_tokens", "output_tokens", "stop_reason"):
            self.assertIn(key, second)
        self.assertEqual(second["output_tokens"], 200, "thinking tokens count as output")
        self.assertEqual(second["settings"]["max_output_tokens"], rb.MAX_OUTPUT_TOKENS)

    def test_transient_failure_moves_on_and_fatal_stops_but_keeps_results(self):
        q = [i["question"] for i in self.items[:4]]
        seen = []
        rb.run_model("openai:m", fake("openai", seen, fail={q[1]}, fatal_on={q[3]}),
                     self.items[:4], self.out, self.log, fatal=(Fatal,))
        rows = rb.read_jsonl(rb.answers_file("openai:m", self.out))
        self.assertEqual([r["id"] for r in rows], [self.items[0]["id"], self.items[2]["id"]])
        errors = rb.read_jsonl(self.out / "errors.jsonl")
        self.assertEqual([e["error"] for e in errors], ["Boom", "Fatal"])
        self.assertNotIn("answer", json.dumps(errors))

    def test_report_and_table_export(self):
        specs = ["anthropic:claude-haiku-5-5", "openai:gpt-6-astra"]
        for s in specs:
            rb.run_model(s, fake(rb.parse_model(s)[0], []), self.items, self.out, self.log)
        export = self.out.parent / "the_table-for-woody.md"
        report = rb.score_all(self.constance, specs, self.items, rb.check_split(), self.out,
                              export, "2026-10-26")
        saved = json.loads((self.out / "report.json").read_text())
        self.assertEqual(saved, report)
        self.assertEqual(report["questions"], 51)
        self.assertEqual(report["human_tier"], 5)
        model = report["models"][0]
        self.assertEqual(model["overall"]["n"], 46)
        self.assertEqual(model["the_table"], {"n": 5, "answered": 5, "human_scores": "pending"})
        self.assertIn("needs_review_rate", model["overall"])
        self.assertEqual(set(model["by_type"]), {i["trap"] for i in self.items} - {"the_table"})
        self.assertIsNotNone(model["cost_usd"])
        self.assertTrue((self.out / "scorecards" / "openai__gpt-6-astra.md").exists())
        text = export.read_text()
        self.assertEqual(text.count("Score (0 to 2):"), 5 * len(specs))
        self.assertIn("CT-v02-tb-01", text)

    def test_dry_run_makes_no_calls(self):
        text = rb.dry_run(rb.DEFAULT_MODELS, self.items, self.out)
        self.assertIn("51 questions x 4 models = 204 calls", text)
        self.assertIn("No API calls were made.", text)
        self.assertFalse(self.out.exists())

    def test_model_specs(self):
        with self.assertRaises(SystemExit):
            rb.parse_model("xai:grok")
        with self.assertRaises(SystemExit):
            rb.parse_model("gpt-6-astra")


if __name__ == "__main__":
    unittest.main()
