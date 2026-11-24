"""Checks for backend/dose_conflicts.py: the fixed list of places where the guide gives two amounts for the same spray.
No Ollama and no internet. Reads the guide text from documents/ (skipped if it is not there)."""
import json, os, re, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(ROOT, 'backend'))
sys.path.insert(0, os.path.join(ROOT, 'eval'))
import dose_conflicts as D
fails = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x)[:400] if (x and not c) else ''))
    if not c: fails.append(n)
def skip(n, why): print('SKIP ' + n + ' (' + why + ')')

GUIDE = os.path.join(ROOT, 'documents', 'CICR_Illustrative_Guide_Cotton_Pests_Diseases_2026.txt')

# ---------------------------------------------------------------- every amount in the list is really in the guide
if not os.path.exists(GUIDE):
    skip('conflict list vs the guide text', 'guide text not found')
else:
    txt = open(GUIDE, encoding='utf-8').read()
    txt = ''.join(chr(ord(c) - 0xF000) if 0xF020 <= ord(c) <= 0xF07E else c for c in txt)
    raw = D._raw_flat(txt)
    bad = [(c['id'], v['dose']) for c in D.CONFLICTS for v in c['variants'] if not re.search(v['seen'], raw)]
    check('every amount in the conflict list appears in the guide text', not bad, bad)
    check('every conflict has at least two different amounts', all(len(c['variants']) >= 2 and len({v['dose'] for v in c['variants']}) == len(c['variants']) for c in D.CONFLICTS))

# ---------------------------------------------------------------- when the note appears
BLB_Q = 'What spray should I use for bacterial leaf blight and how much per 10 litres of water?'
BLB_CTX = ['[Bacterial Leaf Blight] Chemical spray: If early foliar symptoms emerge and the weather is highly humid, spray Carbendazim 12% + Mancozeb 63 % WP @ 30g /10L of water.']
TABLE_CTX = ['Bacterial leaf blight  All stage  Seed treatment with Carboxin 75% WP @ 1.5 g/kg seed or Carboxin 37.5% + Thiram 37.5% DS 2.5 g/kg seed. Foliar spray with Carbendazim 12% + Mancozeb 63% WP @ 25g / 10L of water.']

n = D.note_for(BLB_Q, 'Spray Carbendazim 12% + Mancozeb 63% WP at 30 g per 10 L of water.', BLB_CTX)
check('answer shows one amount -> note shows both', '30 g per 10 L' in n and '25 g per 10 L' in n and 'KVK' in n, n)
n = D.note_for(BLB_Q, 'Use a Carbendazim and Mancozeb spray.', BLB_CTX)
check('answer shows no amount but the question asks "how much" -> note shows both', '30 g per 10 L' in n and '25 g per 10 L' in n, n)
n = D.note_for(BLB_Q, 'Spray 30 g per 10 L, or 25 g per 10 L according to the summary table.', BLB_CTX)
check('answer already shows both amounts -> no note', n == '', n)
n = D.note_for(BLB_Q, 'Spray at 30 g/10L of water', TABLE_CTX)
check('only the table passage was retrieved -> note still shows both', '30 g per 10 L' in n and '25 g per 10 L' in n, n)
n = D.note_for('How does bacterial leaf blight spread?', 'It spreads by infected seed and rain splash.', BLB_CTX)
check('question is not about amounts and the answer shows none -> no note', n == '', n)
n = D.note_for('How can I stop leaf blight?', 'Spray 30 g per 10 L.', BLB_CTX)
check('question does not name bacterial leaf blight and nothing else does -> no note', n == '', n)
n = D.note_for('How do I control it?', 'Spray 30 g per 10 L of water.', BLB_CTX, topic_extra='How do I control it? cotton Bacterial leaf blight')
check('follow-up about the photo: the diagnosed disease counts as the topic', '25 g per 10 L' in n, n)
n = D.note_for(BLB_Q, 'Spray 30 g per 10 L.', ['Root rot: drench with Carbendazim 50% WP @ 10 g/10 L water.'])
check('retrieved passages do not hold the conflicting spray -> no note', n == '', n)
n = D.note_for('How much Carbendazim per litre for root rot?', 'Drench with Carbendazim 50% WP @ 1 g/L.', ['Spot drenching with Carbendazim 50%WP @ 1 g/L water'])
check('a different disease with the same product and amount is left alone', n == '', n)

SEED_Q = 'How much Carboxin plus Thiram should I use to treat the seed against bacterial blight?'
SEED_CTX = ['Seed treatment: Treat delinted seed with Carboxin 37.5% + Thiram 37.5% WS @ 3.5 g/kg seed or Pseudomonas fluorescens @ 10g/kg seed. Bacterial leaf blight']
n = D.note_for(SEED_Q, 'Use Carboxin 37.5% + Thiram 37.5% at 3.5 g per kg of seed.', SEED_CTX)
check('seed treatment: 3.5 and 2.5 g per kg are both shown', '3.5 g per kg' in n and '2.5 g per kg' in n, n)

BOLL_Q = 'Which fungicide should I spray for boll rot and how much?'
BOLL_CTX = ['Boll rot  Fruiting stage  Spray Carbendazim 50% WP @ 1g/L water. For internal boll rot spray with Carbendazim 12% + Mancozeb 63% WP @ 25g / 10L of water.']
n = D.note_for(BOLL_Q, 'Spray Carbendazim 50% WP at 1 g per litre of water.', BOLL_CTX)
check('boll rot: 1 g per L and 4 g per 10 L are both shown', '1 g per L' in n and '4 g per 10 L' in n, n)
n = D.note_for(BOLL_Q, 'Spray Carbendazim 50% WP at 4 g with the other fungicides.', BOLL_CTX)
check('boll rot: answer gives 4 g -> the table amount is added', '1 g per L' in n, n)
n = D.note_for('What weather favours boll rot?', 'Rain and humid weather.', BOLL_CTX)
check('boll rot weather question -> no note', n == '', n)

# two conflicts at once (a follow-up about bacterial blight that mentions both amounts)
n = D.note_for('How do I treat it and how much should I spray?', 'Treat the seed at 3.5 g/kg and spray 30 g per 10 L.', BLB_CTX + SEED_CTX, topic_extra='Bacterial leaf blight')
check('two conflicts can appear in one note', '30 g per 10 L' in n and '2.5 g per kg' in n and n.count('Note:') == 1, n)

check('asks_for_amount catches the usual wordings', all(D.asks_for_amount(q) for q in ['how much per acre?', 'What is the dose?', 'which spray should I use', 'mixing ratio']) and not D.asks_for_amount('How does it spread?'))
check('the note never crashes on empty input', D.note_for('', '', []) == '' and D.note_for(None, None, None) == '')

# ---------------------------------------------------------------- the benchmark counts the note as "both doses shown"
bench = os.path.join(ROOT, 'eval', 'cotton_qa_benchmark.json')
if not os.path.exists(bench):
    skip('benchmark scoring of the note', 'benchmark file not found')
else:
    import advisor_benchmark as AD
    items = {i['id']: i for i in json.load(open(bench, encoding='utf-8'))['items']}
    def score_with_note(qid, model_answer, chunks):
        it = items[qid]
        note = D.note_for(it['question_en'], model_answer, chunks, topic_extra=it.get('disease_context') or '')
        rec = {'answer': model_answer + ('\n\n' + note if note else ''), 'abstained': False, 'source_kind': 'documents', 'context': chunks}
        return AD.score(rec, it, '')['auto']
    check('benchmark: Q12 with one dose + the note -> pass', score_with_note('Q12', 'Spray Carbendazim and Mancozeb at 30 g per 10 L of water.', BLB_CTX) == 'pass')
    check('benchmark: Q13 with one dose + the note -> pass', score_with_note('Q13', 'Use 3.5 g per kg of seed.', SEED_CTX) == 'pass')
    check('benchmark: Q26 with one dose + the note -> pass', score_with_note('Q26', 'Spray Carbendazim 50% WP at 1 g/L water.', BOLL_CTX) == 'pass')
    check('benchmark: Q26 is a conflict item with a note about the evidence', items['Q26']['category'] == 'conflict' and 'Moved from in_document' in items['Q26']['note'])

print('\nFAILED:', fails if fails else 'none')
sys.exit(1 if fails else 0)
