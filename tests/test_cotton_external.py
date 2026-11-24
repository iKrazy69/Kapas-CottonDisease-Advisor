# -*- coding: utf-8 -*-
"""Checks for the outside-photo tools in eval/cotton_external/. No photos, no model, no scikit-learn needed.
The checks that use pandas are skipped (and say so) if pandas is not installed.  Run:  python tests/test_cotton_external.py"""
import ast, glob, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.abspath(os.path.join(HERE, '..', 'eval', 'cotton_external'))
sys.path.insert(0, TOOLS)
import common as C
fails = []
def check(n, c, x=None):
    print(('PASS ' if c else 'FAIL ') + n + (' ' + str(x)[:400] if (x is not None and not c) else ''))
    if not c: fails.append(n)

for path in sorted(glob.glob(os.path.join(TOOLS, '*.py'))):
    with open(path, encoding='utf-8') as fh:
        ast.parse(fh.read(), feature_version=(3, 9))
check('every script in eval/cotton_external parses as Python 3.9', True)

# ---------- Wilson interval and percentage text ----------
lo, hi = C.wilson(50, 100)
check('wilson(50,100) is about 40-60%', abs(lo - 0.4038) < 0.002 and abs(hi - 0.5962) < 0.002, (lo, hi))
lo, hi = C.wilson(0, 10)
check('wilson(0,10) starts at 0 and stays below 0.35', lo == 0.0 and 0.2 < hi < 0.35, (lo, hi))
check('wilson with no photos is NaN, not an error', all(np.isnan(v) for v in C.wilson(0, 0)))
check('pct text', C.pct(47, 81) == '58.0% (47-68)', C.pct(47, 81))
check('pct with no photos', C.pct(0, 0) == 'n/a')

# ---------- class names ----------
check('shared: Bacterial Blight with any case', C.class_map('Bacterial Blight') == ('shared', 'Bacterial leaf blight'))
check('shared: Healthy Leaf and healthy', C.class_map('Healthy Leaf')[1] == 'Healthy Plants' and C.class_map('healthy')[1] == 'Healthy Plants')
check('shared: Curl Virus', C.class_map('Curl Virus') == ('shared', 'Cotton leaf curl virus disease'))
check('never seen: spelling "fussarium wilt" and "Army Worms " (trailing space)',
      C.class_map('fussarium wilt') == ('never_seen', 'Fusarium wilt') and C.class_map('Army Worms ') == ('never_seen', 'Army worm'))
check('Boll rot and Root rot share one label (they are the same photos)',
      C.class_map('Boll rot disease')[1] == C.class_map('Root rot disease')[1])
check('unknown class is "other"', C.class_map('Something new')[0] == 'other')
check('the six app classes are all known', len(C.APP_CLASSES) == 6 and C.APP_CLASSES[3] == 'Healthy Plants')

# ---------- bit counting ----------
rng = np.random.RandomState(1)
x = rng.randint(0, 2 ** 62, size=500, dtype=np.int64).astype(np.uint64) * np.uint64(3) + np.uint64(1)
want = np.array([bin(int(v)).count('1') for v in x])
check('popcount64 matches counting bits one by one', (C.popcount64(x) == want).all())
saved = getattr(np, 'bitwise_count', None)
if saved is not None:
    del np.bitwise_count
try:
    check('popcount64 also works without np.bitwise_count (old numpy)', (C.popcount64(x) == want).all())
finally:
    if saved is not None:
        np.bitwise_count = saved
check('popcount64 of 0 and of all ones', C.popcount64(np.array([0, 2 ** 64 - 1], dtype=np.uint64)).tolist() == [0, 64])

# ---------- cutoff chosen on validation ----------
conf = np.array([0.95] * 30 + [0.55] * 30 + [0.35] * 30)
ok = np.array([True] * 30 + [True] * 25 + [False] * 5 + [True] * 10 + [False] * 20)
t = C.lowest_cutoff(conf, ok, 0.90, 20)
check('lowest_cutoff picks 0.36 where answers (0.55 and above) are 55/60 = 91.7% right', t is not None and 0.36 <= t <= 0.55, t)
check('lowest_cutoff is None when no cutoff reaches the target', C.lowest_cutoff(conf, np.zeros(90, bool), 0.9, 5) is None)
check('lowest_cutoff respects the minimum number of answers', C.lowest_cutoff(np.array([0.9] * 5), np.ones(5, bool), 0.9, 20) is None)

# ---------- distance to the nearest training photos ----------
ref = np.array([[0.0, 0.0], [3.0, 4.0]])
Z = np.array([[0.0, 0.0], [3.0, 4.0], [0.0, 4.0]])
d1 = C.knn_dist(Z, ref, 1)
check('knn_dist k=1', np.allclose(d1, [0.0, 0.0, 3.0]), d1)
d2 = C.knn_dist(Z, ref, 2)
check('knn_dist k=2 is the mean of the two distances', np.allclose(d2, [2.5, 2.5, 3.5]), d2)

# ---------- cleaning (needs pandas) ----------
try:
    import pandas as pd
except ImportError:
    pd = None
    print('SKIPPED the cleaning checks: pandas is not installed (pip install pandas)')
if pd is not None:
    def frame(rows):
        return pd.DataFrame(rows, columns=['source', 'cls', 'name', 'md5', 'bytes', 'png', 'status'])
    rows = [
        ('a', 'Healthy', 'h1', 'M1', 10, 'p1', 'ok'),
        ('a', 'Healthy', 'h2', 'M1', 10, 'p2', 'ok'),          # same bytes, same class -> exact_dup
        ('a', 'Healthy', 'h3', 'M2', 10, 'p3', 'ok'),          # near-identical to h4 -> near_dup of the first
        ('a', 'Healthy', 'h4', 'M3', 10, 'p4', 'ok'),
        ('a', 'Blight', 'b1', 'M2', 10, 'p5', 'ok'),           # same bytes as h3 under another class -> ambiguous (both)
        ('a', 'Blight', 'b2', 'M9', 10, 'p6', 'ok'),
        ('b', 'Healthy', 'x1', 'M1', 10, 'p7', 'ok'),          # same bytes as a/h1 but another source: untouched
    ]
    m = frame(rows)
    near = pd.DataFrame({'png_a': ['p3'], 'png_b': ['p4'], 'dist': [2], 'source_a': ['a'], 'source_b': ['a'], 'cls_a': ['Healthy'], 'cls_b': ['Healthy']})
    out = C.clean_independent(m, near, 4).set_index('png')
    check('same bytes under two classes in one source -> ambiguous (both copies)', out.loc['p3', 'drop'] == 'ambiguous' and out.loc['p5', 'drop'] == 'ambiguous', out['drop'].to_dict())
    check('second copy of the same bytes and class -> exact_dup', out.loc['p2', 'drop'] == 'exact_dup' and out.loc['p1', 'drop'] == '')
    near2 = pd.DataFrame({'png_a': ['p1'], 'png_b': ['p4'], 'dist': [3], 'source_a': ['a'], 'source_b': ['a'], 'cls_a': ['Healthy'], 'cls_b': ['Healthy']})
    out2 = C.clean_independent(m, near2, 4).set_index('png')
    check('a close pair of different files -> the later one is near_dup', out2.loc['p4', 'drop'] == 'near_dup' and out2.loc['p1', 'drop'] == '', out2['drop'].to_dict())
    far = near2.assign(dist=[9])
    out3 = C.clean_independent(m, far, 4).set_index('png')
    check('a pair farther than the limit is kept', out3.loc['p4', 'drop'] == '', out3['drop'].to_dict())
    check('the same bytes in another source are not touched', out.loc['p7', 'drop'] == '')
    cross = near2.assign(source_b=['b'], cls_b=['Healthy'], png_b=['p7'])
    out4 = C.clean_independent(m, cross, 4).set_index('png')
    check('close photos from different sources are not merged', out4.loc['p7', 'drop'] == '' and out4.loc['p1', 'drop'] == '')
    mb = pd.DataFrame([('own614', 'Boll rot disease', 'a', 'Z1', 5, 'q1', 'ok'), ('own614', 'Root rot disease', 'a', 'Z1', 5, 'q2', 'ok'),
                       ('own614', 'Root rot disease', 'b', 'Z2', 5, 'q3', 'ok'), ('own614', 'Healthy Plants', 'c', 'Z3', 5, 'q4', 'ok')],
                      columns=['source', 'cls', 'name', 'md5', 'bytes', 'png', 'status'])
    ob = C.own_boll_root(mb)
    check('own_boll_root: one row per distinct file, Boll/Root only', sorted(ob.png) == ['q1', 'q3'], ob.png.tolist())

print('\nALL PASSED' if not fails else f'\n{len(fails)} FAILED: {fails}')
sys.exit(1 if fails else 0)
