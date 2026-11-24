"""Build eval/cotton_qa_benchmark.json from benchmark_items.py and the guide (copies the cited lines in as reference text)."""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from benchmark_items import ITEMS, EXPECTED  # noqa: E402

GUIDE = os.path.join(ROOT, 'documents', 'CICR_Illustrative_Guide_Cotton_Pests_Diseases_2026.txt')
OUT = os.path.join(HERE, 'cotton_qa_benchmark.json')
PAGE_HEADER = 'Integrated Management of Cotton Pests'


def map_symbols(s):
    """Symbol-font private-use characters back to the ASCII they stand for (U+F02D is the hyphen in '25-30 g')."""
    return ''.join(chr(ord(c) - 0xF000) if 0xF020 <= ord(c) <= 0xF07E else ('-' if c == '–' else c) for c in s)


def flat(s):
    """Form used to compare keys: no spaces, lower case, symbols mapped."""
    return re.sub(r'\s+', '', map_symbols(s)).lower()


def read_guide(path=GUIDE):
    with open(path, encoding='utf-8') as fh:
        return fh.read().split('\n')


def lines_text(guide_lines, ranges):
    out = []
    for a, b in ranges:
        for n in range(a, b + 1):
            raw = guide_lines[n - 1]
            if not raw.strip() or PAGE_HEADER in raw or raw.strip().isdigit():
                continue
            out.append({'line': n, 'text': re.sub(r'\s+', ' ', map_symbols(raw)).strip()})
    return out


def build(guide_lines):
    items = []
    for it in ITEMS:
        d = {'id': it['id'], 'category': it['category'], 'expected': EXPECTED[it['category']], 'topic': it['topic'],
             'disease_context': it.get('disease'), 'question_en': it['en'], 'question_hi': it['hi'],
             'status': 'DRAFT: written from the guide text; not verified by a cotton expert; Hindi not checked by a Hindi speaker'}
        if it.get('lines'):
            d['reference'] = lines_text(guide_lines, it['lines'])
        for k in ('keys', 'conflict_doses', 'derived_doses', 'absent_terms', 'max_mentions', 'note'):
            if k in it:
                d[k] = it[k]
        items.append(d)
    return items


def main():
    guide = read_guide()
    items = build(guide)
    with open(OUT, 'w', encoding='utf-8') as fh:
        json.dump({'source': 'ICAR-CICR, An Illustrative Guide for Integrated Management of Cotton Pests, Diseases and Nematodes (2026), '
                             'as loaded in documents/' + os.path.basename(GUIDE) + '; line numbers refer to that text file',
                   'status': 'DRAFT, not expert-verified', 'items': items}, fh, indent=1, ensure_ascii=False)
    from collections import Counter
    print(f'{len(items)} items written to {OUT}:', dict(Counter(i['category'] for i in items)))


if __name__ == '__main__':
    main()
