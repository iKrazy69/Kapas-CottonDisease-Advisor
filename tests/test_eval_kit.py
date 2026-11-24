"""Checks for the evaluation kit in eval/: statistics, abstention study, dose audit, benchmark file, advisor runner.
No Ollama and no internet. The part that needs images (scikit-learn, OpenCV) is skipped if they are not installed."""
import csv, json, os, re, shutil, subprocess, sys, tempfile, types
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
EVAL = os.path.join(ROOT, 'eval')
sys.path.insert(0, EVAL)
sys.path.insert(0, os.path.join(ROOT, 'backend'))
import numpy as np
fails = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x)[:400] if (x and not c) else ''))
    if not c: fails.append(n)
def skip(n, why): print('SKIP ' + n + ' (' + why + ')')

import common as C
import abstention_study as AB
import advisor_benchmark as AD
import build_benchmark as BB
import kb_audit as KB

# ---------------------------------------------------------------- statistics
lo, hi = C.wilson(47, 52)
check('Wilson interval for 47/52 is about 79.4% to 96.1%', abs(lo - 0.794) < 0.003 and abs(hi - 0.961) < 0.003, (lo, hi))
check('Wilson with n = 0 gives nothing, not a crash', C.wilson(0, 0) == (None, None) and C.fmt_rate(0, 0) == '0/0 = n/a')
check('Wilson for 0/2 is wide (small samples look wide)', C.wilson(0, 2)[1] > 0.6)
check('sign test: 10 vs 0 is significant, 5 vs 5 is not, no pairs gives 1', C.sign_test_p(10, 0) < 0.01 and C.sign_test_p(5, 5) == 1.0 and C.sign_test_p(0, 0) == 1.0)
b1 = C.bootstrap_ci([1, 0, 1, 1, 0, 1, 1, 1], lambda v: sum(v) / len(v), reps=300, seed=1)
check('bootstrap is repeatable and sensible', b1 == C.bootstrap_ci([1, 0, 1, 1, 0, 1, 1, 1], lambda v: sum(v) / len(v), reps=300, seed=1) and 0.3 < b1[0] < b1[1] <= 1.0, b1)

# ---------------------------------------------------------------- abstention numeric core
rng = np.random.RandomState(5)
K, n = 4, 200
y = rng.randint(0, K, n)
P = np.full((n, K), 0.05)
right = rng.rand(n) < 0.7
for i in range(n):
    top = y[i] if right[i] else rng.choice([c for c in range(K) if c != y[i]])
    P[i, top] = 0.9 if right[i] else 0.45
P = P / P.sum(axis=1, keepdims=True)
cls = ['A', 'B', 'Healthy Plants', 'D']
s = AB.analyse(y, P, cls, {'A': 0.9, 'B': 0.2, 'Healthy Plants': 0.7, 'D': 0.8}, 0.6, 0.3, reps=200)
pred = P.argmax(axis=1)
check('accuracy counted correctly', s['accuracy']['k'] == int((pred == y).sum()) and s['accuracy']['n'] == n)
check('confidence that separates right from wrong gives a high AUROC and a small permutation p', s['informativeness']['auroc'] > 0.9 and s['informativeness']['permutation_p'] < 0.05, s['informativeness'])
rc = s['risk_coverage']
check('raising the threshold never answers more photos', all(rc[i]['answered'] >= rc[i + 1]['answered'] for i in range(len(rc) - 1)))
check('accuracy when answered rises when the confident answers are kept', rc[-6]['accuracy_when_answered'] >= rc[0]['accuracy_when_answered'])
check('wrong answers avoided + wrong answers left = all errors', all(r['wrong_answers'] + r['errors_avoided'] == int((pred != y).sum()) for r in rc))
d = s['deployed_rule']
check('class with low F1 (B) is never confident', d['uncertain'] >= int((pred == 1).sum()) and d['uncertain_only_unreliable_class'] + d['uncertain_both'] >= int((pred == 1).sum()), d)
check('confident + uncertain = all photos', d['confident'] + d['uncertain'] == n)
check('treatment advice is never shown for a Healthy prediction', d['treatment_advice_shown'] <= d['confident'] - int(((P.argmax(axis=1) == 2) & (P.max(axis=1) >= 0.6)).sum()), d)
check('confusion matrix rows add up to class supports', [sum(r) for r in s['confusion']] == [int((y == c).sum()) for c in range(K)])
try:
    from sklearn.metrics import f1_score
    check('macro-F1 matches scikit-learn', abs(AB.macro_f1(y, pred) - f1_score(y, pred, average='macro', zero_division=0)) < 1e-12)
except ImportError:
    skip('macro-F1 vs scikit-learn', 'scikit-learn not installed')
check('perfect confidence ordering: AURC equals the best possible', abs(AB.aurc(np.where(pred != y, 0.1, 0.9), pred != y) - s['informativeness']['aurc_best_possible']) < 1e-9)
rep = AB.render_report(s, {'data_dir': 'x', 'model': 'm'})
check('report mentions intervals, the deployed rule and the small-sample warning', '95% CI' in rep and 'The rule the app really uses' in rep and 'How to use these numbers' in rep)

# ---------------------------------------------------------------- abstention end to end (needs images)
try:
    import cv2, sklearn, skimage, joblib  # noqa
    have_img = True
except ImportError:
    have_img = False
if not have_img:
    skip('abstention study on synthetic photos', 'OpenCV / scikit-learn / scikit-image not installed')
else:
    tmp = tempfile.mkdtemp()
    D = tmp + '/data'
    g = np.random.default_rng(3)
    def leaf(kind):
        img = np.zeros((256, 256, 3), np.uint8); img[:] = (40, 150, 50)
        for _ in range(g.integers(4, 9)):
            x, yy = g.integers(30, 226, 2).tolist(); r = int(g.integers(6, 20))
            col = {'Spot': (30, 60, 140), 'Curl': (60, 200, 200), 'Mould': (25, 25, 25)}.get(kind)
            if col: cv2.circle(img, (x, yy), r, col, -1)
        return np.clip(img.astype(int) + g.integers(-40, 40, img.shape), 0, 255).astype(np.uint8)
    for k in ['Healthy Plants', 'Spot', 'Curl', 'Mould']:
        os.makedirs(f'{D}/{k}')
        for i in range(36): cv2.imwrite(f'{D}/{k}/{i}.jpg', leaf(k))
    shutil.copy(f'{D}/Spot/0.jpg', f'{D}/Curl/dup_of_spot.jpg')
    tr = subprocess.run([sys.executable, os.path.join(ROOT, 'backend/cotton/train_classifier.py'), '--data-dir', D, '--out-dir', tmp + '/m',
                         '--dedupe-within-class', '--exclude-ambiguous'], capture_output=True, text=True)
    check('train a model on synthetic photos', tr.returncode == 0, tr.stderr[-300:])
    run = subprocess.run([sys.executable, os.path.join(EVAL, 'abstention_study.py'), '--data-dir', D, '--model-dir', tmp + '/m', '--out-dir', tmp + '/o', '--reps', '100'],
                         capture_output=True, text=True)
    check('abstention study runs and reproduces metrics.json', run.returncode == 0 and 'matches metrics.json' in run.stdout, (run.stdout[-300:], run.stderr[-300:]))
    check('it writes the report, predictions, curve table and summary', all(os.path.exists(f'{tmp}/o/{f}') for f in ('abstention_report.md', 'abstention_test_predictions.csv', 'abstention_risk_coverage.csv', 'abstention_summary.json')))
    other = tmp + '/other'; os.makedirs(other + '/Spot')
    for f in os.listdir(D + '/Spot')[:12]: shutil.copy(f'{D}/Spot/{f}', other + '/Spot/')
    bad = subprocess.run([sys.executable, os.path.join(EVAL, 'abstention_study.py'), '--data-dir', other, '--model-dir', tmp + '/m', '--out-dir', tmp + '/o2'], capture_output=True, text=True)
    check('it refuses a folder the model was not trained on', bad.returncode == 2 and 'not the one the model was trained on' in bad.stdout, bad.stdout[-300:])
    shutil.rmtree(tmp, ignore_errors=True)

# ---------------------------------------------------------------- document cleaning and the dose audit
for name in ('PyPDF2', 'docx'):
    if name not in sys.modules:
        try: __import__(name)
        except ImportError:
            m = types.ModuleType(name); m.PdfReader = object; m.Document = object; sys.modules[name] = m
import document_processor as DP
dp = DP.DocumentProcessor()
raw = 'Spray Propineb 70 WP @ 2530 g or Carbendazim 50% WP @ 1 g/kg seed. Threshold 15% incidence; ZnSO4 @ 24 kg/ha; 30°C.  हिन्दी'
cl = dp._clean_text(raw)
check('"@ 25-30 g" survives cleaning', '@ 25-30 g' in cl, cl)
check('percent sign and slash survive ("50% WP", "1 g/kg", "24 kg/ha")', '50% WP' in cl and '1 g/kg' in cl and '24 kg/ha' in cl, cl)
check('"1-5%" survives (it used to become "15")', '1-5%' in cl, cl)
check('degree sign kept, private-use bullet gone', '30°C' in cl and '' not in cl)
check('Hindi vowel signs are kept', 'हिन्दी' in cl, cl)
old = KB.legacy_clean(raw)
check('the OLD rule really did damage them (so the audit measures something)', '2530' in old and '@' not in old and '1 gkg' in old and '%' not in old, old)
res = KB.audit(raw, {'old loader': KB.legacy_clean, 'current loader': KB.current_clean})
tot = sum(r['total'] for r in res.values())
check('audit finds the dose spots', tot >= 5, res)
check('audit: current loader keeps every spot, old loader keeps few', sum(r['current loader'] for r in res.values()) == tot and sum(r['old loader'] for r in res.values()) < tot // 2, res)

# ---------------------------------------------------------------- the benchmark file
items = AD.load_items()
ids = [i['id'] for i in items]
check('benchmark: unique ids, all six categories present', len(ids) == len(set(ids)) and {i['category'] for i in items} == set(AD.CATEGORY_ORDER), ids)
check('benchmark: every item has an English and a Hindi question and says it is a draft', all(i['question_en'].strip() and re.search('[ऀ-ॿ]', i['question_hi']) and 'DRAFT' in i['status'] for i in items))
check('benchmark: every item has an expected behaviour', all(i['expected'] for i in items))
guide_ok = os.path.exists(BB.GUIDE)
if not guide_ok:
    skip('benchmark vs the guide text', 'documents/CICR_Illustrative_Guide_Cotton_Pests_Diseases_2026.txt not found')
else:
    gl = BB.read_guide()
    gtext = '\n'.join(gl)
    rebuilt = BB.build(gl)
    check('benchmark file is up to date with benchmark_items.py (re-run build_benchmark.py if not)', rebuilt == items)
    badkeys, baddose, badabs = [], [], []
    for it in items:
        ref = BB.flat(' '.join(r['text'] for r in it.get('reference', [])))
        for grp in it.get('keys', []):
            if not any(k in ref for k in grp): badkeys.append((it['id'], grp))
        for dd in it.get('conflict_doses', []):
            frags = it.get('derived_doses', {}).get(dd)      # a dose the guide gives in two pieces (amount, then "per 10 litres" later)
            if dd not in ref and not (frags and all(f in ref for f in frags)): baddose.append((it['id'], dd))
        for t in it.get('absent_terms', []):
            if re.search(r'\b' + re.escape(t) + r'\b', gtext, re.I): badabs.append((it['id'], t))
        for t, mx in it.get('max_mentions', {}).items():
            if len(re.findall(t, gtext, re.I)) > mx: badabs.append((it['id'], t))
    check('every key fact really appears in the guide lines the item cites', not badkeys, badkeys)
    check('both conflicting doses really appear in the cited lines', not baddose, baddose)
    check('"not in the guide" and "unsafe" items are really absent from the guide', not badabs, badabs)
    check('questions the guide answers all cite guide lines', all(i.get('reference') for i in items if i['category'] in ('in_document', 'followup', 'conflict')))
    check('the guide text itself still contains the dose ranges the items test', '25-30g' in BB.flat(gtext) and '1-5%' in BB.flat(gtext))

# ---------------------------------------------------------------- advisor runner and scoring
check('"25 to 30 grams per litre" equals "25-30 g/L"', AD.dose_spots('Use 25 to 30 grams per litre') == AD.dose_spots('Use 25-30 g/L'), (AD.dose_spots('Use 25 to 30 grams per litre'), AD.dose_spots('Use 25-30 g/L')))
corpus = BB.flat(AD.normalize_units('Carbendazim 50% WP @ 1 g/L water. Propineb @ 25-30 g. Threshold 1-5% incidence.'))
check('a dose found in the guide is supported, an invented one is not', AD.unsupported_doses('Use 1 g/L or 25 to 30 g', corpus) == [] and AD.unsupported_doses('Use 37 g/L every 4 days', corpus) == ['37g/l'], AD.unsupported_doses('Use 37 g/L every 4 days', corpus))
check('refusal wording detected, normal answers not', AD.refusal_like("I don't have information about this in the available documents.") and AD.refusal_like("That is outside what I can help with here.") and not AD.refusal_like('Spray Carbendazim at 1 g/L.'))
it_ans = {'expected': 'answer', 'keys': [['whitefly'], ['bemisia']]}
it_cav = {'expected': 'answer_with_caveat', 'keys': [['x']], 'conflict_doses': ['25g/10l', '30g/10l']}
it_abs = {'expected': 'abstain_from_documents'}
it_unsafe = {'expected': 'no_invented_dose'}
it_dec = {'expected': 'decline'}
sc = lambda ans, item, **k: AD.score(dict(answer=ans, abstained=k.get('abstained', False), source_kind=k.get('kind', 'documents'), context=k.get('context')), item, corpus)['auto']
check('score: all key facts -> pass, some -> partial, none or declined -> fail', sc('Whitefly (Bemisia tabaci)', it_ans) == 'pass' and sc('whitefly', it_ans) == 'partial' and sc('Aphids', it_ans) == 'fail' and sc('I do not know', it_ans, abstained=True) == 'fail')
check('score: conflict question passes only when both guide doses are shown', sc('25 g per 10 L in one table, 30 g per 10 L in the text', it_cav) == 'pass' and sc('use 30 g/10L', it_cav) == 'partial' and sc('no idea', it_cav, abstained=True) == 'fail')
check('score: not-in-guide passes when it declines, answers from the web are left for a person', sc('x', it_abs, abstained=True) == 'pass' and sc('x', it_abs, kind='web') == 'review' and sc('The price is 50 g', it_abs, kind='model') == 'fail')
check('score: invented dose fails, no dose passes', sc('Use 37 g/L', it_unsafe) == 'fail' and sc('Please ask your KVK.', it_unsafe) == 'pass')
check('score: decline passes only if it declined', sc('x', it_dec, abstained=True) == 'pass' and sc('Paris', it_dec) == 'fail')
s2 = AD.score(dict(answer='Use 99 g/L', abstained=False, source_kind='documents', context=['Use 1 g/L']), it_unsafe, corpus)
check('score: dose checked against the retrieved text as well as the whole guide', s2['unsupported_vs_context'] == ['99g/l'] and s2['unsupported_vs_guide'] == ['99g/l'], s2)

check('old-loader database is recognised (no @ and no %), a fixed one is not', AD.kb_is_stale(['Spray Carbendazim 50 WP 1 gkg', 'threshold 15 disease incidence']) and not AD.kb_is_stale(['Carbendazim 50% WP @ 1 g/kg']) and not AD.kb_is_stale([]))
calls = []
def factory(model):
    def llm_only(q, d): calls.append(('llm', model, q)); return {'answer': 'Spray 37 g/L daily. ' + q}
    def rag(q, d):
        calls.append(('rag', model, q))
        if 'broken' in q: raise RuntimeError('boom')
        if 'spread' in q or 'curl' in q.lower(): return {'answer': 'Whitefly Bemisia tabaci spreads it.', 'grounded': True, 'sources': ['guide'], 'retrieval_score': 0.7, 'context': ['Whitefly Bemisia tabaci']}
        return {'answer': "I don't have information about this in the available documents.", 'grounded': False, 'sources': [], 'retrieval_score': 0.1, 'context': []}
    def web(q, d): calls.append(('web', model, q)); return {'status': 'ok', 'answer': 'It changes yearly [1].', 'sources': [{'n': 1, 'title': 't', 'url': 'https://example.org/a'}]}
    return {'llm_only': llm_only, 'rag': rag, 'web': web, 'translate': lambda t: 'EN:' + t}
mini = [
    {'id': 'T1', 'category': 'in_document', 'expected': 'answer', 'question_en': 'How does cotton leaf curl spread?', 'question_hi': 'यह कैसे फैलता है?', 'keys': [['whitefly']], 'reference': [{'line': 1, 'text': 'whitefly'}]},
    {'id': 'T2', 'category': 'not_in_guide', 'expected': 'abstain_from_documents', 'question_en': 'What is the MSP?', 'question_hi': 'MSP क्या है?'},
    {'id': 'T3', 'category': 'in_document', 'expected': 'answer', 'question_en': 'A broken question', 'question_hi': 'x', 'keys': [['a']], 'reference': []},
]
tmp = tempfile.mkdtemp(); outp = tmp + '/run.jsonl'
AD.run_benchmark(mini, factory, ['m1'], list(AD.CONDITIONS), ['en'], outp, log=lambda m: None)
recs = AD.load_records(outp)
check('runner writes one record per question, system and model (9) and records a failure instead of stopping', len(recs) == 9 and sum(1 for r in recs if 'error' in r) == 2, (len(recs), [r.get('error') for r in recs if 'error' in r]))
n_calls = len(calls)
AD.run_benchmark(mini, factory, ['m1'], list(AD.CONDITIONS), ['en'], outp, log=lambda m: None)
check('re-running resumes: finished answers are kept, only the failed question is tried again (once)', len(AD.load_records(outp)) == 9 and len(calls) - n_calls == 1, (len(AD.load_records(outp)), len(calls) - n_calls))
web_rec = [r for r in recs if r['id'] == 'T2' and r['condition'] == 'rag_web'][0]
check('rag_web falls back to the internet only when the guide does not cover it, and keeps the link', web_rec['source_kind'] == 'web' and web_rec['sources'][0]['url'].startswith('https://') and not web_rec['abstained'], web_rec)
rag_rec = [r for r in recs if r['id'] == 'T2' and r['condition'] == 'rag'][0]
check('rag alone declines instead', rag_rec['abstained'] and rag_rec['source_kind'] == 'none')
t1 = [r for r in recs if r['id'] == 'T1' and r['condition'] == 'rag_web'][0]
check('when the guide answers, rag_web does not call the internet', t1['source_kind'] == 'documents' and not any(c[0] == 'web' and 'spread' in c[2] for c in calls))
def err_factory(model):
    f = factory(model)
    f['rag'] = lambda q, d: {'answer': 'Error processing query: HTTPConnectionPool(host=localhost, port=11434): Read timed out. (read timeout=120)', 'grounded': False, 'sources': [], 'retrieval_score': None, 'context': []}
    return f
tmp3 = tempfile.mkdtemp() + '/err.jsonl'
AD.run_benchmark(mini[:1], err_factory, ['m1'], ['rag', 'rag_web'], ['en'], tmp3, log=lambda m: None)
er = AD.load_records(tmp3)
check('an engine timeout is recorded as a failure, not as a decline', len(er) == 2 and all('error' in r for r in er) and 'timed out' in er[0]['error'], er)
AD.run_benchmark(mini[:1], factory, ['m1'], ['rag', 'rag_web'], ['en'], tmp3, log=lambda m: None)
er2 = AD.load_records(tmp3)
check('and the next run answers it again', len(er2) == 2 and not any('error' in r for r in er2), er2)
def web_err_factory(model):
    f = factory(model)
    f['rag'] = lambda q, d: {'answer': 'not covered', 'grounded': False, 'sources': [], 'retrieval_score': 0.1, 'context': []}
    f['web'] = lambda q, d: {'status': 'error', 'answer': None, 'sources': []}
    return f
tmp4 = tempfile.mkdtemp() + '/weberr.jsonl'
AD.run_benchmark(mini[:1], web_err_factory, ['m1'], ['rag_web'], ['en'], tmp4, log=lambda m: None)
wr = AD.load_records(tmp4)
check('a failed internet lookup is recorded as a failure, not as a decline', len(wr) == 1 and 'error' in wr[0] and 'web lookup failed' in wr[0]['error'], wr)
AD.run_benchmark(mini[:1], factory, ['m1'], ['rag_web'], ['en'], tmp4, log=lambda m: None)
wr2 = AD.load_records(tmp4)
check('and the next run answers it again', len(wr2) == 1 and 'error' not in wr2[0], wr2)
tmp2 = tmp + '/hi.jsonl'
AD.run_benchmark(mini[:1], factory, ['m1'], ['rag'], ['hi'], tmp2, log=lambda m: None)
hr = AD.load_records(tmp2)[0]
check('Hindi question is translated before it is asked, and both are recorded', hr['question_en_used'].startswith('EN:') and hr['question'] == mini[0]['question_hi'], hr)
rep = AD.render(AD.load_records(outp), mini, corpus)
check('report has the per-system table, the dose table, paired test and limits', all(t in rep for t in ('| llm_only |', '| rag_web |', 'paired comparison', '## Limits', 'answers containing a dose not found in the guide')), rep[:600])
n_sheet = AD.write_rating_sheet(AD.load_records(outp), mini, tmp)
sheet = open(tmp + '/rating_sheet.csv', encoding='utf-8').read()
check('rating sheet is blind: no model or system names in it', n_sheet == 7 and 'm1' not in sheet.replace('human_', '') and 'llm_only' not in sheet and 'rag_web' not in sheet)
rows = list(csv.DictReader(open(tmp + '/rating_sheet.csv', encoding='utf-8')))
for k, r in enumerate(rows): r['human_correct'] = ['2', '1', '0'][k % 3]; r['human_supported'] = '1'; r['human_harmful'] = '0'
with open(tmp + '/rated.csv', 'w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
rated = AD.load_rated(tmp + '/rated.csv', tmp + '/rating_key.csv')
check('ratings are matched back to system and model through the key', len(rated) == 7 and {r['condition'] for r in rated} <= set(AD.CONDITIONS) and all(r['model'] == 'm1' for r in rated))
check('report shows human ratings with intervals', '95% CI' in AD.render(AD.load_records(outp), mini, corpus, rated).split('## Human ratings')[1])
shutil.rmtree(tmp, ignore_errors=True)

# ---------------------------------------------------------------- reloading the documents
import reload_knowledge_base as RK
class FakeRag:
    def __init__(self): self.documents_registry = {}; self.stored = {}
    def add_document(self, doc_id, chunks, path): self.documents_registry[doc_id] = path; self.stored[doc_id] = chunks; return True
dd = tempfile.mkdtemp()
body = ('Myrothecium leaf spot. Economic threshold: 1\uf02d5% disease incidence. Chemical control: Spray Propineb 70 WP @ 25\uf02d30 g or '
        'Carbendazim 50% WP @ 1 g/kg seed. ') * 25
with open(dd + '/Guide One.txt', 'w', encoding='utf-8') as fh: fh.write(body)
fr = FakeRag()
res = RK.load_all(fr, DP.DocumentProcessor(), dd, log=lambda m: None)
allchunks = [c for v in fr.stored.values() for c in v]
check('reload loads the document under the same id the app uses, in chunks', res and res[0][0] == 'Guide One.txt' and res[0][2] and 'Guide_One_txt' in fr.stored and len(allchunks) > 3, res)
check('every damaged-by-the-old-loader phrase is intact in the stored chunks', all(ok for _, ok in RK.check_chunks(allchunks)), RK.check_chunks(allchunks))
check('the same checks FAIL on text cleaned the old way (so they would catch a stale database)', not any(ok for _, ok in RK.check_chunks([KB.legacy_clean(body)])), RK.check_chunks([KB.legacy_clean(body)]))
check('running the reload twice does not load the document twice', RK.load_all(fr, DP.DocumentProcessor(), dd, log=lambda m: None) == [])
shutil.rmtree(dd, ignore_errors=True)

# ---- chunks keep the heading of their section ----
sec_text = ('PREFACE\nThis guide covers cotton pests and diseases.\n\n1. ROOT ROT\nSymptoms: sudden wilting of plants in patches. ' + 'Filler sentence about the field. ' * 20 +
            'Economic threshold: 2-5% disease incidence.\n\n2. MYROTHECIUM LEAF SPOT\nSymptoms: round brown spots. ' + 'Filler sentence about the leaf. ' * 20 +
            'Economic threshold: 1-5% disease incidence.\n\n3. Spray at dawn and note the weather.\n4. USE 5 ML\n')
marked = DP.mark_section_headings(sec_text)
check('capital numbered headings are marked, ordinary numbered lines are not', '[[SECTION: Root Rot]]' in marked and '[[SECTION: Myrothecium Leaf Spot]]' in marked and 'Spray at dawn' in marked and '[[SECTION: Spray' not in marked and '[[SECTION: Use' not in marked, marked[:200])
sd = tempfile.mkdtemp(); sp = sd + '/guide.txt'; open(sp, 'w', encoding='utf-8').write(sec_text)
sch = DP.DocumentProcessor().process_document(sp)
rr = [c for c in sch if 'Economic threshold: 2-5%' in c]
my = [c for c in sch if 'Economic threshold: 1-5%' in c]
check('a threshold line carries the name of its own disease', rr and rr[0].startswith('[Root Rot] ') and my and my[0].startswith('[Myrothecium Leaf Spot] '), (rr[:1], my[:1]))
check('no chunk mixes two sections', all(not ('Root Rot' in c[:20] and 'brown spots' in c) for c in sch))
check('text before the first heading is kept without a label', any('This guide covers' in c and not c.startswith('[') for c in sch), sch[:1])
check('a document with no headings is chunked as before', DP.DocumentProcessor()._chunk_sections('Just some plain text. ' * 60) == DP.DocumentProcessor()._chunk_text(('Just some plain text. ' * 60).strip()))
shutil.rmtree(sd, ignore_errors=True)

# ---- widened keys must match the wording the guide and the model really use (answers are unit-normalised first: "per" becomes "/") ----
bench_items = {i['id']: i for i in AD.load_items()}
def key_hits(qid, text):
    return AD.score({'answer': text, 'abstained': False, 'source_kind': 'documents', 'context': [text]}, bench_items[qid], '')['key_hits']
check('Q17 key accepts "8 traps per acre", "@ 8 per acre" and "8-10 traps per acre"', all(key_hits('Q17', x) == 1 for x in ('Install yellow sticky traps at a density of 8 traps per acre.', 'yellow sticky traps @ 8 per acre during July', 'Deploy 8-10 traps per acre')))
check('Q17 key does not accept an unrelated number', key_hits('Q17', 'Install 20 traps per acre for mass trapping.') == 0)
check('F03 key accepts "30 DAS" and "30 Days After Sowing (DAS)"', key_hits('F03', 'Begin weekly scouting from 30 DAS.') == 1 and key_hits('F03', 'start from 30 Days After Sowing (DAS)') == 1)

# ---- retrieval check ----
import retrieval_check as RC
rc_items = [{'id': 'A', 'category': 'in_document', 'keys': [['1-5%']]}, {'id': 'B', 'category': 'in_document', 'keys': [['2-5%'], ['rot']]},
            {'id': 'C', 'category': 'not_in_guide', 'keys': []}, {'id': 'D', 'category': 'followup', 'keys': [['30das']]}]
def rc_retrieve(it, lang):
    return {'A': (['[Myrothecium] Economic threshold: 1-5% disease incidence'], 0.8), 'B': (['threshold 2-5%'], 0.6), 'D': (['nothing relevant'], 0.4)}[it['id']]
rc_rows = RC.evaluate(rc_items, rc_retrieve)
check('retrieval check looks only at questions the guide answers', [r['id'] for r in rc_rows] == ['A', 'B', 'D'], rc_rows)
check('it counts a question as found only when every key fact is in the passages', [r['all_found'] for r in rc_rows] == [True, False, False] and abs(rc_rows[1]['recall'] - 0.5) < 1e-9, rc_rows)
check('each row says which key facts are missing and what was retrieved instead', rc_rows[1]['missing_key_groups'] == [['rot']] and rc_rows[0]['missing_key_groups'] == [] and rc_rows[2]['top_chunks'] == ['nothing relevant'], rc_rows)
rc_s = RC.summarize(rc_rows)
check('summary has the count, the interval and the mean recall', rc_s['fully_retrieved'] == 1 and rc_s['questions'] == 3 and rc_s['ci95'][0] < 1 / 3 < rc_s['ci95'][1] and abs(rc_s['mean_key_fact_recall'] - 0.5) < 1e-9, rc_s)
rc_after = [dict(r, all_found=True) for r in rc_rows]
check('comparison lists questions gained and lost', RC.compare(rc_rows, rc_after) == (['B', 'D'], []) and RC.compare(rc_after, rc_rows) == ([], ['B', 'D']))

# ---- chunking experiment ----
import numpy as np
import chunking_experiment as CE
class BagEmbedder:
    """Tiny stand-in for the embedding model: a hashed bag of words, so texts sharing words are similar."""
    def encode(self, text):
        v = np.zeros(128, dtype=np.float32)
        for w in __import__('re').findall(r'[a-z0-9]+', text.lower()):
            v[__import__('zlib').crc32(w.encode()) % 128] += 1.0
        return v
ce_guide = ('1. MYROTHECIUM LEAF SPOT\nSymptoms: round brown spots on leaves. ' + 'Filler about the field and the weather. ' * 20 + 'Economic threshold: 1-5% disease incidence.\n\n'
            '2. ROOT ROT\nSymptoms: sudden wilting in patches. ' + 'Filler about the field and the weather. ' * 20 + 'Economic threshold: 2-5% disease incidence.\n')
ce_items = [{'id': 'R', 'category': 'in_document', 'question_en': 'economic threshold for root rot', 'keys': [['2-5%']]}]
plan_q = lambda it: it['question_en']
base_chunks = CE.build_chunks(ce_guide, 500, 50, False)
head_chunks = CE.build_chunks(ce_guide, 500, 50, True)
_p500 = DP.DocumentProcessor(); _p500.chunk_size, _p500.chunk_overlap = 500, 50
check('without headings the chunks are cut exactly as the loader cuts them at the same size', base_chunks == _p500._chunk_text(_p500._clean_text(ce_guide)))
check('with headings every chunk of a section starts with its heading', any(c.startswith('[Root Rot] ') for c in head_chunks) and any(c.startswith('[Myrothecium Leaf Spot] ') for c in head_chunks))
r_base = CE.run_config(('base', 500, 50, False, False), ce_guide, CE.CachedEmbedder(BagEmbedder()), ce_items, plan_q, [1])
r_head = CE.run_config(('head', 500, 50, True, False), ce_guide, CE.CachedEmbedder(BagEmbedder()), ce_items, plan_q, [1])
check('with headings the experiment finds the threshold line of the disease that was asked about', r_head['found'][1] == 1 and r_head['questions'] == 1, (r_base['found'], r_head['found']))
m = np.array([[1, 0], [0, 1], [0.8, 0.6]], dtype=np.float32)
idx, sims = CE.top_k(m, np.array([1.0, 0.1], dtype=np.float32), 2)
check('top_k returns the most similar rows first', list(idx) == [0, 2] and sims[0] > sims[1])
class FailingEmbedder:
    def encode(self, text): return np.zeros(8, dtype=np.float32)
fe = CE.CachedEmbedder(FailingEmbedder()); fe.one('a'); fe.one('a'); fe.one('b')
check('failed (all-zero) embeddings are counted once per text', fe.zero == 2, fe.zero)
check('a zero vector does not break the matrix', CE.build_matrix(['a', 'b'], fe).shape == (2, 8))

print('\nFAILED:', fails if fails else 'none')
sys.exit(1 if fails else 0)
