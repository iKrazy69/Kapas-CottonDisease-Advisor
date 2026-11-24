"""
Keyword rescue for the document search.

The search normally ranks passages by meaning (embeddings). That can miss a passage that holds a very specific word.
Example: "Why should cotton seed be acid delinted?" has no embedding match close to the passage that says
"Acid delinting: ... delinted using sulfuric acid ... destroys bacterial inoculum", so the app fell through to the internet.

The rescue adds AT MOST ONE extra passage from a plain keyword match (BM25), and only when:
  - the question holds at least two rare words (words that occur in few passages), and
  - one passage holds at least two of them, and its keyword score is high enough.
Questions with one rare word (most out-of-scope and "not in the guide" questions) get nothing extra.
The extra passage is added at the end; it never changes which passages the embedding search found, and it never changes
the "is the question covered at all" check (that still uses the embedding similarity only).

No language model, no internet. Switch off with Config.LEXICAL_RESCUE = False.
"""
import collections
import math
import re

STOP = set('''the and for are was were with that this from have has had you your can what which when where why how who whom does did
not but all any one use used using per into such than then also may might should would could about over under between during after
before while their there these those they them our out off its it is be to of in on at by as an or if so do i my me we us a'''.split())

_SUFFIXES = ('ations', 'ation', 'ings', 'ing', 'edly', 'ed', 'es', 's', 'ly')


def stem(word):
    """A crude stemmer, enough to make "delinted" and "delinting" meet ("delint")."""
    for suf in _SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 4:
            return word[:-len(suf)]
    return word


def tokens(text):
    return [stem(w) for w in re.findall(r'[a-z]{3,}', (text or '').lower()) if w not in STOP]


class Index:
    def __init__(self, texts, metadatas=None, k1=1.5, b=0.75):
        self.texts = list(texts or [])
        self.metas = list(metadatas) if metadatas is not None else [None] * len(self.texts)
        self.k1, self.b = k1, b
        docs = [tokens(t) for t in self.texts]
        self.n = len(docs)
        self.avgdl = (sum(len(d) for d in docs) / self.n) if self.n else 0.0
        self.lens = [len(d) for d in docs]
        self.tf = [collections.Counter(d) for d in docs]
        self.df = collections.Counter(w for d in docs for w in set(d))
        # a word is "rare" when it occurs in at most 2% of the passages (and in at least 8 passages' worth of room)
        self.max_df = max(8, int(round(0.02 * self.n)))

    def _score(self, terms, i):
        s = 0.0
        for w in terms:
            f = self.tf[i].get(w)
            if not f:
                continue
            idf = math.log(1 + (self.n - self.df[w] + 0.5) / (self.df[w] + 0.5))
            s += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.lens[i] / self.avgdl))
        return s

    def rescue(self, query, exclude=(), k=1, min_rare_hits=2, min_score=9.0):
        """Up to k passages (text, metadata, score, matched rare words) the embedding search may have missed."""
        if not self.n:
            return []
        terms = list(dict.fromkeys(tokens(query)))
        rare = [w for w in terms if 0 < self.df.get(w, 0) <= self.max_df]
        if len(rare) < min_rare_hits:
            return []
        skip = set(exclude)
        found = []
        for i in range(self.n):
            if self.texts[i] in skip:
                continue
            hits = [w for w in rare if w in self.tf[i]]
            if len(hits) < min_rare_hits:
                continue
            score = self._score(terms, i)
            if score >= min_score:
                found.append((score, -i, i, hits))
        found.sort(reverse=True)
        return [(self.texts[i], self.metas[i], round(score, 2), hits) for score, _, i, hits in found[:k]]
