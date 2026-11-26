"""
============================================
VB-GRAMG GOVERNMENT DOCUMENTS RAG SYSTEM
Flask Backend API - Production Version
============================================
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict

from flask import Flask, request, jsonify, send_file, url_for
from werkzeug.utils import secure_filename

# Import custom modules
from config import Config
from rag_engine import RAGEngine
from document_processor import DocumentProcessor
from voice_handler import VoiceHandler
from translator import translate_answer, translate_to_english
import indic_translate
import cotton_flow
import web_lookup
from cotton_classifier import CottonClassifierUnavailable, load_cotton_classifier

from tts_piper import save_audio_file
from flask import send_from_directory
import time

# ============================================
# LOGGING
# ============================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================
# FLASK APP
# ============================================

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER
app.config['JSON_SORT_KEYS'] = False

# Ensure directories exist
Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
Path(Config.CHROMA_DATA_FOLDER).mkdir(parents=True, exist_ok=True)
Path(Config.AUDIO_OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)
Path(Config.DOCUMENTS_FOLDER).mkdir(parents=True, exist_ok=True)

logger.info('📁 Directories created/verified')

# ============================================
# INITIALIZE MODULES
# ============================================

try:
    rag_engine = RAGEngine()
    document_processor = DocumentProcessor()
    voice_handler = VoiceHandler()
    logger.info('✅ All modules initialized successfully')
except Exception as e:
    logger.error(f'❌ Module initialization failed: {str(e)}')
    sys.exit(1)

# The cotton classifier is optional: if the model has not been trained yet the
# rest of the app keeps working and /api/diagnose explains what is missing.
cotton_classifier = None
cotton_load_error = None
try:
    cotton_classifier = load_cotton_classifier()
except CottonClassifierUnavailable as e:
    cotton_load_error = str(e)
    logger.warning(f'⚠️ {cotton_load_error}')
except Exception as e:
    cotton_load_error = f'Cotton model failed to load: {e}'
    logger.error(f'❌ {cotton_load_error}')

sessions = cotton_flow.SessionStore()

# ============================================
# CORS HEADERS
# ============================================

@app.after_request
def after_request(response):
    """Add CORS headers to every response"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# ============================================
# UTILITY FUNCTIONS
# ============================================

def success_response(data: Dict = None, message: str = 'Success', status_code: int = 200):
    """Return success response"""
    response = {
        'success': True,
        'message': message,
        'timestamp': datetime.now().isoformat()
    }
    if data:
        response.update(data)
    return jsonify(response), status_code


def error_response(message: str, status_code: int = 400, data: Dict = None):
    """Return error response"""
    response = {
        'success': False,
        'error': message,
        'timestamp': datetime.now().isoformat()
    }
    if data:
        response.update(data)
    return jsonify(response), status_code

# ============================================
# HEALTH & STATUS ENDPOINTS
# ============================================

@app.route('/api/health', methods=['GET', 'OPTIONS'])
def health_check():
    """Health check endpoint for presentation and monitoring"""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        logger.info('🔍 Health check requested')
        documents_loaded = rag_engine.has_documents()
        
        health_data = {
            'status': 'healthy',
            'app': 'VB-GRAMG Voice RAG System',
            'version': '2.0.0 (Mac Optimized)',
            'documents_loaded': documents_loaded,
            'timestamp': datetime.now().isoformat(),
            'components': {
                'rag_engine': 'operational',
                'document_processor': 'operational',
                'voice_handler': 'operational'
            }
        }
        return success_response(health_data, 'System is healthy')
    except Exception as e:
        logger.error(f'❌ Health check failed: {str(e)}')
        return error_response(f'Health check failed: {str(e)}', 500)


@app.route('/api/document-status', methods=['GET', 'OPTIONS'])
def document_status():
    """Get current document database status"""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        status = rag_engine.get_status()
        return success_response(status, 'Document status retrieved')
    except Exception as e:
        return error_response(f'Failed to get document status: {str(e)}', 500)

# ============================================
# QUERY ENDPOINT (TEXT INPUT)
# ============================================

@app.route('/api/query', methods=['POST', 'OPTIONS'])
def query_rag():
    """Standard text query to the RAG system"""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.get_json()
        if not data or not data.get('question'):
            return error_response('Question is required', 400)
        
        question = data.get('question').strip()
        top_k = min(data.get('top_k', 5), 10)
        
        logger.info(f'🔍 Text Query received: "{question[:50]}..."')
        
        if not rag_engine.has_documents():
            return error_response('No documents loaded.', 400)
        
        result = rag_engine.query(question, top_k=top_k)
        
        if not result or not result.get('response'):
            return error_response('Failed to generate response. Please try again.', 500)
        
        return success_response({
            'response': result['response'],
            'source_documents': result.get('source_documents', []),
            'retrieval_score': result.get('retrieval_score'),
            'grounded': result.get('grounded', False),
            'response_time': datetime.now().isoformat()
        }, 'Query processed successfully', 200)
    
    except Exception as e:
        logger.error(f'❌ Query failed: {str(e)}')
        return error_response(f'Query failed: {str(e)}', 500)

# ============================================
# VOICE INPUT ENDPOINT (WHISPER)
# ============================================

@app.route('/api/audio/<filename>', methods=['GET'])
def get_audio(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/voice-query', methods=['POST', 'OPTIONS'])
def voice_query():
    """Process voice input using faster-whisper and return RAG answer"""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        if 'audio' not in request.files:
            return error_response('No audio file provided', 400)
        
        audio_file = request.files['audio']
        temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_voice.wav')
        audio_file.save(temp_filepath)
        
        try:
            # 1. Transcribe in the speaker's language and get an English version for retrieval
            logger.info('⚙️ Transcribing audio via faster-whisper...')
            speech = voice_handler.speech_to_text(temp_filepath)
            
            if not speech['supported']:
                return error_response('Please speak only in English or Hindi.', 400)
            
            user_lang = speech['language']          # 'en' or 'hi'
            question_original = speech['text']      # what the user said, in their language
            question_english = speech['english']    # used for retrieval
            
            if not question_english:
                return error_response('Could not transcribe audio. Please speak clearly.', 400)
            
            logger.info(f'✅ Transcribed ({user_lang}): "{question_original}"')
            
            # 2. Retrieve and answer in English (documents are searched in English)
            if not rag_engine.has_documents():
                return error_response('No documents loaded in database', 400)
            
            logger.info('⚙️ Querying RAG engine with English question...')
            result = rag_engine.query(question_english, top_k=5, answer_language='en')
            
            if not result or not result.get('response'):
                return error_response('Failed to generate response', 500)
            
            answer_english = result['response']
            answer_final = answer_english
            answer_language = 'en'
            translation_failed = False
            
            # 3. Translate the answer back into the speaker's language
            if user_lang != 'en':
                translated = translate_answer(answer_english, user_lang)
                if translated:
                    answer_final = translated
                    answer_language = user_lang
                else:
                    # Do not silently pretend: fall back to English and say so.
                    translation_failed = True
                    logger.warning('⚠️ Translation failed; answering in English')
            
            # 4. Speak the answer in the language it is actually written in
            audio_filename = f"response_{int(time.time())}.wav"
            audio_filepath = os.path.join(app.config['UPLOAD_FOLDER'], audio_filename)
            
            logger.info(f'🔊 Saving audio to {audio_filepath} in language {answer_language}')
            save_success = save_audio_file(answer_final, audio_filepath, answer_language)
            
            if not save_success:
                logger.error('❌ Piper failed to save the audio file')
            
            # Build the audio URL from the host the client actually used,
            # instead of a hardcoded 127.0.0.1:8080.
            audio_url = url_for('get_audio', filename=audio_filename, _external=True) if save_success else None
            
            return success_response({
                'question': question_original,
                'question_english': question_english,
                'language': user_lang,
                'response': answer_final,
                'response_english': answer_english,
                'answer_language': answer_language,
                'translation_failed': translation_failed,
                'source_documents': result.get('source_documents', []),
                'audio_url': audio_url,
                'retrieval_score': result.get('retrieval_score'),
                'grounded': result.get('grounded', False),
                'timestamp': datetime.now().isoformat()
            }, 'Voice query processed successfully', 200)
        
        finally:
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
                logger.info('🗑️ Cleaned up temporary audio file')
    
    except Exception as e:
        logger.error(f'❌ Voice query failed: {str(e)}')
        return error_response(f'Voice query failed: {str(e)}', 500)
    
# ============================================
# COTTON: PHOTO DIAGNOSIS + CHAT
# ============================================

SUPPORTED_TEXT_LANGUAGES = ('en', 'hi')   # always available; more with Config.ENABLE_INDICTRANS


def language_supported(lang):
    return lang in SUPPORTED_TEXT_LANGUAGES or indic_translate.available(lang)


def to_english(text, lang):
    """Question in the user's language -> English for retrieval (None = failed)."""
    if lang == 'en':
        return text
    if indic_translate.available(lang):
        return indic_translate.to_english(text, lang)
    return translate_to_english(text, lang)


def render_answer(english, lang):
    """English answer -> (text, language_it_is_written_in, translation_failed)."""
    if lang == 'en':
        return english, 'en', False
    out = indic_translate.from_english(english, lang) if indic_translate.available(lang) else translate_answer(english, lang)
    if out:
        return out, lang, False
    return english, 'en', True      # honest fallback: English, flagged


def speak(text, lang):
    """Piper audio URL, only for languages that have a voice (en, hi)."""
    if lang not in ('en', 'hi'):
        return None
    name = f"response_{int(time.time() * 1000)}.wav"
    path = os.path.join(app.config['UPLOAD_FOLDER'], name)
    try:
        if save_audio_file(text, path, lang):
            return url_for('get_audio', filename=name, _external=True)
    except Exception as e:
        logger.error(f'TTS failed: {e}')
    return None


def advice_for(question_en, retrieval_q=None, background=None):
    """Run RAG on the loaded documents. Returns (english_text, result_dict). Abstains with NO_DOCS_MESSAGE.

    question_en is passed to the model exactly as asked; retrieval_q only widens the document search.
    """
    if not rag_engine.has_documents():
        return cotton_flow.NO_DOCS_MESSAGE, {'grounded': False, 'source_documents': [], 'retrieval_score': None}
    result = rag_engine.query(question_en, top_k=5, answer_language='en',
                              retrieval_query=retrieval_q, background=background)
    if not result or not result.get('response'):
        return cotton_flow.NO_DOCS_MESSAGE, {'grounded': False, 'source_documents': [], 'retrieval_score': None}
    if not result.get('grounded'):
        # The engine abstained: say so and send the farmer to a human expert.
        return (result['response'] + ' ' + cotton_flow.NO_DOCS_MESSAGE), result
    return result['response'], result


def answer_with_fallback(question_en, retrieval_q=None, background=None):
    """Loaded documents first; if they do not cover it, look it up on the internet (when enabled).

    Returns (english_text, info). info['source_kind'] is 'documents', 'web' or 'none';
    info['web_sources'] lists the pages used; info['web_status'] says what the internet step did.
    """
    text, rag = advice_for(question_en, retrieval_q, background)
    info = dict(rag)
    info.update(source_kind='documents' if rag.get('grounded') else 'none', web_sources=[], web_status=None)
    if rag.get('grounded') or not Config.ENABLE_WEB_LOOKUP:
        return text, info
    web = web_lookup.answer_from_web(question_en, background=background,
                                     search_q=web_lookup.search_query(retrieval_q) if retrieval_q else None)
    info['web_status'] = web['status']
    if web['status'] == 'ok':
        info.update(source_kind='web', web_sources=web['sources'], grounded=False, source_documents=[], retrieval_score=None)
        return web['answer'], info
    if web['status'] in ('off_topic', 'need_more', 'no_dose'):
        return web['answer'], info
    return text, info                                  # keep the "ask your KVK" message


FRONTEND_DIR = os.path.join(Config.BASE_DIR_PATH, 'frontend')


@app.route('/', methods=['GET'])
@app.route('/diagnose', methods=['GET'])
def home_page():
    # The Kapas site: photo check, guide Q&A, cotton, seasons, history, diseases.
    # /diagnose is kept so old links and the start scripts keep working.
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/legacy', methods=['GET'])
def legacy_page():
    # The earlier VB-GRAMG voice-assistant page, kept unchanged.
    return send_from_directory(FRONTEND_DIR, 'legacy-vbgramg.html')


def _site_file(filename):
    def view():
        return send_from_directory(FRONTEND_DIR, filename)
    return view


for _name in ('kapas.css', 'kapas.js', 'kapas-data.js', 'chat-style.css'):
    app.add_url_rule('/' + _name, 'site_' + _name.replace('.', '_').replace('-', '_'), _site_file(_name), methods=['GET'])


@app.route('/fonts/<path:filename>', methods=['GET'])
def site_font(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, 'fonts'), filename)


@app.route('/api/cotton-status', methods=['GET'])
def cotton_status():
    info = {
        'classifier_loaded': cotton_classifier is not None,
        'error': cotton_load_error,
        'min_probability': Config.COTTON_MIN_PROBABILITY,
        'min_class_f1': Config.COTTON_MIN_CLASS_F1,
        'model_version': getattr(cotton_classifier, 'version', 1) if cotton_classifier else None,
        'classes': list(cotton_classifier.class_names) if cotton_classifier else [],
        'text_languages': list(SUPPORTED_TEXT_LANGUAGES) + (list(indic_translate.FLORES) if Config.ENABLE_INDICTRANS else []),
        'voice_languages': ['en', 'hi'],
        'documents_loaded': rag_engine.has_documents(),
        'web_lookup': bool(Config.ENABLE_WEB_LOOKUP),
    }
    if cotton_classifier and cotton_classifier.metrics:
        m = cotton_classifier.metrics
        info['test_accuracy'] = m.get('accuracy')
        info['test_macro_f1'] = m.get('macro_f1')
        info['per_class_f1'] = {k: v['f1'] for k, v in m.get('per_class', {}).items()}
    return success_response(info)


@app.route('/api/diagnose', methods=['POST', 'OPTIONS'])
def diagnose():
    """Leaf photo -> (cautious) diagnosis -> grounded advice with sources."""
    if request.method == 'OPTIONS':
        return '', 200
    if cotton_classifier is None:
        return error_response(cotton_load_error or 'Cotton classifier is not available', 503)

    f = request.files.get('image')
    if f is None:
        return error_response('Send the leaf photo as form field "image"', 400)
    raw = f.read(Config.MAX_IMAGE_BYTES + 1)
    if len(raw) > Config.MAX_IMAGE_BYTES:
        return error_response('Image is too large (max 10 MB)', 413)

    import cv2
    import numpy as np
    if cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR) is None:
        return error_response('That file is not a readable image', 400)

    lang = (request.form.get('language') or 'en').lower()
    if not language_supported(lang):
        return error_response(f'Language "{lang}" is not supported here. Use one of: en, hi', 400)
    want_audio = (request.form.get('speak') or '').lower() in ('1', 'true', 'yes')

    tmp = os.path.join(app.config['UPLOAD_FOLDER'], f'leaf_{int(time.time() * 1000)}.jpg')
    try:
        with open(tmp, 'wb') as fh:
            fh.write(raw)
        decision = cotton_classifier.predict(tmp)
    except Exception as e:
        logger.error(f'❌ Classification failed: {e}')
        return error_response('Could not analyse this photo. Try a clearer, closer photo of one leaf.', 500)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    disease = decision['disease']
    confident = decision['status'] == 'confident'
    not_cotton = decision['status'] == 'not_cotton'
    healthy = confident and cotton_classifier.is_healthy(disease)

    no_rag = {'grounded': False, 'source_documents': [], 'retrieval_score': None,
              'source_kind': 'none', 'web_sources': [], 'web_status': None}
    if not_cotton:
        advice_en, rag = cotton_flow.NOT_COTTON_MESSAGE, no_rag
    elif not confident:
        advice_en, rag = cotton_flow.UNCERTAIN_MESSAGE, no_rag
    elif healthy:
        advice_en, rag = cotton_flow.HEALTHY_MESSAGE, no_rag
    else:
        advice_en, rag = answer_with_fallback(cotton_flow.disease_query(disease))

    advice, advice_lang, translation_failed = render_answer(advice_en, lang)

    sid = sessions.create(language=lang, disease=disease if (confident and not healthy) else None,
                          last_decision=decision)

    return success_response({
        'session_id': sid,
        'diagnosis': {
            'status': decision['status'],
            'disease': disease if confident else None,
            'probability': decision['probability'],
            'top3': decision['top3'],
            'reasons': decision['reasons'],
            'cotton_score': decision.get('cotton_score'),
            'note': 'Automated suggestion from a small research model, not a confirmed diagnosis.',
        },
        'advice': advice,
        'advice_english': advice_en,
        'answer_language': advice_lang,
        'translation_failed': translation_failed,
        'source_documents': rag.get('source_documents', []),
        'grounded': rag.get('grounded', False),
        'retrieval_score': rag.get('retrieval_score'),
        'source_kind': rag.get('source_kind', 'none'),
        'web_sources': rag.get('web_sources', []),
        'web_status': rag.get('web_status'),
        'audio_url': speak(advice, advice_lang) if want_audio else None,
    }, 'Diagnosis complete')


@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat():
    """Follow-up question (typed) about the diagnosed disease or cotton in general."""
    if request.method == 'OPTIONS':
        return '', 200
    data = request.get_json(silent=True) or {}
    question = (data.get('question') or '').strip()
    if not question:
        return error_response('Question is required', 400)
    if len(question) > 1000:
        return error_response('Question is too long (max 1000 characters)', 400)

    sid = data.get('session_id')
    session = sessions.get(sid) if sid else None
    if sid and session is None:
        return error_response('Session expired. Upload the leaf photo again.', 404)

    lang = (data.get('language') or '').lower() or \
           (session or {}).get('language') or cotton_flow.detect_script_language(question)
    if not language_supported(lang):
        return error_response(f'Language "{lang}" is not supported here. Use one of: en, hi', 400)
    want_audio = bool(data.get('speak'))

    # The answer comes back in the chosen language, but a question typed in English (Latin letters)
    # is already English: sending it through a "Hindi to English" step could change its meaning.
    question_lang = 'en' if cotton_flow.is_latin_text(question) else lang
    question_en = to_english(question, question_lang)
    if not question_en:
        return error_response('Could not translate the question. Please try English or Hindi.', 502)

    disease = (session or {}).get('disease')
    retrieval_q, background, used_diagnosis = cotton_flow.plan_question(disease, question_en)
    answer_en, rag = answer_with_fallback(question_en, retrieval_q, background)
    answer, answer_lang, translation_failed = render_answer(answer_en, lang)

    if sid:
        sessions.add_turn(sid, question, answer_en)

    return success_response({
        'question_english': question_en,
        'disease_context': disease,
        'used_diagnosis': used_diagnosis,
        'response': answer,
        'response_english': answer_en,
        'answer_language': answer_lang,
        'translation_failed': translation_failed,
        'source_documents': rag.get('source_documents', []),
        'grounded': rag.get('grounded', False),
        'retrieval_score': rag.get('retrieval_score'),
        'source_kind': rag.get('source_kind', 'none'),
        'web_sources': rag.get('web_sources', []),
        'web_status': rag.get('web_status'),
        'audio_url': speak(answer, answer_lang) if want_audio else None,
    }, 'Chat processed')

# ============================================
# ERROR HANDLERS
# ============================================

@app.errorhandler(404)
def not_found(error):
    logger.warning(f'⚠️ 404 Error: {request.path}')
    return error_response('Endpoint not found', 404)

@app.errorhandler(500)
def internal_error(error):
    logger.error(f'❌ 500 Error: {str(error)}')
    return error_response('Internal server error', 500)

@app.errorhandler(405)
def method_not_allowed(error):
    logger.warning(f'⚠️ 405 Error: {request.method} {request.path}')
    return error_response('Method not allowed', 405)

# ============================================
# AUTO-LOAD DOCUMENTS
# ============================================

def auto_load_documents():
    """Auto-load all PDFs and TXTs from documents folder on startup"""
    try:
        docs_folder = Path(Config.DOCUMENTS_FOLDER)
        if not docs_folder.exists():
            logger.warning(f'⚠️ Documents folder not found: {docs_folder}')
            return
        
        documents = list(docs_folder.glob('*.pdf')) + \
                   list(docs_folder.glob('*.docx')) + \
                   list(docs_folder.glob('*.txt'))
        
        if not documents:
            logger.warning(f'⚠️ No documents found in: {docs_folder}')
            return
        
        logger.info(f'📚 Found {len(documents)} documents to load')
        
        for doc_path in documents:
            doc_name = doc_path.name
            doc_id = doc_name.replace('.', '_').replace(' ', '_')
            
            if doc_id in rag_engine.documents_registry or \
               any(doc_name in str(d) for d in rag_engine.documents_registry.keys()):
                continue
            
            logger.info(f'📄 Auto-loading: {doc_name}')
            try:
                chunks = document_processor.process_document(str(doc_path))
                if not chunks: continue
                
                success = rag_engine.add_document(doc_id, chunks, str(doc_path))
                
                if success:
                    logger.info(f'✅ Auto-loaded: {doc_name} ({len(chunks)} chunks)')
            except Exception as e:
                logger.error(f'❌ Error loading {doc_name}: {str(e)}')
                
    except Exception as e:
        logger.error(f'❌ Auto-load failed: {str(e)}')

# ============================================
# STARTUP & MAIN
# ============================================

def startup():
    logger.info('🚀 Application starting up...')
    try:
        rag_engine.initialize()
        logger.info('✅ RAG engine initialized')
    except Exception as e:
        logger.error(f'⚠️ RAG engine initialization warning: {str(e)}')
    
    auto_load_documents()

@app.teardown_appcontext
def shutdown(exception=None):
    if exception:
        logger.error(f'❌ Application error: {str(exception)}')
    logger.info('🛑 Application shutting down...')

if __name__ == '__main__':
    logger.info('=' * 60)
    logger.info('🏛️  VB-GRAMG RAG SYSTEM - PRODUCTION BUILD')
    logger.info('=' * 60)
    logger.info(f'📡 Server starting on http://127.0.0.1:8080')
    logger.info('=' * 60)
    
    startup()
    app.run(host='127.0.0.1', port=8080, debug=False, use_reloader=False)