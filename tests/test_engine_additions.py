"""Checks that the two additions to the search engine work inside RAGEngine: the keyword rescue (extra passage) and the
note that shows both amounts when the guide disagrees with itself. The database and the language model are replaced by
small stand-ins, so no Ollama and no internet are needed."""
import os, sys, types, tempfile
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'backend'))

chroma = types.ModuleType('chromadb'); chroma_cfg = types.ModuleType('chromadb.config')
chroma_cfg.Settings = object; chroma.config = chroma_cfg
sys.modules.setdefault('chromadb', chroma); sys.modules.setdefault('chromadb.config', chroma_cfg)

import rag_engine as RE
import dose_conflicts
from config import Config

fails = []
def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name)
    if not cond:
        fails.append(name)
        if extra != '': print('   ', str(extra)[:500])

FILLER = [f'Passage {i} about cotton whitefly spraying and weather in field number {i} with plenty of ordinary words.' for i in range(60)]
TARGET = '[Bacterial Leaf Blight] Acid delinting: ensure seeds are delinted using sulfuric acid. This destroys bacterial inoculum on the fuzzy seeds.'
BLB = ('[Bacterial Leaf Blight] Chemical spray: if early foliar symptoms emerge and the weather is highly humid, spray '
       'Carbendazim 12% + Mancozeb 63 % WP @ 30g /10L of water.')
ALL = FILLER + [TARGET, BLB]


class FakeCollection:
    def __init__(self, found):
        self.found = found       # the passages the "embedding search" returns
    def count(self): return len(ALL)
    def get(self, include=None): return {'documents': ALL, 'metadatas': [{'doc_id': 'guide'}] * len(ALL)}
    def query(self, query_embeddings, n_results):
        f = self.found[:n_results]
        return {'documents': [f], 'metadatas': [[{'doc_id': 'guide'}] * len(f)], 'distances': [[0.2] * len(f)]}

class FakeEmbedder:
    def encode(self, texts, show_progress_bar=False, prefix=''):
        return np.array([1.0, 2.0]) if isinstance(texts, str) else [[1.0, 2.0] for _ in texts]

def engine(found):
    Config.CHROMA_DATA_FOLDER = tempfile.mkdtemp()
    e = object.__new__(RE.RAGEngine)
    e.collection = FakeCollection(found); e.embeddings_model = FakeEmbedder(); e.documents_registry = {}
    e._save_registry = lambda: None
    e._init_embedding_scheme()
    e.top_k, e.model_name, e.ollama_url, e.temperature = 5, 'm', 'http://x', 0.0
    return e

class Resp:
    def __init__(self, text): self.text = text
    def json(self): return {'response': self.text}
posted = []
def fake_post(text):
    return lambda url, json=None, timeout=None: (posted.append(json['prompt']), Resp(text))[1]

# ---------------------------------------------------------------- keyword rescue inside the engine
Config.LEXICAL_RESCUE = True
e = engine(FILLER[:5])
chunks, metas, sims = e._retrieve_context('Why should cotton seed be acid delinted?', 5)
check('keyword rescue adds the passage the meaning search missed, at the end', chunks[-1] == TARGET and len(chunks) == 6 and len(metas) == len(chunks) == len(sims), chunks[-1][:60])
check('the added passage has similarity 0.0, so "is it covered" still uses the embedding scores', sims[-1] == 0.0 and max(sims) > 0.5, sims)
e = engine(FILLER[:4] + [TARGET])
chunks, _, _ = e._retrieve_context('Why should cotton seed be acid delinted?', 5)
check('a passage the search already found is not added twice', chunks.count(TARGET) == 1 and len(chunks) == 5)
e = engine(FILLER[:5])
chunks, _, _ = e._retrieve_context('How does whitefly spread in cotton?', 5)
check('a question without two rare words gets no extra passage', len(chunks) == 5)
Config.LEXICAL_RESCUE = False
e = engine(FILLER[:5])
check('switched off in the settings: nothing is added', len(e._retrieve_context('Why should cotton seed be acid delinted?', 5)[0]) == 5)
Config.LEXICAL_RESCUE = True
e = engine(FILLER[:5]); e._lexical_index = lambda: (_ for _ in ()).throw(RuntimeError('boom'))
check('if the keyword step breaks, the normal search result is still returned', len(e._retrieve_context('Why should cotton seed be acid delinted?', 5)[0]) == 5)

# ---------------------------------------------------------------- both amounts when the guide disagrees
real_post = RE.requests.post
Q = 'What spray should I use for bacterial leaf blight and how much per 10 litres of water?'
e = engine([BLB] + FILLER[:4])
RE.requests.post = fake_post('Spray Carbendazim 12% + Mancozeb 63% WP at 30 g per 10 L of water.')
r = e.query(Q, top_k=5, answer_language='en')
check('grounded answer with one amount: the note with both amounts is appended', r['grounded'] and r['response'].count('Note:') == 1 and '25 g per 10 L' in r['response'] and r['response'].startswith('Spray Carbendazim'), r['response'])
RE.requests.post = fake_post("I don't have information about this.")
r = e.query(Q, top_k=5, answer_language='en')
check('a declined answer gets no note', not r['grounded'] and 'Note:' not in r['response'])
RE.requests.post = fake_post('Bacterial blight spreads through infected seed and rain splash.')
r = e.query('How does bacterial leaf blight spread?', top_k=5, answer_language='en')
check('a question that is not about amounts gets no note', r['grounded'] and 'Note:' not in r['response'], r['response'])
RE.requests.post = fake_post('Use 30 g per 10 L.')
e2 = engine([BLB] + FILLER[:4])
r = e2.query('How do I control it?', top_k=5, answer_language='en', retrieval_query='How do I control it? cotton Bacterial leaf blight',
             background='The farmer\'s leaf photo was classified by an automated model as "Bacterial leaf blight".')
check('follow-up: the diagnosed disease from the photo counts as the topic', '25 g per 10 L' in r['response'], r['response'])
orig = dose_conflicts.note_for
dose_conflicts.note_for = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('boom'))
RE.requests.post = fake_post('Spray 30 g per 10 L of water.')
r = engine([BLB] + FILLER[:4]).query(Q, top_k=5, answer_language='en')
check('if the note step breaks, the answer is still returned as the model wrote it', r['grounded'] and r['response'] == 'Spray 30 g per 10 L of water.', r['response'])
dose_conflicts.note_for = orig
RE.requests.post = real_post

print('\nFAILED:', fails if fails else 'none')
sys.exit(1 if fails else 0)
