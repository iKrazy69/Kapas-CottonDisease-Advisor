"""
Step 2 of the outside-photo tests: compute the classifier's 31 features for every prepared photo.

Needs scikit-image (the same feature code the app uses). Reads the manifest and PNGs written by
prep_images.py and writes features.csv (one row per photo, key = png path).

Run:
  python eval/cotton_external/extract_features.py --work <folder with manifest.csv and png224/>
"""
import argparse
import csv
import os
import sys
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'backend', 'cotton'))
sys.path.insert(0, HERE)
from features import extract_single_image_features, N_FEATURES  # noqa: E402

_ROOT = None


def _init(root):
    global _ROOT
    _ROOT = root


def one(png):
    try:
        f = extract_single_image_features(os.path.join(_ROOT, 'png224', png))
        assert len(f) == N_FEATURES
        return png, [float(x) for x in f], ''
    except Exception as e:  # damaged or unreadable image
        return png, [], str(e)[:80]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', required=True)
    ap.add_argument('--workers', type=int, default=2)
    args = ap.parse_args()
    work = os.path.expanduser(args.work)
    with open(os.path.join(work, 'manifest.csv'), newline='') as fh:
        pngs = [r['png'] for r in csv.DictReader(fh) if r['status'] == 'ok']
    out = os.path.join(work, 'features.csv')
    done = set()
    if os.path.exists(out):
        with open(out, newline='') as fh:
            done = {r['png'] for r in csv.DictReader(fh)}
    todo = [p for p in pngs if p not in done]
    print(f'{len(pngs)} photos, {len(done)} done, {len(todo)} to do', flush=True)
    new = not os.path.exists(out)
    with open(out, 'a', newline='') as fh, Pool(args.workers, initializer=_init, initargs=(work,)) as pool:
        w = csv.writer(fh)
        if new:
            w.writerow(['png'] + [f'f{i}' for i in range(N_FEATURES)])
        for n, (png, f, err) in enumerate(pool.imap_unordered(one, todo, chunksize=8), 1):
            if err:
                print('  skipped', png, err)
            else:
                w.writerow([png] + [repr(x) for x in f])
            if n % 500 == 0:
                fh.flush()
                print(f'  {n}/{len(todo)}', flush=True)
    print('finished')


if __name__ == '__main__':
    main()
