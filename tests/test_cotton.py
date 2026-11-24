import sys, types, os, json, io, subprocess, shutil, tempfile
import numpy as np, cv2
BACK=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','backend')
BACK=os.path.abspath(BACK)
MODELS=tempfile.mkdtemp()   # never touches the real backend/cotton/models
fails=[]
def check(n,c,x=''):
    print(('PASS ' if c else 'FAIL ')+n+(' '+str(x)[:300] if (x and not c) else ''))
    if not c: fails.append(n)

# ---- synthetic dataset: 3 classes + a 'Healthy' folder ----
rng=np.random.default_rng(0)
D=tempfile.mkdtemp(); 
def leaf(kind):
    img=np.zeros((256,256,3),np.uint8); img[:]=(40,150,50)         # green leaf (BGR)
    for _ in range(rng.integers(4,9)):
        x,y,r=rng.integers(30,226,2).tolist()+[int(rng.integers(6,20))]
        col={'Spot':(30,60,140),'Curl':(60,200,200),'Mould':(25,25,25)}.get(kind)
        if col: cv2.circle(img,(x,y),r,col,-1)
    noise=rng.integers(-12,12,img.shape); return np.clip(img.astype(int)+noise,0,255).astype(np.uint8)
for k in ['Healthy','Spot','Curl','Mould']:
    os.makedirs(f'{D}/{k}')
    for i in range(30): cv2.imwrite(f'{D}/{k}/{i}.jpg', leaf(k))
open(f'{D}/Spot/broken.jpg','wb').write(b'not an image')

r=subprocess.run([sys.executable,BACK+'/cotton/train_classifier.py','--data-dir',D,'--out-dir',MODELS],capture_output=True,text=True)
print(r.stdout[-900:]); 
check('train script runs', r.returncode==0, r.stderr[-800:])
check('model + metrics written', os.path.exists(MODELS+'/cotton_svm.joblib') and os.path.exists(MODELS+'/metrics.json'))
M=json.load(open(MODELS+'/metrics.json'))
check('metrics contain per-class f1 and threshold table', len(M['per_class'])==4 and len(M['threshold_table'])>=5)
check('synthetic data is learnable (sanity)', M['accuracy']>0.8, M['accuracy'])
check('broken image skipped, not fatal', 'skipped' in r.stdout)

# ---- stubs so app.py imports without chromadb/whisper/piper ----
class FakeRAG:
    docs=True; calls=[]
    documents_registry={}
    def has_documents(s): return s.docs
    def initialize(s): pass
    def get_status(s): return {}
    def query(s,q,top_k=5,answer_language=None,retrieval_query=None,background=None):
        FakeRAG.calls.append((q,answer_language,retrieval_query,background))
        if 'blight' in q.lower() or 'spot' in q.lower(): return {'response':'Remove infected leaves. (Source 1)','source_documents':['icar_cotton.pdf'],'retrieval_score':0.62,'grounded':True}
        return {'response':"I don't have information about this in the available documents.",'source_documents':[],'retrieval_score':0.1,'grounded':False}
for name,attrs in {'rag_engine':{'RAGEngine':FakeRAG},
                   'document_processor':{'DocumentProcessor':type('DP',(),{})},
                   'voice_handler':{'VoiceHandler':type('VH',(),{})},
                   'tts_piper':{'save_audio_file':lambda t,p,l=None:(open(p,'wb').write(b'RIFF'),True)[1]}}.items():
    m=types.ModuleType(name); m.__dict__.update(attrs); sys.modules[name]=m
sys.path.insert(0,BACK)
from config import Config
Config.COTTON_MODEL_PATH=MODELS+'/cotton_svm.joblib'; Config.COTTON_METRICS_PATH=MODELS+'/metrics.json'
import app as A
import translator, requests
Config.UPLOAD_FOLDER=tempfile.mkdtemp(); A.app.config['UPLOAD_FOLDER']=Config.UPLOAD_FOLDER
Config.ENABLE_WEB_LOOKUP=False      # these tests never touch the internet; web fallback has its own checks below
C=A.app.test_client()

def jpg(kind):
    ok,buf=cv2.imencode('.jpg',leaf(kind)); return io.BytesIO(buf.tobytes())

# status
d=C.get('/api/cotton-status').get_json()
check('status: loaded, languages, honest metrics', d['classifier_loaded'] and d['voice_languages']==['en','hi'] and 'test_macro_f1' in d, d)

# diagnose errors
check('no image -> 400', C.post('/api/diagnose').status_code==400)
check('garbage file -> 400', C.post('/api/diagnose',data={'image':(io.BytesIO(b'hello'),'x.jpg')},content_type='multipart/form-data').status_code==400)
check('unsupported language -> 400', C.post('/api/diagnose',data={'image':(jpg('Spot'),'a.jpg'),'language':'gu'},content_type='multipart/form-data').status_code==400)

# confident diagnosis -> RAG with disease in the query
Config.COTTON_MIN_PROBABILITY=0.4; Config.COTTON_MIN_CLASS_F1=0.0
FakeRAG.calls.clear()
r=C.post('/api/diagnose',data={'image':(jpg('Spot'),'a.jpg'),'language':'en'},content_type='multipart/form-data'); d=r.get_json()
check('diagnose 200', r.status_code==200, d)
check('diagnose returns Spot confidently', d['diagnosis']['status']=='confident' and d['diagnosis']['disease']=='Spot', d['diagnosis'])
check('advice grounded with sources', d['grounded'] and d['source_documents']==['icar_cotton.pdf'], d)
check('RAG query contains the diagnosed disease', FakeRAG.calls and 'Spot' in FakeRAG.calls[0][0], FakeRAG.calls)
check('always carries the not-a-diagnosis note', 'not a confirmed diagnosis' in d['diagnosis']['note'])
check('uploaded temp image removed', not [f for f in os.listdir(Config.UPLOAD_FOLDER) if f.startswith('leaf_')])
sid=d['session_id']

# chat follows the session
FakeRAG.calls.clear()
r=C.post('/api/chat',json={'session_id':sid,'question':'how do I stop it spreading?'}); d=r.get_json()
check('chat uses disease context', r.status_code==200 and d['disease_context']=='Spot' and d['used_diagnosis'] is True, (d,FakeRAG.calls))
check('question reaches the model exactly as typed', FakeRAG.calls[0][0]=='how do I stop it spreading?', FakeRAG.calls)
check('disease goes in as search words + separate background, not into the question',
      'Spot' in FakeRAG.calls[0][2] and 'Spot' in (FakeRAG.calls[0][3] or ''), FakeRAG.calls)
FakeRAG.calls.clear()
d=C.post('/api/chat',json={'session_id':sid,'question':'How much water does cotton need?'}).get_json()
check('unrelated question: no diagnosis used, no background',
      d['used_diagnosis'] is False and FakeRAG.calls[0][0]=='How much water does cotton need?' and FakeRAG.calls[0][3] is None and 'Spot' not in FakeRAG.calls[0][2], (d,FakeRAG.calls))
check('chat bad session -> 404', C.post('/api/chat',json={'session_id':'nope','question':'x'}).status_code==404)
check('chat empty question -> 400', C.post('/api/chat',json={'question':' '}).status_code==400)
check('chat without session works (general)', C.post('/api/chat',json={'question':'how much water?'}).status_code==200)

# unsupported regional language typed (Gujarati script) with IndicTrans off -> clear 400
r=C.post('/api/chat',json={'question':'કપાસ માં રોગ'}); 
check('gujarati text without IndicTrans -> 400 (no fake support)', r.status_code==400, r.get_json())

# Hindi typed -> translated to English for retrieval, answer translated back, audio in hi
seq=iter(['How to protect cotton from Spot?','रोगग्रस्त पत्तियां हटाएं'])
orig=requests.post
class R:
    status_code=200
    def __init__(s,t): s.t=t
    def json(s): return {'response':s.t}
requests.post=lambda *a,**k: R(next(seq))
FakeRAG.calls.clear()
r=C.post('/api/chat',json={'session_id':sid,'question':'कपास को कैसे बचाएं?','language':'hi','speak':True}); d=r.get_json()
requests.post=orig
check('hindi chat: english used for retrieval', 'protect cotton' in FakeRAG.calls[0][0], FakeRAG.calls)
check('hindi chat: answer in Hindi + audio', d['answer_language']=='hi' and d['response']=='रोगग्रस्त पत्तियां हटाएं' and d['audio_url'], d)

# English typed while Hindi is selected: no 'Hindi -> English' step that could reword it
def boom_early(*a,**k): raise requests.exceptions.ConnectionError('x')
requests.post=boom_early
FakeRAG.calls.clear()
r=C.post('/api/chat',json={'session_id':sid,'question':'what is the best time to sow cotton?','language':'hi'}); d=r.get_json()
requests.post=orig
check('english typed under Hindi: question unchanged, still answered', r.status_code==200 and d['question_english']=='what is the best time to sow cotton?' and FakeRAG.calls[0][0]=='what is the best time to sow cotton?', (r.status_code,d,FakeRAG.calls))

# translation failure -> English fallback, flagged
def boom(*a,**k): raise requests.exceptions.ConnectionError('x')
requests.post=boom
r=C.post('/api/chat',json={'session_id':sid,'question':'hello','language':'en'}); 
requests.post=orig
# hindi question while translator is down -> 502, not a silent wrong answer
requests.post=boom
r=C.post('/api/chat',json={'question':'कपास','language':'hi'}); requests.post=orig
check('hindi question, translator down -> 502', r.status_code==502, r.get_json())

# abstain path adds referral
FakeRAG.calls.clear()
d=C.post('/api/chat',json={'question':'what is the moon made of'}).get_json()
check('abstain is not grounded and refers to KVK', d['grounded'] is False and 'Krishi Vigyan Kendra' in d['response'], d)

# ---- internet fallback ----
Config.ENABLE_WEB_LOOKUP=True
real_web=A.web_lookup.answer_from_web
calls_web=[]; search_seen=[]
def fake_web(q,background=None,**k):
    calls_web.append((q,background)); search_seen.append(k.get('search_q')); return {'status':'ok','answer':'Whitefly spreads it [1].','sources':[{'n':1,'title':'ICAR guide','url':'https://icar.gov.in/x'}]}
A.web_lookup.answer_from_web=fake_web
d=C.post('/api/chat',json={'question':'what is the moon made of'}).get_json()
check('documents miss -> internet answer with its links', d['source_kind']=='web' and d['response']=='Whitefly spreads it [1].' and d['web_sources'][0]['url']=='https://icar.gov.in/x' and d['grounded'] is False, d)
check('internet step got the exact question', calls_web and calls_web[-1][0]=='what is the moon made of', calls_web)
d=C.post('/api/chat',json={'session_id':sid,'question':'How do I treat it?'}).get_json()
check('follow-up: the web search words carry the diagnosed disease', d['source_kind']=='web' and search_seen and 'Spot' in (search_seen[-1] or ''), (d,search_seen))
calls_web.clear()
d=C.post('/api/chat',json={'session_id':sid,'question':'which spot treatment is in the guide?'}).get_json()
check('documents answer -> internet not used', d['source_kind']=='documents' and d['grounded'] and not calls_web, (d,calls_web))
A.web_lookup.answer_from_web=lambda q,background=None,**k:{'status':'offline','answer':None,'sources':[]}
d=C.post('/api/chat',json={'question':'what is the moon made of'}).get_json()
check('offline -> KVK message kept and status reported', d['source_kind']=='none' and d['web_status']=='offline' and 'Krishi Vigyan Kendra' in d['response'], d)
A.web_lookup.answer_from_web=lambda q,background=None,**k:{'status':'off_topic','answer':'That is outside what I can help with here.','sources':[]}
d=C.post('/api/chat',json={'question':'who won the match'}).get_json()
check('off-topic question is declined, not answered', d['response']=='That is outside what I can help with here.' and d['source_kind']=='none', d)
A.web_lookup.answer_from_web=lambda q,background=None,**k:{'status':'need_more','answer':'Which disease or pest do you mean?','sources':[]}
d=C.post('/api/chat',json={'question':'How do I treat it?'}).get_json()
check('need_more: the farmer is asked which disease, no KVK message', d['response']=='Which disease or pest do you mean?' and d['source_kind']=='none' and d['web_status']=='need_more', d)
A.web_lookup.answer_from_web=lambda q,background=None,**k:{'status':'no_dose','answer':'I do not give spray doses from the internet.','sources':[]}
d=C.post('/api/chat',json={'question':'how much acephate per litre'}).get_json()
check('no_dose: refusal shown as the answer', d['response']=='I do not give spray doses from the internet.' and d['source_kind']=='none' and d['web_status']=='no_dose', d)
A.web_lookup.answer_from_web=fake_web
FakeRAG.docs=False
d=C.post('/api/chat',json={'question':'how do I manage pink bollworm?'}).get_json()
check('no documents loaded -> internet fallback still works', d['source_kind']=='web', d)
FakeRAG.docs=True
A.web_lookup.answer_from_web=real_web
Config.ENABLE_WEB_LOOKUP=False
d=C.post('/api/chat',json={'question':'what is the moon made of'}).get_json()
check('web lookup switched off -> stays offline', d['source_kind']=='none' and d['web_status'] is None, d)
check('status says whether web lookup is on', 'web_lookup' in C.get('/api/cotton-status').get_json())

# no documents
FakeRAG.docs=False
d=C.post('/api/chat',json={'question':'x?'}).get_json()
check('no documents -> no invented advice', d['grounded'] is False and 'No official document' in d['response'], d)
FakeRAG.docs=True

# uncertain: high threshold => never presented as diagnosis, RAG not called
Config.COTTON_MIN_PROBABILITY=0.9999
FakeRAG.calls.clear()
d=C.post('/api/diagnose',data={'image':(jpg('Curl'),'a.jpg')},content_type='multipart/form-data').get_json()
check('below threshold -> uncertain, disease hidden, RAG not called', d['diagnosis']['status']=='uncertain' and d['diagnosis']['disease'] is None and not FakeRAG.calls, d)
check('uncertain keeps top3 for transparency', len(d['diagnosis']['top3'])==3)
s=A.sessions.get(d['session_id']); check('uncertain session has no confirmed disease', s['disease'] is None)

# unreliable class (F1 below minimum) -> uncertain even at high probability
Config.COTTON_MIN_PROBABILITY=0.0; Config.COTTON_MIN_CLASS_F1=1.01
d=C.post('/api/diagnose',data={'image':(jpg('Mould'),'a.jpg')},content_type='multipart/form-data').get_json()
check('low-F1 class -> uncertain with reason', d['diagnosis']['status']=='uncertain' and any('unreliable' in x for x in d['diagnosis']['reasons']), d['diagnosis'])

# healthy leaf -> no RAG, healthy message
Config.COTTON_MIN_PROBABILITY=0.4; Config.COTTON_MIN_CLASS_F1=0.0
FakeRAG.calls.clear()
d=C.post('/api/diagnose',data={'image':(jpg('Healthy'),'a.jpg')},content_type='multipart/form-data').get_json()
check('healthy leaf -> healthy message, no RAG', d['diagnosis']['disease']=='Healthy' and 'looks healthy' in d['advice'] and not FakeRAG.calls, d)

# classifier missing -> 503 with instructions
A.cotton_classifier=None; A.cotton_load_error='Cotton model not found. Train it first'
r=C.post('/api/diagnose',data={'image':(jpg('Spot'),'a.jpg')},content_type='multipart/form-data')
check('no model -> 503 with instructions', r.status_code==503 and 'Train it first' in r.get_json()['error'])

# page served
r=C.get('/diagnose'); check('/diagnose page served', r.status_code==200 and b'Kapas' in r.data); r.close()

# session store prune
import cotton_flow
st=cotton_flow.SessionStore(ttl=0.01,max_sessions=2); a=st.create(); import time; time.sleep(0.03)
check('sessions expire', st.get(a) is None)
st=cotton_flow.SessionStore(ttl=100,max_sessions=2); ids=[st.create() for _ in range(4)]
check('sessions capped', sum(st.get(i) is not None for i in ids)<=2)
check('script detection', cotton_flow.detect_script_language('कपास')=='hi' and cotton_flow.detect_script_language('કપાસ')=='gu' and cotton_flow.detect_script_language('cotton')=='en')

# ---- startup loader must not re-embed documents that are already loaded ----
_dd=tempfile.mkdtemp(); open(_dd+'/Guide One.txt','w').write('x'); open(_dd+'/two.txt','w').write('y')
_added=[]
class _DP:
    def process_document(s,path): return ['chunk of '+os.path.basename(path)]
class _RG:
    documents_registry={}
    def add_document(s,doc_id,chunks,path):
        _added.append(doc_id); s.documents_registry[doc_id]={'path':path}; return True
_old=(A.rag_engine,A.document_processor,Config.DOCUMENTS_FOLDER)
A.rag_engine=_RG(); A.document_processor=_DP(); Config.DOCUMENTS_FOLDER=_dd
A.auto_load_documents(); first=sorted(_added)
A.auto_load_documents()
check('startup loads each document once', first==['Guide_One_txt','two_txt'], first)
check('second startup loads nothing again', sorted(_added)==first, _added)
A.rag_engine,A.document_processor,Config.DOCUMENTS_FOLDER=_old

print('\nFAILED:',fails if fails else 'none')
sys.exit(1 if fails else 0)
