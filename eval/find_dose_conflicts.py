"""
Scan the whole guide for the same product (same active ingredients, same strength) given with different amounts for the
same kind of carrier (per litre of water, per kg of seed, per hectare, per acre).

This is how the short list in backend/dose_conflicts.py was found. It only lists CANDIDATES: the same product often has
different amounts for different pests or growth stages, so a person has to read each one in the guide before it goes on
the list. Needs no Ollama and no internet.

    python eval/find_dose_conflicts.py

Writes eval/results/dose_conflict_candidates.md
"""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GUIDE = os.path.join(ROOT, 'documents', 'CICR_Illustrative_Guide_Cotton_Pests_Diseases_2026.txt')

DOSE = re.compile(r'(?P<amt>\d+(?:\.\d+)?(?:\s*[-–]\s*\d+(?:\.\d+)?)?)\s*(?P<unit>g|gm|mL|ml|ML|kg|L)\s*(?:/|per)\s*'
                  r'(?P<den>\d*\.?\d*\s*(?:L|litres?|liters?|kg(?:\s*seeds?)?|ha|acre))\b')
SPLIT = re.compile(r'(?:\.\s|;\s|\bor\b|,\s|:\s|\bSpray\b|\bspray\b|\bwith\b|\bapply\b|\bApply\b|\bsuch as\b|\blike\b|\band\b(?! [A-Z][a-z]+ \d))')
FORM = {'WP', 'WS', 'DS', 'EC', 'SC', 'WG', 'SL', 'SG', 'OD', 'FS', 'WDG', 'EW', 'ZC', 'CS', 'GR'}


def events(text):
    flat = re.sub(r'\s+', ' ', ''.join(chr(ord(c) - 0xF000) if 0xF020 <= ord(c) <= 0xF07E else c for c in text))
    rows = []
    for m in DOSE.finditer(flat):
        pre = re.sub(r'\s*@\s*$', '', flat[max(0, m.start() - 95):m.start()].rstrip(' @'))
        seg = SPLIT.split(pre)[-1].strip()
        names = [n.lower() for n in re.findall(r'\b[A-Z][a-z]{3,}(?:-[a-z]+)?\b', seg) if n.upper() not in FORM]
        if not names:
            continue
        strengths = re.findall(r'(\d+(?:\.\d+)?)\s*%', seg)
        unit = m.group('unit').lower().replace('gm', 'g')
        den = m.group('den').lower()
        dn = re.match(r'(\d*\.?\d*)', den.strip()).group(1)
        dnum = float(dn) if dn else 1.0
        carrier = ('kg seed' if 'seed' in den else 'kg') if 'kg' in den else ('ha' if 'ha' in den else ('acre' if 'acre' in den else 'L'))
        norm = tuple(round(float(x) / dnum, 4) for x in re.split(r'\s*[-–]\s*', m.group('amt')))
        rows.append({'pos': m.start(), 'key': (tuple(sorted(set(names))), tuple(strengths)), 'unit': unit, 'carrier': carrier,
                     'norm': norm, 'raw': m.group(0), 'context': flat[max(0, m.start() - 110):m.end() + 40]})
    return rows


def candidates(rows):
    groups = collections.defaultdict(list)
    for r in rows:
        groups[(r['key'], r['unit'], r['carrier'])].append(r)
    out = []
    for k, rs in groups.items():
        by_value = {}
        for r in rs:
            by_value.setdefault(r['norm'], []).append(r)
        if len(by_value) > 1:
            out.append((k, by_value))
    return out


def main():
    with open(GUIDE, encoding='utf-8') as fh:
        rows = events(fh.read())
    cands = candidates(rows)
    lines = ['# Dose conflict candidates', '',
             f'Scanned {len(rows)} amounts written as "x g/mL per litre, kg seed, ha or acre" in the guide. '
             f'{len(cands)} product groups appear with more than one amount for the same kind of carrier.', '',
             'These are CANDIDATES. The same product often has different amounts for different pests or growth stages. '
             'A person must read each one in the guide before it is called a conflict. Confirmed ones are in backend/dose_conflicts.py.', '']
    for (key, unit, carrier), by_value in cands:
        lines += [f"## {' + '.join(key[0])} {'/'.join(key[1])}% ({unit} per {carrier})", '']
        for v, rs in by_value.items():
            lines.append(f"- {sorted({r['raw'] for r in rs})} ({len(rs)}x). Example: ...{rs[0]['context']}...")
        lines.append('')
    out = os.path.join(HERE, 'results', 'dose_conflict_candidates.md')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')
    print(f'{len(rows)} amounts, {len(cands)} candidate groups -> {out}')


if __name__ == '__main__':
    sys.exit(main())
