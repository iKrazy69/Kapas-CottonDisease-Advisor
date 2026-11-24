"""
Step 4: run the saved classifier (unchanged) on the outside photos and report what it does.

Shared classes (bacterial blight, curl virus, healthy): accuracy, how often the app would answer
(confident rule), and how often a confident answer is right.
Never-seen conditions: how often the app says "uncertain" and how often it confidently names a wrong
disease (or calls the leaf healthy).

Run: python eval/cotton_external/external_test.py --work <folder> --model <cotton_svm.joblib> --metrics <metrics.json>
Writes external_predictions.csv and external_results.json into --work.
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
from common import APP_CLASSES, class_map, clean_independent, load_all, own_boll_root, pct, wilson  # noqa: E402

MIN_PROB = 0.70      # Config.COTTON_MIN_PROBABILITY
MIN_F1 = 0.30        # Config.COTTON_MIN_CLASS_F1


def predict_all(bundle, metrics, X):
    proba = bundle['model'].predict_proba(bundle['scaler'].transform(X))
    classes = [bundle['class_names'][int(c)] for c in bundle['model'].classes_]
    top = proba.argmax(1)
    names = np.array(classes)[top]
    conf = proba.max(1)
    f1 = np.array([metrics['per_class'][n]['f1'] for n in names])
    return names, conf, f1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--metrics', required=True)
    args = ap.parse_args()
    warnings.filterwarnings('ignore')
    work = os.path.expanduser(args.work)
    m, F = load_all(work)
    near = pd.read_csv(os.path.join(work, 'near_pairs.csv'))
    m = clean_independent(m, near)
    bundle = joblib.load(args.model)
    metrics = json.load(open(args.metrics))
    names, conf, f1 = predict_all(bundle, metrics, F.loc[m.png].values)
    m['pred'] = names
    m['prob'] = conf
    m['top_f1'] = f1
    m['confident'] = (conf >= MIN_PROB) & (f1 >= MIN_F1)
    kinds = [class_map(c) for c in m.cls]
    m['kind'] = [k for k, _ in kinds]
    m['truth'] = [t for _, t in kinds]
    m['correct'] = m.pred == m.truth
    m.drop(columns=['bytes_ok']).to_csv(os.path.join(work, 'external_predictions.csv'), index=False)

    out = {'rule': {'min_prob': MIN_PROB, 'min_class_f1': MIN_F1}, 'cleaning': {}, 'shared': [], 'never_seen': []}
    for s, g in m.groupby('source'):
        out['cleaning'][s] = {'photos': int(len(g)), **{k: int((g['drop'] == k).sum()) for k in ('ambiguous', 'exact_dup', 'near_dup')},
                              'independent': int((g['drop'] == '').sum())}
    outside = m[(m['drop'] == '') & (~m.source.isin(['own296', 'own614']))]
    keep = pd.concat([outside, m.loc[own_boll_root(m).index]])    # the project's own Boll/Root rot photos count as never-seen

    for (s, t), g in keep[keep.kind == 'shared'].groupby(['source', 'truth']):
        n = len(g); c = g[g.confident]
        out['shared'].append({'source': s, 'truth': t, 'n': n, 'top1_right': int(g.correct.sum()),
                              'confident': int(len(c)), 'confident_right': int(c.correct.sum()),
                              'pred_counts': g.pred.value_counts().to_dict()})
    for (s, t), g in keep[keep.kind == 'never_seen'].groupby(['source', 'truth']):
        n = len(g); c = g[g.confident]
        out['never_seen'].append({'source': s, 'truth': t, 'n': n, 'confident': int(len(c)),
                                  'confident_calls_healthy': int((c.pred == 'Healthy Plants').sum()),
                                  'confident_pred_counts': c.pred.value_counts().to_dict()})
    json.dump(out, open(os.path.join(work, 'external_results.json'), 'w'), indent=2)

    print('CLEANING per source:'); print(pd.DataFrame(out['cleaning']).T.to_string())
    print('\nSHARED CLASSES (independent photos only)')
    tbl = pd.DataFrame(out['shared'])
    for _, r in tbl.iterrows():
        print(f"{r.source:13s} {r.truth:32s} n={r.n:4d} top1 {pct(r.top1_right, r.n):18s} confident {pct(r.confident, r.n):18s} right-when-confident {pct(r.confident_right, r.confident)}")
    print('\nNEVER-SEEN')
    for r in out['never_seen']:
        print(f"{r['source']:13s} {r['truth']:34s} n={r['n']:4d} confident(wrong) {pct(r['confident'], r['n']):18s} of which 'Healthy': {r['confident_calls_healthy']}")


if __name__ == '__main__':
    main()
