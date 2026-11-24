# -*- coding: utf-8 -*-
"""Checks for the Hindi crop-term glossary and the question translation step. No Ollama needed: the model is replaced
by a stand-in.  Run:  python tests/test_crop_glossary.py"""
import ast, os, sys
BACK = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backend'))
sys.path.insert(0, BACK)
import crop_glossary as G
import translator as T
fails = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x)[:400] if (x and not c) else ''))
    if not c: fails.append(n)

for name in ('crop_glossary.py', 'translator.py'):
    with open(os.path.join(BACK, name), encoding='utf-8') as fh:
        ast.parse(fh.read(), feature_version=(3, 9))
check('both files parse as Python 3.9', True)

# ---------- the terms the model got wrong in the benchmark run ----------
t, f = G.apply('टिंडा सड़न रोग के लिए कौन सा फफूंदनाशक छिड़कें?')
check('boll rot', t.startswith('boll rot रोग') and f == ['boll rot', 'fungicide'], (t, f))
t, f = G.apply('फफूंद जनित टिंडा सड़न रोग से कितना नुकसान?')
check('longer phrase wins: fungal boll rot', t.startswith('fungal boll rot') and f == ['fungal boll rot'], (t, f))
t, f = G.apply('कपास का जीवाणु पत्ती झुलसा रोग किस जीवाणु से होता है?')
check('bacterial leaf blight, and the plain word जीवाणु is left alone', 'bacterial leaf blight' in t and 'किस जीवाणु' in t, t)
t, f = G.apply('कपास की पत्तियों पर काली फफूंद (सूटी मोल्ड) किससे होती है?')
check('sooty mould, not repeated in brackets', t.count('sooty mould') == 1 and f == ['sooty mould'], t)
t, f = G.apply('कपास के बीज का अम्ल से रेशा हटाना क्यों जरूरी है?')
check('acid delinting', 'acid delinting' in t, t)
t, f = G.apply('प्रोपिनेब 70 डब्ल्यूपी की कितनी मात्रा')
check('pesticide name and formulation code', t.startswith('Propineb 70 WP'), t)

# ---------- spelling variants ----------
check('nukta optional: सफ़ेद = सफेद', G.apply('सफ़ेद मक्खी')[1] == ['whitefly'] and G.apply('सफेद मक्खी')[1] == ['whitefly'])
check('nukta optional: जड़ = जड', G.apply('जड सडन')[1] == ['root rot'] and G.apply('जड़ सड़न')[1] == ['root rot'])
t, _ = G.apply('सफ़ेद मक्खी पर छिड़काव')
check('other words keep their nukta', 'छिड़काव' in t, t)

# ---------- no matches inside other words ----------
t, f = G.apply('तेल और तेलंगाना')
check('तेला (jassid) not found inside तेल / तेलंगाना', f == [] and t == 'तेल और तेलंगाना', (t, f))
t, f = G.apply('नीमच जिले में')
check('नीम (neem) not found inside नीमच', f == [], f)
t, f = G.apply('फ्रांस की राजधानी क्या है?')
check('nothing to swap -> text unchanged', f == [] and t == 'फ्रांस की राजधानी क्या है?', t)

# ---------- missing_terms ----------
check('missing_terms ignores case and spaces', G.missing_terms('What causes Boll Rot?', ['boll rot', 'fungicide']) == ['fungicide'])
check('missing_terms accepts plurals and -ing', G.missing_terms('How many whiteflies? How to drench roots?', ['whitefly', 'drenching']) == [])
check('missing_terms still catches a dropped term', G.missing_terms('What spray to use for the disease?', ['bacterial leaf blight']) == ['bacterial leaf blight'])

# ---------- translate_to_english with a stand-in model ----------
class Resp:
    status_code = 200
    def __init__(self, text): self._t = text
    def json(self): return {'response': self._t}
seen = {}
def fake_post(reply):
    def post(url, json=None, timeout=None):
        seen['prompt'] = json['prompt']
        return Resp(reply)
    return post

T.requests.post = fake_post('Which fungicide should be sprayed for boll rot and how much?')
out = T.translate_to_english('टिंडा सड़न रोग के लिए कौन सा फफूंदनाशक और कितनी मात्रा में छिड़कें?', 'hi')
check('model sees the English terms, not the Hindi ones', 'boll rot' in seen['prompt'] and 'टिंडा' not in seen['prompt'], seen['prompt'])
check('prompt tells the model to keep the terms', 'Keep each one exactly' in seen['prompt'] and 'boll rot; fungicide' in seen['prompt'], seen['prompt'])
check('good translation returned unchanged', out == 'Which fungicide should be sprayed for boll rot and how much?', out)

T.requests.post = fake_post('What fungicide to spray for Tinda rot?')
out = T.translate_to_english('टिंडा सड़न रोग के लिए कौन सा फफूंदनाशक छिड़कें?', 'hi')
check('a term the model dropped is added back', out == 'What fungicide to spray for Tinda rot? (boll rot)', out)

T.requests.post = fake_post('What is the capital of France?')
out = T.translate_to_english('फ्रांस की राजधानी क्या है?', 'hi')
check('no crop terms -> no extra instruction, nothing added', 'Keep each one' not in seen['prompt'] and out == 'What is the capital of France?', (seen['prompt'], out))

T.requests.post = fake_post('   ')
check('empty model reply -> None', T.translate_to_english('टिंडा सड़न', 'hi') is None)
check('English question -> None (no translation needed)', T.translate_to_english('What is boll rot?', 'en') is None)

print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: {fails}')
sys.exit(1 if fails else 0)
