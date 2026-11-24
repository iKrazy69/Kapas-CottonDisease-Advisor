"""
Chunking experiment: which way of cutting up and embedding the guide lets search find the answer most often?

It builds several versions of the search index in memory from the guide (your database is not touched), asks the same
questions as the benchmark, and reports in how many cases the passage with the answer is among the top 3, 5 and 8 results.
No language model is used, only the embedding model, so it takes a few minutes.

Compared:  chunk size and overlap  |  section heading in front of each chunk  |  the "search_document:" / "search_query:"
prefixes that nomic-embed-text is trained with (the app does not use them today).
The first row, 500/50 without heading or prefix, is how the app builds its database today.

    python eval/chunking_experiment.py

Needs Ollama running with nomic-embed-text. The best row is a candidate, not a proof: it is chosen on the same 34 questions
it is scored on, so expect the gain to shrink on new questions.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'backend'))

import numpy as np  # noqa: E402

import advisor_benchmark as AD  # noqa: E402
import retrieval_check as RC  # noqa: E402

GUIDE = AD.GUIDE
DOC_PREFIX = 'search_document: '
QUERY_PREFIX = 'search_query: '

# name, chunk size, overlap, section heading in front, nomic prefixes
CONFIGS = [
    ('today: 500/50', 500, 50, False, False),
    ('500/50 + heading', 500, 50, True, False),
    ('500/50 + prefixes', 500, 50, False, True),
    ('500/50 + heading + prefixes', 500, 50, True, True),
    ('800/100 + prefixes', 800, 100, False, True),
    ('800/100 + heading + prefixes', 800, 100, True, True),
    ('1200/150 + heading + prefixes', 1200, 150, True, True),
]


def build_chunks(raw_text, size, overlap, heading, processor=None):
    """Cut the guide the way DocumentProcessor does, with the given size and overlap."""
    import document_processor as DP
    proc = processor or DP.DocumentProcessor()
    proc.chunk_size, proc.chunk_overlap = size, overlap
    if heading:
        return proc._chunk_sections(proc._clean_text(DP.mark_section_headings(raw_text)))
    return proc._chunk_text(proc._clean_text(raw_text))


class CachedEmbedder:
    """Wraps an embedder with encode(text) -> vector; remembers answers and counts all-zero results (failed requests)."""
    def __init__(self, inner):
        self.inner, self.cache, self.zero = inner, {}, 0

    def one(self, text):
        if text not in self.cache:
            v = np.asarray(self.inner.encode(text), dtype=np.float32)
            if not np.any(v):
                self.zero += 1
            self.cache[text] = v
        return self.cache[text]


def build_matrix(chunks, embedder, prefix=''):
    m = np.vstack([embedder.one(prefix + c) for c in chunks])
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms


def top_k(matrix, qvec, k):
    """Indices of the k most similar rows (cosine) and their similarities. Matrix rows are unit length."""
    q = np.asarray(qvec, dtype=np.float32)
    n = np.linalg.norm(q)
    sims = matrix @ (q / n if n else q)
    idx = np.argsort(-sims)[:k]
    return idx, sims[idx]


def run_config(cfg, raw, embedder, items, plan, ks):
    name, size, overlap, heading, prefixes = cfg
    chunks = build_chunks(raw, size, overlap, heading)
    before_zero = embedder.zero
    matrix = build_matrix(chunks, embedder, DOC_PREFIX if prefixes else '')
    out = {'name': name, 'chunks': len(chunks), 'avg_chars': round(sum(map(len, chunks)) / max(1, len(chunks))),
           'zero_vectors': embedder.zero - before_zero, 'found': {}, 'mean_recall': {}, 'missed': {}}
    for k in ks:
        def retrieve(it, lang, k=k):
            q = plan(it)
            idx, sims = top_k(matrix, embedder.one((QUERY_PREFIX if prefixes else '') + q), k)
            return [chunks[i] for i in idx], float(sims[0])
        rows = RC.evaluate(items, retrieve)
        s = RC.summarize(rows)
        out['found'][k] = s['fully_retrieved']
        out['mean_recall'][k] = round(s['mean_key_fact_recall'], 3)
        out['missed'][k] = [r['id'] for r in rows if not r['all_found']]
        out['questions'] = s['questions']
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--ks', default='3,5,8')
    args = ap.parse_args()
    ks = [int(x) for x in args.ks.split(',')]
    import cotton_flow
    from rag_engine import NomicEmbeddings
    from config import Config
    raw = open(GUIDE, encoding='utf-8', errors='ignore').read()
    embedder = CachedEmbedder(NomicEmbeddings(f'http://localhost:{Config.OLLAMA_PORT}'))
    items = AD.load_items()

    def plan(it):
        d = it.get('disease_context')
        return cotton_flow.plan_question(d, it['question_en'])[0] if d else it['question_en']

    results = []
    print(f'{"setup":34} {"chunks":>6} {"chars":>6} {"zero":>5}  ' + '  '.join(f'top{k:<2}' for k in ks) + '   mean key-fact recall at top ' + str(ks[1] if len(ks) > 1 else ks[0]))
    for cfg in CONFIGS:
        r = run_config(cfg, raw, embedder, items, plan, ks)
        results.append(r)
        mid = ks[1] if len(ks) > 1 else ks[0]
        print(f'{r["name"]:34} {r["chunks"]:>6} {r["avg_chars"]:>6} {r["zero_vectors"]:>5}  ' +
              '  '.join(f'{r["found"][k]:>2}/{r["questions"]}' for k in ks) + f'   {r["mean_recall"][mid]:.3f}', flush=True)
    print()
    for r in results:
        print(f'{r["name"]}: not found at top {ks[1] if len(ks) > 1 else ks[0]}: ' + (', '.join(r['missed'][ks[1] if len(ks) > 1 else ks[0]]) or 'none'))
    os.makedirs(AD.RESULTS, exist_ok=True)
    out = os.path.join(AD.RESULTS, 'chunking_experiment.json')
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(results, fh, indent=1)
    print(f'\nSaved {out}')
    if embedder.zero:
        print(f'WARNING: {embedder.zero} embedding requests returned nothing (stored as zero vectors). Those chunks can never be found.')


if __name__ == '__main__':
    main()
