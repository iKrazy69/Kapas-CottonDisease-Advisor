"""
Glue between the classifier and the RAG engine: question building, chat
sessions and Indic-script language detection. No heavy imports, so it is easy
to test.
"""

import re
import threading
import time
import uuid

from config import Config

NO_DOCS_MESSAGE = ("No official document about this is loaded, so I cannot give treatment advice. "
                   "Please show the leaf to your nearest Krishi Vigyan Kendra (KVK) or agriculture officer.")

UNCERTAIN_MESSAGE = ("I could not identify the disease reliably from this photo, so I am not giving a "
                     "diagnosis. Please try again with one leaf, flat on a plain light background, in daylight, "
                     "filling the frame and in focus. If I am still not sure, show the plant to your nearest "
                     "Krishi Vigyan Kendra (KVK) or agriculture officer.")

HEALTHY_MESSAGE = ("The photo looks healthy to the model, but this is not a guarantee. "
                   "If the plant still looks unwell, ask your agriculture officer.")

# Unicode blocks -> language code. Devanagari is shared by Hindi and Marathi,
# so it maps to 'hi' unless the caller says otherwise.
SCRIPT_RANGES = [
    ('hi', 0x0900, 0x097F),
    ('bn', 0x0980, 0x09FF),
    ('pa', 0x0A00, 0x0A7F),
    ('gu', 0x0A80, 0x0AFF),
    ('ta', 0x0B80, 0x0BFF),
    ('te', 0x0C00, 0x0C7F),
    ('kn', 0x0C80, 0x0CFF),
    ('ml', 0x0D00, 0x0D7F),
]


def detect_script_language(text, default='en'):
    counts = {}
    for ch in text or '':
        cp = ord(ch)
        for code, lo, hi in SCRIPT_RANGES:
            if lo <= cp <= hi:
                counts[code] = counts.get(code, 0) + 1
                break
    return max(counts, key=counts.get) if counts else default


def disease_query(disease, user_question=None):
    """English retrieval question that carries the diagnosed disease."""
    if user_question:
        return f'{user_question.strip()} (about {disease} in cotton)'
    return (f'What are the symptoms, prevention and management of {disease} in cotton? '
            'Include any recommended treatment from the documents.')


def general_query(user_question):
    return f'{user_question.strip()} (cotton crop)'


# Words that mean "the plant in my photo". Only then is the diagnosis used as background.
_PHOTO_REFERENCE = re.compile(
    r"\b(it|its|this|that|these|those|here|my\s+(?:plant|plants|crop|crops|leaf|leaves|field|fields|cotton))\b", re.I)


def refers_to_photo(question):
    return bool(_PHOTO_REFERENCE.search(question or ''))


def plan_question(disease, question_en):
    """How a follow-up is answered. The user's question itself is NEVER reworded.

    Returns (retrieval_query, background, used_diagnosis):
      retrieval_query  extra search words used only to find document passages (not shown to the model)
      background       separate context for the model, only when the question points at the photo
      used_diagnosis   True when the diagnosed disease was used, so the page can say so
    """
    q = (question_en or '').strip()
    used = bool(disease) and refers_to_photo(q)
    search = q
    if used:
        search += f' {disease}'
    if 'cotton' not in q.lower():
        search += ' cotton'
    background = (f'The farmer\'s leaf photo was classified by an automated model as "{disease}". '
                  'This is a suggestion, not a confirmed diagnosis.') if used else None
    return search, background, used


def is_latin_text(text):
    """True when the text has no letters from another script (so it needs no translation into English)."""
    return not any(ord(c) > 0x024F and c.isalpha() for c in (text or ''))


class SessionStore:
    """In-memory chat sessions. Lost on restart; fine for a single-machine demo."""

    def __init__(self, ttl=None, max_sessions=None):
        self.ttl = ttl or Config.SESSION_TTL_SECONDS
        self.max = max_sessions or Config.SESSION_MAX
        self._data = {}
        self._lock = threading.Lock()

    def _prune(self, now):
        for sid in [k for k, v in self._data.items() if now - v['updated'] > self.ttl]:
            del self._data[sid]
        while len(self._data) > self.max:
            oldest = min(self._data, key=lambda k: self._data[k]['updated'])
            del self._data[oldest]

    def create(self, **fields):
        now = time.time()
        sid = uuid.uuid4().hex
        with self._lock:
            self._prune(now)
            self._data[sid] = {'updated': now, 'disease': None, 'history': [], **fields}
        return sid

    def get(self, sid):
        now = time.time()
        with self._lock:
            self._prune(now)
            s = self._data.get(sid)
            if s is not None:
                s['updated'] = now
            return s

    def add_turn(self, sid, question, answer):
        with self._lock:
            s = self._data.get(sid)
            if s is not None:
                s['history'].append({'q': question, 'a': answer})
                s['history'] = s['history'][-10:]
