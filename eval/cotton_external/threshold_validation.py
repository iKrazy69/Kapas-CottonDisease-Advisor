"""
Step 9: choose the confidence cutoff on the VALIDATION photos, not the test photos.

The live app uses top probability >= 0.70 and class test-F1 >= 0.30; both numbers were looked at on the 81 test photos.
Here: for the saved model, on its 80 validation photos, find the lowest cutoff whose answers are >= TARGET right (and
>= MIN_ANSWERS answers), compute per-class F1 on validation, then check that cutoff on the 81 test photos and on the
outside photos of the shared classes.

Run: python eval/cotton_external/threshold_validation.py --work <folder> --model <joblib> --metrics <json> [--target 0.90]
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
from common import APP_CLASSES, class_map, clean_independent, load_all, lowest_cutoff, own_boll_root, pct  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--metrics', required=True)
    ap.add_argument('--target', type=float, default=0.90)
    ap.add_argument('--min-answers', type=int, default=20)
    args = ap.parse_args()
    warnings.filterwarnings('ignore')
    from sklearn.metrics import f1_score
    work = os.path.expanduser(args.work)
    m, F = load_all(work)
    near = pd.read_csv(os.path.join(work, 'near_pairs.csv'))
    m = clean_independent(m, near, 4)
    live = joblib.load(args.model); metrics = json.load(open(args.metrics))
    split = json.load(open(os.path.join(work, 'own614_split.json')))
    cls = np.array([live['class_names'][int(c)] for c in live['model'].classes_])
    cls_of = dict(zip(m.png, m.cls))

    def run(pngs):
        p = live['model'].predict_proba(live['scaler'].transform(F.loc[pngs].values))
        return cls[p.argmax(1)], p.max(1)
    pv, cv = run(split['val']); tv = np.array([cls_of[p] for p in split['val']])
    pt, ct = run(split['test']); tt = np.array([cls_of[p] for p in split['test']])
    print('VALIDATION table (threshold, answered, right when answered)')
    for t in (0.5, 0.6, 0.7, 0.8):
        k = cv >= t
        print(f'  {t:.1f}  answered {int(k.sum()):2d}/{len(cv)}  right {pct(int((pv[k] == tv[k]).sum()), int(k.sum()))}')
    thr = lowest_cutoff(cv, pv == tv, args.target, args.min_answers)
    print(f'lowest cutoff with >= {args.target*100:.0f}% right and >= {args.min_answers} answers on validation: {thr}')
    f1v = dict(zip(APP_CLASSES, f1_score(tv, pv, labels=APP_CLASSES, average=None, zero_division=0)))
    f1t = {k: v['f1'] for k, v in metrics['per_class'].items()}
    print('per-class F1 on validation vs on test (the app uses the test column):')
    for c in APP_CLASSES:
        print(f'  {c:32s} val {f1v[c]:.2f}  test {f1t[c]:.2f}  n_val {int((tv == c).sum())}')
    out = {'target': args.target, 'cutoff_from_validation': thr, 'f1_val': f1v, 'f1_test': f1t}
    for label, T in (('0.70 (live app)', 0.70), (f'{thr} (from validation)', thr)):
        if T is None:
            continue
        rule = lambda p, c, f1map: (c >= T) & np.array([f1map[x] >= 0.30 for x in p])
        for fname, fmap in (('test-F1 rule', f1t), ('validation-F1 rule', f1v)):
            a = rule(pt, ct, fmap)
            print(f'TEST photos, cutoff {label:22s} {fname:20s}: answers {int(a.sum()):2d}/81, right {int(((pt == tt) & a).sum()):2d}  ({pct(int(((pt == tt) & a).sum()), int(a.sum()))})')
            out[f'test|{T}|{fname}'] = {'answers': int(a.sum()), 'right': int(((pt == tt) & a).sum())}
    keep = pd.concat([m[(m['drop'] == '') & (~m.source.isin(['own296', 'own614']))], m.loc[own_boll_root(m).index]]).copy()
    kinds = [class_map(c) for c in keep.cls]
    keep['kind'] = [k for k, _ in kinds]; keep['truth'] = [t for _, t in kinds]
    keep = keep[keep.kind.isin(['shared', 'never_seen'])]
    pe, ce = run(keep.png.tolist())
    keep['pred'] = pe; keep['prob'] = ce
    print('\nOUTSIDE photos (all datasets pooled; shared classes and never-seen conditions)')
    for label, T, fmap in (('0.70 + test-F1 (live app)', 0.70, f1t), (f'{thr} + validation-F1', thr, f1v)):
        if T is None:
            continue
        a = (keep.prob >= T) & np.array([fmap[x] >= 0.30 for x in keep.pred])
        right = a & (keep.pred == keep.truth)
        print(f'  {label:28s}: answers {int(a.sum())}/{len(keep)} ({a.mean()*100:.0f}%), wrong answers {int((a & ~right).sum())} ({pct(int((a & ~right).sum()), int(a.sum()))})')
        out[f'outside|{label}'] = {'answers': int(a.sum()), 'wrong': int((a & ~right).sum()), 'n': int(len(keep))}
    json.dump(out, open(os.path.join(work, 'threshold_results.json'), 'w'), indent=2, default=float)


if __name__ == '__main__':
    main()
