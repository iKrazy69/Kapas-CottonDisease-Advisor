"""
Answer translation for the voice pipeline.

The RAG engine answers in English (retrieval works on English text), and the
answer is then translated into the speaker's language with the local LLM.

Translation by an 8B model can change numbers or names, so the caller should
also return the English original, and this module tells the model to keep
numbers, units, names and source labels unchanged. It cannot guarantee that.
"""

import logging
import requests

from config import Config
import crop_glossary

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {
    'hi': 'Hindi (Devanagari script)',
}


def translate_to_english(text: str, lang_code: str):
    """
    Translate a typed question into English for retrieval, with the local LLM.
    Returns None on failure or when no translation is needed.

    Hindi crop terms are first swapped for the guide's English words (crop_glossary.py), because the 8B model
    gets them wrong ("टिंडा सड़न" -> "Tinda rot"). If the model still drops one, it is added at the end.
    """
    if not text or lang_code == 'en':
        return None
    lang_name = LANGUAGE_NAMES.get(lang_code)
    if lang_name is None:
        return None
    terms = []
    if lang_code == 'hi':
        text, terms = crop_glossary.apply(text)
    keep = ''
    if terms:
        keep = ('The question already contains these English crop terms. Keep each one exactly as written, '
                'do not translate or change them: ' + '; '.join(terms) + '\n')
    prompt = (
        f'Translate this {lang_name} question into plain English.\n'
        + keep +
        'Return only the translation, nothing else.\n\n'
        f'Question:\n{text}\n\nEnglish:'
    )
    try:
        response = requests.post(
            f'http://localhost:{Config.OLLAMA_PORT}/api/generate',
            json={'model': Config.OLLAMA_MODEL, 'prompt': prompt, 'stream': False,
                  'options': {'temperature': 0.1}},
            timeout=Config.OLLAMA_TIMEOUT
        )
        if response.status_code != 200:
            return None
        english = response.json().get('response', '').strip()
        if not english:
            return None
        lost = crop_glossary.missing_terms(english, terms)
        if lost:
            logger.info(f'Translation dropped crop terms {lost}; adding them back')
            english = english.rstrip() + ' (' + ', '.join(lost) + ')'
        return english
    except Exception as e:
        logger.error(f'Question translation failed: {e}')
        return None


def translate_answer(answer: str, lang_code: str):
    """
    Translate an English answer into lang_code.

    Returns the translated text, or None if translation is not needed or failed
    (callers fall back to the English answer and an English voice).
    """
    if not answer or lang_code == 'en':
        return None

    lang_name = LANGUAGE_NAMES.get(lang_code)
    if lang_name is None:
        logger.warning(f'No translation target configured for language: {lang_code}')
        return None

    prompt = (
        f'Translate the following English answer into simple {lang_name}.\n'
        'Rules:\n'
        '- Keep every number, unit, date, name, scheme name and "Source N" label exactly as written.\n'
        '- Do not add, remove or explain anything.\n'
        '- Return only the translation.\n\n'
        f'English answer:\n{answer}\n\nTranslation:'
    )

    try:
        response = requests.post(
            f'http://localhost:{Config.OLLAMA_PORT}/api/generate',
            json={
                'model': Config.OLLAMA_MODEL,
                'prompt': prompt,
                'stream': False,
                'options': {'temperature': 0.2}
            },
            timeout=Config.OLLAMA_TIMEOUT
        )
        if response.status_code != 200:
            logger.error(f'Translation failed: Ollama returned {response.status_code}')
            return None
        translated = response.json().get('response', '').strip()
        return translated or None
    except Exception as e:
        logger.error(f'Translation failed: {e}')
        return None
