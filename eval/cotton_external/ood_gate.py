"""
Step 8: a "this photo looks unlike the photos I learned from" check, added to the confidence rule.

For a photo, take its 31 features, scale them with the live model's scaler, and measure the mean distance to its
K nearest training photos (the saved model's 368 training photos). A photo farther away than a cutoff is called
"unfamiliar" and the app would stay silent. The cutoff is chosen on the 80 VALIDATION photos only
(--pass-rate of them must pass), then checked on the test photos and on every outside photo.

Run: python eval/cotton_external/ood_gate.py --work <folder> --model <joblib> --metrics <json> [--k 3 --pass-rate 0.95]
Writes ood_results.json (and ood_reference.npz when --save-reference is given).
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
from common import APP_CLASSES, class_map, clean_independent, knn_dist, load_all, own_boll_root, pct  # noqa: E402

MIN_PROB, MIN_F1 = 0.70, 0.30


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--metrics', required=True)
    ap.add_argument('--k', type=int, default=3)
    ap.add_argument('--pass-rate', type=float, default=0.95)
    ap.add_argument('--save-reference', default='')
    args = ap.parse_args()
    warnings.filterwarnings('ignore')
    from sklearn.metrics import roc_auc_score
    work = os.path.expanduser(args.work)
    m, F = load_all(work)
    near = pd.read_csv(os.path.join(work, 'near_pairs.csv'))
    m = clean_independent(m, near, 4)
    live = joblib.load(args.model); metrics = json.load(open(args.metrics))
    split = json.load(open(os.path.join(work, 'own614_split.json')))
    sc = live['scaler']
    ref = sc.transform(F.loc[split['train']].values)
    Zval = sc.transform(F.loc[split['val']].values)
    Ztest = sc.transform(F.loc[split['test']].values)
    dval, dtest = knn_dist(Zval, ref, args.k), knn_dist(Ztest, ref, args.k)
    tau = float(np.quantile(dval, args.pass_rate))
    print(f'K={args.k}; cutoff {tau:.3f} = the distance {args.pass_rate*100:.0f}% of the 80 validation photos stay within')
    print(f'own test photos that pass: {pct(int((dtest <= tau).sum()), len(dtest))}')

    keep = m[(m['drop'] == '') & (~m.source.isin(['own296', 'own614']))]
    keep = pd.concat([keep, m.loc[own_boll_root(m).index]]).copy()     # own photos in the split are covered above; own Boll/Root rot are never-seen
    kinds = [class_map(c) for c in keep.cls]
    keep['kind'] = [k for k, _ in kinds]; keep['truth'] = [t for _, t in kinds]
    Z = sc.transform(F.loc[keep.png].values)
    keep['dist'] = knn_dist(Z, ref, args.k)
    keep['pass'] = keep.dist <= tau
    proba = live['model'].predict_proba(Z)
    cls = np.array([live['class_names'][int(c)] for c in live['model'].classes_])
    keep['pred'] = cls[proba.argmax(1)]; keep['prob'] = proba.max(1)
    f1 = np.array([metrics['per_class'][n]['f1'] for n in keep.pred])
    keep['confident'] = (keep.prob >= MIN_PROB) & (f1 >= MIN_F1)
    keep['answer'] = keep.confident & keep['pass']
    keep['right'] = keep.pred == keep.truth

    # can the distance alone separate "own test photo" from "outside photo"?
    y = np.r_[np.zeros(len(dtest)), np.ones(len(keep))]
    auc = roc_auc_score(y, np.r_[dtest, keep.dist.values])
    print(f'distance separates own test photos from outside photos: AUROC {auc:.3f}')

    out = {'k': args.k, 'tau': tau, 'pass_rate_val': args.pass_rate, 'auroc_own_vs_outside': float(auc), 'own_test_pass': int((dtest <= tau).sum()), 'own_test_n': int(len(dtest)), 'rows': []}
    # own test photos with the full rule
    Zt = Ztest
    pt = live['model'].predict_proba(Zt)
    pred_t = cls[pt.argmax(1)]; conf_t = pt.max(1)
    f1t = np.array([metrics['per_class'][n]['f1'] for n in pred_t])
    truth_t = np.array([m.set_index('png').loc[p].cls for p in split['test']])
    c_t = (conf_t >= MIN_PROB) & (f1t >= MIN_F1); a_t = c_t & (dtest <= tau)
    print(f'\nown test (81): confident {int(c_t.sum())} right {int(((pred_t == truth_t) & c_t).sum())}  ->  confident and familiar {int(a_t.sum())} right {int(((pred_t == truth_t) & a_t).sum())}')
    out['own_test'] = {'confident': int(c_t.sum()), 'confident_right': int(((pred_t == truth_t) & c_t).sum()), 'answer': int(a_t.sum()), 'answer_right': int(((pred_t == truth_t) & a_t).sum())}

    print('\nSHARED classes, outside datasets: how many photos the app would answer, how many of those answers are right')
    for (s, t), g in keep[keep.kind == 'shared'].groupby(['source', 'truth']):
        a, c = g[g.answer], g[g.confident]
        row = dict(source=s, truth=t, n=len(g), familiar=int(g['pass'].sum()), confident=int(len(c)), conf_right=int(c.right.sum()), answer=int(len(a)), answer_right=int(a.right.sum()))
        out['rows'].append(row)
        print(f'{s:13s} {t:31s} n={len(g):4d} familiar {pct(row["familiar"], len(g)):15s} | confident {row["confident"]:4d} right {row["conf_right"]:4d} | + familiar: answers {row["answer"]:4d} right {row["answer_right"]:4d}')
    print('\nNEVER-SEEN: confident wrong answers before and after the familiarity check')
    tot_c = tot_a = tot_n = 0
    for (s, t), g in keep[keep.kind == 'never_seen'].groupby(['source', 'truth']):
        row = dict(source=s, truth=t, n=len(g), familiar=int(g['pass'].sum()), confident_wrong=int(g.confident.sum()), answer_wrong=int(g.answer.sum()))
        out['rows'].append(row)
        tot_c += row['confident_wrong']; tot_a += row['answer_wrong']; tot_n += len(g)
        print(f'{s:13s} {t:34s} n={len(g):4d} familiar {pct(row["familiar"], len(g)):15s} | confident wrong {pct(row["confident_wrong"], len(g)):16s} -> after check {pct(row["answer_wrong"], len(g))}')
    print(f'ALL never-seen photos: confident wrong {pct(tot_c, tot_n)} -> {pct(tot_a, tot_n)}')
    out['never_seen_total'] = {'n': tot_n, 'confident_wrong': tot_c, 'answer_wrong': tot_a}
    for k in (1, 3, 5, 10):
        dv = knn_dist(Zval, ref, k); dt = knn_dist(Ztest, ref, k); do = knn_dist(Z, ref, k)
        t_k = float(np.quantile(dv, args.pass_rate))
        print(f'  K={k:2d}: own test passes {(dt <= t_k).mean()*100:.0f}%, outside photos pass {(do <= t_k).mean()*100:.1f}%')
    json.dump(out, open(os.path.join(work, 'ood_results.json'), 'w'), indent=2)
    if args.save_reference:
        allref = sc.transform(F.loc[split['train']].values)
        np.savez_compressed(args.save_reference, reference=allref.astype(np.float32), k=args.k, tau=tau,
                            note='scaled training features of the live model; cutoff chosen on its validation photos')
        print('saved reference to', args.save_reference)


if __name__ == '__main__':
    main()
