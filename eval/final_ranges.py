"""
Put a range on every headline number by comparing several runs of the same benchmark.

Each run file is one full pass over the benchmark (50 questions x 3 systems x English/Hindi) with the same settings.
At temperature 0 the model gives the same answer to the same passages, so the runs differ only through the search (ties
between passages), the internet pages of the day and the translation step. The ranges below show how much that matters.

    python eval/final_ranges.py --runs eval/results/final_run_1.jsonl eval/results/final_run_2.jsonl eval/results/final_run_3.jsonl \
        --out-dir eval/results/final

Writes final_ranges.md and final_ranges.csv. Needs no Ollama and no internet.
"""
import argparse
import csv
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import advisor_benchmark as AD  # noqa: E402
from common import sign_test_p  # noqa: E402

ANSWERABLE_PAIRED = ('in_document', 'followup')


def per_run(records, items, corpus):
    """{(lang, condition): {metric: (count, n)}}, {(lang, 'A vs B'): (x, y, n)}, {(id, lang, condition): auto}, {(id, lang): context}"""
    rows = AD.scored(records, items, corpus)
    metrics, paired, autos, contexts = {}, {}, {}, {}
    for r, i, s in rows:
        autos[(r['id'], r['lang'], r['condition'])] = s['auto']
        if r['condition'] == 'rag' and r.get('context') is not None:
            contexts[(r['id'], r['lang'])] = tuple(r['context'])
    for lang in sorted({r['lang'] for r, _, _ in rows}):
        for cond in AD.CONDITIONS:
            sel = [(r, i, s) for r, i, s in rows if r['lang'] == lang and r['condition'] == cond]
            if not sel:
                continue
            m = {}
            for cat in AD.CATEGORY_ORDER:
                cs = [s for r, i, s in sel if i['category'] == cat]
                n = len(cs) - sum(1 for s in cs if s['auto'] == 'review')
                m['passed: ' + cat] = (sum(1 for s in cs if s['auto'] == 'pass'), n)
            ans = [s for r, i, s in sel if i['category'] in ('in_document', 'followup', 'conflict')]
            m['passed: all questions the guide can answer'] = (sum(1 for s in ans if s['auto'] == 'pass'), len(ans))
            answered = [s for r, i, s in sel if not s['abstained']]
            m['answers with a dose not in the guide'] = (sum(1 for s in answered if s['unsupported_vs_guide']), len(answered))
            metrics[(lang, cond)] = m

        def passes(cond):
            return {i['id']: s['auto'] == 'pass' for r, i, s in rows
                    if r['lang'] == lang and r['condition'] == cond and i['category'] in ANSWERABLE_PAIRED}
        for a, b in (('rag', 'llm_only'), ('rag_web', 'rag')):
            pa, pb = passes(a), passes(b)
            common = sorted(set(pa) & set(pb))
            if common:
                paired[(lang, f'{a} vs {b}')] = (sum(1 for k in common if pa[k] and not pb[k]),
                                                  sum(1 for k in common if pb[k] and not pa[k]), len(common))
    return metrics, paired, autos, contexts


def missing_report(records, items, models_langs=None):
    """Answers that failed or are absent in a run (so a run with holes is not mistaken for a complete one)."""
    expected = len(items) * len(AD.CONDITIONS) * 2
    done = len([r for r in records if 'error' not in r])
    return expected, done, len([r for r in records if 'error' in r])


def rate(k, n):
    return (k / n) if n else None


def fmt_pair(k, n):
    return f'{k}/{n}' if n else '-'


def fmt_range(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return '-'
    lo, hi = min(vals), max(vals)
    return f'{lo:.0%}' if lo == hi else f'{lo:.0%} to {hi:.0%}'


def build(run_paths, items, corpus):
    runs = []
    for p in run_paths:
        recs = AD.load_records(p)
        runs.append({'path': p, 'records': recs, 'out': per_run(recs, items, corpus)})
    return runs


def render(runs, items):
    k = len(runs)
    L = ['# Ranges over repeated runs', '',
         f'{k} run(s) of the same benchmark with the same settings: ' + ', '.join(os.path.basename(r['path']) for r in runs) + '.', '']
    for r in runs:
        exp, done, err = missing_report(r['records'], items)
        L.append(f'- {os.path.basename(r["path"])}: {done} answers saved, {err} failed (a full run has {exp}).')
    L += ['']
    csv_rows = []
    langs = sorted({lang for r in runs for (lang, _) in r['out'][0]})
    for lang in langs:
        L += [f'## Language: {lang}', '', '### Pass rate by system and question type (range over runs)', '',
              '| system | ' + ' | '.join(AD.CATEGORY_ORDER) + ' | all the guide can answer | answers with a dose not in the guide |',
              '|---|' + '---|' * (len(AD.CATEGORY_ORDER) + 2)]
        for cond in AD.CONDITIONS:
            if not any((lang, cond) in r['out'][0] for r in runs):
                continue
            cells = []
            names = ['passed: ' + c for c in AD.CATEGORY_ORDER] + ['passed: all questions the guide can answer', 'answers with a dose not in the guide']
            for name in names:
                per = [r['out'][0].get((lang, cond), {}).get(name) for r in runs]
                per = [p for p in per if p]
                rates = [rate(a, b) for a, b in per]
                cell = ' / '.join(fmt_pair(a, b) for a, b in per) + ' (' + fmt_range(rates) + ')' if per else '-'
                cells.append(cell)
                csv_rows.append({'language': lang, 'system': cond, 'measure': name,
                                 **{f'run{n + 1}': fmt_pair(*p) for n, p in enumerate(per)},
                                 'lowest_rate': min((x for x in rates if x is not None), default=''),
                                 'highest_rate': max((x for x in rates if x is not None), default='')})
            L.append(f'| {cond} | ' + ' | '.join(cells) + ' |')
        L += ['', 'Each cell: count in run 1 / run 2 / run 3 (lowest to highest rate). "web" answers that need a person to judge them are not counted as passed or failed.', '']
        L += ['### Paired comparison on the questions the guide answers (in_document + followup)', '',
              '| comparison | A only right (per run) | B only right (per run) | sign test p (per run) |', '|---|---|---|---|']
        for pair in ('rag vs llm_only', 'rag_web vs rag'):
            vals = [r['out'][1].get((lang, pair)) for r in runs]
            vals = [v for v in vals if v]
            if vals:
                L.append(f'| A = {pair.split(" vs ")[0]}, B = {pair.split(" vs ")[1]} | ' + ' / '.join(str(v[0]) for v in vals) + ' | ' +
                         ' / '.join(str(v[1]) for v in vals) + ' | ' + ' / '.join(f'{sign_test_p(v[0], v[1]):.3f}' for v in vals) + ' |')
                csv_rows.append({'language': lang, 'system': pair, 'measure': 'A only right / B only right / p',
                                 **{f'run{n + 1}': f'{v[0]} / {v[1]} / {sign_test_p(v[0], v[1]):.3f}' for n, v in enumerate(vals)}})
        L += ['']
    # how stable are single answers and the retrieved passages
    if k > 1:
        L += ['## How stable are the answers?', '']
        keys = set.intersection(*[set(r['out'][2]) for r in runs])
        changed = [key for key in keys if len({r['out'][2][key] for r in runs}) > 1]
        L.append(f'- Automatic result (pass / partial / fail / review) of an answer that is the same in every run: {len(keys) - len(changed)} of {len(keys)}; '
                 f'it changed between runs for {len(changed)}.')
        if changed:
            L.append('- Changed: ' + ', '.join(f'{i} {l} {c}' for i, l, c in sorted(changed)[:40]) + (' ...' if len(changed) > 40 else ''))
        ckeys = set.intersection(*[set(r['out'][3]) for r in runs])
        cchanged = [key for key in ckeys if len({r['out'][3][key] for r in runs}) > 1]
        L.append(f'- The passages handed to the model were identical in every run for {len(ckeys) - len(cchanged)} of {len(ckeys)} questions '
                 f'(question, language); they differed for {len(cchanged)}.')
        L.append('')
    L += ['## Limits', '',
          '- Three runs of one model on 50 draft questions give a range, not a confidence interval. They show run-to-run noise from the search, '
          'the internet and the translation step; they do not show how the system behaves on other questions.',
          '- The "passed" checks are automatic (key facts present, declined or not, doses not found in the guide). Human ratings are separate.']
    return '\n'.join(L) + '\n', csv_rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--runs', nargs='+', required=True)
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--bench', default=AD.BENCH)
    ap.add_argument('--guide', default=AD.GUIDE)
    a = ap.parse_args()
    items = AD.load_items(a.bench)
    corpus = AD.support_text(a.guide)
    runs = build(a.runs, items, corpus)
    text, rows = render(runs, items)
    os.makedirs(a.out_dir, exist_ok=True)
    with open(os.path.join(a.out_dir, 'final_ranges.md'), 'w', encoding='utf-8') as fh:
        fh.write(text)
    if rows:
        cols = []
        for r in rows:
            for c in r:
                if c not in cols:
                    cols.append(c)
        with open(os.path.join(a.out_dir, 'final_ranges.csv'), 'w', newline='', encoding='utf-8') as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
    print(text)


if __name__ == '__main__':
    main()
