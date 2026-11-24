"""
Step 3 of the outside-photo tests: find exact and near-duplicate photos.

Exact: same md5 of the original file bytes (from manifest.csv).
Near: a 256-bit average hash of a 16x16 grey thumbnail of the 224x224 copy, compared over all 8
rotations/flips of the other photo (so flipped or rotated copies, which is what augmentation makes,
are caught). Distance = smallest Hamming distance (0-256) over the 8 orientations.

Writes near_pairs.csv (pairs closer than --max-dist) and nn.csv (nearest other photo for every photo).

Run: python eval/cotton_external/dup_check.py --work <folder with manifest.csv and png224/>
"""
import argparse
import os

import cv2
import numpy as np
import pandas as pd

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import popcount64  # noqa: E402


def thumb_hash_variants(path):
    g = cv2.cvtColor(cv2.imread(path), cv2.COLOR_BGR2GRAY)
    t = cv2.resize(g, (16, 16), interpolation=cv2.INTER_AREA).astype(np.float32)
    out = []
    for k in range(4):
        r = np.rot90(t, k)
        for x in (r, np.fliplr(r)):
            out.append(np.packbits((x > x.mean()).ravel()).view('<u8'))   # 4 words of 64 bits
    return np.stack(out)   # (8, 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', required=True)
    ap.add_argument('--max-dist', type=int, default=24)
    args = ap.parse_args()
    work = os.path.expanduser(args.work)
    m = pd.read_csv(os.path.join(work, 'manifest.csv'), keep_default_na=False)
    m = m[m.status == 'ok'].reset_index(drop=True)
    H = np.stack([thumb_hash_variants(os.path.join(work, 'png224', p)) for p in m.png])   # (N, 8, 4)
    base = H[:, 0, :]
    N = len(m)
    best = np.full(N, 999, dtype=np.int32); arg = np.full(N, -1)
    pairs = []
    for i in range(0, N, 64):
        a = base[i:i + 64]                                   # (b, 4)
        d = np.full((len(a), N), 999, dtype=np.int32)
        for v in range(8):
            x = np.bitwise_xor(a[:, None, :], H[None, :, v, :])        # (b, N, 4)
            d = np.minimum(d, popcount64(x).sum(axis=2).astype(np.int32))
        for r in range(len(a)):
            d[r, i + r] = 999                                 # not itself
        best[i:i + len(a)] = d.min(axis=1); arg[i:i + len(a)] = d.argmin(axis=1)
        rr, cc = np.nonzero(d <= args.max_dist)
        pairs.extend((i + r, c, int(d[r, c])) for r, c in zip(rr, cc) if i + r < c)
    nn = pd.DataFrame({'png': m.png, 'source': m.source, 'cls': m.cls, 'nn_png': m.png.values[arg],
                       'nn_source': m.source.values[arg], 'nn_cls': m.cls.values[arg], 'nn_dist': best})
    nn.to_csv(os.path.join(work, 'nn.csv'), index=False)
    p = pd.DataFrame(pairs, columns=['i', 'j', 'dist'])
    p['png_a'] = m.png.values[p.i]; p['png_b'] = m.png.values[p.j]
    p['source_a'] = m.source.values[p.i]; p['source_b'] = m.source.values[p.j]
    p['cls_a'] = m.cls.values[p.i]; p['cls_b'] = m.cls.values[p.j]
    p.drop(columns=['i', 'j']).to_csv(os.path.join(work, 'near_pairs.csv'), index=False)
    print(len(p), 'pairs within', args.max_dist, 'bits')


if __name__ == '__main__':
    main()
