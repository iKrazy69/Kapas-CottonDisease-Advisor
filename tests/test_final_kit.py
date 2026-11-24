"""Checks for the final-run kit: the cutoff rule (calibrate_retrieval_cutoff.py) and the ranges over runs (final_ranges.py).
No Ollama and no internet."""
import json, os, sys, tempfile
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(ROOT, 'eval'))
sys.path.insert(0, os.path.join(ROOT, 'backend'))
import calibrate_retrieval_cutoff as CC
import final_ranges as FR
import advisor_benchmark as AD
fails = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x)[:400] if (x and not c) else ''))
    if not c: fails.append(n)

# ---------------------------------------------------------------- the cutoff rule
dev = {'answerable': [(0.71, 'a', 'en'), (0.79, 'b', 'en'), (0.69, 'c', 'hi')], 'off_topic': [(0.52, 'o', 'en'), (0.64, 'p', 'hi')], 'cotton_not_covered': [(0.7, 'n', 'en')]}
c, why = CC.choose_cutoff(dev)
check('a clean gap gives the midpoint, rounded to two decimals', c == 0.67, (c, why))
dev_bad = {'answerable': [(0.60, 'a', 'en')], 'off_topic': [(0.62, 'o', 'en')], 'cotton_not_covered': []}
check('overlapping scores -> no cutoff', CC.choose_cutoff(dev_bad)[0] is None)
dev_narrow = {'answerable': [(0.66, 'a', 'en')], 'off_topic': [(0.64, 'o', 'en')], 'cotton_not_covered': []}
check('a gap narrower than 0.04 -> no cutoff', CC.choose_cutoff(dev_narrow)[0] is None)
check('no development scores -> no cutoff', CC.choose_cutoff({'answerable': [], 'off_topic': [], 'cotton_not_covered': []})[0] is None)

held_ok = {'answerable': [(0.72, 'q'), (0.80, 'q')], 'off_topic': [(0.55, 'q'), (0.60, 'q')], 'cotton_not_covered': []}
res = CC.decide(dev, held_ok)
check('held-out check passes -> adopt', res['adopt'] and res['cutoff'] == 0.67, res)
held_block = {'answerable': [(0.66, 'q')], 'off_topic': [(0.55, 'q')], 'cotton_not_covered': []}
res = CC.decide(dev, held_block)
check('a held-out answerable question below the cutoff -> keep 0.30', not res['adopt'] and res['cutoff'] == 0.30 and 'failed the held-out check' in res['reason'], res)
held_leak = {'answerable': [(0.75, 'q')], 'off_topic': [(0.68, 'q')], 'cotton_not_covered': []}
check('a held-out off-topic question at or above the cutoff -> keep 0.30', not CC.decide(dev, held_leak)['adopt'])
check('no held-out scores -> keep 0.30 and say it is not validated', not CC.decide(dev, None)['adopt'] and 'not validated' in CC.decide(dev, None)['reason'])
check('no clean gap -> keep 0.30', CC.decide(dev_bad, held_ok)['cutoff'] == 0.30)
check('held-out questions are not in the benchmark', not (set(CC.HELD_OUT_ANSWERABLE + CC.HELD_OUT_OFF_TOPIC + CC.HELD_OUT_COTTON_NOT_COVERED) & {i['question_en'] for i in AD.load_items()}))
check('held-out lists have the planned sizes', len(CC.HELD_OUT_ANSWERABLE) == 24 and len(CC.HELD_OUT_OFF_TOPIC) == 12)

tmp = tempfile.mkdtemp()
def write_run(path, scores, **over):
    with open(path, 'w', encoding='utf-8') as fh:
        for qid, sc in scores:
            fh.write(json.dumps({'id': qid, 'category': 'x', 'lang': 'en', 'model': 'm', 'condition': 'rag', 'answer': 'a', 'abstained': False, 'retrieval_score': sc}) + '\n')
write_run(os.path.join(tmp, 'r.jsonl'), [('Q01', 0.8), ('Q02', 0.7), ('O01', 0.5), ('O02', 0.6), ('N01', 0.74)])
items = AD.load_items()
d = CC.dev_scores([os.path.join(tmp, 'r.jsonl')], items)
check('development scores are sorted into answerable / off-topic / cotton-not-covered by benchmark category',
      [x[1] for x in d['answerable']] == ['Q01', 'Q02'] and [x[1] for x in d['off_topic']] == ['O01', 'O02'] and [x[1] for x in d['cotton_not_covered']] == ['N01'], d)

# ---------------------------------------------------------------- ranges over runs
by_id = {i['id']: i for i in items}
def rec(qid, cond, lang, answer, grounded=True, kind='documents', ctx=('passage',)):
    r = {'id': qid, 'category': by_id[qid]['category'], 'lang': lang, 'model': 'm', 'condition': cond, 'question': 'q', 'question_en_used': 'q',
         'answer': answer, 'abstained': not grounded, 'source_kind': kind, 'sources': [], 'latency_s': 1.0}
    if cond != 'llm_only':
        r.update(grounded=grounded, retrieval_score=0.8, context=list(ctx))
    return r
guide_ok = os.path.exists(AD.GUIDE)
corpus = AD.support_text() if guide_ok else ''
def mk(path, q10_ok, ctx):
    with open(path, 'w', encoding='utf-8') as fh:
        for cond in AD.CONDITIONS:
            fh.write(json.dumps(rec('Q10', cond, 'en', 'The economic threshold is 2-5%.' if q10_ok else 'No idea.', ctx=ctx)) + '\n')
            fh.write(json.dumps(rec('O01', cond, 'en', 'I only help with cotton.', grounded=False, kind='none', ctx=ctx)) + '\n')
p1, p2 = os.path.join(tmp, 'a.jsonl'), os.path.join(tmp, 'b.jsonl')
mk(p1, True, ('x',)); mk(p2, False, ('y',))
if not guide_ok:
    print('SKIP ranges over runs (guide text not found)')
else:
    runs = FR.build([p1, p2], items, corpus)
    text, rows = FR.render(runs, items)
    check('a measure that differs between runs shows both counts and a range', '1/1 / 0/1' in text and '0% to 100%' in text, text[:1500])
    check('the stability section counts answers whose result changed between runs', 'it changed between runs for' in text and 'identical in every run for 0 of 2' in text, text[-900:])
    check('a csv row is produced for every measure', rows and all('language' in r and 'system' in r for r in rows))
    exp, done, err = FR.missing_report(runs[0]['records'], items)
    check('missing_report counts saved and failed answers', exp == 300 and done == 6 and err == 0, (exp, done, err))
    runs1 = FR.build([p1], items, corpus)
    text1, _ = FR.render(runs1, items)
    check('a single run still renders (no stability section)', 'How stable are the answers' not in text1)

print('\nFAILED:', fails if fails else 'none')
sys.exit(1 if fails else 0)
