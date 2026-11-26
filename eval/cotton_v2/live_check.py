"""
Run the SAVED v2 classifier, exactly as the app does, on photos that were not used
in training (checked by SHA-1 against the catalogue):
  - cannabis photos from the same Kaggle set but not in the training sample
  - PlantVillage 'val' split (training used only 'train')
  - Imagenette 'val' split
  - Ayaz 'Validation-Testing' and other cotton photos not in the catalogue, if any

    python eval/cotton_v2/live_check.py [--per 60]
Writes eval/results/cotton_v2/live_check.md
"""
import argparse
import collections
import csv
import hashlib
import io
import os
import random
import re
import sys
import tarfile
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'backend'))
V2 = os.path.expanduser('~/Downloads/Cottondataset/v2')
RAW = os.path.join(V2, 'raw')
IMG = re.compile(r'\.(jpe?g|png)$', re.I)


def sources():
    yield 'cannabis (unseen photos)', 'folder', os.path.join(RAW, 'cannabis_holdout'), r''
    yield 'plantvillage val', 'zip', os.path.join(RAW, 'mohitsingh1804_plantvillage.zip'), r'/val/'
    yield 'imagenette val', 'tgz', os.path.join(RAW, 'imagenette2-160.tgz'), r'/val/'


def items(kind, path, inc):
    if kind == 'folder':
        for root, _, fs in os.walk(path):
            for f in fs:
                if IMG.search(f):
                    p = os.path.join(root, f)
                    yield p, (lambda p=p: open(p, 'rb').read())
    elif kind == 'zip':
        z = zipfile.ZipFile(path)
        for n in z.namelist():
            if IMG.search(n) and re.search(inc, n):
                yield n, (lambda n=n: z.read(n))
    else:
        t = tarfile.open(path)
        for m in t.getmembers():
            if m.isfile() and IMG.search(m.name) and re.search(inc, m.name):
                yield m.name, (lambda m=m: t.extractfile(m).read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--per', type=int, default=300)
    a = ap.parse_args()
    from config import Config
    from cotton_classifier import CottonClassifierV2
    clf = CottonClassifierV2(Config.COTTON_V2_MODEL_PATH, Config.COTTON_V2_METRICS_PATH)
    known = {r['sha1'] for r in csv.DictReader(open(os.path.join(V2, 'catalog.csv')))}
    tmp = os.path.join(V2, '_live_check.jpg')
    L = ['# Saved v2 model on photos not used in training', '',
         f'Model {Config.COTTON_V2_MODEL_PATH}. Photos whose bytes appear in the training catalogue were skipped.', '',
         '| Photos | n | Not cotton | Healthy | Disease named | Not sure |', '|---|---|---|---|---|---|']
    t0, total = time.time(), 0
    for name, kind, path, inc in sources():
        if not os.path.exists(path):
            continue
        pool = list(items(kind, path, inc))
        random.Random(3).shuffle(pool)
        c, n = collections.Counter(), 0
        for p, opener in pool:
            if n >= a.per:
                break
            data = opener()
            if hashlib.sha1(data).hexdigest() in known:
                continue
            open(tmp, 'wb').write(data)
            try:
                d = clf.predict(tmp)
            except Exception:
                continue
            n += 1
            if d['status'] == 'not_cotton':
                c['not'] += 1
            elif d['status'] == 'confident' and clf.is_healthy(d['disease']):
                c['healthy'] += 1
            elif d['status'] == 'confident':
                c['disease'] += 1
            else:
                c['unsure'] += 1
        total += n
        if n:
            L.append(f"| {name} | {n} | {100 * c['not'] / n:.1f}% | {100 * c['healthy'] / n:.1f}% | "
                     f"{100 * c['disease'] / n:.1f}% | {100 * c['unsure'] / n:.1f}% |")
            print(L[-1], flush=True)
    if os.path.exists(tmp):
        os.remove(tmp)
    L += ['', f'{total} photos in {time.time() - t0:.0f} s ({(time.time() - t0) / max(total, 1):.2f} s per photo, '
          'including model loading).']
    open(os.path.join(ROOT, 'eval', 'results', 'cotton_v2', 'live_check.md'), 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
