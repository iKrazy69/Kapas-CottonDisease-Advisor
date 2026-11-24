"""Shared helpers for the outside-photo tests (cotton classifier)."""
import json
import os

import numpy as np

APP_CLASSES = ['Anthracnose', 'Bacterial leaf blight', 'Cotton leaf curl virus disease',
               'Healthy Plants', 'Myrothecium leaf spot', 'Sooty mould disease']

# raw class name (lower case, from each dataset) -> the app's class, or None when the app has no such class
SHARED = {
    'bacterial blight': 'Bacterial leaf blight', 'bacterial leaf blight': 'Bacterial leaf blight',
    'curl virus': 'Cotton leaf curl virus disease', 'cotton leaf curl virus disease': 'Cotton leaf curl virus disease',
    'healthy': 'Healthy Plants', 'healthy leaf': 'Healthy Plants', 'healthy plants': 'Healthy Plants',
}
# Boll rot and Root rot of the project's own photos hold the same 35 files, so neither label is usable.
NEVER_SEEN_NAMES = {
    'alternaria leaf spot': 'Alternaria leaf spot', 'fusarium wilt': 'Fusarium wilt', 'fussarium wilt': 'Fusarium wilt',
    'verticillium wilt': 'Verticillium wilt', 'aphids': 'Aphids', 'army worm': 'Army worm', 'army worms': 'Army worm',
    'powdery mildew': 'Powdery mildew', 'target spot': 'Target spot', 'cotton boll rot': 'Cotton boll rot (boll photo)',
    'green cotton boll': 'Green cotton boll (boll photo)', 'herbicide growth damage': 'Herbicide damage',
    'leaf hopper jassids': 'Leaf hopper (jassid)', 'leaf redding': 'Leaf reddening',
    'leaf variegation': 'Leaf variegation',
    'boll rot disease': 'Boll rot / Root rot (same photos)', 'root rot disease': 'Boll rot / Root rot (same photos)',
}


def wilson(k, n, z=1.96):
    if n == 0:
        return (float('nan'), float('nan'))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def pct(k, n):
    if n == 0:
        return 'n/a'
    lo, hi = wilson(k, n)
    return f'{100 * k / n:.1f}% ({100 * lo:.0f}-{100 * hi:.0f})'


def popcount64(x):
    """Number of set bits in each uint64 (works on old numpy that has no np.bitwise_count)."""
    if hasattr(np, 'bitwise_count'):
        return np.bitwise_count(x)
    x = x.astype(np.uint64)
    x = x - ((x >> np.uint64(1)) & np.uint64(0x5555555555555555))
    x = (x & np.uint64(0x3333333333333333)) + ((x >> np.uint64(2)) & np.uint64(0x3333333333333333))
    x = (x + (x >> np.uint64(4))) & np.uint64(0x0F0F0F0F0F0F0F0F)
    return (x * np.uint64(0x0101010101010101)) >> np.uint64(56)


def lowest_cutoff(conf, correct, target, min_answers):
    """Lowest probability cutoff (0.30-0.95) whose answers are >= target right and number >= min_answers; None if none."""
    conf = np.asarray(conf); correct = np.asarray(correct)
    for t in np.round(np.arange(0.30, 0.96, 0.01), 2):
        k = conf >= t
        if k.sum() >= min_answers and correct[k].mean() >= target:
            return float(t)
    return None


def knn_dist(Z, ref, k):
    """Mean Euclidean distance from each row of Z to its k nearest rows of ref."""
    d = np.sqrt(((Z[:, None, :] - ref[None, :, :]) ** 2).sum(2))
    return np.sort(d, axis=1)[:, :k].mean(1)


def load_all(work):
    import pandas as pd
    m = pd.read_csv(os.path.join(work, 'manifest.csv'), keep_default_na=False)
    m = m[m.status == 'ok'].reset_index(drop=True)
    F = pd.read_csv(os.path.join(work, 'features.csv')).set_index('png')
    m = m[m.png.isin(F.index)].reset_index(drop=True)
    return m, F


def class_map(row_cls):
    key = row_cls.strip().lower()
    if key in SHARED:
        return 'shared', SHARED[key]
    if key in NEVER_SEEN_NAMES:
        return 'never_seen', NEVER_SEEN_NAMES[key]
    return 'other', row_cls


def clean_independent(m, near_pairs, near_dist=4):
    """
    Marks each photo with why it is kept or dropped, per source:
      ambiguous  same bytes appear under more than one class in the source
      exact_dup  same bytes as an earlier photo of the same class
      near_dup   hash distance <= near_dist (any rotation/flip) to an earlier kept photo of the same class
    Returns a copy of m with columns 'drop' ('' = keep) and 'group' (near-duplicate group id).
    """
    import pandas as pd  # noqa: F401
    m = m.copy()
    m['drop'] = ''
    m['bytes_ok'] = m.bytes.astype(int) > 0
    for (src), g in m.groupby('source'):
        cls_of = g.groupby('md5').cls.nunique()
        amb = set(cls_of[cls_of > 1].index)
        m.loc[g.index[g.md5.isin(amb)], 'drop'] = 'ambiguous'
    keep = m[m['drop'] == ''].sort_values('png')
    seen = set()
    for idx, r in keep.iterrows():
        k = (r.source, r.cls, r.md5)
        if k in seen:
            m.loc[idx, 'drop'] = 'exact_dup'
        seen.add(k)
    # near duplicates: union-find over close pairs inside one source and one class
    idx_of = {p: i for i, p in enumerate(m.png)}
    parent = list(range(len(m)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    close = near_pairs[near_pairs.dist <= near_dist]
    for a, b, sa, sb, ca, cb in zip(close.png_a, close.png_b, close.source_a, close.source_b, close.cls_a, close.cls_b):
        if sa == sb and ca == cb:
            ra, rb = find(idx_of[a]), find(idx_of[b])
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    m['group'] = [find(i) for i in range(len(m))]
    first = {}
    for i, r in m.sort_values('png').iterrows():
        if r['drop'] == '':
            if r.group in first:
                m.loc[i, 'drop'] = 'near_dup'
            else:
                first[r.group] = i
    return m


def own_boll_root(m):
    """
    The project's 'Boll rot' and 'Root rot' folders hold the same 35 photos, so the saved model never learned either class
    and the photos are removed as "ambiguous" elsewhere. As photos of a condition the model has never seen, taken with the
    project's own camera, they are still a useful test: one row per distinct file.
    """
    r = m[(m.source == 'own614') & m.cls.str.lower().isin(['boll rot disease', 'root rot disease'])]
    return r.sort_values('png').drop_duplicates('md5').copy()
