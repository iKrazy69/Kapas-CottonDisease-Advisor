"""
Selective-prediction study of the cotton classifier ("when should it stay silent?").

It answers, with confidence intervals and without touching the training code:
  1. How accurate is the classifier overall, and per class? (with the sample sizes, which are small)
  2. If it refuses to answer low-confidence photos, how much better does it get? (risk-coverage table)
  3. Is its confidence actually informative, or would refusing at random do as well? (AUROC, AURC, permutation test)
  4. Is the confidence calibrated? (reliability table, ECE, Brier score)
  5. What does the rule the app really uses do (confident only if probability >= COTTON_MIN_PROBABILITY
     AND the class test F1 >= COTTON_MIN_CLASS_F1)? How many photos get "not sure", and what are the harmful errors?

Usage (in your venv, needs the dataset folder the model was trained on; no Ollama, no internet):
    python eval/abstention_study.py --data-dir path/to/cotton_full

It rebuilds the exact test split from metrics.json (same filters, same seed), refuses to run if the folder is not
the one the model was trained on (a different folder would put training images into the test set), and checks that
it reproduces the accuracy stored in metrics.json before it reports anything.
"""
import argparse
import csv
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from common import wilson, fmt_rate, pct, bootstrap_ci  # noqa: E402

THRESHOLDS = [round(0.05 * i, 2) for i in range(0, 20)]          # 0.00 ... 0.95
CAL_BINS = [0.0, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0001]


# ---------------------------------------------------------------- numeric core (no sklearn, no images)

def macro_f1(y, pred):
    labels = sorted(set(y.tolist()) | set(pred.tolist()))
    f = []
    for c in labels:
        tp = int(((y == c) & (pred == c)).sum())
        fp = int(((y != c) & (pred == c)).sum())
        fn = int(((y == c) & (pred != c)).sum())
        d = 2 * tp + fp + fn
        f.append(2 * tp / d if d else 0.0)
    return float(np.mean(f)) if f else 0.0


def auroc(conf, correct):
    """Probability that a random correct prediction has higher confidence than a random wrong one (ties count half)."""
    pos, neg = conf[correct], conf[~correct]
    if len(pos) == 0 or len(neg) == 0:
        return None
    diff = pos[:, None] - neg[None, :]
    return float(((diff > 0).sum() + 0.5 * (diff == 0).sum()) / (len(pos) * len(neg)))


def aurc(conf, errors):
    """Area under the risk-coverage curve: average error among the k most confident answers, over k = 1..n."""
    order = np.argsort(-conf, kind='stable')
    e = errors[order].astype(float)
    return float((np.cumsum(e) / np.arange(1, len(e) + 1)).mean())


def analyse(y, proba, class_names, class_f1, min_prob, min_f1, seed=0, reps=2000):
    """y: int labels (index into class_names); proba: (n, K) probabilities in class_names order."""
    y = np.asarray(y)
    proba = np.asarray(proba, dtype=float)
    n, K = proba.shape
    pred = proba.argmax(axis=1)
    conf = proba.max(axis=1)
    correct = pred == y
    errors = ~correct
    rng = np.random.RandomState(seed)
    out = {'n': int(n), 'class_names': list(class_names)}

    # 1. accuracy
    lo, hi = wilson(int(correct.sum()), n)
    out['accuracy'] = {'k': int(correct.sum()), 'n': int(n), 'low': lo, 'high': hi}
    idx = list(range(n))
    boots = []
    for _ in range(reps):
        s = rng.randint(0, n, n)
        boots.append(macro_f1(y[s], pred[s]))
    boots.sort()
    out['macro_f1'] = {'value': macro_f1(y, pred), 'low': boots[int(0.025 * reps)], 'high': boots[int(0.975 * reps) - 1]}
    per = []
    for c, name in enumerate(class_names):
        sup = int((y == c).sum())
        tp = int(((y == c) & (pred == c)).sum())
        npred = int((pred == c).sum())
        rlo, rhi = wilson(tp, sup)
        d = 2 * tp + (npred - tp) + (sup - tp)
        per.append({'class': name, 'support': sup, 'predicted': npred, 'correct': tp,
                    'recall': tp / sup if sup else None, 'recall_low': rlo, 'recall_high': rhi,
                    'precision': tp / npred if npred else None, 'f1': 2 * tp / d if d else 0.0})
    out['per_class'] = per
    cm = np.zeros((K, K), dtype=int)
    for t, p in zip(y, pred):
        cm[t, p] += 1
    out['confusion'] = cm.tolist()

    # 2. risk-coverage
    rc = []
    for th in THRESHOLDS:
        keep = conf >= th
        k = int(keep.sum())
        ok = int((correct & keep).sum())
        l, h = wilson(ok, k)
        rc.append({'threshold': th, 'answered': k, 'answered_fraction': k / n,
                   'correct_when_answered': ok, 'accuracy_when_answered': (ok / k) if k else None,
                   'acc_low': l, 'acc_high': h,
                   'wrong_answers': k - ok, 'errors_avoided': int(errors.sum()) - (k - ok)})
    out['risk_coverage'] = rc

    # 3. is the confidence informative?
    a = aurc(conf, errors)
    perm = [aurc(conf, rng.permutation(errors)) for _ in range(reps)]
    p_val = (sum(1 for v in perm if v <= a) + 1) / (reps + 1)
    oracle = aurc(np.where(errors, 0.0, 1.0), errors)
    au = auroc(conf, correct)
    au_boot = []
    if au is not None:
        for _ in range(reps):
            s = rng.randint(0, n, n)
            v = auroc(conf[s], correct[s])
            if v is not None:
                au_boot.append(v)
        au_boot.sort()
    out['informativeness'] = {
        'auroc': au,
        'auroc_low': au_boot[int(0.025 * len(au_boot))] if au_boot else None,
        'auroc_high': au_boot[max(0, int(0.975 * len(au_boot)) - 1)] if au_boot else None,
        'aurc': a, 'aurc_random_abstention': float(errors.mean()), 'aurc_best_possible': oracle,
        'permutation_p': p_val, 'n_wrong': int(errors.sum()), 'n_correct': int(correct.sum())}

    # 4. calibration
    bins = []
    ece = 0.0
    for lo_b, hi_b in zip(CAL_BINS[:-1], CAL_BINS[1:]):
        m = (conf >= lo_b) & (conf < hi_b)
        k = int(m.sum())
        if k:
            acc_b, conf_b = float(correct[m].mean()), float(conf[m].mean())
            ece += k / n * abs(acc_b - conf_b)
            bins.append({'range': f'{lo_b:.1f}-{min(hi_b, 1.0):.1f}', 'n': k, 'mean_confidence': conf_b, 'accuracy': acc_b})
    onehot = np.eye(K)[y]
    out['calibration'] = {'bins': bins, 'ece': float(ece), 'brier': float(((proba - onehot) ** 2).sum(axis=1).mean())}

    # 5. the rule the app actually uses
    f1_of = np.array([class_f1.get(nm) if class_f1.get(nm) is not None else -1.0 for nm in class_names])
    low_prob = conf < min_prob
    low_f1 = f1_of[pred] < min_f1
    confident = ~(low_prob | low_f1)
    healthy = np.array([nm.strip().lower().startswith('healthy') for nm in class_names])
    true_healthy, pred_healthy = healthy[y], healthy[pred]
    advice = confident & ~pred_healthy                              # the app shows treatment advice
    c_n = int(confident.sum())
    cl, ch = wilson(int((correct & confident).sum()), c_n)
    out['deployed_rule'] = {
        'min_probability': min_prob, 'min_class_f1': min_f1,
        'confident': c_n, 'confident_fraction': c_n / n,
        'confident_correct': int((correct & confident).sum()), 'conf_acc_low': cl, 'conf_acc_high': ch,
        'uncertain': int((~confident).sum()),
        'uncertain_only_low_probability': int((low_prob & ~low_f1).sum()),
        'uncertain_only_unreliable_class': int((~low_prob & low_f1).sum()),
        'uncertain_both': int((low_prob & low_f1).sum()),
        'uncertain_but_was_right': int((~confident & correct).sum()),
        'treatment_advice_shown': int(advice.sum()),
        'advice_for_right_disease': int((advice & correct).sum()),
        'advice_for_wrong_disease': int((advice & errors & ~true_healthy).sum()),
        'advice_shown_for_healthy_plant': int((advice & true_healthy).sum()),
        'diseased_called_healthy_confidently': int((confident & pred_healthy & ~true_healthy).sum()),
        'wrong_if_always_answered': int(errors.sum())}
    byclass = []
    for c, name in enumerate(class_names):
        m = y == c
        byclass.append({'class': name, 'n': int(m.sum()), 'not_sure': int((m & ~confident).sum()),
                        'answered_right': int((m & confident & correct).sum()),
                        'answered_wrong': int((m & confident & errors).sum())})
    out['deployed_by_true_class'] = byclass
    return out


# ---------------------------------------------------------------- report

def render_report(s, meta):
    L = []
    a = s['accuracy']
    L += ['# Abstention study: when should the cotton classifier stay silent?', '',
          f"Test images: {s['n']} (from {meta.get('data_dir', '?')}). Model: {meta.get('model', '?')}.",
          f"Reproduction check: {meta.get('reproduction', 'not run')}", '',
          '## 1. Overall performance (the baseline)', '',
          f"- Accuracy: {fmt_rate(a['k'], a['n'])}",
          f"- Macro-F1: {s['macro_f1']['value']:.3f} (bootstrap 95% interval {s['macro_f1']['low']:.3f} to {s['macro_f1']['high']:.3f})",
          '', '| class | test images | found | recall | recall 95% CI | precision | F1 |', '|---|---|---|---|---|---|---|']
    for r in s['per_class']:
        L.append(f"| {r['class']} | {r['support']} | {r['correct']} | {pct(r['recall'])} | "
                 f"{pct(r['recall_low'])} to {pct(r['recall_high'])} | {pct(r['precision'])} | {r['f1']:.2f} |")
    small = [r['class'] for r in s['per_class'] if r['support'] < 10]
    if small:
        L += ['', f"Classes with fewer than 10 test images ({', '.join(small)}) have very wide intervals: do not read their scores as measurements."]

    L += ['', '## 2. Risk-coverage: what refusing low-confidence photos buys', '',
          '| refuse below | photos answered | accuracy when answered | 95% CI | wrong answers left | wrong answers avoided |',
          '|---|---|---|---|---|---|']
    for r in s['risk_coverage']:
        if r['answered'] == 0:
            L.append(f"| {r['threshold']:.2f} | 0/{s['n']} | - | - | 0 | {r['errors_avoided']} |")
        else:
            L.append(f"| {r['threshold']:.2f} | {r['answered']}/{s['n']} ({pct(r['answered_fraction'], 0)}) | {pct(r['accuracy_when_answered'])} | "
                     f"{pct(r['acc_low'])} to {pct(r['acc_high'])} | {r['wrong_answers']} | {r['errors_avoided']} |")

    i = s['informativeness']
    L += ['', '## 3. Is the confidence informative, or would random refusal do as well?', '',
          f"- AUROC (confidence separating right from wrong answers): {i['auroc']:.3f}" +
          (f" (95% interval {i['auroc_low']:.3f} to {i['auroc_high']:.3f})" if i['auroc_low'] is not None else '') +
          '. 0.5 means no information, 1.0 means perfect.' if i['auroc'] is not None else '- AUROC: not defined (all answers right or all wrong).',
          f"- AURC (average error among the most confident answers; lower is better): {i['aurc']:.3f}; "
          f"random refusal gives {i['aurc_random_abstention']:.3f}; best possible ordering gives {i['aurc_best_possible']:.3f}.",
          f"- Permutation test: shuffling which answers are wrong gives an AURC this low in {pct(i['permutation_p'], 2)} of shuffles "
          f"(wrong answers in the test set: {i['n_wrong']}; small numbers of errors make this test weak).", '']

    c = s['calibration']
    L += ['## 4. Calibration', '', f"ECE {c['ece']:.3f}, Brier score {c['brier']:.3f}. (lower is better for both)", '',
          '| confidence range | photos | mean confidence | actual accuracy |', '|---|---|---|---|']
    for b in c['bins']:
        L.append(f"| {b['range']} | {b['n']} | {pct(b['mean_confidence'])} | {pct(b['accuracy'])} |")
    L += ['', 'Bins with few photos are noisy.']

    d = s['deployed_rule']
    L += ['', '## 5. The rule the app really uses', '',
          f"Confident only if probability >= {d['min_probability']:.2f} and the class's test F1 >= {d['min_class_f1']:.2f}.", '',
          f"- Photos the app calls confident: {d['confident']}/{s['n']} ({pct(d['confident_fraction'], 0)}); of those, right: {fmt_rate(d['confident_correct'], d['confident'])}",
          f"- Photos it says \"not sure\" about: {d['uncertain']} "
          f"(only low probability: {d['uncertain_only_low_probability']}, only an unreliable class: {d['uncertain_only_unreliable_class']}, both: {d['uncertain_both']}); "
          f"{d['uncertain_but_was_right']} of them would have been right",
          f"- Photos where treatment advice is shown: {d['treatment_advice_shown']} "
          f"(right disease: {d['advice_for_right_disease']}, wrong disease: {d['advice_for_wrong_disease']}, healthy plant: {d['advice_shown_for_healthy_plant']})",
          f"- Diseased photos confidently called healthy: {d['diseased_called_healthy_confidently']}",
          f"- For comparison, answering every photo would give {d['wrong_if_always_answered']} wrong answers out of {s['n']}", '',
          '| true class | photos | said "not sure" | confident and right | confident and wrong |', '|---|---|---|---|---|']
    for r in s['deployed_by_true_class']:
        L.append(f"| {r['class']} | {r['n']} | {r['not_sure']} | {r['answered_right']} | {r['answered_wrong']} |")
    L += ['', '## How to use these numbers', '',
          '- Report counts together with the intervals; with this test-set size a difference of a few photos is within chance.',
          '- Everything here is on one random split of one dataset. Photos taken in other fields, phones or seasons may behave differently.',
          '- A refusal threshold read off this same test set (as the app\'s 0.70 was) gives an optimistic accuracy-when-answered. '
          'To report it fairly, choose the threshold on the validation split and report the result on the test split.',
          '- The dataset contains images whose bytes appear under more than one class (see metrics.json data_filters); '
          'those were removed before training, and that label noise is a finding in its own right.']
    return '\n'.join(L) + '\n'


def plot(s, path):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except Exception:
        return False
    rc = [r for r in s['risk_coverage'] if r['answered'] > 0]
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    cov = [r['answered_fraction'] for r in rc]
    acc = [r['accuracy_when_answered'] for r in rc]
    ax[0].plot(cov, acc, marker='o', label='accuracy when answered')
    ax[0].fill_between(cov, [r['acc_low'] for r in rc], [r['acc_high'] for r in rc], alpha=0.2, label='95% interval')
    ax[0].axhline(s['accuracy']['k'] / s['accuracy']['n'], linestyle='--', color='grey', label='answer everything')
    ax[0].set_xlabel('fraction of photos answered')
    ax[0].set_ylabel('accuracy on those photos')
    ax[0].set_title('Refusing low-confidence photos')
    ax[0].legend(fontsize=8)
    bins = s['calibration']['bins']
    ax[1].plot([0, 1], [0, 1], linestyle='--', color='grey')
    ax[1].scatter([b['mean_confidence'] for b in bins], [b['accuracy'] for b in bins], s=[20 + 6 * b['n'] for b in bins])
    ax[1].set_xlabel('mean confidence')
    ax[1].set_ylabel('actual accuracy')
    ax[1].set_title('Calibration (dot size = photos)')
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return True


# ---------------------------------------------------------------- the real run (needs the dataset and the saved model)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data-dir', default=os.path.expanduser('~/Downloads/cotton_full'))
    ap.add_argument('--model-dir', default=os.path.join(ROOT, 'backend', 'cotton', 'models'))
    ap.add_argument('--out-dir', default=os.path.join(HERE, 'results'))
    ap.add_argument('--reps', type=int, default=2000, help='bootstrap / permutation repetitions')
    args = ap.parse_args()

    sys.path.insert(0, os.path.join(ROOT, 'backend', 'cotton'))
    sys.path.insert(0, os.path.join(ROOT, 'backend'))
    import joblib
    import train_classifier as tc                          # reuse the exact discovery / split code
    from config import Config

    bundle = joblib.load(os.path.join(args.model_dir, 'cotton_svm.joblib'))
    with open(os.path.join(args.model_dir, 'metrics.json')) as fh:
        metrics = json.load(fh)
    class_names = list(bundle['class_names'])
    flt = metrics.get('data_filters', {})

    names, paths, labels, report = tc.discover(args.data_dir, flt.get('dedupe_within', False), flt.get('exclude_ambiguous', False))
    if report['counts_before'] != flt.get('counts_before') or names != class_names:
        print('\nSTOP: this folder is not the one the model was trained on.')
        print('  model was trained on image counts :', flt.get('counts_before'))
        print('  this folder has                   :', report['counts_before'])
        print('Using a different folder would put training images into the test set and inflate every number.')
        sys.exit(2)
    _, _, te = tc.split(paths, labels, metrics.get('seed', 42))

    feats, ys, files = [], [], []
    for i, j in enumerate(te, 1):
        try:
            feats.append(tc.extract_single_image_features(paths[j]))
            ys.append(int(labels[j]))
            files.append(os.path.basename(paths[j]))
        except Exception as e:
            print(f'  [skipped] {paths[j]}: {e}')
        if i % 20 == 0:
            print(f'  featurised {i}/{len(te)}')
    X = bundle['scaler'].transform(np.array(feats))
    raw = bundle['model'].predict_proba(X)
    proba = np.zeros((len(ys), len(class_names)))
    proba[:, [int(c) for c in bundle['model'].classes_]] = raw
    y = np.array(ys)

    acc = float((proba.argmax(axis=1) == y).mean())
    ok = len(y) == metrics['n_test'] and abs(acc - metrics['accuracy']) < 1e-9
    repro = (f"OK, accuracy {acc:.4f} on {len(y)} images matches metrics.json" if ok else
             f"MISMATCH: got accuracy {acc:.4f} on {len(y)} images, metrics.json says {metrics['accuracy']:.4f} on {metrics['n_test']}. "
             'These numbers are NOT for the saved model on its own test set.')
    print(repro)

    class_f1 = {n: v.get('f1') for n, v in metrics.get('per_class', {}).items()}
    s = analyse(y, proba, class_names, class_f1, Config.COTTON_MIN_PROBABILITY, Config.COTTON_MIN_CLASS_F1, reps=args.reps)
    os.makedirs(args.out_dir, exist_ok=True)
    meta = {'data_dir': args.data_dir, 'model': os.path.join(args.model_dir, 'cotton_svm.joblib'), 'reproduction': repro}
    report_text = render_report(s, meta)
    with open(os.path.join(args.out_dir, 'abstention_report.md'), 'w', encoding='utf-8') as fh:
        fh.write(report_text)
    with open(os.path.join(args.out_dir, 'abstention_summary.json'), 'w') as fh:
        json.dump(s, fh, indent=2)
    with open(os.path.join(args.out_dir, 'abstention_test_predictions.csv'), 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['file', 'true_class', 'predicted_class', 'confidence'] + ['p_' + n for n in class_names])
        for f, t, p in zip(files, y, proba):
            w.writerow([f, class_names[t], class_names[int(p.argmax())], f'{p.max():.4f}'] + [f'{v:.4f}' for v in p])
    with open(os.path.join(args.out_dir, 'abstention_risk_coverage.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(s['risk_coverage'][0].keys()))
        w.writeheader()
        w.writerows(s['risk_coverage'])
    made = plot(s, os.path.join(args.out_dir, 'abstention_curves.png'))
    print('\n' + report_text)
    print(f'Saved to {args.out_dir}' + (' (including abstention_curves.png)' if made else ' (install matplotlib for the picture)'))


if __name__ == '__main__':
    main()
