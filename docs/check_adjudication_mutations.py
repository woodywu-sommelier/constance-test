"""Run guard mutations in disposable public-only copies, never in the checkout."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ('table-mean', 'runner/adjudicate.py',
     "sum(result['scores']) / result['n'] if result['n'] else None",
     '1.0',
     'test_table_scores_are_bound_to_evidence_and_aggregated_per_model'),
    ('negation', 'runner/constance_v021.py',
     'if local_negation(answer, match.start()) or other_vintage_score(item, answer, match):',
     'if False or other_vintage_score(item, answer, match):',
     'test_real_negated_bargain_is_not_a_failure_but_raw_stays_fail'),
    ('owner-gate', 'runner/adjudicate.py',
     "raise ValueError('Woody decisions are incomplete; no adjudicated numbers written')",
     "decisions = {k: v or {'verdict': 'pass', 'owner_entry': 'MUTATION'} for k, v in decisions.items()}",
     'test_unfilled_or_invalid_decisions_cannot_write_final_numbers'),
]


def main():
    evidence = []
    for name, relative, before, after, test in CASES:
        with tempfile.TemporaryDirectory(prefix='constance-adjudication-') as temp:
            target = Path(temp)
            for folder in ['runner', 'tests', 'huggingface', 'examples', 'data/dev', 'results/v0.2-baseline']:
                shutil.copytree(ROOT / folder, target / folder,
                                ignore=shutil.ignore_patterns('__pycache__', 'adjudicated-v2'))
            for file in ['data/split-manifest.json', 'README.md', 'REVIEW.md', 'LICENSE-DATA', 'rubric.md', 'CITATION.cff', 'results/the_table-for-woody.md']:
                dest = target / file
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / file, dest)
            # Raw-hash paths are repo-relative, so an identical scratch copy validates.
            path = target / relative
            text = path.read_text()
            assert text.count(before) == 1
            path.write_text(text.replace(before, after))
            run = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                                  '-p', 'test_adjudication.py'], cwd=target,
                                 capture_output=True, text=True)
            expected_failure = f'FAIL: {test}' in run.stderr
            evidence.append({'mutation': name, 'exit_code': run.returncode,
                             'intended_test_failed': expected_failure})
    print(json.dumps(evidence, indent=2))
    return 0 if all(e['exit_code'] and e['intended_test_failed'] for e in evidence) else 1


if __name__ == '__main__':
    raise SystemExit(main())
