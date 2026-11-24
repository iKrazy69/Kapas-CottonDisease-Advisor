"""Turn an answer written for the screen into text that is safe to read aloud.

The text shown on screen contains things a voice should not say: markdown marks
(** - # `), source references like "(Source 1)", file names, links, symbols such as
% & / and every comma and full stop.  Piper can say these out loud.

So this module does two things:
  1. removes or rewrites everything that is not meant to be spoken
     (for example "70%" becomes "70 percent");
  2. splits the text at the punctuation and returns the pieces ("clauses") together with
     how long to stay silent after each one.  The caller synthesises each piece and writes
     the silence itself, so no punctuation mark ever reaches the speech engine.

Pure Python, no extra packages, so it can be tested without Piper or a speaker.
"""
import re
import unicodedata

PAUSE_COMMA = 0.20       # seconds of silence after a comma, colon, bracket or dash
PAUSE_SENTENCE = 0.50    # after a full stop, question mark, bullet or line break
PAUSE_PARAGRAPH = 0.75   # after a blank line

_WORDS = {
    'en': {'percent': ' percent ', 'and': ' and ', 'or': ' or ', 'to': ' to ', 'per': ' per ', 'by': ' by ',
           'rupees': ' rupees ', 'degrees': ' degrees Celsius ', 'deg': ' degrees ', 'plus': ' plus ', 'times': ' times ',
           'equals': ' equals '},
    'hi': {'percent': ' प्रतिशत ', 'and': ' और ', 'or': ' या ', 'to': ' से ', 'per': ' प्रति ', 'by': ' बटा ',
           'rupees': ' रुपये ', 'degrees': ' डिग्री सेल्सियस ', 'deg': ' डिग्री ', 'plus': ' प्लस ', 'times': ' गुणा ',
           'equals': ' बराबर '},
}
_EN_ABBREVIATIONS = [
    (re.compile(r'\be\.g\.', re.I), 'for example'),
    (re.compile(r'\bi\.e\.', re.I), 'that is'),
    (re.compile(r'\betc\.', re.I), 'and so on'),
    (re.compile(r'\bvs\.', re.I), 'versus'),
    (re.compile(r'\bapprox\.', re.I), 'approximately'),
]
_KEEP_FORMAT = {'‌', '‍'}          # joiners that Devanagari needs

_URL = re.compile(r'(?:https?://|www\.)\S+|\b[\w.+-]+@[\w-]+\.[\w.-]+\b', re.I)
_FILENAME = re.compile(r'\b[\w\-]+\.(?:txt|pdf|md|docx?|csv|json)\b', re.I)
# any bracket group that mentions a source: (Source 1), [Sources 1, 2], (स्रोत 2), (see Source: guide)
_SOURCE_GROUP = re.compile(r'[\(\[\{][^()\[\]{}\n]*?(?:\bSources?\b|स्रोत)[^()\[\]{}\n]*?[\)\]\}]', re.I)
_SOURCE_LINE = re.compile(r'^\s*(?:Sources?|स्रोत)\s*[:：].*$', re.I | re.M)
_BULLET = re.compile(r'^\s*(?:[-*•·▪●◦–—]|\d{1,3}[.)])\s+')
_RULE = re.compile(r'^\s*(?:[-*_=~]\s*){3,}$')
_CITE_NUMBER = re.compile(r'\[\s*\d+(?:\s*[,–-]\s*\d+)*\s*\]')       # [1] or [1, 2] after a fact
_UNIT_SLASH = re.compile(r'\b(kg|g|mg|ml|l|ha|acre|litre|liter|hectare|plant|day|week)\s*/\s*(?=[A-Za-zऀ-ॿ])', re.I)


def _symbols_to_words(s, W, lang):
    s = re.sub(r'₹\s*(\d[\d,]*(?:\.\d+)?)', lambda m: m.group(1) + W['rupees'], s)
    s = re.sub(r'(\d)\s*%', lambda m: m.group(1) + W['percent'], s)
    s = s.replace('%', W['percent'])
    s = re.sub(r'°\s*C\b', W['degrees'], s)
    s = s.replace('°', W['deg'])
    s = s.replace('&', W['and'])
    s = re.sub(r'(?<=\S)\s*\+\s*(?=\S)', W['plus'], s)
    s = s.replace('×', W['times'])
    s = re.sub(r'(?<=\S)\s*=\s*(?=\S)', W['equals'], s)
    s = re.sub(r'(?<=\d)\s*[-–—]\s*(?=\d)', W['to'], s)          # 5-10  ->  5 to 10
    s = _UNIT_SLASH.sub(lambda m: m.group(1) + W['per'], s)       # 2 g/litre  ->  2 g per litre
    s = re.sub(r'(?<=\d)\s*/\s*(?=\d)', W['by'], s)               # 1/2  ->  1 by 2
    s = s.replace('/', W['or'])
    s = re.sub(r'\s[-–—]+\s|[–—]', ', ', s)                       # a dash used as a pause
    s = re.sub(r'(?<=\S)-(?=\S)', ' ', s)                         # whitefly-borne -> whitefly borne
    return s


def _line_to_text(line, lang):
    W = _WORDS.get(lang, _WORDS['en'])
    s = re.sub(r'^\s*#{1,6}\s*', '', line)                        # heading marks
    s = re.sub(r'^\s*>+\s*', '', s)                               # quote marks
    s = re.sub(r'\*+|_{2,}|~~|`+', '', s)                         # bold / italic / code marks
    s = s.replace('_', ' ')
    if lang == 'en':
        for pat, word in _EN_ABBREVIATIONS:
            s = pat.sub(word, s)
    s = _symbols_to_words(s, W, lang)
    s = re.sub(r'[\(\)\[\]\{\}]', ', ', s)                        # brackets become a short pause
    s = re.sub(r'\.{2,}|…', '. ', s)
    s = re.sub(r'[।॥]+', '. ', s)                                 # Hindi full stop
    s = re.sub(r'["“”„«»]', '', s)
    s = s.replace('’', "'").replace('‘', "'")
    s = re.sub(r"(?<![A-Za-z])'|'(?![A-Za-z])", '', s)            # quote marks, but keep don't
    s = re.sub(r'(?<=\d),(?=\d{3}(?!\d))', '', s)                 # 1,500 -> 1500
    return s


def _clean_clause(c):
    """Keep letters, marks, digits, joiners; a dot only inside a number, an apostrophe only inside a word."""
    out, n = [], len(c)
    for i, ch in enumerate(c):
        cat = unicodedata.category(ch)
        if cat[0] in 'LMN' or ch in _KEEP_FORMAT:
            out.append(ch)
        elif ch == "'" and 0 < i < n - 1 and c[i - 1].isalpha() and c[i + 1].isalpha():
            out.append(ch)
        elif ch == '.' and 0 < i < n - 1 and c[i - 1].isdigit() and c[i + 1].isdigit():
            out.append(ch)
        else:
            out.append(' ')                                       # any other symbol or punctuation
    return re.sub(r'\s+', ' ', ''.join(out)).strip()


def speech_clauses(text, lang='en'):
    """Return [(clause_text, pause_seconds_after), ...]. No clause contains punctuation or symbols."""
    if not text:
        return []
    text = unicodedata.normalize('NFC', str(text)).replace('\r', '')
    if '(From Source:' in text:
        text = text.split('(From Source:')[0]
    text = _URL.sub(' ', text)
    text = _FILENAME.sub(' ', text)
    text = _SOURCE_LINE.sub('', text)
    text = _SOURCE_GROUP.sub(' ', text)
    text = _CITE_NUMBER.sub(' ', text)

    clauses = []

    def add(clause, pause):
        clause = _clean_clause(clause)
        if re.search(r'[^\W_]', clause):
            clauses.append([clause, pause])
        elif clauses:                                             # nothing to say: keep the pause
            clauses[-1][1] = max(clauses[-1][1], pause)

    for raw in text.split('\n'):
        if not raw.strip():
            if clauses:
                clauses[-1][1] = max(clauses[-1][1], PAUSE_PARAGRAPH)
            continue
        if _RULE.match(raw):
            continue
        line = _BULLET.sub('', raw, count=1) if _BULLET.match(raw) else raw
        line = _line_to_text(line, lang)
        parts = re.split(r'([.!?;:,]+)(?=\s|$)', line)
        for i in range(0, len(parts), 2):
            piece = parts[i]
            punct = parts[i + 1] if i + 1 < len(parts) else ''
            if punct:
                pause = PAUSE_SENTENCE if any(c in punct for c in '.!?') else PAUSE_COMMA
            else:
                pause = PAUSE_SENTENCE                            # end of the line
            add(piece, pause)
    if clauses:
        clauses[-1][1] = 0.0
    return [(c, p) for c, p in clauses]


def speech_text(text, lang='en'):
    """One plain string with no punctuation, for engines that cannot take pieces."""
    return ' '.join(c for c, _ in speech_clauses(text, lang))
