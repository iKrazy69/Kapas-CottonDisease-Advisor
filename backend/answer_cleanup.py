"""Remove repeated sentences from a model answer.

A small local model sometimes falls into a loop and writes the same few sentences until it hits the token limit
(seen once in the 300-answer benchmark: 676 words, 18 repeated sentences, cut off mid-sentence). Only repeats are
removed (a sentence that repeats an earlier one, or mostly repeats it), so a normal answer comes back unchanged.
"""
import re

_SENTENCE_END = re.compile(r'(?<=[.!?।])\s+')
_TERMINAL = ('.', '!', '?', '।', ')', '"', "'")
MIN_WORDS_EXACT = 5      # a sentence this long that appears twice is a repeat
MIN_WORDS_NEAR = 8       # a longer sentence is also a repeat when most of it was already said
NEAR_SHARE = 0.6         # share of its 4-word runs that must already appear earlier


def _words(sentence):
    return re.findall(r'\w+', sentence.lower())


def _runs(words, n=4):
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def collapse_repeats(text):
    """Return the answer with repeated sentences removed (and a cut-off last sentence dropped if repeats were found)."""
    if not text or len(text) < 200:
        return text
    seen_exact = set()
    seen_runs = set()
    out_lines = []
    removed = 0
    for line in text.split('\n'):
        kept = []
        for sent in _SENTENCE_END.split(line):
            w = _words(sent)
            key = tuple(w)
            drop = False
            if len(w) >= MIN_WORDS_EXACT and key in seen_exact:
                drop = True
            elif len(w) >= MIN_WORDS_NEAR:
                runs = _runs(w)
                if runs and len(runs & seen_runs) / len(runs) >= NEAR_SHARE:
                    drop = True
            seen_exact.add(key)
            seen_runs |= _runs(w)
            if drop:
                removed += 1
            else:
                kept.append(sent)
        out_lines.append(' '.join(kept))
    if not removed:
        return text
    result = re.sub(r'\n{3,}', '\n\n', '\n'.join(out_lines)).strip()
    if result and not result.endswith(_TERMINAL):
        cut = max(result.rfind(c) for c in ('.', '!', '?', '।'))
        if cut > 0:
            result = result[:cut + 1]
    return result
