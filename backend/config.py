"""
============================================
CONFIGURATION
VB-GRAMG Government Documents RAG System
============================================
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
CHROMA_DATA_FOLDER = os.path.join(BASE_DIR, 'chroma_data')
AUDIO_OUTPUT_FOLDER = os.path.join(BASE_DIR, 'audio_output')
DOCUMENTS_FOLDER = os.path.join(BASE_DIR, 'documents')


class Config:
    BASE_DIR_PATH = str(BASE_DIR)

    """Main Configuration"""

    DEBUG = True
    TESTING = False

    # Folders
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    CHROMA_DATA_FOLDER = os.path.join(BASE_DIR, 'chroma_data')
    AUDIO_OUTPUT_FOLDER = os.path.join(BASE_DIR, 'audio_output')
    DOCUMENTS_FOLDER = os.path.join(BASE_DIR, 'documents')

    # ========================================
    # RAG CONFIGURATION
    # ========================================

    # Chosen with eval/chunking_experiment.py (800/100 with section headings and nomic prefixes found the answer
    # passage for 30 of 34 benchmark questions at the top 5 results, against 26 for the earlier 500/50).
    CHUNK_SIZE = 800
    CHUNK_OVERLAP = 100
    # nomic-embed-text is trained with these prefixes on documents and questions. The search scheme is stored next to
    # the database (embedding_scheme.txt), so a database built without them keeps being searched without them.
    USE_NOMIC_PREFIXES = True
    TOP_K_DOCUMENTS = 5
    # 0.4 is what the live /api/query path already used (it was hardcoded there).
    LLM_TEMPERATURE = 0.4
    OLLAMA_MODEL = 'llama3.1:8b'
    OLLAMA_PORT = 11434
    OLLAMA_TIMEOUT = 120
    # Upper bound on generated tokens. A model that falls into a repetition loop would otherwise run until the
    # request times out; a normal answer is a few hundred tokens.
    LLM_MAX_TOKENS = 1024
    # Context window given to the model. Five 800-character passages, the instructions and the answer need about 2,500
    # tokens; a smaller window makes Ollama drop the start of the prompt without any warning.
    LLM_NUM_CTX = 4096

    # Minimum cosine similarity (1 - cosine distance) the best retrieved chunk
    # must reach before the LLM is asked to answer. Below it the system says
    # "I don't have information".
    # UNCALIBRATED PLACEHOLDER: run evaluate_system.py, look at the printed
    # retrieval scores for in-scope vs out-of-scope questions, then set this
    # value between the two groups.
    LEXICAL_RESCUE = True      # add one keyword-matched passage when the question holds 2+ rare words (backend/lexical_rescue.py)
    LEXICAL_RESCUE_K = 1
    MIN_COSINE_SIMILARITY = 0.67

    # ========================================
    # SPEECH-TO-TEXT (faster-whisper)
    # ========================================

    WHISPER_MODEL = 'small'
    WHISPER_LANGUAGE = None          # None = auto-detect
    WHISPER_DEVICE = 'cpu'
    WHISPER_COMPUTE_TYPE = 'int8'
    WHISPER_SAMPLE_RATE = 16000

    # ========================================
    # TEXT-TO-SPEECH (Piper, see tts_piper.py)
    # ========================================

    TTS_ENGINE = 'piper'
    TTS_OUTPUT_FORMAT = 'wav'

    # ========================================
    # COTTON DISEASE CLASSIFIER (backend/cotton/)
    # ========================================

    COTTON_MODEL_PATH = os.path.join(BASE_DIR, 'backend', 'cotton', 'models', 'cotton_svm.joblib')
    COTTON_METRICS_PATH = os.path.join(BASE_DIR, 'backend', 'cotton', 'models', 'metrics.json')
    # A prediction is only treated as a diagnosis if its top probability is at
    # least this. UNCALIBRATED PLACEHOLDER: after running train_classifier.py,
    # read the "threshold / accuracy-when-answered" table it prints and pick
    # a value you can defend.
    COTTON_MIN_PROBABILITY = 0.70   # full-data run (81 test images): answers ~64% of photos, ~90% right when it answers. Re-check after any retraining.
    # Classes whose test F1 is below this are never presented as a confirmed
    # diagnosis (the notebook's SVM scores 0 on three of them).
    COTTON_MIN_CLASS_F1 = 0.30
    MAX_IMAGE_BYTES = 10 * 1024 * 1024
    SESSION_TTL_SECONDS = 3600
    SESSION_MAX = 200

    # ========================================
    # INTERNET FALLBACK
    # When the loaded documents do not cover a question, search the web and answer only from what the pages say.
    # Set to False to stay fully offline.
    # ========================================
    ENABLE_WEB_LOOKUP = True
    WEB_TIMEOUT_SECONDS = 8
    WEB_MAX_PAGES = 3
    WEB_USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'

    # ========================================
    # OPTIONAL: IndicTrans2 for typed regional languages (OFF by default)
    # ========================================
    ENABLE_INDICTRANS = False
    INDICTRANS_EN_INDIC = 'ai4bharat/indictrans2-en-indic-dist-200M'
    INDICTRANS_INDIC_EN = 'ai4bharat/indictrans2-indic-en-dist-200M'

    # ========================================
    # DOCUMENT PROCESSING
    # ========================================

    ALLOWED_DOCUMENT_TYPES = {'.pdf', '.txt', '.docx', '.doc'}
    MAX_FILE_SIZE = 50 * 1024 * 1024

    # ========================================
    # LOGGING
    # ========================================

    LOG_LEVEL = 'INFO'
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
