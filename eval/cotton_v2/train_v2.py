"""
Step 3: train and test the v2 cotton models on the cached embeddings.

    python eval/cotton_v2/train_v2.py [--save]

Two small models on top of the frozen ConvNeXt-Tiny numbers:
  gate    : cotton leaf/plant photo vs anything else (logistic regression + a
            nearest-cotton-photo similarity check)
  disease : which condition, for photos the gate accepts (multinomial logistic regression)

Honesty rules built in:
  * exact copies (same bytes) are collapsed; the same photo under two different
    labels is dropped;
  * near-identical photos (cosine >= NEAR) are grouped and always kept on the
    same side of every split;
  * "leave one source out" (LOSO): each dataset is tested by a model trained
    without it AND without any photo that has a near twin in it.

--save writes backend/cotton/models/cotton_v2.joblib and metrics_v2.json.
A full report goes to eval/results/cotton_v2/report.md and report.json.
"""

import argparse
import collections
import csv
import json
import os
import sys
import time

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_recall_fscore_support
from sklearn.model_selection import StratifiedGroupKFold

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V2 = os.path.expanduser('~/Downloads/Cottondataset/v2')
OUT_DIR = os.path.join(ROOT, 'eval', 'results', 'cotton_v2')
MODEL_DIR = os.path.join(ROOT, 'backend', 'cotton', 'models')
NEAR = 0.96              # cosine similarity at or above which two photos count as near-identical
MIN_GROUPS = 30          # a condition needs this many independent photos to be learned
MIN_PROB = 0.70          # same confidence rule as the live app
SOURCE_ORDER = ['own', 'eastwest', 'severity', 'sarcld', 'cosev', 'ayaz', 'dhamur', 'janmejay',
                'seroshkarim', 'raaavan', 'fatimacurl']


def log(*a):
    print(*a, flush=True)


# ----------------------------------------------------------------- data
# Re-uploads of the same photos: held out together in every leave-one-source-out test.
FAMILY = {'dhamur': 'ayaz', 'raaavan': 'seroshkarim'}


def family(src):
    return FAMILY.get(src, src)


def load(features):
    with open(os.path.join(V2, 'catalog.csv')) as fh:
        rows = [r for r in csv.DictReader(fh) if r['role'] in ('cotton', 'negative')]
    mats = {}
    for f in sorted(set(features) | {'convnext'}):
        d = np.load(os.path.join(V2, 'embeddings.npz' if f == 'convnext' else f'embeddings_{f}.npz'))
        mats[f] = ({fn: i for i, fn in enumerate(d['files'])}, d['X'])
    rows = [r for r in rows if all(r['file'] in idx for idx, _ in mats.values())]
    get = lambda f: mats[f][1][[mats[f][0][r['file']] for r in rows]]
    Xg = get('convnext')                                   # near-twin grouping always uses ConvNeXt
    X = np.hstack([get(f) for f in features]) / np.sqrt(len(features))
    return rows, X.astype(np.float32), Xg.astype(np.float32)


def collapse_exact(rows, X, Xg):
    """One row per distinct photo (sha1). Same bytes under two cotton labels -> dropped."""
    rank = {s: i for i, s in enumerate(SOURCE_ORDER)}
    by = collections.defaultdict(list)
    for i, r in enumerate(rows):
        by[r['sha1']].append(i)
    keep, conflicts, copies = [], 0, 0
    for _, ids in by.items():
        cot = [i for i in ids if rows[i]['role'] == 'cotton']
        if cot:
            labs = {rows[i]['label'] for i in cot if rows[i]['label']}
            if len(labs) > 1:
                conflicts += len(cot)
                continue
            best = sorted(cot, key=lambda i: (not rows[i]['label'], rank.get(rows[i]['source'], 99)))[0]
            if labs and not rows[best]['label']:
                rows[best]['label'] = labs.pop()
            rows[best]['also_in'] = sorted({rows[i]['source'] for i in ids} - {rows[best]['source']})
            keep.append(best)
            copies += len(ids) - 1
        else:
            keep.append(ids[0])
            copies += len(ids) - 1
    keep.sort()
    return [rows[i] for i in keep], X[keep], Xg[keep], conflicts, copies


def near_groups(X, mask):
    """Union-find over photos (only where mask) with cosine >= NEAR. Returns group id per row."""
    n = len(X)
    parent = np.arange(n)

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    ids = np.where(mask)[0]
    Xs = X[ids]
    for s in range(0, len(ids), 1024):
        sim = Xs[s:s + 1024] @ Xs.T
        a, b = np.where(sim >= NEAR)
        for i, j in zip(a + s, b):
            if i < j:
                ri, rj = find(ids[i]), find(ids[j])
                if ri != rj:
                    parent[ri] = rj
    return np.array([find(i) for i in range(n)])


# ----------------------------------------------------------------- weights
def source_balanced_weights(rows, y):
    """Each source counts equally inside its class side, and the two sides equally."""
    w = np.zeros(len(rows))
    for side in np.unique(y):
        sel = np.where(y == side)[0]
        cnt = collections.Counter(rows[i]['source'] for i in sel)
        for i in sel:
            w[i] = 1.0 / cnt[rows[i]['source']]
        w[sel] *= len(sel) / w[sel].sum()
    return w * len(w) / w.sum()


# ----------------------------------------------------------------- gate
def fit_gate(Xtr, ytr, wtr):
    m = LogisticRegression(C=1.0, max_iter=3000)
    m.fit(Xtr, ytr, sample_weight=wtr)
    return m


def knn_sim(Xq, Xref, k=5):
    out = np.zeros(len(Xq))
    for s in range(0, len(Xq), 2048):
        sim = Xq[s:s + 2048] @ Xref.T
        out[s:s + 2048] = np.sort(sim, axis=1)[:, -k:].mean(axis=1)
    return out


def gate_loso(rows, X, groups, zs):
    y = np.array([1 if r['role'] == 'cotton' else 0 for r in rows])
    src = np.array([family(r['source']) for r in rows])
    res = {}
    for s in sorted(set(src)):
        test = src == s
        bad_groups = set(groups[test])
        train = ~test & ~np.isin(groups, list(bad_groups))
        if len(set(y[train])) < 2:
            continue
        w = source_balanced_weights([rows[i] for i in np.where(train)[0]], y[train])
        m = fit_gate(X[train], y[train], w)
        p = m.predict_proba(X[test])[:, 1]
        ks = knn_sim(X[test], X[train & (y == 1)])
        res[s] = {'role': 'cotton' if y[test][0] == 1 else 'negative', 'n': int(test.sum()),
                  'p': p.tolist(), 'knn': ks.tolist(), 'zs': zs[test].tolist()}
        log(f'  gate LOSO {s:13s} n={test.sum():5d}  median p(cotton)={np.median(p):.3f}')
    return res


def gate_cv(rows, X, groups, zs, rule):
    """In-distribution check: grouped 5-fold CV over all photos (every kind of photo is in training,
    as in the live model). Returns share accepted as cotton per source."""
    y = np.array([1 if r['role'] == 'cotton' else 0 for r in rows])
    src = np.array([r['source'] for r in rows])
    acc = np.zeros(len(y), bool)
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    strat = np.array([f'{r["role"]}:{r["source"]}' for r in rows])
    for tr, te in cv.split(X, strat, groups):
        m = fit_gate(X[tr], y[tr], source_balanced_weights([rows[i] for i in tr], y[tr]))
        p = m.predict_proba(X[te])[:, 1]
        ks = knn_sim(X[te], X[tr][y[tr] == 1])
        acc[te] = (p >= rule['p_min']) & (ks >= rule['knn_min']) & (zs[te] >= rule['z_min'])
    return {s: {'role': 'cotton' if y[src == s][0] == 1 else 'negative', 'n': int((src == s).sum()),
                'accepted': float(acc[src == s].mean())} for s in sorted(set(src))}


def pick_gate_rule(loso, floor=0.95):
    """p(cotton) >= t, knn >= k, CLIP zero-shot cotton share >= z.
    Maximise the mean share of not-cotton sources rejected, keeping mean cotton acceptance >= floor."""
    best = None
    cot = [v for v in loso.values() if v['role'] == 'cotton']
    neg = [v for v in loso.values() if v['role'] == 'negative']
    all_knn_cot = np.concatenate([v['knn'] for v in cot])
    for t in np.arange(0.05, 0.96, 0.05):
        for q in [0.0, 1.0, 2.0, 5.0]:
            k = float(np.percentile(all_knn_cot, q)) if q > 0 else -1.0
            for z in [0.0, 0.002, 0.005, 0.01, 0.02, 0.03, 0.05]:
                rule = {'p_min': round(float(t), 2), 'knn_min': k, 'z_min': z}
                acc = np.mean([np.mean(apply_gate(v, rule)) for v in cot])
                rej = np.mean([np.mean(~apply_gate(v, rule)) for v in neg])
                if acc >= floor and (best is None or rej > best[0]):
                    best = (rej, rule, q, acc)
    rej, rule, q, acc = best
    return dict(rule, knn_percentile=q, mean_cotton_accept=float(acc), mean_negative_reject=float(rej))


def apply_gate(v, rule):
    return ((np.array(v['p']) >= rule['p_min']) & (np.array(v['knn']) >= rule['knn_min'])
            & (np.array(v['zs']) >= rule.get('z_min', 0.0)))


# ----------------------------------------------------------------- disease
def disease_data(rows, X, groups):
    lab = [r['label'] for r in rows]
    is_c = np.array([r['role'] == 'cotton' and bool(r['label']) for r in rows])
    gcount = collections.defaultdict(set)
    for i in np.where(is_c)[0]:
        gcount[lab[i]].add(groups[i])
    # drop near-identical groups that carry two different labels
    glabs = collections.defaultdict(set)
    for i in np.where(is_c)[0]:
        glabs[groups[i]].add(lab[i])
    mixed = {g for g, ls in glabs.items() if len(ls) > 1}
    classes = sorted(c for c, gs in gcount.items() if len(gs - mixed) >= MIN_GROUPS)
    sel = np.array([is_c[i] and lab[i] in classes and groups[i] not in mixed for i in range(len(rows))])
    dropped = {c: len(gs) for c, gs in gcount.items() if c not in classes}
    return sel, classes, mixed, dropped


def fit_disease(Xtr, ytr, wtr, C):
    m = LogisticRegression(C=C, max_iter=4000, class_weight=None)
    m.fit(Xtr, ytr, sample_weight=wtr)
    return m


def class_source_weights(rows_sel, y):
    """Balanced over classes; inside a class each source counts equally (capped at 4x)."""
    w = np.zeros(len(y))
    for c in np.unique(y):
        sel = np.where(y == c)[0]
        cnt = collections.Counter(rows_sel[i]['source'] for i in sel)
        for i in sel:
            w[i] = min(4.0, len(sel) / len(cnt) / cnt[rows_sel[i]['source']])
        w[sel] *= 1.0 / w[sel].sum()
    return w * len(w) / w.sum()


def disease_cv(Xd, yd, gd, rows_d, C, n_classes):
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    P = np.zeros((len(yd), n_classes))
    for tr, te in cv.split(Xd, yd, gd):
        m = fit_disease(Xd[tr], yd[tr], class_source_weights([rows_d[i] for i in tr], yd[tr]), C)
        P[np.ix_(te, m.classes_)] = m.predict_proba(Xd[te])
    return P


def summarise(P, y, classes):
    pred = P.argmax(1)
    conf = P.max(1)
    p, r, f, s = precision_recall_fscore_support(y, pred, labels=range(len(classes)), zero_division=0)
    ans = conf >= MIN_PROB
    return {
        'n': int(len(y)), 'accuracy': float((pred == y).mean()),
        'macro_f1': float(f1_score(y, pred, average='macro', labels=range(len(classes)), zero_division=0)),
        'answered_at_0.70': float(ans.mean()),
        'right_when_answered': float((pred[ans] == y[ans]).mean()) if ans.any() else None,
        'per_class': {classes[i]: {'precision': float(p[i]), 'recall': float(r[i]), 'f1': float(f[i]),
                                   'support': int(s[i])} for i in range(len(classes))},
    }


def disease_loso(rows_d, Xd, yd, gd, classes, C):
    src = np.array([family(r['source']) for r in rows_d])
    out = {}
    for s in sorted(set(src)):
        test = src == s
        train = ~test & ~np.isin(gd, list(set(gd[test])))
        known = set(yd[train])
        test = test & np.isin(yd, list(known))
        if test.sum() < 10:
            continue
        m = fit_disease(Xd[train], yd[train],
                        class_source_weights([rows_d[i] for i in np.where(train)[0]], yd[train]), C)
        P = np.zeros((test.sum(), len(classes)))
        P[:, m.classes_] = m.predict_proba(Xd[test])
        pred, conf, yt = P.argmax(1), P.max(1), yd[test]
        ans = conf >= MIN_PROB
        per = {}
        for c in sorted(set(yt)):
            sel = yt == c
            per[classes[c]] = {'n': int(sel.sum()), 'recall': float((pred[sel] == c).mean()),
                               'answered': float(ans[sel].mean()),
                               'right_when_answered': float((pred[sel & ans] == c).mean()) if (sel & ans).any() else None,
                               'confident_wrong': float(((pred[sel] != c) & ans[sel]).mean())}
        out[s] = {'n': int(test.sum()), 'accuracy': float((pred == yt).mean()),
                  'answered': float(ans.mean()),
                  'right_when_answered': float((pred[ans] == yt[ans]).mean()) if ans.any() else None,
                  'per_class': per}
        log(f'  disease LOSO {s:12s} n={test.sum():5d} acc={out[s]["accuracy"]:.3f} '
            f'answered={out[s]["answered"]:.2f} right-when-answered={out[s]["right_when_answered"]}')
    return out


# ----------------------------------------------------------------- report
def pct(x):
    return '-' if x is None else f'{100 * x:.1f}%'


def write_report(rep, tag=''):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, f'report{tag}.json'), 'w') as fh:
        json.dump(rep, fh, indent=1)
    L = ['# Cotton classifier v2: results', '',
         f"Run {rep['time']}. Features: {' + '.join(rep['features'])} (frozen pretrained networks). "
         'All numbers below come from this run; nothing typed in by hand.', '',
         '## Data after cleaning', '',
         f"- Photos read: {rep['data']['rows_read']}; exact copies collapsed: {rep['data']['exact_copies']}; "
         f"same photo under two labels, dropped: {rep['data']['label_conflicts']}.",
         f"- Near-identical groups (cosine >= {NEAR}) with two different labels, dropped: {rep['data']['mixed_groups']}.",
         f"- Cotton photos: {rep['data']['cotton']} ({rep['data']['cotton_labelled']} with a usable condition label); "
         f"not-cotton photos: {rep['data']['negative']}.", '',
         '| Source | Role | Photos kept | Labels |', '|---|---|---|---|']
    for s, v in rep['data']['per_source'].items():
        L.append(f"| {s} | {v['role']} | {v['n']} | {', '.join(f'{k} {n}' for k, n in sorted(v['labels'].items()))} |")
    g = rep['gate']
    L += ['', '## Gate: is it a cotton photo?', '',
          f"Rule: gate p(cotton) >= {g['rule']['p_min']}, mean similarity to the 5 nearest cotton training photos "
          f">= {g['rule']['knn_min']:.3f} ({g['rule']['knn_percentile']} percentile of held-out cotton), and CLIP "
          f"zero-shot cotton share >= {g['rule']['z_min']}. Chosen on the leave-one-source-out results "
          '(largest mean not-cotton rejection with mean cotton acceptance at least 95%).', '',
          'Two tests. Held out: the source is left out of training entirely, so its kind of photo (for not-cotton: its '
          'plant species) is new to the model. In-distribution: grouped 5-fold CV over all photos, as for the live '
          'model, which has seen every listed kind of photo.', '',
          '| Source | Role | n | Accepted as cotton, held out | Accepted as cotton, in-distribution |', '|---|---|---|---|---|']
    for s, v in g['loso'].items():
        cvv = g['cv'].get(s) or {}
        L.append(f"| {s} | {v['role']} | {v['n']} | {pct(v['accepted'])} | {pct(cvv.get('accepted'))} |")
    d = rep['disease']
    L += ['', '## Disease model', '',
          f"Classes ({len(d['classes'])}): {', '.join(d['classes'])}.",
          f"Not learned (fewer than {MIN_GROUPS} independent photos): "
          f"{', '.join(f'{k} ({v})' for k, v in d['too_few'].items()) or 'none'}.",
          f"C = {d['C']} (chosen by grouped 5-fold CV macro-F1 from {d['C_grid']}).", '',
          '### Grouped 5-fold cross-validation (near twins kept together)', '',
          f"Accuracy {pct(d['cv']['accuracy'])}, macro-F1 {d['cv']['macro_f1']:.3f}, n = {d['cv']['n']}. "
          f"At the 0.70 rule: answers {pct(d['cv']['answered_at_0.70'])}, right when it answers "
          f"{pct(d['cv']['right_when_answered'])}.", '',
          '| Class | Precision | Recall | F1 | Photos |', '|---|---|---|---|---|']
    for c, v in d['cv']['per_class'].items():
        L.append(f"| {c} | {v['precision']:.2f} | {v['recall']:.2f} | {v['f1']:.2f} | {v['support']} |")
    L += ['', '### Leave one source out (the honest test: a dataset the model never saw)', '',
          '| Held-out source | n | Accuracy | Answered at 0.70 | Right when answered |', '|---|---|---|---|---|']
    for s, v in d['loso'].items():
        L.append(f"| {s} | {v['n']} | {pct(v['accuracy'])} | {pct(v['answered'])} | {pct(v['right_when_answered'])} |")
    L += ['', 'Per class inside each held-out source:', '',
          '| Held-out source | Class | n | Named correctly | Answered | Confident and wrong |', '|---|---|---|---|---|---|']
    for s, v in d['loso'].items():
        for c, pc in v['per_class'].items():
            L.append(f"| {s} | {c} | {pc['n']} | {pct(pc['recall'])} | {pct(pc['answered'])} | {pct(pc['confident_wrong'])} |")
    L += ['', '## Limits', '',
          '- Labels are the dataset authors\'; no cotton expert has checked them.',
          '- Several Kaggle sets are re-uploads of each other; exact and near copies were merged, but a source that '
          'shares photos with another is not a fully independent test.',
          '- The gate was tested on the kinds of non-cotton photos listed above; a kind of photo not in the list is untested.']
    with open(os.path.join(OUT_DIR, f'report{tag}.md'), 'w') as fh:
        fh.write('\n'.join(L) + '\n')


# ----------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--save', action='store_true')
    ap.add_argument('--features', default='convnext+clip', help='convnext, clip or convnext+clip')
    ap.add_argument('--tag', default='', help='suffix for the report file names')
    a = ap.parse_args()
    features = a.features.split('+')
    t0 = time.time()
    rows, X, Xg = load(features)
    _, Xclip, _ = load(['clip'])
    n_read = len(rows)
    rows, XX, Xg, conflicts, copies = collapse_exact(rows, np.hstack([X, Xclip]), Xg)
    X, Xclip = XX[:, :-512], XX[:, -512:]
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import zeroshot_check as Z
    T_text, logit_scale = Z.text_features()
    zs = Z.cotton_share(Xclip, T_text, logit_scale)
    cot_mask = np.array([r['role'] == 'cotton' for r in rows])
    groups = near_groups(Xg, np.ones(len(rows), bool))
    log(f'{n_read} rows -> {len(rows)} distinct photos ({copies} copies, {conflicts} conflicting); '
        f'{len(set(groups))} near-identical groups')

    per_source = collections.OrderedDict()
    for r in rows:
        v = per_source.setdefault(r['source'], {'role': r['role'], 'n': 0, 'labels': collections.Counter()})
        v['n'] += 1
        if r['role'] == 'cotton':
            v['labels'][r['label'] or '(no disease named)'] += 1

    # ---- gate
    log('gate: leave one source out')
    gl = gate_loso(rows, X, groups, zs)
    rule = pick_gate_rule(gl)
    for s, v in gl.items():
        v['accepted'] = float(apply_gate(v, rule).mean())
    log(f'gate rule {rule}')
    log('gate: grouped 5-fold CV (in-distribution)')
    gcv = gate_cv(rows, X, groups, zs, rule)

    # ---- disease
    sel, classes, mixed, too_few = disease_data(rows, X, groups)
    rows_d = [rows[i] for i in np.where(sel)[0]]
    Xd, gd = X[sel], groups[sel]
    yd = np.array([classes.index(r['label']) for r in rows_d])
    log(f'disease: {len(classes)} classes, {len(yd)} photos')
    grid = [3.0, 10.0, 30.0, 100.0]
    best_C, best_f1, cv_by_C = None, -1, {}
    for C in grid:
        P = disease_cv(Xd, yd, gd, rows_d, C, len(classes))
        f = f1_score(yd, P.argmax(1), average='macro')
        cv_by_C[C] = (f, P)
        log(f'  C={C}: CV macro-F1 {f:.3f}')
        if f > best_f1:
            best_C, best_f1 = C, f
    cv = summarise(cv_by_C[best_C][1], yd, classes)
    loso = disease_loso(rows_d, Xd, yd, gd, classes, best_C)

    rep = {
        'time': time.strftime('%Y-%m-%d %H:%M'), 'features': features,
        'data': {'rows_read': n_read, 'exact_copies': copies, 'label_conflicts': conflicts,
                 'mixed_groups': len(mixed), 'cotton': int(cot_mask.sum()),
                 'cotton_labelled': int(sum(1 for r in rows if r['role'] == 'cotton' and r['label'])),
                 'negative': int((~cot_mask).sum()),
                 'per_source': {s: {'role': v['role'], 'n': v['n'], 'labels': dict(v['labels'])}
                                for s, v in per_source.items()}},
        'gate': {'rule': rule, 'loso': {s: {k: v[k] for k in ('role', 'n', 'accepted')} for s, v in gl.items()},
                 'cv': gcv},
        'disease': {'classes': classes, 'too_few': too_few, 'C': best_C, 'C_grid': grid,
                    'cv': cv, 'loso': loso},
    }
    write_report(rep, a.tag)
    log(f'report written to {OUT_DIR}/report{a.tag}.md ({time.time() - t0:.0f} s)')

    if a.save:
        import joblib
        y_gate = np.array([1 if r['role'] == 'cotton' else 0 for r in rows])
        gate = fit_gate(X, y_gate, source_balanced_weights(rows, y_gate))
        disease = fit_disease(Xd, yd, class_source_weights(rows_d, yd), best_C)
        cotton_ref = X[y_gate == 1].astype(np.float16)
        bundle = {'version': 2, 'features': features, 'gate': gate, 'gate_rule': rule,
                  'text_prompts': Z.COTTON + Z.OTHER, 'n_cotton_prompts': len(Z.COTTON),
                  'text_features': T_text.astype(np.float32), 'logit_scale': logit_scale,
                  'cotton_ref': cotton_ref, 'disease': disease, 'class_names': classes,
                  'created': rep['time']}
        joblib.dump(bundle, os.path.join(MODEL_DIR, 'cotton_v2.joblib'), compress=3)
        metrics = {'version': 2, 'created': rep['time'], 'features': features, 'evaluation': 'grouped 5-fold CV (near twins together)',
                   'accuracy': cv['accuracy'], 'macro_f1': cv['macro_f1'], 'per_class': cv['per_class'],
                   'answered_at_0.70': cv['answered_at_0.70'], 'right_when_answered': cv['right_when_answered'],
                   'gate_rule': rule,
                   'loso': {s: {k: v[k] for k in ('n', 'accuracy', 'answered', 'right_when_answered')}
                            for s, v in loso.items()}}
        with open(os.path.join(MODEL_DIR, 'metrics_v2.json'), 'w') as fh:
            json.dump(metrics, fh, indent=1)
        log('saved backend/cotton/models/cotton_v2.joblib and metrics_v2.json')


if __name__ == '__main__':
    main()
