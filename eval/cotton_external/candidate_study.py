"""
Step 7: would training on several datasets help? (A study. It does NOT touch the live model.)

Candidate: the same recipe as the live model (31 features, standard scaling, one-vs-rest RBF SVM,
C=10, gamma='auto') but trained on photos from several datasets and with more disease classes.

Fair comparison with the live model:
  * the project's own photos keep the saved model's split (368 / 80 / 81), so both models are scored on the
    same 81 test photos;
  * every other dataset is split 60 / 20 / 20 with near-identical photos kept together;
  * training uses at most --cap photos per (dataset, class) so one big class (Severity 'healthy') does not
    dominate;
  * SAR-CLD (augmented copies only) is never used for training; it is a held-out dataset;
  * photos of conditions left out of training (SAR herbicide, reddening, variegation, jassid; boll photos; the
    project's Boll/Root rot) are the "never seen" test;
  * the confidence cutoff is chosen on the validation photos only.
Also a leave-one-dataset-out table: train on the other datasets, test on the one left out.

Run: python eval/cotton_external/candidate_study.py --work <folder> --model <joblib> --metrics <json> [--save-dir DIR]
With --save-dir the candidate is written as candidate_svm.joblib + candidate_metrics.json (same layout as the live model);
nothing in backend/ is changed.
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

CAND_CLASSES = ['Anthracnose', 'Bacterial leaf blight', 'Cotton leaf curl virus disease', 'Healthy Plants',
                'Myrothecium leaf spot', 'Sooty mould disease', 'Alternaria leaf spot', 'Fusarium wilt',
                'Verticillium wilt', 'Target spot', 'Powdery mildew', 'Aphids', 'Army worm']
POOL_SOURCES = ['own614', 'eastwest', 'severity', 'ayaz']
SHARED3 = ['Bacterial leaf blight', 'Cotton leaf curl virus disease', 'Healthy Plants']
MIN_F1 = 0.30


def label_of(row):
    kind, name = class_map(row.cls)
    return name if name in CAND_CLASSES else None


def fit(Xtr, ytr, C=10):
    from sklearn.multiclass import OneVsRestClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC
    sc = StandardScaler().fit(Xtr)
    mdl = OneVsRestClassifier(SVC(kernel='rbf', C=C, gamma='auto', probability=True, random_state=42)).fit(sc.transform(Xtr), ytr)
    return sc, mdl


def predict(sc, mdl, X, class_names):
    p = mdl.predict_proba(sc.transform(X))
    cls = np.array([class_names[int(c)] for c in mdl.classes_])
    return cls[p.argmax(1)], p.max(1)


def class_f1(truth, pred, names):
    from sklearn.metrics import f1_score
    f = f1_score(truth, pred, labels=names, average=None, zero_division=0)
    return dict(zip(names, f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--metrics', required=True)
    ap.add_argument('--cap', type=int, default=150)
    ap.add_argument('--save-dir', default='')
    args = ap.parse_args()
    warnings.filterwarnings('ignore')
    from sklearn.model_selection import StratifiedGroupKFold
    work = os.path.expanduser(args.work)
    m, F = load_all(work)
    near = pd.read_csv(os.path.join(work, 'near_pairs.csv'))
    m = clean_independent(m, near, 4)
    live = joblib.load(args.model); live_metrics = json.load(open(args.metrics))
    split = json.load(open(os.path.join(work, 'own614_split.json')))

    m['label'] = [label_of(r) for r in m.itertuples()]
    m['role'] = ''
    # own photos: the saved model's split
    for role, key in (('train', 'train'), ('val', 'val'), ('test', 'test')):
        m.loc[m.png.isin(split[key]) & (m.source == 'own614'), 'role'] = role
    # outside photos: 60/20/20 by near-identical group
    rng = np.random.RandomState(0)
    outside = m[(m.source.isin(['eastwest', 'severity', 'ayaz_train', 'ayaz_valtest'])) & (m['drop'] == '') & m.label.notna()].copy()
    outside['dataset'] = outside.source.replace({'ayaz_train': 'ayaz', 'ayaz_valtest': 'ayaz'})
    outside['strat'] = outside.dataset + '|' + outside.label
    sgkf = StratifiedGroupKFold(5, shuffle=True, random_state=0)
    fold = np.zeros(len(outside), int)
    for i, (_, te) in enumerate(sgkf.split(outside, outside.strat, outside.group)):
        fold[te] = i
    outside['role'] = np.select([fold <= 2, fold == 3], ['train', 'val'], 'test')
    m.loc[outside.index, 'role'] = outside.role
    m['dataset'] = m.source.replace({'ayaz_train': 'ayaz', 'ayaz_valtest': 'ayaz'})
    own = m[(m.source == 'own614') & m.role.isin(['train', 'val', 'test']) & m.label.isin(APP_CLASSES)]
    pool = pd.concat([own, m.loc[outside.index]])
    # cap per (dataset, class) in train only
    tr_parts = []
    for (_, _), g in pool[pool.role == 'train'].groupby(['dataset', 'label']):
        tr_parts.append(g if len(g) <= args.cap else g.sample(args.cap, random_state=0))
    train = pd.concat(tr_parts)
    val = pool[pool.role == 'val']; test = pool[pool.role == 'test']
    print(f'candidate training photos {len(train)}  validation {len(val)}  test {len(test)}')
    print(train.groupby(['label', 'dataset']).size().unstack(fill_value=0).to_string())

    class_names = CAND_CLASSES
    ytr = np.array([class_names.index(l) for l in train.label])
    sc, mdl = fit(F.loc[train.png].values, ytr)
    cp, cc = predict(sc, mdl, F.loc[val.png].values, class_names)
    f1_val = class_f1(val.label.values, cp, class_names)
    thr = lowest_cutoff(cc, cp == val.label.values, 0.90, 10)
    print('validation per-class F1:', {k: round(v, 2) for k, v in f1_val.items()})
    print('cutoff chosen on validation (first p with >=90% right when answering, >=10 answers):', thr)
    use_thr = thr if thr is not None else 0.70

    def conf_rule(pred, prob, T, f1map):
        return (prob >= T) & np.array([f1map.get(p, 0) >= MIN_F1 for p in pred])

    def evaluate(df, label, classes_for_score=None):
        res = {}
        X = F.loc[df.png].values
        lp, lc = predict_live(live, X)
        lf1 = {k: v['f1'] for k, v in live_metrics['per_class'].items()}
        np_, nc = predict(sc, mdl, X, class_names)
        res['n'] = len(df)
        truth = df.label.values
        res['live'] = dict(top1=int((lp == truth).sum()), conf=int(conf_rule(lp, lc, 0.70, lf1).sum()), conf_right=int(((lp == truth) & conf_rule(lp, lc, 0.70, lf1)).sum()))
        for tag, T in (('cand_0.70', 0.70), (f'cand_val_{use_thr}', use_thr)):
            c = conf_rule(np_, nc, T, f1_val)
            res[tag] = dict(top1=int((np_ == truth).sum()), conf=int(c.sum()), conf_right=int(((np_ == truth) & c).sum()))
        print(f'{label:34s} n={len(df):4d} | live: top1 {pct(res["live"]["top1"], len(df)):17s} answers {res["live"]["conf"]:3d} right {res["live"]["conf_right"]:3d} || '
              f'cand@0.70: top1 {pct(res["cand_0.70"]["top1"], len(df)):17s} answers {res["cand_0.70"]["conf"]:3d} right {res["cand_0.70"]["conf_right"]:3d} || '
              f'cand@{use_thr}: answers {res[f"cand_val_{use_thr}"]["conf"]:3d} right {res[f"cand_val_{use_thr}"]["conf_right"]:3d}')
        return res

    out = {'threshold_from_validation': thr, 'val_f1': f1_val, 'train_counts': train.groupby('label').size().to_dict(), 'rows': {}}
    print('\n== held-out test photos (same 81 own test photos; outside datasets 20%), shared classes only ==')
    for d in ('own614', 'eastwest', 'severity', 'ayaz'):
        for c in SHARED3:
            g = test[(test.dataset == d) & (test.label == c)]
            if len(g) >= 5:
                out['rows'][f'test|{d}|{c}'] = evaluate(g, f'{d} / {c}')
    print('\n== held-out test photos, all candidate classes (live model cannot name the extra ones) ==')
    for d in ('own614', 'eastwest', 'severity', 'ayaz'):
        g = test[test.dataset == d]
        out['rows'][f'test_all|{d}'] = evaluate(g, f'{d} / all classes')
    print('\n== SAR-CLD (never used in training; augmented copies) shared classes ==')
    sar = m[(m.source == 'sarcld_aug') & (m['drop'] == '') & m.label.isin(SHARED3)]
    for c in SHARED3:
        g = sar[sar.label == c]
        out['rows'][f'sar|{c}'] = evaluate(g, f'sarcld_aug / {c}')
    print('\n== never-seen conditions: any confident answer is wrong ==')
    ns = pd.concat([m[(m['drop'] == '') & (~m.source.isin(['own296', 'own614'])) & (m.label.isna())], m.loc[own_boll_root(m).index]])
    lf1 = {k: v['f1'] for k, v in live_metrics['per_class'].items()}
    for (d, t), g in ns.assign(truth=[class_map(c)[1] for c in ns.cls], dataset=ns.source).groupby(['dataset', 'truth']):
        if class_map(g.cls.iloc[0])[0] == 'shared':
            continue
        X = F.loc[g.png].values
        lp, lc = predict_live(live, X); np_, nc = predict(sc, mdl, X, class_names)
        l = conf_rule(lp, lc, 0.70, lf1).sum(); c1 = conf_rule(np_, nc, 0.70, f1_val).sum(); c2 = conf_rule(np_, nc, use_thr, f1_val).sum()
        out['rows'][f'never|{d}|{t}'] = dict(n=len(g), live=int(l), cand_070=int(c1), cand_val=int(c2))
        print(f'{d:13s} {t:34s} n={len(g):4d} | confident-wrong live {pct(l, len(g)):17s} candidate@0.70 {pct(c1, len(g)):17s} candidate@{use_thr} {pct(c2, len(g))}')

    print('\n== leave-one-dataset-out (train on the others\' training photos, test on every photo of the dataset left out, shared classes) ==')
    for held in ('eastwest', 'severity', 'ayaz', 'own614'):
        tr = train[train.dataset != held]
        te = pool[(pool.dataset == held) & pool.label.isin(SHARED3)] if held != 'own614' else test[(test.dataset == 'own614') & test.label.isin(SHARED3)]
        names = [c for c in class_names if c in set(tr.label)]
        y = np.array([names.index(l) for l in tr.label])
        s2, m2 = fit(F.loc[tr.png].values, y)
        p2, c2 = predict(s2, m2, F.loc[te.png].values, names)
        truth = te.label.values
        right = int((p2 == truth).sum()); conf = c2 >= 0.70
        out['rows'][f'loo|{held}'] = dict(n=len(te), right=right, conf=int(conf.sum()), conf_right=int(((p2 == truth) & conf).sum()))
        per = {c: pct(int(((p2 == truth) & (truth == c)).sum()), int((truth == c).sum())) for c in SHARED3 if (truth == c).any()}
        print(f'left out {held:9s} n={len(te):4d} top1 {pct(right, len(te)):17s} answers {int(conf.sum()):4d} right {int(((p2 == truth) & conf).sum()):4d}  per class: {per}')

    if args.save_dir:
        os.makedirs(args.save_dir, exist_ok=True)
        joblib.dump({'scaler': sc, 'model': mdl, 'class_names': class_names}, os.path.join(args.save_dir, 'candidate_svm.joblib'))
        json.dump({'class_names': class_names, 'n_train': int(len(train)), 'val_per_class_f1': f1_val, 'threshold_from_validation': thr,
                   'train_counts': out['train_counts'], 'note': 'candidate only; the live model is unchanged'}, open(os.path.join(args.save_dir, 'candidate_metrics.json'), 'w'), indent=2)
    json.dump(out, open(os.path.join(work, 'candidate_results.json'), 'w'), indent=2, default=str)


def predict_live(bundle, X):
    p = bundle['model'].predict_proba(bundle['scaler'].transform(X))
    cls = np.array([bundle['class_names'][int(c)] for c in bundle['model'].classes_])
    return cls[p.argmax(1)], p.max(1)


if __name__ == '__main__':
    main()
