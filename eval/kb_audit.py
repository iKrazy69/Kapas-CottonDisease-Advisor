"""
Knowledge-base audit: do the dose numbers in a document survive the loader?

The RAG answers only from the text that was stored in the database. If the loader damages
"Propineb 70 WP @ 25-30 g" the model can only copy the damaged version. This script takes the
document text, finds every dose-like expression (application rates after "@", percentage strengths,
numeric ranges), and checks that each one is still readable after cleaning, with the old cleaning
rule and with the current one.

    python eval/kb_audit.py
    python eval/kb_audit.py --file documents/CICR_Illustrative_Guide_Cotton_Pests_Diseases_2026.txt

Writes eval/results/kb_dose_audit.md and .json. Needs no Ollama and no internet.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'backend'))
sys.path.insert(0, HERE)

from common import fmt_rate  # noqa: E402

DEFAULT_FILE = os.path.join(ROOT, 'documents', 'CICR_Illustrative_Guide_Cotton_Pests_Diseases_2026.txt')

FAMILIES = {
    'application rate (after @)': re.compile(
        r'@\s*\d[\d.]*(?:\s*-\s*\d[\d.]*)?\s*(?:g|kg|mL|ml|L|litres?|liters?)\b(?:\s*/\s*\d*\s*(?:kg|ha|acre|L|l|litre|plant|seed|mL)\b)?'),
    'strength in percent': re.compile(r'\d[\d.]*\s*%(?:\s*(?:WP|EC|SC|WG|SL|w/w|w/v))?'),
    'numeric range (includes years and page numbers)': re.compile(r'(?<![\d.])\d+\s*-\s*\d+(?![\d-])'),
}


def legacy_clean(text):
    """The loader's old rule, copied as it was: whitespace collapse, then delete every character not in the list."""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s\.\,\!\?\:\;\-\(\)$\n]', '', text)
    return text.strip()


def norm(s):
    return re.sub(r'\s+', ' ', s).strip().lower()


def current_clean(text):
    try:
        from document_processor import DocumentProcessor
    except ImportError as e:                       # PyPDF2 / python-docx missing: stub them, only _clean_text is used
        import types
        for name in ('PyPDF2', 'docx'):
            if name not in sys.modules:
                m = types.ModuleType(name)
                m.PdfReader = object
                m.Document = object
                sys.modules[name] = m
        from document_processor import DocumentProcessor
    return DocumentProcessor()._clean_text(text)


def audit(raw_text, clean_fns):
    """Look at every dose-like spot in the document and ask each cleaner to clean just that spot.

    A spot is intact when the cleaned text equals what the document meant (Symbol-font characters read as the
    ASCII they stand for). Returns {family: {'total': n, <cleaner name>: intact_count, 'examples': {name: [(meant, got)]}}}.
    """
    # same length as the raw text, so match positions line up with the raw characters
    mapped = ''.join(chr(ord(c) - 0xF000) if 0xF020 <= ord(c) <= 0xF07E else c for c in raw_text)
    result = {}
    for fam, pat in FAMILIES.items():
        row = {'total': 0}
        seen = {name: {} for name in clean_fns}
        for name in clean_fns:
            row[name] = 0
        for m in pat.finditer(mapped):
            span = raw_text[m.start():m.end()]
            meant = norm(m.group(0))
            row['total'] += 1
            for name, fn in clean_fns.items():
                got = norm(fn(span))
                if got == meant:
                    row[name] += 1
                else:
                    seen[name].setdefault(meant, got)
        row['examples'] = {name: list(d.items())[:10] for name, d in seen.items()}
        result[fam] = row
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--file', default=DEFAULT_FILE)
    ap.add_argument('--out-dir', default=os.path.join(HERE, 'results'))
    args = ap.parse_args()

    with open(args.file, encoding='utf-8') as fh:
        raw = fh.read()
    fns = {'old loader': legacy_clean, 'current loader': current_clean}
    res = audit(raw, fns)

    os.makedirs(args.out_dir, exist_ok=True)
    lines = [f'# Dose-text audit: {os.path.basename(args.file)}', '',
             'Every dose-like spot in the document (application rates, strengths, numeric ranges), and whether the cleaned text still says the same thing.', '',
             '| type of spot | spots in document | intact, old loader | intact, current loader |', '|---|---|---|---|']
    tot = {'total': 0, 'old loader': 0, 'current loader': 0}
    for fam, r in res.items():
        lines.append(f"| {fam} | {r['total']} | {fmt_rate(r['old loader'], r['total'])} | {fmt_rate(r['current loader'], r['total'])} |")
        for k in tot:
            tot[k] += r[k]
    lines += ['', f"All types together: old loader kept {fmt_rate(tot['old loader'], tot['total'])}; "
                  f"current loader kept {fmt_rate(tot['current loader'], tot['total'])}.", '',
              'Examples the old loader damaged (what the document says -> what the model was given):', '']
    for fam, r in res.items():
        for expr, damaged in r['examples']['old loader']:
            lines.append(f'- `{expr}` became `{damaged}`')
    cur = [(f, e) for f, r in res.items() for e in r['examples']['current loader']]
    if cur:
        lines += ['', 'Still damaged by the current loader:', ''] + [f'- `{e[0]}` became `{e[1]}`' for f, e in cur]
    lines += ['', 'Scope: each spot is checked before the document is cut into chunks. A chunk boundary can still fall inside a '
                  'dose; that is not measured here.']
    report = '\n'.join(lines)
    with open(os.path.join(args.out_dir, 'kb_dose_audit.md'), 'w', encoding='utf-8') as fh:
        fh.write(report + '\n')
    with open(os.path.join(args.out_dir, 'kb_dose_audit.json'), 'w', encoding='utf-8') as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False)
    print(report)


if __name__ == '__main__':
    main()
