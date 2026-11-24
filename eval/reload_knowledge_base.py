"""
Load every document in documents/ into the database (what the app does at start-up) and then check that the doses survived.

    python eval/reload_knowledge_base.py

Use it after `mv chroma_data chroma_data_before_cleaning_fix`. It needs Ollama running (the documents are embedded with
nomic-embed-text), takes a few minutes, stops by itself, and prints a PASS/FAIL line for the checks at the end. It skips documents
that are already loaded, so it is safe to run twice.
"""
import os
import re
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Text that appears in the CICR guide and was damaged by the old loader.
CHECKS = [
    ('dose range kept ("@ 25-30 g")', 'Propineb 70 WP @ 25-30 g'),
    ('threshold range kept ("1-5%")', 'Economic threshold: 1-5% disease incidence'),
    ('percent sign kept ("50% WP")', '50% WP'),
    ('per-kg dose kept ("@ 1 g/kg")', '@ 1 g/kg'),
]


def load_all(rag, processor, folder, log=print):
    """Same steps and same document ids as the app's auto_load_documents. Returns [(file, chunks, ok)]."""
    folder = Path(folder)
    docs = sorted(list(folder.glob('*.pdf')) + list(folder.glob('*.docx')) + list(folder.glob('*.txt')))
    out = []
    for p in docs:
        doc_id = p.name.replace('.', '_').replace(' ', '_')
        if doc_id in rag.documents_registry:
            log(f'  already loaded: {p.name}')
            continue
        log(f'  loading {p.name} ...')
        chunks = processor.process_document(str(p))
        if not chunks:
            log('    no text found, skipped')
            continue
        ok = bool(rag.add_document(doc_id, chunks, str(p)))
        log(f'    {"loaded" if ok else "FAILED"}: {len(chunks)} chunks')
        out.append((p.name, len(chunks), ok))
    return out


def check_chunks(chunks):
    """[(label, passed)] for the damaged-by-the-old-loader phrases, looked up in the stored text."""
    joined = re.sub(r'\s+', ' ', ' '.join(chunks))
    return [(label, phrase in joined) for label, phrase in CHECKS]


def main():
    sys.path.insert(0, os.path.join(ROOT, 'backend'))
    from config import Config
    from rag_engine import RAGEngine
    from document_processor import DocumentProcessor

    rag = RAGEngine()
    if not rag._check_ollama_connection():
        raise SystemExit('Ollama is not running. Open the Ollama app (or run: ollama serve) and try again.')
    print(f'Loading documents from {Config.DOCUMENTS_FOLDER}')
    results = load_all(rag, DocumentProcessor(), Config.DOCUMENTS_FOLDER)
    chunks = rag.collection.get(include=['documents']).get('documents', [])
    print(f'\nDatabase now holds {len(chunks)} chunks.')
    print(f'Search scheme: {getattr(rag, "embedding_scheme", "?")}   chunk size: {Config.CHUNK_SIZE}/{Config.CHUNK_OVERLAP}')
    checks = check_chunks(chunks)
    for label, ok in checks:
        print(('PASS ' if ok else 'FAIL ') + label)
    if all(ok for _, ok in checks):
        print('\nThe stored guide text is correct. You can run the advisor benchmark now.')
    else:
        print('\nSome doses are still damaged in the stored text. If this folder was not empty before, stop here: '
              'run  mv chroma_data chroma_data_old  and then this script again.')
        sys.exit(1)


if __name__ == '__main__':
    main()
