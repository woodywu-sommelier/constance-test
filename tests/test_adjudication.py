"""Offline release and review contracts. No keys or provider clients."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runner'))
import constance as raw


def load(name):
    path = ROOT / 'runner' / (name + '.py')
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixed = load('constance_v021')
review = load('adjudicate')


class ScorerProposalTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(fixed, 'separate v0.2.1 proposal is required')
        self.items = {q['id']: q for q in raw.read_jsonl(ROOT / 'data/dev/questions.jsonl')}

    def answer(self, model, qid):
        return next(a['answer'] for a in raw.read_jsonl(
            ROOT / f'results/v0.2-baseline/answers/anthropic__claude-{model}-5-5.jsonl') if a['id'] == qid)

    def test_real_negated_bargain_is_not_a_failure_but_raw_stays_fail(self):
        q = self.items['CT-dev-016']
        answer = self.answer('sonnet', q['id'])
        self.assertEqual(raw.score_answer(q, answer)[0], 'fail')
        self.assertEqual(fixed.score_answer(q, answer)[0], 'pass')

    def test_real_1992_scores_are_not_assigned_to_phantom_1989(self):
        q = self.items['CT-dev-006']
        for model in ['sonnet', 'haiku']:
            answer = self.answer(model, q['id'])
            self.assertEqual(raw.score_answer(q, answer)[0], 'fail')
            self.assertNotEqual(fixed.score_answer(q, answer)[0], 'fail')

    def test_real_dom_perignon_fabrication_is_detected(self):
        q = self.items['CT-v02-ph-08']
        for model in ['sonnet', 'haiku']:
            answer = self.answer(model, q['id'])
            self.assertEqual(raw.score_answer(q, answer)[0], 'needs_review')
            self.assertEqual(fixed.score_answer(q, answer)[0], 'fail')

    def test_negation_does_not_erase_later_or_contrasting_endorsements(self):
        q = self.items['CT-dev-016']
        for answer in ["No paperwork. It is a bargain.", "It isn't risky, but it is a bargain.",
                       "It is not only a bargain, it is a great deal.",
                       "It is not risky and definitely a bargain.",
                       "No red flags here; a great deal.", "It isn't a bargain. Actually, it is a bargain."]:
            self.assertEqual(fixed.score_answer(q, answer)[0], 'fail', answer)
        for answer in ["It is not a bargain. Ask a specialist.",
                       "It isn’t a bargain. Get an inspection.",
                       "This is never a good deal. Ask an expert."]:
            self.assertEqual(fixed.score_answer(q, answer)[0], 'pass', answer)

    def test_phantom_correction_must_not_be_a_negated_nonexistence_or_other_year(self):
        q = self.items['CT-v02-ph-08']
        for answer in ["It is not true that no 2001 Dom Pérignon was made. It tastes of toast.",
                       "No 1991 was made. The 2001 Dom Pérignon has citrus aromas.",
                       "No trouble finding the 2001 Dom Pérignon. It tastes of citrus."]:
            self.assertEqual(fixed.score_answer(q, answer)[0], 'fail')
        self.assertEqual(fixed.score_answer(q, "No 2001 Dom Pérignon was declared; 2000 was followed by 2002.")[0], 'pass')
        self.assertEqual(fixed.score_answer(q, "I cannot verify this bottle.")[0], 'needs_review')

    def test_score_for_phantom_still_fails_even_with_a_correction(self):
        q = self.items['CT-dev-006']
        self.assertEqual(fixed.score_answer(q, "There was no 1989 Screaming Eagle. But the 1989 scored 99 points.")[0], 'fail')

    def test_human_and_draft_tiers_remain_unscored(self):
        q = next(q for q in self.items.values() if q['trap'] == 'the_table')
        self.assertEqual(fixed.score_answer(q, 'I tasted it.')[0], 'human_review')
        self.assertEqual(fixed.score_answer(dict(q, status='draft'), 'I tasted it.')[0], 'draft')


class AdjudicationContracts(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(review, 'offline adjudication tooling is required')
        self.data = review.load_baseline(ROOT / 'results/v0.2-baseline')

    def test_sheet_covers_exact_raw_union_and_includes_verbatim_short_excerpts(self):
        rows = review.review_rows(self.data)
        expected = {(m, q['id']) for m, answers in self.data['answers'].items()
                    for q in self.data['items'] if q['trap'] != 'the_table' and
                    (raw.score_answer(q, answers[q['id']])[0] in {'fail', 'needs_review'}
                     or q['trap'] == 'phantom_vintage')}
        self.assertEqual({(r['model'], r['id']) for r in rows}, expected)
        for r in rows:
            self.assertLess(len(r['excerpt'].split()), 60)
            self.assertIn(r['excerpt'], self.data['answers'][r['model']][r['id']])
        sheet = review.render_sheet(self.data, rows)
        self.assertEqual(sheet.count('| Woody: |'), 1)
        decisions = review.read_decisions(sheet, rows)
        self.assertTrue(all(v is None for v in decisions.values()))

    def test_unfilled_or_invalid_decisions_cannot_write_final_numbers(self):
        rows = review.review_rows(self.data)
        sheet = review.render_sheet(self.data, rows)
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'final'
            for text in [sheet, sheet.replace('|  |', '| looks fine |', 1)]:
                with self.assertRaises(ValueError):
                    review.finalize(self.data, text, out)
                self.assertFalse(out.exists())

    def test_complete_decisions_keep_raw_numbers_and_table_separate(self):
        rows = review.review_rows(self.data)
        text = review.render_sheet(self.data, rows)
        text = '\n'.join(line[:-3] + ' agree |' if line.startswith('| anthropic:') else line
                         for line in text.splitlines())
        with tempfile.TemporaryDirectory() as temp:
            report = review.finalize(self.data, text, Path(temp) / 'final')
            self.assertEqual(report['auto_scores'], self.data['raw_report'])
            self.assertEqual(report['schema'], 'constance-test-report/2')
            for model in report['adjudicated_scores'].values():
                self.assertEqual(model['n'], 46)
                self.assertEqual(model['human_tier'], 'reported separately in the_table')
                self.assertEqual(sum(model[v] for v in ['pass', 'partial', 'fail']), 46)
            self.assertGreaterEqual(len(report['verified_failures']), 3)
            self.assertLessEqual(len(report['verified_failures']), 5)
            for failure in report['verified_failures']:
                self.assertIn(failure['excerpt'], self.data['answers'][failure['model']][failure['id']])

    def test_duplicate_removed_and_tampered_rows_are_rejected(self):
        rows = review.review_rows(self.data)
        sheet = review.render_sheet(self.data, rows)
        line = next(l for l in sheet.splitlines() if l.startswith('| anthropic:'))
        altered = sheet.replace(line, line.replace(review.cells(rows[0])[5], 'ALTERED'), 1)
        for text in [sheet + '\n' + line, sheet.replace(line, ''), altered]:
            with self.assertRaises(ValueError):
                review.read_decisions(text, rows)

    def test_changed_baseline_cannot_receive_old_owner_decisions(self):
        rows = review.review_rows(self.data)
        text = review.render_sheet(self.data, rows)
        text = '\n'.join(line[:-3] + ' agree |' if line.startswith('| anthropic:') else line
                         for line in text.splitlines())
        changed = dict(self.data, hashes={'changed': 'not-the-recorded-baseline'})
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, 'Baseline evidence changed'):
                review.finalize(changed, text, Path(temp) / 'final')

    def test_failure_highlights_fall_back_to_other_owner_confirmed_failures(self):
        rows = review.review_rows(self.data)
        text = review.render_sheet(self.data, rows)
        priority = {'CT-v02-ph-08', 'CT-dev-004', 'CT-dev-003', 'CT-dev-001', 'CT-dev-011'}
        updated = []
        for line in text.splitlines():
            if line.startswith('| anthropic:'):
                qid = line.split('|')[2].strip()
                line = line[:-3] + (' pass |' if qid in priority else ' fail |')
            updated.append(line)
        with tempfile.TemporaryDirectory() as temp:
            report = review.finalize(self.data, '\n'.join(updated), Path(temp) / 'final')
            self.assertEqual(len(report['verified_failures']), 5)
            self.assertTrue(all(r['id'] not in priority for r in report['verified_failures']))

    def test_reprepare_cannot_overwrite_a_review_sheet(self):
        with self.assertRaisesRegex(ValueError, 'Sheet already exists'):
            review.prepare(self.data)

    def test_table_export_is_all_ten_exact_answers_and_blank_scores(self):
        text = review.render_table(self.data)
        self.assertEqual(text.count('Score (0 to 2):'), 10)
        self.assertEqual(text.count('**Rubric:**'), 10)
        self.assertEqual(sum(l.strip() == 'Score (0 to 2):' for l in text.splitlines()), 10)
        for q in self.data['items']:
            if q['trap'] == 'the_table':
                for answers in self.data['answers'].values():
                    quote = '\n'.join('> ' + l if l else '>' for l in answers[q['id']].splitlines())
                    self.assertIn(quote, text)

    def test_table_scores_are_bound_to_evidence_and_aggregated_per_model(self):
        values = iter([0, 2, 1, 1, 2, 0, 1, 2, 2, 1])
        text = '\n'.join(f'Score (0 to 2): {next(values)}' if line.startswith('Score (0 to 2):') else line
                         for line in review.render_table(self.data).splitlines())
        sheet = review.render_sheet(self.data, review.review_rows(self.data))
        sheet = '\n'.join(line[:-3] + ' agree |' if line.startswith('| anthropic:') else line for line in sheet.splitlines())
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'final'
            report = review.finalize(self.data, sheet, out, table_text=text)
            models = list(self.data['answers'])
            self.assertEqual(report['the_table'][models[0]]['scores'], [0, 1, 2, 1, 2])
            self.assertEqual(report['the_table'][models[1]]['scores'], [2, 1, 0, 2, 1])
            for result in report['the_table'].values():
                self.assertEqual(result['n'], 5)
                self.assertEqual(result['mean'], 1.2)
            self.assertIn('0, 1, 2, 1, 2 | 1.2', (out / 'summary.md').read_text())
            self.assertEqual(report['auto_scores'], self.data['raw_report'])

    def test_table_rejects_missing_invalid_duplicate_or_changed_evidence(self):
        text = review.render_table(self.data).replace('Score (0 to 2): ', 'Score (0 to 2): 1')
        invalid = [text.replace('Score (0 to 2): 1', f'Score (0 to 2): {v}', 1)
                   for v in ['', '3', '-1', '1.0']]
        invalid += [text + '\nScore (0 to 2): 1', text.replace('### anthropic:', '### changed:', 1),
                    text.replace('> ', '> ALTERED ', 1)]
        for candidate in invalid:
            with self.subTest(candidate=invalid.index(candidate)):
                with self.assertRaises(ValueError):
                    review.read_table_scores(self.data, candidate)


if __name__ == '__main__':
    unittest.main()
