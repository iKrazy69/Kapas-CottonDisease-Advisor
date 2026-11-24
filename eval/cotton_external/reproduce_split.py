"""
Step 0 of the checks (run it first): prove that this pipeline gives the saved model's own test numbers.

It rebuilds the saved model's training split from the project's own photos (the same byte-identical-file filters,
the same StratifiedShuffleSplit seed as backend/cotton/train_classifier.py), scores the saved model on the same 81 test
photos and compares with metrics.json. If these do not match, nothing else in this folder should be trusted.
It also writes own614_split.json (the photo lists of the train / validation / test split) for the other scripts.

Run: python eval/cotton_external/reproduce_split.py --work <folder> --model <joblib> --metrics <json>
"""
import argparse
import json
import os
import sys
import warnings

import joblib
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--metrics', required=True)
    args = ap.parse_args()
    warnings.filterwarnings('ignore')
    import pandas as pd
    from sklearn.model_selection import StratifiedShuffleSplit
    work = os.path.expanduser(args.work)
    m = pd.read_csv(os.path.join(work, 'manifest.csv'), keep_default_na=False)
    F = pd.read_csv(os.path.join(work, 'features.csv')).set_index('png')
    own = m[m.source == 'own614']
    rows = {(r.cls, r.name): (r.md5 if int(r.bytes) > 0 else None, r.png) for r in own.itertuples()}
    files = {c: sorted(g.name.tolist()) for c, g in own.groupby('cls')}
    classes_of = {}
    for c, names in files.items():
        for n in names:
            h = rows[(c, n)][0]
            if h:
                classes_of.setdefault(h, set()).add(c)
    removed_amb = removed_dup = 0
    for c in files:                                   # same order as train_classifier.discover()
        keep = [n for n in files[c] if not (rows[(c, n)][0] and len(classes_of[rows[(c, n)][0]]) > 1)]
        removed_amb += len(files[c]) - len(keep); files[c] = keep
    for c in files:
        seen, keep = set(), []
        for n in files[c]:
            h = rows[(c, n)][0]
            if h and h in seen:
                continue
            if h:
                seen.add(h)
            keep.append(n)
        removed_dup += len(files[c]) - len(keep); files[c] = keep
    class_names = [c for c in sorted(files) if len(files[c]) >= 6]
    plist = [(c, n) for c in class_names for n in files[c]]
    labels = np.array([class_names.index(c) for c, _ in plist])
    idx = np.arange(len(plist))
    tr, tmp = next(StratifiedShuffleSplit(n_splits=1, test_size=0.30, random_state=42).split(idx, labels))
    va, te = next(StratifiedShuffleSplit(n_splits=1, test_size=0.50, random_state=42).split(idx[tmp], labels[tmp]))
    va, te = tmp[va], tmp[te]
    print(f'removed {removed_amb} photos whose bytes appear under two classes, {removed_dup} duplicate copies; '
          f'classes kept {class_names}')

    def pngs(ix):
        return [rows[plist[i]][1] for i in ix if rows[plist[i]][1] and rows[plist[i]][1] in F.index]
    split = {'train': pngs(tr), 'val': pngs(va), 'test': pngs(te)}
    json.dump(split, open(os.path.join(work, 'own614_split.json'), 'w'))
    print('usable photos train/val/test:', {k: len(v) for k, v in split.items()}, '(saved metrics.json: n_train 368, n_test 81)')

    bundle = joblib.load(args.model)
    mt = json.load(open(args.metrics))
    cls = np.array([bundle['class_names'][int(c)] for c in bundle['model'].classes_])
    truth = np.array([own.set_index('png').loc[p].cls for p in split['test']])
    proba = bundle['model'].predict_proba(bundle['scaler'].transform(F.loc[split['test']].values))
    pred = cls[proba.argmax(1)]; conf = proba.max(1)
    acc = float((pred == truth).mean())
    print(f'test accuracy here {acc:.4f}   saved {mt["accuracy"]:.4f}')
    ok = abs(acc - mt['accuracy']) < 1e-9
    for row in mt['threshold_table']:
        t = row['threshold']
        if t == 0:
            continue
        k = conf >= t
        a = float((pred[k] == truth[k]).mean()) if k.any() else None
        same = abs(k.mean() - row['answered_fraction']) < 1e-9 and a is not None and abs(a - row['accuracy_when_answered']) < 1e-9
        ok = ok and same
        print(f'  cutoff {t}: answered {k.mean():.4f} (saved {row["answered_fraction"]:.4f})  right {a:.4f} (saved {row["accuracy_when_answered"]:.4f})  {"same" if same else "DIFFERENT"}')
    print('REPRODUCED the saved model exactly' if ok else 'DOES NOT MATCH the saved model: stop and find out why')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
