"""
Train the cotton-disease classifier and save it for the backend.

Run once, on the machine that has the dataset:

    python backend/cotton/train_classifier.py --data-dir "/path/to/Cotton Data set Man Mohan"

It reproduces the notebook's protocol: the same stratified 70/15/15 split
(random_state=42, two StratifiedShuffleSplit steps), StandardScaler fitted on
train only, OneVsRest RBF SVM (C=10, gamma='auto', the values the notebook's
grid search chose; pass --grid to search again). The model is trained on the
TRAIN split only, so the numbers in metrics.json are honest test numbers.

Outputs (in backend/cotton/models/):
    cotton_svm.joblib   {'scaler', 'model', 'class_names'}
    metrics.json        test accuracy, macro-F1, per-class P/R/F1, and a table
                        of accuracy vs. confidence threshold (used to pick
                        COTTON_MIN_PROBABILITY and to flag unreliable classes)
"""

import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from features import extract_single_image_features  # noqa: E402

VALID_EXT = ('.jpg', '.jpeg', '.png', '.bmp')
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')


MIN_IMAGES_PER_CLASS = 6   # fewer cannot be split into train/val/test


def _md5(path):
    import hashlib
    h = hashlib.md5()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def discover(data_dir, dedupe_within=False, exclude_ambiguous=False):
    """
    Returns class_names, paths, labels, report.

    dedupe_within      keep one copy of byte-identical files inside a class
                       (copies can land in both train and test and inflate scores)
    exclude_ambiguous  drop every file whose bytes appear under more than one
                       class (its label cannot be right for all of them)
    A class left with fewer than MIN_IMAGES_PER_CLASS images is dropped.
    """
    folders = sorted(d for d in os.listdir(data_dir)
                     if os.path.isdir(os.path.join(data_dir, d)) and not d.startswith('.'))
    files = {}
    for name in folders:
        folder = os.path.join(data_dir, name)
        files[name] = [os.path.join(folder, f) for f in sorted(os.listdir(folder))
                       if f.lower().endswith(VALID_EXT)]

    report = {'dedupe_within': dedupe_within, 'exclude_ambiguous': exclude_ambiguous,
              'counts_before': {k: len(v) for k, v in files.items()},
              'removed_within_class_duplicates': 0, 'removed_ambiguous': 0, 'dropped_classes': []}

    if dedupe_within or exclude_ambiguous:
        hashes = {p: (_md5(p) if os.path.getsize(p) > 0 else None) for v in files.values() for p in v}
        if exclude_ambiguous:
            classes_of = {}
            for name, v in files.items():
                for p in v:
                    if hashes[p]:
                        classes_of.setdefault(hashes[p], set()).add(name)
            for name in files:
                keep = [p for p in files[name] if not (hashes[p] and len(classes_of[hashes[p]]) > 1)]
                report['removed_ambiguous'] += len(files[name]) - len(keep)
                files[name] = keep
        if dedupe_within:
            for name in files:
                seen, keep = set(), []
                for p in files[name]:
                    h = hashes[p]
                    if h and h in seen:
                        continue
                    if h:
                        seen.add(h)
                    keep.append(p)
                report['removed_within_class_duplicates'] += len(files[name]) - len(keep)
                files[name] = keep

    class_names = []
    for name in folders:
        if len(files[name]) < MIN_IMAGES_PER_CLASS:
            report['dropped_classes'].append(name)
        else:
            class_names.append(name)
    paths, labels = [], []
    for idx, name in enumerate(class_names):
        paths.extend(files[name])
        labels.extend([idx] * len(files[name]))
    report['counts_after'] = {n: len(files[n]) for n in class_names}
    return class_names, np.array(paths), np.array(labels), report


def split(paths, labels, seed=42):
    from sklearn.model_selection import StratifiedShuffleSplit
    s1 = StratifiedShuffleSplit(n_splits=1, test_size=0.30, random_state=seed)
    tr, tmp = next(s1.split(paths, labels))
    s2 = StratifiedShuffleSplit(n_splits=1, test_size=0.50, random_state=seed)
    va, te = next(s2.split(paths[tmp], labels[tmp]))
    return tr, tmp[va], tmp[te]


def featurize(paths, labels, name):
    X, y, skipped = [], [], 0
    for i, (p, l) in enumerate(zip(paths, labels), 1):
        try:
            X.append(extract_single_image_features(p))
            y.append(l)
        except Exception as e:  # unreadable file
            skipped += 1
            print(f'  [skipped] {p}: {e}')
        if i % 50 == 0:
            print(f'  {name}: {i}/{len(paths)}')
    print(f'{name}: {len(X)} usable, {skipped} skipped')
    return np.array(X), np.array(y)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', required=True)
    ap.add_argument('--grid', action='store_true', help='re-run the GridSearch instead of C=10, gamma=auto')
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--dedupe-within-class', action='store_true',
                    help='keep one copy of byte-identical images inside a class')
    ap.add_argument('--exclude-ambiguous', action='store_true',
                    help='drop images whose bytes appear under more than one class')
    ap.add_argument('--out-dir', default=OUT_DIR, help='where to save the model (default: backend/cotton/models)')
    args = ap.parse_args()

    from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
    from sklearn.model_selection import GridSearchCV
    from sklearn.multiclass import OneVsRestClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC
    import joblib
    import sklearn

    class_names, paths, labels, report = discover(args.data_dir, args.dedupe_within_class,
                                                   args.exclude_ambiguous)
    if args.dedupe_within_class or args.exclude_ambiguous:
        print(f"data filters: removed {report['removed_ambiguous']} ambiguous, "
              f"{report['removed_within_class_duplicates']} duplicate images; "
              f"dropped classes: {report['dropped_classes'] or 'none'}")
    print(f'{len(paths)} images, {len(class_names)} classes: {class_names}')
    tr, va, te = split(paths, labels, args.seed)
    print(f'split train/val/test = {len(tr)}/{len(va)}/{len(te)}')

    t0 = time.time()
    Xtr, ytr = featurize(paths[tr], labels[tr], 'train')
    Xte, yte = featurize(paths[te], labels[te], 'test')

    scaler = StandardScaler().fit(Xtr)
    Xtr_s, Xte_s = scaler.transform(Xtr), scaler.transform(Xte)

    base = OneVsRestClassifier(SVC(kernel='rbf', probability=True, random_state=42))
    if args.grid:
        grid = GridSearchCV(base, {'estimator__C': [0.5, 1, 10, 50],
                                   'estimator__gamma': ['scale', 'auto', 0.01, 0.1]},
                            cv=3, scoring='f1_macro', n_jobs=-1, verbose=1)
        grid.fit(Xtr_s, ytr)
        model, params = grid.best_estimator_, grid.best_params_
    else:
        model = OneVsRestClassifier(SVC(kernel='rbf', C=10, gamma='auto',
                                        probability=True, random_state=42)).fit(Xtr_s, ytr)
        params = {'estimator__C': 10, 'estimator__gamma': 'auto'}

    proba = model.predict_proba(Xte_s)
    pred = model.classes_[proba.argmax(axis=1)]
    conf = proba.max(axis=1)
    acc = float(accuracy_score(yte, pred))
    # The notebook scored model.predict() (decision values); the app uses the
    # probabilities above. Report both so the two can be compared.
    pred_direct = model.predict(Xte_s)
    acc_predict = float(accuracy_score(yte, pred_direct))
    f1_predict = float(f1_score(yte, pred_direct, average='macro', zero_division=0))
    macro_f1 = float(f1_score(yte, pred, average='macro', zero_division=0))
    p, r, f, s = precision_recall_fscore_support(yte, pred, labels=list(range(len(class_names))), zero_division=0)

    per_class = {class_names[i]: {'precision': float(p[i]), 'recall': float(r[i]),
                                  'f1': float(f[i]), 'support': int(s[i])}
                 for i in range(len(class_names))}

    table = []
    for th in (0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8):
        keep = conf >= th
        table.append({'threshold': th,
                      'answered_fraction': float(keep.mean()),
                      'accuracy_when_answered': float((pred[keep] == yte[keep]).mean()) if keep.any() else None})

    metrics = {
        'class_names': class_names, 'n_train': int(len(ytr)), 'n_test': int(len(yte)),
        'accuracy': acc, 'macro_f1': macro_f1,
        'accuracy_model_predict': acc_predict, 'macro_f1_model_predict': f1_predict, 'per_class': per_class,
        'threshold_table': table, 'svm_params': {k: str(v) for k, v in params.items()},
        'sklearn_version': sklearn.__version__, 'seed': args.seed,
        'data_filters': report,
        'majority_baseline': float(np.mean(yte == np.bincount(ytr).argmax())),
    }

    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)
    joblib.dump({'scaler': scaler, 'model': model, 'class_names': class_names},
                os.path.join(out_dir, 'cotton_svm.joblib'))
    with open(os.path.join(out_dir, 'metrics.json'), 'w') as fh:
        json.dump(metrics, fh, indent=2)

    print(f'\nTEST accuracy {acc*100:.2f}%  macro-F1 {macro_f1:.3f}  (majority baseline {metrics["majority_baseline"]*100:.1f}%)')
    print(f'same model scored with model.predict() as in the notebook: accuracy {acc_predict*100:.2f}%  macro-F1 {f1_predict:.3f}')
    for n, m in per_class.items():
        print(f'  {n:<28} F1 {m["f1"]:.2f}  n={m["support"]}')
    print('\nthreshold  answered  accuracy-when-answered')
    for row in table:
        a = row['accuracy_when_answered']
        print(f'  {row["threshold"]:.1f}      {row["answered_fraction"]*100:5.1f}%   {"-" if a is None else f"{a*100:.1f}%"}')
    print(f'\nSaved to {out_dir}  ({time.time()-t0:.0f}s)')


if __name__ == '__main__':
    main()
