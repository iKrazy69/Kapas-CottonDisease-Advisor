"""
Step 2: embed every catalogue photo once with the frozen ConvNeXt-Tiny.

    python eval/cotton_v2/embed_all.py [convnext|clip]   (resumable; only new files are embedded)

Writes ~/Downloads/Cottondataset/v2/embeddings.npz (convnext) or embeddings_clip.npz,
with arrays 'files' and 'X' (n x dim).
"""

import csv
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'backend'))

from cotton.embedder import Embedder  # noqa: E402

V2 = os.path.expanduser('~/Downloads/Cottondataset/v2')
CATALOG = os.path.join(V2, 'catalog.csv')
BATCH = 64


def main():
    backbone = sys.argv[1] if len(sys.argv) > 1 else 'convnext'
    OUT = os.path.join(V2, 'embeddings.npz' if backbone == 'convnext' else f'embeddings_{backbone}.npz')
    with open(CATALOG) as fh:
        files = list(dict.fromkeys(r['file'] for r in csv.DictReader(fh) if r['role'] != 'skip'))
    have_files, have_X = [], None
    if os.path.exists(OUT):
        d = np.load(OUT, allow_pickle=False)
        have_files, have_X = list(d['files']), d['X']
    have = set(have_files)
    todo = [f for f in files if f not in have]
    print(f'{len(files)} photos, {len(have)} already embedded, {len(todo)} to do', flush=True)
    if not todo:
        return
    emb = Embedder(backbone)
    if have_X is None:
        have_X = np.zeros((0, emb.dim), np.float32)
    new_files, new_X, t0 = [], [], time.time()
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        imgs, ok = [], []
        for f in chunk:
            try:
                imgs.append(emb.load_image(os.path.join(V2, 'img', f)))
                ok.append(f)
            except Exception as e:
                print(f'  unreadable {f}: {e}', flush=True)
        if imgs:
            new_X.append(emb.embed_images(imgs))
            new_files += ok
        if (i // BATCH) % 40 == 0:
            print(f'  {i + len(chunk)}/{len(todo)}  {time.time() - t0:.0f} s', flush=True)
    X = np.concatenate([have_X] + new_X).astype(np.float32)
    np.savez(OUT, files=np.array(have_files + new_files), X=X)
    print(f'saved {X.shape[0]} embeddings to {OUT}', flush=True)


if __name__ == '__main__':
    main()
