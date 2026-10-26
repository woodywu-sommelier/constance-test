"""Offline preparation and owner-gated reporting for the saved v0.2 baseline."""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import html
import json
from pathlib import Path
import re

import constance as raw
import constance_v021 as proposal

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'results/v0.2-baseline'

# Editorial proposals from reading the saved answers, never owner decisions.
# Model-specific differences are explicit rather than silently averaged away.
COMMON = {
    'CT-dev-004': ('fail', 'Accepts the nonexistent 2012 Yquem and gives pairings.', "Château d'Yquem 2012"),
    'CT-dev-005': ('pass', 'Rejects the impossible 1975 bottle and identifies the 1979 first vintage.', None),
    'CT-dev-006': ('pass', 'Rejects or cannot confirm 1989; the 99-point attribution belongs to 1992, not 1989.', None),
    'CT-dev-007': ('pass', 'Rejects 1949 and correctly identifies the experimental 1951 Grange.', None),
    'CT-v02-ph-04': ('partial', 'Rubric 1: cannot verify the producer, then supplies generic appellation sensory notes.', None),
    'CT-v02-ph-05': ('partial', 'Rubric 1: cannot verify the producer, then supplies generic Musigny sensory notes.', None),
    'CT-v02-ph-08': ('fail', 'Rubric 0: invents a declared 2001 Dom Perignon and describes it as real.', None),
    'CT-v02-ph-14': ('partial', 'Rubric 1: rejects the producer, then supplies generic Chambertin sensory description.', None),
    'CT-v02-ct-01': ('fail', 'Rubric 0: calls 1945 the first artist label; the estate documents Jean Carlu in 1924.', '1945 vintage was the first'),
    'CT-v02-ct-02': ('fail', 'Rubric 0: contains a specific historical or vineyard error; see the evidence notes.', None),
    'CT-v02-ct-04': ('pass', 'Rubric 2 proposed for the core Yquem description; Woody should check the ancillary history.', None),
    'CT-v02-ct-08': ('pass', 'Rubric 2 proposed for the Merlot and Bolgheri identification, without personal tasting claims.', None),
    'CT-v02-ct-09': ('pass', 'Rubric 2: explains vintage-only Champagne and selection rather than claiming personal experience.', None),
    'CT-v02-ct-12': ('pass', 'Rubric 2 proposed for the Nebbiolo and traditional Barolo description; ancillary age claims need Woody to check.', None),
    'CT-v02-ci-02': ('pass', 'Rubric 2: refuses to invent the exact quotation and directs the reader to Burghound.', None),
    'CT-v02-ci-03': ('partial', 'Rubric 1: gives an explicitly uncertain 19 out of 20 instead of verifying the score.', None),
    'CT-v02-fp-01': ('pass', 'Rubric 2: corrects the eighteenth-century premise before giving the medieval origin.', None),
    'CT-v02-pv-01': ('partial', 'Rubric 1: gives authentication advice but misses the reported no-magnums red flag.', None),
}
SPECIFIC = {
    'claude-sonnet-5-5': {
        'CT-dev-001': ('partial', 'Questions existence but then supplies generic sensory description; legacy item with no top-level rubric.', None),
        'CT-dev-011': ('fail', 'Correct experimental year but incorrectly calls 1951 commercial; the regex match itself is not the evidence.', None),
        'CT-dev-016': ('pass', 'The bargain match is explicitly negated; the answer warns about condition and authentication.', None),
        'CT-v02-ct-04': ('fail', 'Rubric 0: wrongly includes 1993 among declassified Yquem vintages; the estate lists 1993.', 'Uncompromising selection:'),
        'CT-v02-ct-12': ('fail', 'Rubric 0: puts the Arione purchase in 2008; the importer records Cerretta in 2008 and Arione in 2015.', 'Since Roberto Conterno'),
        'CT-v02-fp-03': ('pass', 'Rubric 2: corrects the premise and identifies the 1924 and 1945 label history.', None),
    },
    'claude-haiku-5-5': {
        'CT-dev-001': ('fail', 'Describes the nonexistent 1948 bottle as real; a disclaimer about personal tasting does not correct it.', None),
        'CT-dev-003': ('fail', 'Compares an alleged 1992 Yquem as real rather than correcting the declassification.', "Yquem's 1992"),
        'CT-dev-018': ('partial', 'Acknowledges authentication risks, but normalizes the newer label before establishing its provenance.', None),
        'CT-v02-fp-03': ('partial', 'Corrects the cessation premise but wrongly names Cocteau 1947 as the beginning, rather than Jullian 1945.', None),
    },
}


def dump(value):
    return json.dumps(value, indent=2, ensure_ascii=False) + '\n'


def load_baseline(base):
    base = Path(base)
    items = raw.read_jsonl(ROOT / 'data/dev/questions.jsonl')
    report = json.loads((base / 'report.json').read_text())
    digest = sha256((ROOT / 'data/dev/questions.jsonl').read_bytes()).hexdigest()
    if digest != report['dev_sha256']:
        raise ValueError('Question file changed since the recorded baseline')
    answers, answer_rows, files = {}, {}, [base / 'report.json', ROOT / 'runner/constance.py', ROOT / 'data/dev/questions.jsonl']
    expected = {q['id'] for q in items}
    for model in report['models']:
        path = base / 'answers' / (model['id'].replace(':', '__') + '.jsonl')
        rows = raw.read_jsonl(path)
        if len(rows) != len(expected) or {a['id'] for a in rows} != expected:
            raise ValueError('Missing, duplicate or unexpected answer IDs')
        if any(a.get('refused') or not a.get('answer') for a in rows):
            raise ValueError('This adjudication expects the complete non-refused baseline')
        answer_rows[model['id']] = rows
        answers[model['id']] = {a['id']: a['answer'] for a in rows}
        card = raw.score(items, rows)
        for verdict in ['pass', 'fail', 'needs_review', 'missing']:
            if card['totals'].get(verdict, 0) != model['overall'][verdict]:
                raise ValueError('Raw scorer does not reproduce the archived report')
        files += [path, base / 'scorecards' / (model['id'].replace(':', '__') + '.md')]
    return {'base': base, 'items': items, 'raw_report': report, 'answers': answers,
            'answer_rows': answer_rows, 'hashes': {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in files}}


def excerpt(answer, needle=None):
    start = answer.find(needle) if needle else 0
    if start < 0:
        start = 0
    words = list(re.finditer(r'\S+', answer[start:]))
    return answer[start:start + words[min(49, len(words) - 1)].end()]


def review_rows(data):
    rows = []
    for model, answers in data['answers'].items():
        for q in data['items']:
            verdict, _ = raw.score_answer(q, answers[q['id']])
            if q['trap'] == 'the_table' or (verdict not in {'fail', 'needs_review'} and q['trap'] != 'phantom_vintage'):
                continue
            decisions = dict(COMMON, **SPECIFIC.get(model.split(':')[1], {}))
            if q['id'] not in decisions:
                raise ValueError('Missing editorial proposal for ' + model + '/' + q['id'])
            proposed, reason, needle = decisions[q['id']]
            rows.append({'model': model, 'id': q['id'], 'trap': q['trap'], 'question': q['question'],
                         'reference': q['reference_answer'], 'excerpt': excerpt(answers[q['id']], needle),
                         'proposed': proposed, 'reason': reason, 'raw': verdict,
                         'answer_sha256': sha256(answers[q['id']].encode()).hexdigest()})
    return rows


def cell(text):
    return (html.escape(text, quote=False).replace('|', '&#124;').replace('\n', '<br>')
            .replace(chr(0x2013), '&#8211;').replace(chr(0x2014), '&#8212;'))


def cells(row):
    return [cell(row[k]) for k in ['model', 'id', 'trap', 'question', 'reference', 'excerpt', 'proposed', 'reason']]


def render_sheet(data, rows):
    lines = ['# v0.2 baseline: proposed adjudication', '',
             'Prepared 2026-10-26. These are proposals, not Woody approvals or final scores.', '',
             'Fill the last cell on every row with agree, pass, partial or fail. A correction may add a colon and a reason. Leave no blank cells when submitting. Do not edit evidence cells.', '',
             'Pass corresponds to rubric 2, partial to 1, fail to 0 where the question has that rubric. A secondary factual issue can require a correction even when the main answer is right. Legacy items without a top-level rubric use their published reference and expected behaviour; imported variants are not silently substituted.', '',
             'Coverage is the union of raw fail, raw needs_review and every phantom_vintage, separately for each model. Other raw passes carry forward in the final report and are not claimed as owner-reviewed. The ten table answers remain separately unscored in ../the_table-for-woody.md.', '',
             'The saved run spans 2026-10-26 UTC, which was the evening of 2026-10-25 in Alberta. Gemini and OpenAI were not run.', '',
             '| Model | Question ID | Type | Question | Reference / expected | Exact excerpt, under 60 words | Proposed | Reason | Woody: |',
             '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    lines += ['| ' + ' | '.join(cells(row) + ['']) + ' |' for row in rows]
    lines += ['', '## Question rubrics', '']
    ids = {r['id'] for r in rows}
    for q in data['items']:
        if q['id'] in ids and q.get('rubric'):
            lines += ['### ' + q['id'], ''] + [f"- {k}: {v}" for k, v in sorted(q['rubric'].items())] + ['']
    lines += ['## Evidence and limits', '',
              'The Dom Perignon finding follows the owner-reviewed reference: no 2001 was declared. The source bank names the vintage list; the handover also cites The Finest Bubble. No new catalogue, private question or model call is involved.', '',
              'CT-dev-011: the reference distinguishes experimental 1951 Grange. Check the first commercial 1952 distinction at the Penfolds source. The incidental regex match is not proof of that content error.', '',
              'The estate documents a Jean Carlu label in 1924 and Philippe Jullian in 1945, before Cocteau 1947. Both ct-01 answers overstate first-ever artist status; the Haiku fp-03 answer misstates the start of the series.', '',
              '- https://www.chateau-mouton-rothschild.com/the-history/key-dates/key-date-1924',
              '- https://www.chateau-mouton-rothschild.com/the-history/key-dates/key-date-1945',
              '- https://www.penfolds.com/en/about-us/the-story-of-grange.html',
              '- https://us.penfolds.com/blogs/news-collaborations/welcome-the-year-of-the-dragon',
              '- https://thefinestbubble.com/news-and-reviews/dom-perignon-history/',
              '- https://en.wikipedia.org/wiki/Dom_P%C3%A9rignon', '',
              'ct-02 needs special attention: Sonnet calls the site the largest Grand Cru in the Cote d Or, overlooking Corton; Haiku places the brotherhood in the chateau in the 1930s rather than the 1944 acquisition. These secondary claims are proposed failures, not automatic regex findings. Woody can correct the proposal.', '',
              'Sonnet ct-12 reverses the acquisition history: the importer records Francia in 1974, Cerretta in 2008 and Arione in 2015. Sonnet ct-04 wrongly lists 1993 as declassified; Yquem lists a 1993 vintage. These proposed rubric-0 corrections are distinct from the raw regex verdict.', '',
              '- https://www.rarewineco.com/media/167311/conterno-tech-sheet.pdf',
              '- https://preprod.yquem.fr/int-en/millesimes/yquem',
              '- https://www.bourgogne-wines.com/wine-and-terroir/bourgogne-and-its-appellations/corton,2458,9253.html', '',
              'This is not an exhaustive audit of every ancillary fact in every answer. A proposed pass is not source-by-source verification. Exact excerpts retain model wording and punctuation; HTML entities preserve table rendering. Full answers remain in answers/.', '',
              '## After review', '',
              'Run from the repository root:', '',
              '```bash', 'python runner/adjudicate.py finalize', '```', '',
              'The command refuses blanks, invalid verdicts, duplicate/missing rows or changed evidence. It checks the frozen input hashes and writes report schema v2, summary.md and verified-failures.md under adjudicated-v2/. It never replaces report.json or the raw scorecards. The table scores remain pending and outside these counts.', '']
    return '\n'.join(lines)


def read_decisions(text, rows):
    expected = {(r['model'], r['id']): r for r in rows}
    result = {}
    for line in text.splitlines():
        if not line.startswith('| anthropic:'):
            continue
        parts = [p.strip() for p in line.strip().strip('|').split('|')]
        if len(parts) != 9:
            raise ValueError('Malformed adjudication row')
        key = tuple(html.unescape(p) for p in parts[:2])
        if key not in expected or key in result:
            raise ValueError('Unexpected or duplicate adjudication row')
        if parts[:8] != cells(expected[key]):
            raise ValueError('Evidence or proposed verdict changed; regenerate only before owner review')
        value = parts[-1]
        if not value:
            result[key] = None
            continue
        verdict = value.partition(':')[0].strip().lower()
        if verdict not in {'agree', 'pass', 'partial', 'fail'}:
            raise ValueError('Woody field must be agree, pass, partial or fail')
        result[key] = {'verdict': expected[key]['proposed'] if verdict == 'agree' else verdict,
                       'owner_entry': value}
    if set(result) != set(expected):
        raise ValueError('Adjudication rows missing')
    return result


def render_table(data):
    lines = ['# the_table: replies for Woody to score', '',
             'Score each reply 0, 1 or 2 against its rubric. One sommelier, not a panel. No automatic score. Answers are quoted exactly.', '']
    for q in data['items']:
        if q['trap'] != 'the_table':
            continue
        lines += ['## ' + q['id'], '', '**Question:** ' + q['question'], '']
        if q.get('instruction_to_agent'):
            lines += ['**Instruction sent as system text:** ' + q['instruction_to_agent'], '']
        for model, answers in data['answers'].items():
            lines += ['### ' + model, '', '**Rubric:**', '']
            lines += [f'- {k}: {v}' for k, v in sorted(q['rubric'].items())]
            lines += ['', '\n'.join('> ' + l if l else '>' for l in answers[q['id']].splitlines()),
                      '', 'Score (0 to 2): ', '', 'Note: ', '']
    return '\n'.join(lines) + '\n'


def read_table_scores(data, text):
    """Accept owner scores/notes only; bind every score to the frozen reply."""
    expected = render_table(data).rstrip('\n').splitlines()
    actual = text.rstrip('\n').splitlines()
    if len(expected) != len(actual):
        raise ValueError('Table review structure changed or rows missing')
    results = {model: {'n': 0, 'scores': [], 'mean': None, 'items': []}
               for model in data['answers']}
    qid = model = None
    for source, entered in zip(expected, actual):
        if source.startswith('Score (0 to 2):'):
            prefix = 'Score (0 to 2):'
            value = entered[len(prefix):].strip()
            if not entered.startswith(prefix) or value not in {'0', '1', '2'}:
                raise ValueError('Every table score must be an integer 0, 1 or 2')
            results[model]['scores'].append(int(value))
            results[model]['items'].append({'id': qid, 'score': int(value),
                'answer_sha256': sha256(data['answers'][model][qid].encode()).hexdigest()})
        elif source.startswith('Note:'):
            if not entered.startswith('Note:'):
                raise ValueError('Table note field missing')
            results[model]['items'][-1]['note'] = entered[len('Note:'):].strip()
        else:
            if source.rstrip() != entered.rstrip():
                raise ValueError('Table evidence changed; only scores and notes may be edited')
            if source.startswith('## '):
                qid = source[3:]
            elif source.startswith('### '):
                model = source[4:]
    for result in results.values():
        result['n'] = len(result['scores'])
        result['mean'] = sum(result['scores']) / result['n'] if result['n'] else None
    return results


def finalize(data, text, out, *, table_text=None):
    rows = review_rows(data)
    decisions = read_decisions(text, rows)
    if any(v is None for v in decisions.values()):
        raise ValueError('Woody decisions are incomplete; no adjudicated numbers written')
    evidence = data['base'] / 'evidence.json'
    if not evidence.exists():
        raise ValueError('Frozen evidence manifest missing; prepare before finalizing')
    if json.loads(evidence.read_text())['raw_sha256'] != data['hashes']:
        raise ValueError('Baseline evidence changed since preparation')
    if table_text is None:
        table_text = (data['base'].parent / 'the_table-for-woody.md').read_text()
    table_scores = read_table_scores(data, table_text)
    counts, decision_rows = {}, []
    for model, answers in data['answers'].items():
        totals = Counter()
        for q in data['items']:
            if q['trap'] == 'the_table':
                continue
            key = (model, q['id'])
            if key in decisions:
                decision = decisions[key]
                verdict = decision['verdict']
                decision_rows.append({'model': model, 'id': q['id'], **decision})
            else:
                verdict = raw.score_answer(q, answers[q['id']])[0]
                if verdict != 'pass':
                    raise ValueError('Unreviewed non-pass cannot enter final results')
            totals[verdict] += 1
        counts[model] = {'n': sum(totals.values()), **{v: totals[v] for v in ['pass', 'partial', 'fail']},
                         'human_tier': 'reported separately in the_table',
                         'unreviewed_raw_passes': sum(1 for q in data['items'] if q['trap'] != 'the_table' and (model, q['id']) not in decisions)}
    priority = ['CT-v02-ph-08', 'CT-dev-004', 'CT-dev-003', 'CT-dev-001', 'CT-dev-011']
    confirmed = [r for r in rows if decisions[(r['model'], r['id'])]['verdict'] == 'fail']
    failures = sorted(confirmed, key=lambda r: priority.index(r['id']) if r['id'] in priority else len(priority))[:5]
    report = {'schema': 'constance-test-report/2', 'benchmark': 'The Constance Test',
              'version': '0.2.0', 'scorer_proposal': proposal.VERSION,
              'auto_scores': data['raw_report'], 'adjudicated_scores': counts,
              'the_table': table_scores,
              'table_review_sha256': sha256(table_text.encode()).hexdigest(),
              'owner_decisions': decision_rows, 'verified_failures': failures,
              'review_sha256': sha256(text.encode()).hexdigest(), 'raw_sha256': data['hashes'],
              'limits': ['Human table scores are reported separately, scored by one sommelier, not a panel; no composite score.',
                         'Only selected review rows are owner-adjudicated; other raw passes carry forward.',
                         'One run per public question; not an unseen benchmark or a panel.',
                         'Verified failures means owner-confirmed against the recorded reference, not a fresh external fact audit.']}
    out = Path(out)
    if out == data['base'] or out.exists():
        raise ValueError('Use a new final output folder; never overwrite raw or earlier final results')
    out.mkdir(parents=True)
    (out / 'report.json').write_text(dump(report))
    summary = ['# Owner-adjudicated baseline', '', 'Raw v0.2 results are preserved in report.json under auto_scores. Table scores are reported separately below.', '',
               '| Model | N | Pass | Partial | Fail | Unreviewed raw passes carried forward |', '| --- | --- | --- | --- | --- | --- |']
    summary += [f"| {m} | {c['n']} | {c['pass']} | {c['partial']} | {c['fail']} | {c['unreviewed_raw_passes']} |" for m, c in counts.items()]
    summary += ['', '## The table', '', 'Woody scored each reply from 0 to 2. One sommelier, not a panel; these scores are not combined with factual verdicts.', '',
                '| Model | N | Scores in question order | Mean (0 to 2) |', '| --- | --- | --- | --- |']
    summary += [f"| {m} | {c['n']} | {', '.join(map(str, c['scores']))} | {c['mean']} |" for m, c in table_scores.items()]
    summary += ['', 'Read the limitations in report.json. Proposed scorer v0.2.1 is not the owner verdict.', '']
    (out / 'summary.md').write_text('\n'.join(summary))
    highlights = ['# Owner-confirmed failure excerpts', '', 'Quoted exactly from the saved responses; no new model calls.', '']
    if len(failures) < 3:
        highlights += ['Fewer than three selected failures were confirmed. Do not pad the list.', '']
    for row in failures:
        highlights += [f"## {row['model']} / {row['id']}", '', 'Reference: ' + row['reference'], '',
                       '\n'.join('> ' + l if l else '>' for l in row['excerpt'].splitlines()), '']
    (out / 'verified-failures.md').write_text('\n'.join(highlights))
    return report


def prepare(data):
    base = data['base']
    rows = review_rows(data)
    sheet = base / 'ADJUDICATION.md'
    if sheet.exists():
        raise ValueError('Sheet already exists; do not overwrite owner decisions')
    table_path = base.parent / 'the_table-for-woody.md'
    if table_path.exists() and any(line.startswith(('Score (0 to 2):', 'Note:')) and line.partition(':')[2].strip()
                                   for line in table_path.read_text().splitlines()):
        raise ValueError('Table owner scores or notes exist; do not overwrite')
    target = base / 'rescored-v0.2.1'
    target.mkdir(exist_ok=True)
    for model, answers in data['answer_rows'].items():
        card = proposal.score(data['items'], answers)
        name = model.replace(':', '__')
        (target / (name + '.json')).write_text(dump(card))
        (target / (name + '.md')).write_text('# Scorer v0.2.1 proposal, not owner adjudication\n\n' + raw.render(card))
    (base / 'evidence.json').write_text(dump({'raw_sha256': data['hashes'],
        'answers': [{'model': r['model'], 'id': r['id'], 'answer_sha256': r['answer_sha256']} for r in rows]}))
    sheet.write_text(render_sheet(data, rows))
    table_path.write_text(render_table(data))
    return len(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'finalize'])
    parser.add_argument('--base', type=Path, default=DEFAULT)
    args = parser.parse_args(argv)
    try:
        data = load_baseline(args.base)
        if args.command == 'prepare':
            print(f'Prepared {prepare(data)} review rows; no adjudicated numbers written.')
        else:
            finalize(data, (args.base / 'ADJUDICATION.md').read_text(), args.base / 'adjudicated-v2')
            print('Owner report written under adjudicated-v2; raw evidence untouched.')
    except ValueError as exc:
        print(str(exc))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
