"""Checks for the v2 cotton classifier (gate + disease model) and its use in app.py.
Uses a tiny synthetic bundle and a fake embedder, so no photos or backbone are needed.
Run: python tests/test_cotton_v2.py"""
import io
import json
import os
import sys
import tempfile
import types

import numpy as np

BACK = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backend'))
fails = []


def check(n, c, x=''):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x)[:300] if (x and not c) else ''))
    if not c:
        fails.append(n)


# ---- synthetic embeddings: cotton near A, not-cotton near B; Healthy / Spot inside cotton
rng = np.random.default_rng(0)
D = 768
VA, VB, VH, VS = (rng.normal(size=D) for _ in range(4))


def unit(v):
    return (v / np.linalg.norm(v)).astype(np.float32)


def sample(kind):
    base = {'healthy': VA + 0.8 * VH, 'spot': VA + 0.8 * VS, 'other': VB}[kind]
    return unit(base + 0.25 * rng.normal(size=D))


from sklearn.linear_model import LogisticRegression  # noqa: E402

Xc = np.stack([sample('healthy') for _ in range(40)] + [sample('spot') for _ in range(40)])
Xn = np.stack([sample('other') for _ in range(80)])
gate = LogisticRegression(max_iter=2000).fit(np.vstack([Xc, Xn]), [1] * 80 + [0] * 80)
dis = LogisticRegression(max_iter=2000).fit(Xc, [0] * 40 + [1] * 40)
M = tempfile.mkdtemp()
import joblib  # noqa: E402

joblib.dump({'version': 2, 'gate': gate, 'gate_rule': {'p_min': 0.5, 'knn_min': 0.3},
             'cotton_ref': Xc.astype(np.float16), 'disease': dis, 'class_names': ['Healthy', 'Spot']},
            M + '/cotton_v2.joblib')
json.dump({'per_class': {'Healthy': {'f1': 0.9}, 'Spot': {'f1': 0.8}}, 'accuracy': 0.9, 'macro_f1': 0.85},
          open(M + '/metrics_v2.json', 'w'))

# the fake embedder reads the kind from the uploaded file's bytes
KIND = {'next': 'healthy'}


def fake_embed(path):
    return sample(KIND['next'])


# ---- stubs so app.py imports without chromadb/whisper/piper
class FakeRAG:
    calls = []
    documents_registry = {}

    def has_documents(s): return True
    def initialize(s): pass
    def get_status(s): return {}

    def query(s, q, top_k=5, answer_language=None, retrieval_query=None, background=None):
        FakeRAG.calls.append(q)
        return {'response': 'Remove infected leaves. (Source 1)', 'source_documents': ['icar.pdf'],
                'retrieval_score': 0.8, 'grounded': True}


for name, attrs in {'rag_engine': {'RAGEngine': FakeRAG},
                    'document_processor': {'DocumentProcessor': type('DP', (), {})},
                    'voice_handler': {'VoiceHandler': type('VH', (), {})},
                    'tts_piper': {'save_audio_file': lambda t, p, l=None: True}}.items():
    m = types.ModuleType(name)
    m.__dict__.update(attrs)
    sys.modules[name] = m
sys.path.insert(0, BACK)
from config import Config  # noqa: E402

Config.COTTON_MODEL_VERSION = 'v2'
Config.COTTON_V2_MODEL_PATH = M + '/cotton_v2.joblib'
Config.COTTON_V2_METRICS_PATH = M + '/metrics_v2.json'
Config.ENABLE_WEB_LOOKUP = False
import cotton_classifier as CC  # noqa: E402

clf = CC.load_cotton_classifier()
check('factory loads v2 when its files exist', isinstance(clf, CC.CottonClassifierV2) and clf.version == 2)
clf._embed_fn = fake_embed

KIND['next'] = 'other'
d = clf.predict('x.jpg')
check('not-cotton photo -> status not_cotton, no disease, no guesses',
      d['status'] == 'not_cotton' and d['disease'] is None and d['top3'] == [], d)
KIND['next'] = 'healthy'
d = clf.predict('x.jpg')
check('healthy cotton leaf -> confident Healthy', d['status'] == 'confident' and d['disease'] == 'Healthy', d)
KIND['next'] = 'spot'
d = clf.predict('x.jpg')
check('diseased cotton leaf -> confident Spot', d['status'] == 'confident' and d['disease'] == 'Spot', d)
check('decision carries the cotton score', 0.5 <= d['cotton_score'] <= 1.0, d)

# missing v2 file -> falls back to v1 (v1 file also missing here -> raises the v1 error)
Config.COTTON_V2_MODEL_PATH = M + '/nope.joblib'
Config.COTTON_MODEL_PATH = M + '/nope_svm.joblib'
try:
    CC.load_cotton_classifier()
    check('missing v2 falls back to v1', False, 'no error raised')
except CC.CottonClassifierUnavailable as e:
    check('missing v2 falls back to v1 (and reports the v1 file)', 'train_classifier.py' in str(e), e)
Config.COTTON_V2_MODEL_PATH = M + '/cotton_v2.joblib'

# ---- through the app
import app as A  # noqa: E402

A.cotton_classifier = clf
Config.UPLOAD_FOLDER = tempfile.mkdtemp()
A.app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER
C = A.app.test_client()
import cv2  # noqa: E402

ok, buf = cv2.imencode('.jpg', np.full((64, 64, 3), 120, np.uint8))


def post():
    return C.post('/api/diagnose', data={'image': (io.BytesIO(buf.tobytes()), 'a.jpg'), 'language': 'en'},
                  content_type='multipart/form-data').get_json()


KIND['next'] = 'other'
FakeRAG.calls.clear()
r = post()
check('app: not-cotton photo -> not_cotton message, no RAG call',
      r['diagnosis']['status'] == 'not_cotton' and 'does not look like a cotton leaf' in r['advice']
      and not FakeRAG.calls, r)
check('app: not-cotton session has no disease', A.sessions.get(r['session_id'])['disease'] is None)
KIND['next'] = 'healthy'
r = post()
check('app: healthy -> healthy message, no RAG call',
      r['diagnosis']['disease'] == 'Healthy' and 'looks healthy' in r['advice'] and not FakeRAG.calls, r)
KIND['next'] = 'spot'
r = post()
check('app: disease -> grounded advice with the disease in the query',
      r['diagnosis']['disease'] == 'Spot' and r['grounded'] and FakeRAG.calls and 'Spot' in FakeRAG.calls[0], r)
s = C.get('/api/cotton-status').get_json()
s = s.get('data', s)
check('status reports model version 2 and its classes', s.get('model_version') == 2 and s.get('classes') == ['Healthy', 'Spot'], s)

print(f'\n{len(fails)} failed' if fails else '\nall passed')
sys.exit(1 if fails else 0)
