import os, sys, types, tempfile, shutil
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'backend'))
sys.path.insert(0, os.path.join(HERE, '..', 'eval'))

# chromadb is not needed here: the engine is built by hand around a fake collection
chroma = types.ModuleType('chromadb'); chroma_cfg = types.ModuleType('chromadb.config')
chroma_cfg.Settings = object; chroma.config = chroma_cfg
sys.modules.setdefault('chromadb', chroma); sys.modules.setdefault('chromadb.config', chroma_cfg)

import rag_engine as RE
from config import Config

fails = []
def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name)
    if not cond:
        fails.append(name)
        if extra != '': print('   ', extra)


class FakeCollection:
    def __init__(self, n=0): self.n, self.added = n, []
    def count(self): return self.n
    def add(self, ids, embeddings, documents, metadatas): self.added.append(documents); self.n += len(documents)
    def query(self, query_embeddings, n_results):
        return {'documents': [['a chunk']], 'metadatas': [[{'doc_id': 'd'}]], 'distances': [[0.2]]}

class FakeEmbedder:
    def __init__(self, zero_for=()): self.calls, self.zero_for = [], zero_for
    def encode(self, texts, show_progress_bar=False, prefix=''):
        self.calls.append((texts, prefix))
        if isinstance(texts, str): return np.array([1.0, 2.0])
        return [[0.0, 0.0] if i in self.zero_for else [1.0, 2.0] for i, _ in enumerate(texts)]

def engine(folder, count=0, scheme_file=None, embedder=None):
    Config.CHROMA_DATA_FOLDER = folder
    if scheme_file is not None:
        open(os.path.join(folder, 'embedding_scheme.txt'), 'w').write(scheme_file)
    e = object.__new__(RE.RAGEngine)
    e.collection = FakeCollection(count); e.embeddings_model = embedder or FakeEmbedder(); e.documents_registry = {}
    e._save_registry = lambda: None
    e._init_embedding_scheme()
    return e

old_folder = Config.CHROMA_DATA_FOLDER
tmp = tempfile.mkdtemp()
def fresh():
    d = tempfile.mkdtemp(dir=tmp); return d

# ---- the prefix reaches the embedding request
sent = []
class Resp:
    status_code = 200
    def json(self): return {'embedding': [0.1, 0.2]}
real_post = RE.requests.post
RE.requests.post = lambda url, json=None, timeout=None: (sent.append(json['prompt']), Resp())[1]
RE.NomicEmbeddings('http://x').encode(['alpha', 'beta'], prefix='search_document: ')
RE.NomicEmbeddings('http://x').encode('question?', prefix='search_query: ')
RE.NomicEmbeddings('http://x').encode('plain')
RE.requests.post = real_post
check('the prefix is added to every text sent for embedding, and only when asked for', sent == ['search_document: alpha', 'search_document: beta', 'search_query: question?', 'plain'], sent)

# ---- which scheme a database uses
check('a new empty database uses the prefixes', engine(fresh()).use_prefixes is True)
check('an existing database without the marker file is searched without prefixes (it was built without them)', engine(fresh(), count=900).use_prefixes is False)
check('a database that says "plain" stays plain even when empty', engine(fresh(), scheme_file='plain').use_prefixes is False)
check('a database that says "nomic-prefixes" uses them', engine(fresh(), count=500, scheme_file='nomic-prefixes').use_prefixes is True)
Config.USE_NOMIC_PREFIXES = False
check('with the setting off, a new database is built without prefixes', engine(fresh()).use_prefixes is False)
Config.USE_NOMIC_PREFIXES = True
check('a marker file with nonsense in it is ignored', engine(fresh(), count=10, scheme_file='???').use_prefixes is False)

# ---- documents and questions use the scheme of the database
d = fresh(); emb = FakeEmbedder(); e = engine(d, embedder=emb)
ok = e.add_document('guide_txt', ['chunk one', 'chunk two'], 'guide.txt')
check('documents are embedded with the document prefix', ok and emb.calls[-1] == (['chunk one', 'chunk two'], 'search_document: '), emb.calls)
check('the scheme is saved next to the database after the first document', open(os.path.join(d, 'embedding_scheme.txt')).read() == 'nomic-prefixes')
e._retrieve_context('how much water?', 3)
check('questions are embedded with the query prefix', emb.calls[-1] == ('how much water?', 'search_query: '), emb.calls)

d2 = fresh(); emb2 = FakeEmbedder(); e2 = engine(d2, count=50, embedder=emb2)
e2.add_document('more_txt', ['x'], 'more.txt'); e2._retrieve_context('q', 3)
check('an older database keeps getting plain embeddings for documents and questions', emb2.calls[0][1] == '' and emb2.calls[1][1] == '', emb2.calls)
check('and its marker file records that', open(os.path.join(d2, 'embedding_scheme.txt')).read() == 'plain')

# ---- a failed embedding is not stored
d3 = fresh(); emb3 = FakeEmbedder(zero_for=(1,)); e3 = engine(d3, embedder=emb3)
ok3 = e3.add_document('bad_txt', ['good', 'bad one'], 'bad.txt')
check('a document with an unembeddable chunk is refused, not stored with an empty vector', ok3 is False and e3.collection.added == [] and 'bad_txt' not in e3.documents_registry)

import chunking_experiment as CE
check('the experiment that chose this setup used the same prefixes as the app', CE.DOC_PREFIX == RE.NOMIC_DOCUMENT_PREFIX and CE.QUERY_PREFIX == RE.NOMIC_QUERY_PREFIX)
check('the chunk size in the settings is the one the experiment chose', (Config.CHUNK_SIZE, Config.CHUNK_OVERLAP) == (800, 100) and Config.LLM_NUM_CTX >= 4096)

Config.CHROMA_DATA_FOLDER = old_folder
shutil.rmtree(tmp, ignore_errors=True)
print('\nFAILED:', fails if fails else 'none')
sys.exit(1 if fails else 0)
