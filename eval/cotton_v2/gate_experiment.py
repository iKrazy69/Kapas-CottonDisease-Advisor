"""
Which inputs make the best cotton / not-cotton gate on sources it has never seen?

    python eval/cotton_v2/gate_experiment.py

Variants (all leave-one-source-out, same cleaning and rule search as train_v2.py):
  img_clip            CLIP image numbers
  img_both            ConvNeXt + CLIP image numbers
  img_clip+text       CLIP image numbers + similarity to every text prompt in zeroshot_check.py
  img_both+text       ConvNeXt + CLIP image numbers + the prompt similarities
Writes eval/results/cotton_v2/gate_experiment.md
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import train_v2 as T  # noqa: E402
import zeroshot_check as Z  # noqa: E402

TEXT_WEIGHT = 1.0


def prompt_sims(Xclip, Tm):
    S = Xclip @ Tm.T
    S = (S - S.mean(0)) / (S.std(0) + 1e-6)
    return S / np.sqrt(S.shape[1])


def run(name, rows, X, groups):
    loso = T.gate_loso(rows, X, groups)
    rule = T.pick_gate_rule(loso)
    acc = {s: float(T.apply_gate(v, rule).mean()) for s, v in loso.items()}
    return name, rule, acc, {s: v['role'] for s, v in loso.items()}


def main():
    Tm, _ = Z.text_features()
    out = []
    for feats, text in [(['clip'], False), (['convnext', 'clip'], False), (['clip'], True), (['convnext', 'clip'], True)]:
        rows, X, Xg = T.load(feats)
        _, Xc, _ = T.load(['clip'])
        rows, X, Xg, _, _ = T.collapse_exact(rows, np.hstack([X, Xc]), Xg)
        X, Xc = X[:, :-512], X[:, -512:]
        if text:
            X = np.hstack([X, TEXT_WEIGHT * prompt_sims(Xc, Tm)]).astype(np.float32)
        groups = T.near_groups(Xg, np.ones(len(rows), bool))
        name = ('img_both' if len(feats) == 2 else 'img_clip') + ('+text' if text else '')
        T.log(f'=== {name}')
        out.append(run(name, rows, X, groups))
        T.log(f'    rule {out[-1][1]}')
    srcs = sorted(out[0][2], key=lambda s: (out[0][3][s], s))
    L = ['# Gate experiment: share of each held-out source accepted as cotton', '',
         'Leave one source out. For cotton sources higher is better; for not-cotton sources lower is better.', '',
         '| Source | Role | ' + ' | '.join(o[0] for o in out) + ' |', '|---|---|' + '---|' * len(out)]
    for s in srcs:
        L.append(f'| {s} | {out[0][3][s]} | ' + ' | '.join(f'{100 * o[2][s]:.1f}%' for o in out) + ' |')
    L += ['', '| Variant | p_min | knn percentile | mean cotton accepted | mean not-cotton rejected |', '|---|---|---|---|---|']
    for name, rule, _, _ in out:
        L.append(f"| {name} | {rule['p_min']} | {rule['knn_percentile']} | {100 * rule['mean_cotton_accept']:.1f}% | "
                 f"{100 * rule['mean_negative_reject']:.1f}% |")
    os.makedirs(T.OUT_DIR, exist_ok=True)
    open(os.path.join(T.OUT_DIR, 'gate_experiment.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
