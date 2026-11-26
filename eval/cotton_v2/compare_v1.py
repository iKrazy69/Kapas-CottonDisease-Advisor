"""
Old (v1 SVM) vs new (v2) on the SAME outside photos.

    python eval/cotton_v2/compare_v1.py [--per 100]

For every outside source (not the project's own set, which trained v1) and every
condition that both models know (Healthy, Bacterial leaf blight, Cotton leaf
curl virus disease), up to --per photos are taken. Non-cotton photos are taken
from every negative source. Both models run their full live rule (v1: 0.70 +
class F1; v2: gate, then 0.70 + class F1).

v2 here is the SAVED model, which was trained on all sources, so its numbers on
these photos are training-set numbers, not a fair test. The fair v2 numbers are
the leave-one-source-out tables in eval/results/cotton_v2/report.md. This
script answers a narrower question: what does each model actually do with a
given photo; and for v1 these photos were never seen, so its numbers ARE fair.
Writes eval/results/cotton_v2/compare_v1.md
"""

import argparse
import collections
import csv
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'backend'))
V2 = os.path.expanduser('~/Downloads/Cottondataset/v2')
SHARED = {'Healthy', 'Bacterial leaf blight', 'Cotton leaf curl virus disease'}
V1_NAME = {'Healthy': 'Healthy Plants'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--per', type=int, default=100)
    a = ap.parse_args()
    from config import Config
    from cotton_classifier import CottonClassifier
    v1 = CottonClassifier(Config.COTTON_MODEL_PATH, Config.COTTON_METRICS_PATH)

    rows = list(csv.DictReader(open(os.path.join(V2, 'catalog.csv'))))
    seen, pick = set(), collections.defaultdict(list)
    for r in rows:
        if r['sha1'] in seen or r['source'] == 'own':
            continue
        seen.add(r['sha1'])
        if r['role'] == 'cotton' and r['label'] in SHARED:
            pick[(r['source'], r['label'])].append(r)
        elif r['role'] == 'negative':
            pick[(r['source'], 'not cotton')].append(r)
    res = {}
    for key, items in sorted(pick.items()):
        items = random.Random(7).sample(items, min(a.per, len(items)))
        right = conf_wrong = answered = 0
        for r in items:
            d = v1.predict(os.path.join(V2, 'img', r['file']))
            ok = d['status'] == 'confident'
            answered += ok
            if key[1] == 'not cotton':
                conf_wrong += ok          # v1 has no "not cotton" answer: any confident answer is wrong
            else:
                hit = d['disease'] == V1_NAME.get(key[1], key[1])
                right += ok and hit
                conf_wrong += ok and not hit
        res[key] = (len(items), right, conf_wrong, answered)
        print(key, res[key], flush=True)

    L = ['# v1 SVM on outside photos (same photos as the v2 tests)', '',
         'v1 never saw these photos, so its numbers are a fair test. "Right" = confident and the correct name.', '',
         '| Source | True condition | n | v1 right | v1 confident and wrong | v1 answered |', '|---|---|---|---|---|---|']
    for (s, lab), (n, right, cw, ans) in res.items():
        L.append(f'| {s} | {lab} | {n} | {100 * right / n:.1f}% | {100 * cw / n:.1f}% | {100 * ans / n:.1f}% |')
    os.makedirs(os.path.join(ROOT, 'eval', 'results', 'cotton_v2'), exist_ok=True)
    open(os.path.join(ROOT, 'eval', 'results', 'cotton_v2', 'compare_v1.md'), 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
