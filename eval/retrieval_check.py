"""
Retrieval check: does search put the passage that holds the answer into the top results?

No language model is used, only the search step, so it takes seconds. Use it before and after changing how the guide is
cut into chunks. For each question the guide can answer it looks at the passages the app would hand to the model and asks
whether the key facts of the answer are in them (the same key facts the benchmark uses).

    python eval/retrieval_check.py --label before
    (rebuild the database, see eval/README.md)
    python eval/retrieval_check.py --label after --compare before

Needs Ollama running (it embeds the question) and the guide loaded.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import advisor_benchmark as AD  # noqa: E402
from common import wilson, fmt_rate  # noqa: E402

CATEGORIES = ('in_document', 'followup')


def evaluate(items, retrieve, lang='en'):
    """retrieve(item, lang) -> (chunks, best_similarity). Returns one row per question the guide answers."""
    rows = []
    for it in items:
        if it.get('category') not in CATEGORIES or not it.get('keys'):
            continue
        chunks, best = retrieve(it, lang)
        s = AD.score({'answer': '', 'abstained': False, 'source_kind': 'documents', 'context': chunks}, it, '')
        text = AD.flat(AD.normalize_units(' '.join(chunks)))
        missing = [g for g in it['keys'] if not any(k in text for k in g)]
        rows.append({'id': it['id'], 'category': it['category'], 'recall': s['retrieval_recall'],
                     'all_found': s['retrieval_recall'] == 1, 'best_similarity': best,
                     'missing_key_groups': missing, 'top_chunks': [c[:110].replace('\n', ' ') for c in chunks]})
    return rows


def summarize(rows):
    n = len(rows)
    k = sum(1 for r in rows if r['all_found'])
    lo, hi = wilson(k, n) if n else (0, 0)
    return {'questions': n, 'fully_retrieved': k, 'share_fully_retrieved': (k / n) if n else None, 'ci95': [lo, hi],
            'mean_key_fact_recall': (sum(r['recall'] for r in rows) / n) if n else None}


def compare(before, after):
    b = {r['id']: r for r in before}
    a = {r['id']: r for r in after}
    gained = sorted(i for i in a if a[i]['all_found'] and i in b and not b[i]['all_found'])
    lost = sorted(i for i in a if not a[i]['all_found'] and i in b and b[i]['all_found'])
    return gained, lost


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--label', required=True, help='name for this measurement, e.g. before or after')
    ap.add_argument('--lang', default='en', choices=['en', 'hi'])
    ap.add_argument('--top-k', type=int, default=5)
    ap.add_argument('--compare', help='label of an earlier measurement to compare with')
    ap.add_argument('--db-folder', help='measure another database folder (default: chroma_data), e.g. chroma_data_before_sections')
    ap.add_argument('--show-misses', action='store_true', help='print, for every question not found, what is missing and what was retrieved instead')
    args = ap.parse_args()

    sys.path.insert(0, os.path.join(ROOT, 'backend'))
    from config import Config
    if args.db_folder:
        Config.CHROMA_DATA_FOLDER = os.path.abspath(args.db_folder)
        if not os.path.isdir(Config.CHROMA_DATA_FOLDER):
            raise SystemExit(f'Folder not found: {Config.CHROMA_DATA_FOLDER}')
    import cotton_flow
    from translator import translate_to_english
    from rag_engine import RAGEngine
    rag = RAGEngine()
    if not rag.has_documents():
        raise SystemExit('No documents are loaded. Run:  python eval/reload_knowledge_base.py')
    stored = rag.collection.get(include=['documents']).get('documents', [])
    if AD.kb_is_stale(stored):
        raise SystemExit('The database was built with the old document loader. Rebuild it first (see eval/README.md).')
    labelled = sum(1 for c in stored if c.startswith('['))

    def retrieve(it, lang):
        q = it['question_en'] if lang == 'en' else translate_to_english(it['question_hi'], 'hi')
        disease = it.get('disease_context')
        search = cotton_flow.plan_question(disease, q)[0] if disease else q
        chunks, _, sims = rag._retrieve_context(search, args.top_k)
        return chunks, (float(max(sims)) if sims else None)

    items = AD.load_items()
    rows = evaluate(items, retrieve, args.lang)
    summ = summarize(rows)
    summ.update(db_folder=Config.CHROMA_DATA_FOLDER, label=args.label, lang=args.lang, top_k=args.top_k, chunks_in_database=len(stored), chunks_with_section_label=labelled)
    os.makedirs(AD.RESULTS, exist_ok=True)
    out = os.path.join(AD.RESULTS, f'retrieval_check_{args.label}.json')
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump({'summary': summ, 'rows': rows}, fh, indent=1)

    print(f'Database: {len(stored)} chunks, {labelled} start with a section label.')
    print(f'Search scheme: {getattr(rag, "embedding_scheme", "?")}')
    print(f'Questions the guide answers: {summ["questions"]} ({args.lang}, top {args.top_k} passages)')
    print(f'Passage with the answer found: {fmt_rate(summ["fully_retrieved"], summ["questions"])}   '
          f'mean key-fact recall {summ["mean_key_fact_recall"]:.3f}')
    missed = [r['id'] for r in rows if not r['all_found']]
    print('Not found:', ', '.join(missed) if missed else 'none')
    if args.show_misses:
        for r in rows:
            if not r['all_found']:
                print(f'  {r["id"]}: missing {r["missing_key_groups"]}')
                for c in r['top_chunks']:
                    print('      ' + c)
    if args.compare:
        prev = os.path.join(AD.RESULTS, f'retrieval_check_{args.compare}.json')
        if not os.path.exists(prev):
            print(f'(no earlier measurement named "{args.compare}")')
        else:
            before = json.load(open(prev, encoding='utf-8'))
            gained, lost = compare(before['rows'], rows)
            print(f'Compared with "{args.compare}": now found {len(gained)} more ({", ".join(gained) or "-"}), '
                  f'lost {len(lost)} ({", ".join(lost) or "-"}). Before: {before["summary"]["fully_retrieved"]}/{before["summary"]["questions"]}.')
    print(f'Saved {out}')


if __name__ == '__main__':
    main()
