"""Count image files per folder inside each downloaded archive.
Run: python eval/cotton_v2/inventory.py [zip names...]"""
import collections
import os
import sys
import tarfile
import zipfile

RAW = os.path.expanduser('~/Downloads/Cottondataset/v2/raw')
IMG = ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.heic', '.tif', '.tiff')


def names(path):
    if path.endswith('.zip'):
        with zipfile.ZipFile(path) as z:
            return z.namelist()
    with tarfile.open(path) as t:
        return t.getnames()


targets = sys.argv[1:] or sorted(f for f in os.listdir(RAW) if f.endswith(('.zip', '.tgz')))
for f in targets:
    try:
        n = names(os.path.join(RAW, f))
    except Exception as e:
        print(f'== {f}: cannot read ({e})')
        continue
    c = collections.Counter(os.path.dirname(x) for x in n if x.lower().endswith(IMG))
    print(f'== {f}: {sum(c.values())} images in {len(c)} folders')
    for d, k in sorted(c.items())[:60]:
        print(f'   {k:6d}  {d}')
