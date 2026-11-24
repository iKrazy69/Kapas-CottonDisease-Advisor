"""
Step 5: how much of the 80.25% comes from near-identical photos of the same leaf, and can the 31
features tell which dataset a photo came from?

(a) The saved model's own 81 test photos: how many have a near-identical twin among the training photos,
    and how accurate is the model on those versus the rest?
(b) Cross-validation on the project's own photos: random folds versus folds that keep near-identical
    photos together (this is the fair one).
(c) Source detectability: predict the dataset name from the 31 features alone.

Run: python eval/cotton_external/internal_check.py --work <folder> --model <joblib> --metrics <json>   (after reproduce_split.py)
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
from common import APP_CLASSES, clean_independent, load_all, pct  # noqa: E402


def own_frame(m, near, near_dist):
    m = clean_independent(m, near, near_dist)
    o = m[m.source == 'own614'].copy()
    o = o[~o['drop'].isin(['ambiguous', 'exact_dup'])]
    o = o[o.cls.isin(APP_CLASSES)]
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--metrics', required=True)
    ap.add_argument('--near-dist', type=int, default=4)
    args = ap.parse_args()
    warnings.filterwarnings('ignore')
    from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold
    from sklearn.multiclass import OneVsRestClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC
    from sklearn.metrics import f1_score
    work = os.path.expanduser(args.work)
    m, F = load_all(work)
    near = pd.read_csv(os.path.join(work, 'near_pairs.csv'))
    out = {}

    # ---- (a) test photos with a twin in training
    split = json.load(open(os.path.join(work, 'own614_split.json')))   # written by reproduce_split.py
    tr, te = set(split['train']), set(split['test'])
    bundle = joblib.load(args.model)
    metrics = json.load(open(args.metrics))
    te_list = [p for p in split['test']]
    proba = bundle['model'].predict_proba(bundle['scaler'].transform(F.loc[te_list].values))
    classes = [bundle['class_names'][int(c)] for c in bundle['model'].classes_]
    pred = np.array(classes)[proba.argmax(1)]
    truth_map = dict(zip(m.png, m.cls))
    truth = np.array([truth_map[p] for p in te_list])
    dmin = {p: 999 for p in te_list}
    for a, b, d in zip(near.png_a, near.png_b, near.dist):
        if a in te and b in tr:
            dmin[a] = min(dmin[a], d)
        elif b in te and a in tr:
            dmin[b] = min(dmin[b], d)
    dm = np.array([dmin[p] for p in te_list])
    out['test_twin'] = {}
    for label, sel in (('twin in training (<=4 bits)', dm <= 4), ('no twin (>4 bits)', dm > 4)):
        k = int((pred[sel] == truth[sel]).sum()); n = int(sel.sum())
        out['test_twin'][label] = {'n': n, 'right': k}
        print(f'(a) {label:30s} n={n:3d} accuracy {pct(k, n)}')

    # ---- (b) cross-validation on own photos
    o = own_frame(m, near, args.near_dist)
    X = F.loc[o.png].values
    y = np.array([APP_CLASSES.index(c) for c in o.cls])
    groups = o.group.values
    print(f'\n(b) {len(o)} own photos after removing ambiguous and exact copies; {len(set(groups))} near-identical groups (<= {args.near_dist} bits)')

    def cv(splitter, label, seeds=(0, 1, 2)):
        accs, f1s, conf_fracs, conf_accs = [], [], [], []
        for seed in seeds:
            s = splitter(seed)
            P = np.zeros((len(y), len(APP_CLASSES)))
            for trn, tst in s.split(X, y, groups):
                sc = StandardScaler().fit(X[trn])
                mdl = OneVsRestClassifier(SVC(kernel='rbf', C=10, gamma='auto', probability=True, random_state=42)).fit(sc.transform(X[trn]), y[trn])
                pr = mdl.predict_proba(sc.transform(X[tst]))
                P[np.ix_(tst, [int(c) for c in mdl.classes_])] = pr
            pr_y = P.argmax(1); conf = P.max(1)
            accs.append((pr_y == y).mean()); f1s.append(f1_score(y, pr_y, average='macro', zero_division=0))
            c = conf >= 0.70
            conf_fracs.append(c.mean()); conf_accs.append((pr_y[c] == y[c]).mean() if c.any() else float('nan'))
        r = {'accuracy': float(np.mean(accs)), 'macro_f1': float(np.mean(f1s)), 'confident_fraction': float(np.mean(conf_fracs)),
             'accuracy_when_confident': float(np.nanmean(conf_accs)), 'accuracy_range': [float(min(accs)), float(max(accs))]}
        print(f'    {label:34s} accuracy {r["accuracy"]*100:.1f}% (range {min(accs)*100:.1f}-{max(accs)*100:.1f})  macro-F1 {r["macro_f1"]:.2f}  '
              f'answers {r["confident_fraction"]*100:.0f}% at p>=0.70, right {r["accuracy_when_confident"]*100:.1f}%')
        return r
    out['cv_random'] = cv(lambda s: StratifiedKFold(5, shuffle=True, random_state=s), 'random 5-fold (twins can split)')
    out['cv_grouped'] = cv(lambda s: StratifiedGroupKFold(5, shuffle=True, random_state=s), 'grouped 5-fold (twins together)')
    # twins defined more loosely
    o2 = own_frame(m, near, 10)
    groups = o2.group.values; X = F.loc[o2.png].values; y = np.array([APP_CLASSES.index(c) for c in o2.cls])
    out['cv_grouped_10bits'] = cv(lambda s: StratifiedGroupKFold(5, shuffle=True, random_state=s), 'grouped 5-fold, looser twins (<=10)')

    # ---- (c) which dataset does a photo come from?
    ind = clean_independent(m, near, args.near_dist)
    ind = ind[(ind['drop'] == '') & (ind.source != 'own296')].copy()
    ind['dataset'] = ind.source.replace({'ayaz_train': 'ayaz', 'ayaz_valtest': 'ayaz'})
    ind = pd.concat([g.sample(min(len(g), 400), random_state=0) for _, g in ind.groupby('dataset')])
    Xs = F.loc[ind.png].values; ys = ind.dataset.values; gs = ind.group.values
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import cross_val_predict
    pr = cross_val_predict(RandomForestClassifier(300, random_state=0, n_jobs=2), Xs, ys, cv=StratifiedGroupKFold(5, shuffle=True, random_state=0), groups=gs)
    out['source_detect'] = {'accuracy': float((pr == ys).mean()), 'chance_majority': float(pd.Series(ys).value_counts(normalize=True).max()),
                            'per_dataset_recall': {d: float((pr[ys == d] == d).mean()) for d in sorted(set(ys))}, 'n': int(len(ys))}
    print(f'\n(c) dataset recognised from the 31 features alone: {out["source_detect"]["accuracy"]*100:.1f}% (n={len(ys)}, majority-guess {out["source_detect"]["chance_majority"]*100:.0f}%)')
    print('    recall per dataset:', {k: round(v, 2) for k, v in out['source_detect']['per_dataset_recall'].items()})
    json.dump(out, open(os.path.join(work, 'internal_results.json'), 'w'), indent=2)


if __name__ == '__main__':
    main()
