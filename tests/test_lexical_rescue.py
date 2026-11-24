"""Checks for backend/lexical_rescue.py (the keyword add-on to the document search). No Ollama, no internet.
Part of it runs on the real guide text if documents/ has it."""
import json, os, sys, types
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(ROOT, 'backend'))
sys.path.insert(0, os.path.join(ROOT, 'eval'))
import lexical_rescue as L
fails = []
def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x)[:400] if (x and not c) else ''))
    if not c: fails.append(n)
def skip(n, why): print('SKIP ' + n + ' (' + why + ')')

# ---------------------------------------------------------------- the pieces
check('stemmer joins delinted / delinting / delint', L.stem('delinted') == L.stem('delinting') == L.stem('delint') == 'delint')
check('stemmer leaves short words alone', L.stem('was') == 'was' and L.stem('rot') == 'rot')
check('stop words and short words are dropped', L.tokens('Why should the cotton be at it?') == ['cotton'])

# ---------------------------------------------------------------- a small corpus
filler = [f'Passage {i} about cotton whitefly spraying and weather in field number {i} with plenty of ordinary words.' for i in range(60)]
target = 'Acid delinting: ensure seeds are delinted using sulfuric acid. This destroys bacterial inoculum on the fuzzy seeds of cotton.'
other = 'Treat acid-delinted seeds with Carbendazim before sowing cotton.'
texts = filler + [target, other]
metas = [{'doc_id': 'guide'}] * len(texts)
ix = L.Index(texts, metas)
r = ix.rescue('Why should cotton seed be acid delinted?')
check('two rare words in the question -> the passage that holds both is added', len(r) == 1 and r[0][0] == target and {'acid', 'delint'} <= set(r[0][3]), r)
check('the passage already found by the embedding search is not added again', ix.rescue('Why should cotton seed be acid delinted?', exclude=[target])[0][0] == other)
check('only one rare word in the question -> nothing added', ix.rescue('What is acid?') == [] and ix.rescue('Who won the world cup?') == [])
check('a question with no rare word -> nothing added', ix.rescue('How does cotton spread in the field?') == [])
check('k limits how many are added', len(ix.rescue('Why should cotton seed be acid delinted?', k=2)) == 2 and len(ix.rescue('Why should cotton seed be acid delinted?', k=1)) == 1)
check('same answer every time', ix.rescue('Why should cotton seed be acid delinted?') == ix.rescue('Why should cotton seed be acid delinted?'))
check('empty corpus and empty question do not crash', L.Index([]).rescue('anything here') == [] and ix.rescue('') == [] and ix.rescue(None) == [])

# ---------------------------------------------------------------- the real guide
GUIDE = os.path.join(ROOT, 'documents', 'CICR_Illustrative_Guide_Cotton_Pests_Diseases_2026.txt')
BENCH = os.path.join(ROOT, 'eval', 'cotton_qa_benchmark.json')
if not (os.path.exists(GUIDE) and os.path.exists(BENCH)):
    skip('rescue on the real guide', 'guide or benchmark file not found')
else:
    for name in ('PyPDF2', 'docx'):
        if name not in sys.modules:
            m = types.ModuleType(name); m.PdfReader = object; m.Document = object; sys.modules[name] = m
    from document_processor import DocumentProcessor
    import advisor_benchmark as AD
    dp = DocumentProcessor()
    chunks = dp._chunk_sections(dp._clean_text(open(GUIDE, encoding='utf-8').read()))
    gix = L.Index(chunks)
    items = AD.load_items()
    by = {i['id']: i for i in items}
    q11 = gix.rescue(by['Q11']['question_en'])
    flat = lambda t: AD.flat(AD.normalize_units(t))
    check('Q11 (acid delinting): the rescue finds the passage with sulfuric acid and inoculum',
          len(q11) == 1 and 'sulfuric' in flat(q11[0][0]) and 'inoculum' in flat(q11[0][0]), q11[:1])
    quiet = [i['id'] for i in items if i['category'] in ('not_in_guide', 'unsafe_probe', 'out_of_scope') and gix.rescue(i['question_en'])]
    check('no extra passage for any "not in the guide", unsafe or out-of-scope question', not quiet, quiet)
    quiet_f = [i['id'] for i in items if i['category'] == 'followup' and gix.rescue(i['question_en'])]
    check('no extra passage for the follow-up questions ("How does it spread?")', not quiet_f, quiet_f)
    extra = [i['id'] for i in items if gix.rescue(i['question_en'])]
    check('the rescue stays rare: at most a third of the questions get an extra passage', len(extra) <= len(items) / 3, extra)
    print('     (questions that get an extra passage:', extra, ')')

print('\nFAILED:', fails if fails else 'none')
sys.exit(1 if fails else 0)
