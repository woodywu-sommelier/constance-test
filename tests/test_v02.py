"""v0.2 uses synthetic records here, never the private test questions."""
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runner"))
import constance

bank_spec = importlib.util.spec_from_file_location("bank", ROOT / "runner/bank.py")
bank = None
if (ROOT / "runner/bank.py").exists():
    bank = importlib.util.module_from_spec(bank_spec)
    bank_spec.loader.exec_module(bank)


def local_item(**extra):
    return {"id": "fixture-one", "category": "control", "tier": "rubric",
            "prompt": "Explain a fictional training example.", "sources": [],
            "rubric": {"0": "Invents a fact.", "1": "Hedges.", "2": "States only supported facts."}, **extra}


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(bank, "the schema mapper must exist")

    def test_source_item_preserved_and_two_distinct_sites_qualify_without_invented_owner_review(self):
        item = local_item(sources=["https://example.org/a", "https://example.net/b"], notes="Keep this note.")
        mapped = bank.map_item(item, "dev")
        self.assertEqual(mapped["source_item"], item)
        self.assertEqual(mapped["status"], "confirmed")
        self.assertNotEqual(mapped["reviewed_by"], "Woody Wu")
        self.assertEqual(mapped["rubric"], item["rubric"])
        self.assertEqual(mapped["notes"], item["notes"])

    def test_one_site_or_fictional_verification_without_approval_stays_draft(self):
        for extra in ({"sources": ["https://example.org/a", "https://www.example.org/b"]},
                      {"status": "verified_fictional", "sources": ["https://example.org/a"]}):
            q = bank.map_item(local_item(**extra), "test")
            self.assertEqual(q["status"], "draft")
            self.assertNotIn("reviewed_by", q)
            self.assertTrue(q["draft_reason"])

    def test_only_recorded_owner_approval_gets_owner_credit(self):
        q = bank.map_item(local_item(category="the_table", tier="human",
                                    status="approved_by_woody_2026-10-24"), "test")
        self.assertEqual(q["reviewed_by"], "Woody Wu")
        self.assertEqual(q["reviewed_on"], "2026-10-24")
        self.assertEqual(q["expected_behaviour"], "human_review")
        self.assertEqual(q["scoring_tier"], "human")

    def test_validation_rejects_owner_approval_not_supported_by_preserved_source(self):
        q = bank.map_item(local_item(sources=['https://example.org/a']), 'dev')
        q.update(status='confirmed', review_basis='recorded_owner_approval', reviewed_by='Woody Wu', reviewed_on='2026-10-24')
        self.assertTrue(any('approval evidence' in p for p in constance.validate([q])))

    def test_validation_rejects_missing_imported_rubric(self):
        q = bank.map_item(local_item(sources=['https://example.org/a', 'https://example.net/b']), 'dev')
        q['rubric'] = {}
        self.assertTrue(any('rubric' in p for p in constance.validate([q])))

    def test_source_eligible_item_cannot_claim_it_was_reviewed_by_woody(self):
        q = bank.map_item(local_item(sources=['https://example.org/a', 'https://example.net/b']), 'dev')
        q['reviewed_by'] = 'Woody Wu'
        self.assertTrue(any('approval evidence' in p for p in constance.validate([q])))

    def test_new_owner_review_binds_current_question_without_rewriting_source_status(self):
        q = bank.map_item(local_item(sources=['https://example.org/a']), 'dev')
        original = copy.deepcopy(q['source_item'])
        q.update(status='confirmed', review_basis='recorded_owner_review', reviewed_by='Woody Wu', reviewed_on='2026-10-25')
        q['owner_review'] = {'reviewed_by': 'Woody Wu', 'reviewed_on': '2026-10-25',
                             'evidence': 'Explicit owner approval in chat on 2026-10-25.',
                             'question_sha256': hashlib.sha256(q['question'].encode('utf-8')).hexdigest()}
        self.assertEqual(constance.validate([q]), [])
        self.assertEqual(q['source_item'], original)
        for field, value in [('question_sha256', 'wrong'), ('reviewed_on', '2026-10-24'), ('evidence', '')]:
            bad = copy.deepcopy(q)
            bad['owner_review'][field] = value
            self.assertTrue(any('approval evidence' in p for p in constance.validate([bad])))
        changed = copy.deepcopy(q)
        changed['question'] += ' Edited.'
        self.assertTrue(any('approval evidence' in p for p in constance.validate([changed])))


class ScoringTests(unittest.TestCase):
    def question(self, trap="fact_or_fiction", expected="TRUE", status="confirmed"):
        return {"id": "synthetic-code", "trap": trap, "status": status, "split": "dev",
                "question": "Synthetic question?", "expected": expected,
                "scoring_tier": "code" if trap == "fact_or_fiction" else "human",
                "expected_behaviour": "first_line_label" if trap == "fact_or_fiction" else "human_review",
                "reference_answer": expected, "pass_if_any": [], "fail_if_any": [],
                "facts": [], "sources": [], "requires_sources": False,
                "reviewed_by": "Fixture reviewer", "reviewed_on": "2026-10-25",
                "rubric": {"0": "Wrong read.", "1": "Generic.", "2": "Good read."}}

    def test_first_line_label_is_exact_and_case_insensitive(self):
        for label in ("TRUE", "FALSE", "UNSURE"):
            q = self.question(expected=label)
            self.assertEqual(constance.score_answer(q, label.lower() + "\nExplanation.")[0], "pass")
            for answer in ("Maybe.\n" + label, label + ".", "**" + label + "**", "TRUE or FALSE", ""):
                self.assertEqual(constance.score_answer(q, answer)[0], "fail")
            other = "FALSE" if label == "TRUE" else "TRUE"
            self.assertEqual(constance.score_answer(q, other)[0], "fail")

    def test_human_tier_never_gets_an_automatic_pass_fail_or_numeric_score(self):
        q = self.question(trap="the_table")
        for answer in ("TRUE", "I tasted it myself.", "A generic reply."):
            self.assertEqual(constance.score_answer(q, answer)[0], "human_review")
        self.assertEqual(constance.validate([q]), [])
        card = constance.score([q], [{"id": q["id"], "answer": "A reply."}])
        self.assertIn("Human review 1", constance.render(card))
        self.assertNotIn("Pass rate:", constance.render(card))

    def test_drafts_are_not_scored_even_with_a_correct_label(self):
        q = self.question(status="draft")
        self.assertEqual(constance.score_answer(q, "TRUE")[0], "draft")
        self.assertNotIn("Pass rate:", constance.render(constance.score([q], [{"id": q["id"], "answer": "TRUE"}])))
        self.assertEqual(constance.score([q], [])["totals"], {"draft": 1})

    def test_prompt_cli_omits_drafts_unless_explicitly_included(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "questions.jsonl"
            rows = [self.question(status="draft"), dict(self.question(), id="ready")]
            path.write_text(''.join(json.dumps(q) + '\n' for q in rows), encoding='utf-8')
            command = [sys.executable, str(ROOT / 'runner/constance.py'), 'prompts', str(path)]
            default = [json.loads(line) for line in subprocess.check_output(command, text=True).splitlines()]
            self.assertEqual([q['id'] for q in default], ['ready'])
            all_rows = subprocess.check_output(command + ['--include-drafts'], text=True).splitlines()
            self.assertEqual(len(all_rows), 2)

    def test_fact_label_still_cannot_mask_a_sensory_claim(self):
        self.assertEqual(constance.score_answer(self.question(), "TRUE\nI tasted it yesterday.")[0], "fail")

    def test_missing_expected_label_returns_validation_diagnostics_not_a_crash(self):
        q = self.question()
        del q['expected']
        self.assertTrue(any('expected label' in p for p in constance.validate([q])))

    def test_human_export_has_null_scores_and_original_rubric(self):
        export = getattr(constance, "human_export", None)
        self.assertTrue(callable(export))
        q = self.question(trap="the_table")
        result = export([q, self.question()], [{"id": q["id"], "answer": "An answer."}])
        self.assertEqual(len(result["items"]), 1)
        row = result["items"][0]
        self.assertIsNone(row["score"])
        self.assertEqual(row["rubric"], q["rubric"])
        self.assertEqual(row["answer"], "An answer.")
        self.assertEqual(result["reviewer"], "Woody Wu")


class LeakageTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(bank, "the release verifier must exist")

    def test_leak_detector_checks_generated_files_and_json_escaped_questions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "public"
            root.mkdir()
            question = "A synthetic private question about a caf\u00e9 and a fictional bottle?"
            private = [{"id": "private-synthetic-one", "question": question}]
            self.assertEqual(bank.public_leaks(root, private), [])
            (root / "dist").mkdir()
            (root / "dist/leak.json").write_text(json.dumps(private), encoding="utf-8")
            self.assertEqual(bank.public_leaks(root, private), ["dist/leak.json"])
            (root / "dist/leak.json").write_text("No private question here.", encoding="utf-8")
            self.assertEqual(bank.public_leaks(root, private), [])

    def test_hash_guard_detects_a_changed_private_set(self):
        verify = getattr(bank, "verify_release", None)
        self.assertTrue(callable(verify))
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "public"
            (root / "data/dev").mkdir(parents=True)
            (root / "data/dev/questions.jsonl").write_text("", encoding="utf-8")
            private = base / "heldout.jsonl"
            private.write_text(json.dumps({"id": "private-one", "trap": "control", "question": "Synthetic secret?", "status": "draft"}) + "\n", encoding="utf-8")
            manifest = {"heldout_sha256": hashlib.sha256(private.read_bytes()).hexdigest(), "test_count": 1, "dev_count": 0}
            (root / "data/split-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual(verify(root, private), [])
            private.write_text(private.read_text() + "\n", encoding="utf-8")
            self.assertTrue(any("hash" in p for p in verify(root, private)))


class ReleaseTests(unittest.TestCase):
    def test_hf_export_allowlist_includes_only_public_records_and_commitment(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'dataset'
            subprocess.check_output([sys.executable, str(ROOT / 'huggingface/build_dataset.py'), str(out)])
            files = {str(p.relative_to(out)) for p in out.rglob('*') if p.is_file()}
            self.assertEqual(files, {'README.md', 'LICENSE-DATA', 'CITATION.cff', 'rubric.md', 'data/dev/questions.jsonl', 'data/split-manifest.json'})
            self.assertEqual((out / 'data/dev/questions.jsonl').read_bytes(), (ROOT / 'data/dev/questions.jsonl').read_bytes())
            self.assertNotIn('data/test/questions.jsonl', files)

    def test_public_split_counts_and_hash_match_manifest(self):
        manifest = json.loads((ROOT / 'data/split-manifest.json').read_text())
        raw = (ROOT / 'data/dev/questions.jsonl').read_bytes()
        rows = [json.loads(line) for line in raw.decode().splitlines()]
        self.assertEqual(len(rows), manifest['dev_count'])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), manifest['dev_sha256'])
        self.assertEqual(manifest['source_items'], 70)
        self.assertEqual(manifest['retained_public_items'] + 70 - manifest['duplicate_source_items'], manifest['dev_count'] + manifest['test_count'])
        self.assertGreaterEqual(manifest['counts']['test']['the_table'], 3)
        self.assertFalse(any(p in manifest for p in ['test_items', 'test_ids', 'test_questions']))

    def test_historical_example_does_not_become_a_v02_baseline(self):
        questions = constance.read_jsonl(ROOT / 'data/dev/questions.jsonl')
        card = constance.score(questions, constance.read_jsonl(ROOT / 'examples/answers-careful.jsonl'))
        self.assertEqual(card['totals'].get('pass'), 23)
        self.assertEqual(card['totals'].get('draft', 0), sum(q['status']=='draft' for q in questions))
        self.assertEqual(card['totals'].get('missing'), sum(q['status']=='confirmed' for q in questions)-23)

    def test_no_owner_credit_is_manufactured_for_imported_records(self):
        for q in constance.read_jsonl(ROOT / 'data/dev/questions.jsonl'):
            if not q.get('source_item'):
                continue
            source = q['source_item']
            self.assertEqual(q['question'], source['prompt'])
            self.assertEqual(q['sources'], source.get('sources', []))
            if q.get('reviewed_by') == 'Woody Wu':
                if q.get('review_basis') == 'recorded_owner_review':
                    self.assertEqual(q['owner_review']['reviewed_on'], q['reviewed_on'])
                    self.assertEqual(q['owner_review']['question_sha256'], hashlib.sha256(q['question'].encode('utf-8')).hexdigest())
                else:
                    self.assertEqual(source['status'], 'approved_by_woody_' + q['reviewed_on'])

    def test_october25_owner_approval_is_exactly_the_eleven_named_public_items(self):
        questions = constance.read_jsonl(ROOT / 'data/dev/questions.jsonl')
        approved = [q for q in questions if q.get('review_basis') == 'recorded_owner_review']
        self.assertEqual({q['source_id'] for q in approved}, set('ph-04 ph-05 ph-08 ph-14 ct-09 ct-12 ff-11 ff-12 ci-02 ci-03 fp-03'.split()))
        for q in approved:
            self.assertEqual(q['status'], 'confirmed')
            self.assertEqual(q['reviewed_by'], 'Woody Wu')
            self.assertEqual(q['reviewed_on'], '2026-10-25')
        self.assertFalse(any(q['status']=='draft' for q in questions))


if __name__ == "__main__":
    unittest.main()
