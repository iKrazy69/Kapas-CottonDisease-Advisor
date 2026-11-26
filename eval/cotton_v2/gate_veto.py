"""
Image gate (ConvNeXt + CLIP, leave one source out) combined with CLIP's zero-shot
cotton share as a veto: accept only if the gate accepts AND share >= z.

    python eval/cotton_v2/gate_veto.py
Writes eval/results/cotton_v2/gate_veto.md and gate_veto.json
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import train_v2 as T  # noqa: E402
import zeroshot_check as Z  # noqa: E402


def main():
    Tm, scale = Z.text_features()
    rows, X, Xg = T.load(['convnext', 'clip'])
    _, Xc, _ = T.load(['clip'])
    rows, XX, Xg, _, _ = T.collapse_exact(rows, np.hstack([X, Xc]), Xg)
    X, Xc = XX[:, :-512], XX[:, -512:]
    zs = Z.cotton_share(Xc, Tm, scale)
    groups = T.near_groups(Xg, np.ones(len(rows), bool))
    loso = T.gate_loso(rows, X, groups)
    src = np.array([T.family(r['source']) for r in rows])
    for s, v in loso.items():
        v['zs'] = zs[src == s]
    cot = [s for s, v in loso.items() if v['role'] == 'cotton']
    neg = [s for s, v in loso.items() if v['role'] == 'negative']
    table = []
    for t in np.arange(0.05, 0.96, 0.05):
        for q in [0.0, 1.0, 2.0, 5.0]:
            k = float(np.percentile(np.concatenate([loso[s]['knn'] for s in cot]), q)) if q else -1.0
            for z in [0.0, 0.002, 0.005, 0.01, 0.02, 0.03, 0.05]:
                acc = {s: float(np.mean((np.array(loso[s]['p']) >= t) & (np.array(loso[s]['knn']) >= k)
                                        & (loso[s]['zs'] >= z))) for s in loso}
                table.append({'p_min': round(float(t), 2), 'knn_pct': q, 'knn_min': k, 'z_min': z,
                              'cot': float(np.mean([acc[s] for s in cot])),
                              'cot_worst': float(min(acc[s] for s in cot)),
                              'rej': float(np.mean([1 - acc[s] for s in neg])), 'acc': acc})
    L = ['# Image gate + zero-shot veto (leave one source out)', '',
         'Best rule (mean not-cotton rejected) for each floor on mean cotton accepted.', '',
         '| Cotton accepted at least | p_min | knn pct | z_min | cotton accepted (mean / worst source) | not-cotton rejected (mean) | '
         + ' | '.join(neg) + ' |', '|---|---|---|---|---|---|' + '---|' * len(neg)]
    best = {}
    for floor in [0.97, 0.95, 0.93, 0.90, 0.85]:
        ok = [r for r in table if r['cot'] >= floor]
        if not ok:
            continue
        b = max(ok, key=lambda r: r['rej'])
        best[floor] = b
        L.append(f"| {100 * floor:.0f}% | {b['p_min']} | {b['knn_pct']} | {b['z_min']} | {100 * b['cot']:.1f}% / "
                 f"{100 * b['cot_worst']:.1f}% | {100 * b['rej']:.1f}% | "
                 + ' | '.join(f"{100 * (1 - b['acc'][s]):.0f}%" for s in neg) + ' |')
    L += ['', 'Per-source columns show the share of that not-cotton source REJECTED (higher is better).']
    os.makedirs(T.OUT_DIR, exist_ok=True)
    open(os.path.join(T.OUT_DIR, 'gate_veto.md'), 'w').write('\n'.join(L) + '\n')
    json.dump({str(k): v for k, v in best.items()}, open(os.path.join(T.OUT_DIR, 'gate_veto.json'), 'w'), indent=1)
    print('\n'.join(L))


if __name__ == '__main__':
    main()
