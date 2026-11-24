"""
Step 6: does photo size alone change what the saved model says about the project's own photos?

prep_images.py --pre-shrink N shrinks the longest side to N pixels before the usual 224x224 resize. This
script runs the saved model on the same photos at full size and at each shrunken size and compares the
answers. Only the 81 photos in the saved model's own test split are scored for accuracy; all are used for
how often the answer changes.

Run: python eval/cotton_external/resolution_test.py --work <folder> --model <joblib> --metrics <json> --variants 1000,400
"""
import argparse
import json
import os
import sys
import warnings

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import pct  # noqa: E402

MIN_PROB, MIN_F1 = 0.70, 0.30


def run(bundle, metrics, F, pngs):
    proba = bundle['model'].predict_proba(bundle['scaler'].transform(F.loc[pngs].values))
    classes = np.array([bundle['class_names'][int(c)] for c in bundle['model'].classes_])
    pred = classes[proba.argmax(1)]
    conf = proba.max(1)
    f1 = np.array([metrics['per_class'][n]['f1'] for n in pred])
    return pred, conf, (conf >= MIN_PROB) & (f1 >= MIN_F1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--metrics', required=True)
    ap.add_argument('--variants', default='1000,400')
    args = ap.parse_args()
    warnings.filterwarnings('ignore')
    work = os.path.expanduser(args.work)
    bundle = joblib.load(args.model); metrics = json.load(open(args.metrics))
    m0 = pd.read_csv(os.path.join(work, 'manifest.csv'), keep_default_na=False)
    m0 = m0[(m0.source == 'own614') & (m0.status == 'ok')].set_index('relpath')
    F0 = pd.read_csv(os.path.join(work, 'features.csv')).set_index('png')
    split = json.load(open(os.path.join(work, 'own614_split.json')))
    test_rel = m0.reset_index().set_index('png').loc[split['test']].relpath.tolist()
    truth = m0.loc[test_rel].cls.values
    base_pred, base_conf, base_c = run(bundle, metrics, F0, m0.loc[test_rel].png.tolist())
    rows = [{'variant': 'full size (as trained)', 'longest_side_px': 'median 6720', 'n': len(test_rel), 'accuracy': float((base_pred == truth).mean()),
             'right': int((base_pred == truth).sum()), 'confident': int(base_c.sum()), 'confident_right': int(((base_pred == truth) & base_c).sum()), 'answer_changed': 0}]
    for v in [int(x) for x in args.variants.split(',')]:
        d = os.path.join(work, f'shrink_{v}')
        mv = pd.read_csv(os.path.join(d, 'manifest.csv'), keep_default_na=False)
        mv = mv[(mv.source == 'own614') & (mv.status == 'ok')].set_index('relpath')
        Fv = pd.read_csv(os.path.join(d, 'features.csv')).set_index('png')
        pred, conf, c = run(bundle, metrics, Fv, mv.loc[test_rel].png.tolist())
        rows.append({'variant': f'shrunk to {v}px longest side', 'longest_side_px': v, 'n': len(test_rel), 'accuracy': float((pred == truth).mean()),
                     'right': int((pred == truth).sum()), 'confident': int(c.sum()), 'confident_right': int(((pred == truth) & c).sum()),
                     'answer_changed': int((pred != base_pred).sum())})
    for r in rows:
        print(f"{r['variant']:28s} accuracy {pct(r['right'], r['n']):18s} answers {r['confident']:2d}/{r['n']}, right {r['confident_right']:2d}; answer changed vs full size: {r['answer_changed']}")
    json.dump(rows, open(os.path.join(work, 'resolution_results.json'), 'w'), indent=2)


if __name__ == '__main__':
    main()
