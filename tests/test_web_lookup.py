"""Checks for the internet fallback and for how follow-up questions are built.
No internet needed: searches and page downloads are replaced by small stand-ins.
(The real search is checked on your computer with:  python backend/web_lookup.py "your question")"""
import os, sys, types
BACK = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backend'))
sys.path.insert(0, BACK)
import requests
import web_lookup as W
import cotton_flow as F
fails = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x)[:400] if (x and not c) else ''))
    if not c: fails.append(n)

# ---------- question plan: the user's words are never rewritten ----------
s, bg, used = F.plan_question('Cotton leaf curl virus disease', 'How does it spread?')
check('pointing at the photo -> disease added to the search words and background', used and 'Cotton leaf curl virus disease' in s and 'Cotton leaf curl virus disease' in bg and s.startswith('How does it spread?'), (s, bg))
s, bg, used = F.plan_question('Cotton leaf curl virus disease', 'How much water does cotton need?')
check('general question -> diagnosis not used', not used and bg is None and 'curl' not in s, (s, bg))
s, bg, used = F.plan_question(None, 'How does it spread?')
check('no diagnosis -> nothing to add', not used and bg is None)
s, bg, used = F.plan_question('X', 'What can I do about whitefly')
check('"cotton" added to the search words only when missing', s == 'What can I do about whitefly cotton', s)
check('my plant / my leaves count as the photo', F.refers_to_photo('My leaves are curling, what now?') and F.refers_to_photo('is that serious'))
check('latin text detected', F.is_latin_text('How to sow?') and not F.is_latin_text('कपास कब बोएं'))

# ---------- search words ----------
check('stop words dropped, cotton added', W.search_query('How can I stop the whitefly from spreading?') == 'stop whitefly spreading cotton', W.search_query('How can I stop the whitefly from spreading?'))
check('cotton not repeated', W.search_query('cotton leaf curl virus treatment') == 'cotton leaf curl virus treatment')

# ---------- DuckDuckGo page ----------
DDG = '''<html><body>
<div class="result results_links"><h2 class="result__title"><a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fcicr.org.in%2Fleaf-curl%2F&amp;rut=abc">Cotton Leaf Curl Virus &#8211; <b>CICR</b></a></h2>
<a class="result__snippet" href="//duckduckgo.com/l/?uddg=x">Whitefly <b>spreads</b> the virus between plants.</a></div>
<div class="result result--ad"><a class="result__a" href="https://duckduckgo.com/y.js?ad=1">Buy sprays now</a><a class="result__snippet">ad</a></div>
<div class="result"><a class="result__a" href="https://www.facebook.com/somepost">Facebook post</a><a class="result__snippet">chat</a></div>
<div class="result"><a class="result__a" href="https://someblog.example.com/cotton">A cotton blog</a><a class="result__snippet">Blog text about cotton leaf curl.</a></div>
</body></html>'''
res = W.parse_ddg(DDG)
check('links unwrapped from DuckDuckGo redirects', res[0]['url'] == 'https://cicr.org.in/leaf-curl/' and 'CICR' in res[0]['title'], res)
check('ads dropped', all('duckduckgo.com' not in r['url'] for r in res) and len(res) == 3, res)
check('snippet kept', 'Whitefly spreads the virus' in res[0]['snippet'], res[0])
ranked = W._rank(res)
check('trusted source first, social media removed', ranked[0]['url'].startswith('https://cicr.org.in') and all('facebook' not in r['url'] for r in ranked), ranked)

# ---------- page text ----------
PAGE = '''<html><head><title>x</title><script>var a = "ignore me ignore me ignore me ignore me ignore me ignore me";</script></head><body>
<nav><p>Home About Contact Login Register Subscribe to our newsletter today for updates</p></nav>
<h1>Cotton leaf curl virus disease</h1>
<p>The disease is caused by begomoviruses and is spread by the whitefly Bemisia tabaci feeding on the underside of leaves.</p>
<p>Our company was founded in 1998 and we have offices in many cities across the country for you.</p>
<ul><li>Remove infected plants early and keep the field free of weeds that host whitefly populations.</li></ul>
<footer><p>Copyright 2026 all rights reserved terms and conditions privacy policy cookie settings</p></footer></body></html>'''
paras = W.html_to_paragraphs(PAGE)
check('scripts, menus and footers skipped', not any('ignore me' in p or 'Subscribe' in p or 'Copyright' in p for p in paras), paras)
ex = W.best_excerpt(paras, 'how does leaf curl spread by whitefly')
check('most relevant paragraphs kept, unrelated dropped', 'whitefly' in ex and 'founded in 1998' not in ex, ex)

# ---------- gather ----------
def fake_search(q, t): return res
def fake_fetch(url, t): return paras
exs, st = W.gather('how does leaf curl spread by whitefly', searcher=fake_search, fetcher=fake_fetch)
check('gather ok with numbered excerpts and links', st == 'ok' and exs[0]['n'] == 1 and exs[0]['url'].startswith('https://cicr.org.in') and 'whitefly' in exs[0]['text'], (st, exs))
def offline(q, t): raise requests.ConnectionError('no internet')
orig_wiki = W.search_wikipedia
W.search_wikipedia = lambda q, t, limit=3: (_ for _ in ()).throw(requests.ConnectionError('no internet'))
check('no internet -> offline', W.gather('x leaf', searcher=offline)[1] == 'offline')
def blocked(q, t): raise RuntimeError('DuckDuckGo answered HTTP 202')
W.search_wikipedia = lambda q, t, limit=3: [{'title': 'Cotton leaf curl virus - Wikipedia', 'url': 'https://en.wikipedia.org/wiki/Cotton_leaf_curl_virus',
                                              'snippet': '', 'text': 'Cotton leaf curl virus is a plant virus spread by whiteflies and it causes severe yield loss in cotton in South Asia.\nSymptoms include upward leaf curling and thickened veins on the underside of leaves.'}]
exs, st = W.gather('cotton leaf curl virus symptoms', searcher=blocked)
check('search engine blocked -> Wikipedia used instead', st == 'ok' and 'wikipedia.org' in exs[0]['url'], (st, exs))
W.search_wikipedia = lambda q, t, limit=3: (_ for _ in ()).throw(RuntimeError('Wikipedia returned nothing'))
check('nothing anywhere -> none', W.gather('zzz', searcher=blocked)[1] == 'none')
W.search_wikipedia = orig_wiki
long_snip = [dict(res[0], snippet='Whitefly spreads the cotton leaf curl virus between plants, and infected plants should be removed early to protect neighbouring fields.')]
exs2, st2 = W.gather('leaf curl whitefly', searcher=lambda q, t: long_snip, fetcher=lambda u, t: (_ for _ in ()).throw(RuntimeError('timeout')))
check('page download failing falls back to the search snippet', st2 == 'ok' and 'Whitefly spreads the cotton leaf curl virus' in exs2[0]['text'], (st2, exs2))

# ---------- prompt + answer ----------
p = W.build_prompt('How does it spread?', exs, background='The farmer\'s leaf photo was classified as "X".')
check('prompt carries the question verbatim, excerpts, citation rule, safety rule',
      'QUESTION:\nHow does it spread?' in p and '[1]' in p and 'Never give an amount' in p and 'BACKGROUND' in p, p[:300])
good = lambda prompt: 'The virus is spread by whitefly [1]. Remove infected plants early [2][9].'
BG = 'The farmer\'s leaf photo was classified by an automated model as "Cotton leaf curl virus disease". This is a suggestion, not a confirmed diagnosis.'
Q_FARM = 'how does leaf curl spread by whitefly'
r = W.answer_from_web('How does it spread?', background=BG, searcher=fake_search, fetcher=fake_fetch, llm=good)
check('answer ok, invalid citation number removed, only cited pages listed', r['status'] == 'ok' and '[9]' not in r['answer'] and '[1]' in r['answer'] and all(s['url'].startswith('http') for s in r['sources']), r)
check('sources carry number, title and link', r['sources'] and set(r['sources'][0]) == {'n', 'title', 'url'}, r)
r = W.answer_from_web(Q_FARM, searcher=fake_search, fetcher=fake_fetch, llm=lambda p: W.NO_ANSWER)
check('model says pages do not answer -> no_answer', r['status'] == 'no_answer' and r['answer'] is None, r)
r = W.answer_from_web('who won the match', searcher=fake_search, fetcher=fake_fetch, llm=lambda p: W.OFF_TOPIC)
check('off-topic question -> declined', r['status'] == 'off_topic' and r['answer'] == W.OFF_TOPIC and r['sources'] == [], r)
def llm_down(p): raise requests.ConnectionError('ollama stopped')
r = W.answer_from_web(Q_FARM, searcher=fake_search, fetcher=fake_fetch, llm=llm_down)
check('language model down -> error status, no crash', r['status'] == 'error', r)
W.search_wikipedia = lambda q, t, limit=3: (_ for _ in ()).throw(requests.ConnectionError('no internet'))
r = W.answer_from_web(Q_FARM, searcher=offline, fetcher=fake_fetch, llm=good)
check('offline reported to the caller', r['status'] == 'offline' and r['answer'] is None, r)

# ---------- rules before the web search (no model, no internet) ----------
def boom(q, t): raise AssertionError('the web must not be searched for this question')
OFF = ['What is the capital of France?', 'Who won the 2018 FIFA World Cup?', 'How do I cook chicken biryani?',
       'Which tablet should I take for a headache?', 'Should I buy shares of a bank today?', 'How do I install Python on my laptop?']
for qq in OFF:
    r = W.answer_from_web(qq, searcher=boom, fetcher=fake_fetch, llm=good)
    check('off-topic, web not searched: ' + qq, r['status'] == 'off_topic' and r['answer'] == W.OFF_TOPIC and r['sources'] == [], r)
FARM = ['What is the minimum support price of cotton?', 'How can I get crop insurance for my cotton field?',
        'What seed rate should I use per acre for Bt cotton?', 'How do I apply for a Kisan Credit Card?',
        'What should I spray if sooty mould develops on my cotton?', 'How much water does cotton need per acre?',
        'When should I pick cotton?', 'How do I stop pink bollworm?', 'Why are my leaves turning red?',
        'How can I increase production?']
for qq in FARM:
    check('farming question goes on to the web: ' + qq, W.pre_check(qq) is None, W.pre_check(qq))
check('a question still in Hindi script is left to the model', W.pre_check('कपास में कीड़े का इलाज') is None)
check('empty question is not blocked here', W.pre_check('') is None)

r = W.pre_check('How do I treat it?')
check('"it" with no diagnosed photo -> asks which disease', r['status'] == 'need_more' and r['answer'] == W.NEED_MORE, r)
check('same question with a diagnosed photo goes on', W.pre_check('How do I treat it?', background=BG) is None)
r = W.answer_from_web('How do I treat it?', searcher=boom, fetcher=fake_fetch, llm=good)
check('need_more: web not searched', r['status'] == 'need_more' and r['sources'] == [], r)
check('"What can I do about it" also asks', W.pre_check('What can I do about it?')['status'] == 'need_more')

DOSEQ = ['What is the exact dose of glyphosate to spray on weeds in my cotton field?',
         'How much monocrotophos should I mix per litre of water for aphids?',
         'Give me the spray schedule and dose of acephate for cotton jassids.',
         'How many ml of imidacloprid per 15 litre pump?']
for qq in DOSEQ:
    r = W.answer_from_web(qq, searcher=boom, fetcher=fake_fetch, llm=good)
    check('dose question, web not searched: ' + qq[:50], r['status'] == 'no_dose' and r['answer'] == W.DOSE_MESSAGE and r['sources'] == [], r)
check('the dose refusal has no numbers', not any(ch.isdigit() for ch in W.DOSE_MESSAGE) and not any(ch.isdigit() for ch in W.DOSE_NOTE))
for qq in ['What should I spray for whitefly on cotton?', 'How often does whitefly come back?', 'What fertiliser does cotton need?']:
    check('no amount asked -> goes on: ' + qq, W.pre_check(qq) is None, W.pre_check(qq))

# ---------- amounts are removed from web answers ----------
DOSES = ['Use Trichoderma at about 4 g per kg of seed as an added bio layer for young roots [1].', 'Apply 250 g/ha of the product.',
         'Spray carbendazim at 1 g/L [1]', 'Mix 2 ml of imidacloprid in 1 litre of water [2].', 'Apply 50 kg urea per acre [1].',
         'Use 2.5 g per litre of copper oxychloride.', 'Spray @ 2 ml/L on the leaves.', 'Dissolve 25-30 g in 10 L of water.',
         'Use a 0.5% solution of neem oil [3].', 'Apply 500 ppm of the product.', 'Spray 5 ml in 1 litre.', 'Use 10 ml/10 L water']
for s in DOSES:
    check('dose sentence found: ' + s[:40], W.has_dose(s), s)
KEEP = ['Bolls weigh about 3.5 g per boll [1].', 'Remove infected plants early [2].', 'The seed rate is 8 kg per acre [1].', 'Whitefly can cause 20-25% yield loss [1].',
        'Check the field every 7 days [1].', 'Sow in June when the soil has enough moisture [2].', 'Spray when you see whitefly on the underside of leaves [1].',
        'The disease appeared in 2019 in 3 districts [1].']
for s in KEEP:
    check('no dose, kept: ' + s[:40], not W.has_dose(s), s)
t, n = W.strip_doses('- Spray carbendazim at 1 g/L [1]\n- Remove infected plants early [2]\n- Keep the field free of weeds [2]')
check('dose bullet removed, others kept', n == 1 and 'g/L' not in t and 'Remove infected plants early [2]' in t and t.count('\n') == 1 and t.startswith('- Remove'), (t, n))
t, n = W.strip_doses('Whitefly spreads the virus [1]. Spray 2 ml/L of imidacloprid [2]. Remove infected plants [1].')
check('only the dose sentence is cut out of a paragraph', n == 1 and t == 'Whitefly spreads the virus [1]. Remove infected plants [1].', (t, n))
t, n = W.strip_doses('Whitefly spreads the virus [1].')
check('nothing to remove -> unchanged', n == 0 and t == 'Whitefly spreads the virus [1].', (t, n))
t, n = W.strip_doses('1. Mix 2 g in 1 litre of water.\n2. Spray the plants.')
check('numbered list: dose step removed', n == 1 and 'Mix' not in t and 'Spray the plants.' in t, (t, n))

LLM_DOSE = lambda p: ('- Whitefly spreads the leaf curl virus [1].\n- Spray imidacloprid at 0.5 ml/L of water [2].\n- Remove infected plants early [1].')
r = W.answer_from_web('what can I do about leaf curl in cotton', searcher=fake_search, fetcher=fake_fetch, llm=LLM_DOSE)
check('web answer with a dose: dose removed, note added, rest kept',
      r['status'] == 'ok' and 'ml/L' not in r['answer'] and 'imidacloprid' not in r['answer'] and r['answer'].endswith(W.DOSE_NOTE)
      and 'Whitefly spreads' in r['answer'] and 'Remove infected plants' in r['answer'], r)
r = W.answer_from_web('what can I do about leaf curl in cotton', searcher=fake_search, fetcher=fake_fetch,
                      llm=lambda p: 'Spray imidacloprid at 0.5 ml/L of water [1].')
check('web answer that is only a dose -> refused, no sources', r['status'] == 'no_dose' and r['answer'] == W.DOSE_MESSAGE and r['sources'] == [], r)
r = W.answer_from_web('what can I do about leaf curl in cotton', searcher=fake_search, fetcher=fake_fetch,
                      llm=lambda p: '- Whitefly spreads the leaf curl virus between cotton plants, so infected plants should be removed early [1].\n- Use 2 g/L of a fungicide [2].')
check('sources only list pages still cited after removal', r['status'] == 'ok' and [s['n'] for s in r['sources']] == [1], r)
check('the prompt tells the model not to give amounts', 'Never give an amount' in W.build_prompt('q', exs, None))

# ---------- the search uses the diagnosed disease ----------
s, bg2, used = F.plan_question('Anthracnose', 'How do I treat it?')
check('follow-up search words carry the disease: "treat Anthracnose cotton"', W.search_query(s) == 'treat Anthracnose cotton', W.search_query(s))
seen = []
def spy(q, t): seen.append(q); return res
W.answer_from_web('How do I treat it?', background=bg2, search_q=W.search_query(s), searcher=spy, fetcher=fake_fetch, llm=good)
check('the web search got the disease name', seen and 'Anthracnose' in seen[0], seen)
check('the search words end with India (other countries kept out)', seen[0].endswith(' India'), seen)
seen.clear()
W.answer_from_web('how does leaf curl spread by whitefly in India', searcher=spy, fetcher=fake_fetch, llm=good)
check('India is not added twice', seen and seen[0].lower().count('india') == 1, seen)

print('\nFAILED:', fails if fails else 'none')
sys.exit(1 if fails else 0)
