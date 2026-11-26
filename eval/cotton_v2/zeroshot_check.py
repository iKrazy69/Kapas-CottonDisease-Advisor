"""
Does CLIP's own text knowledge tell cotton from other plants?

    python eval/cotton_v2/zeroshot_check.py

For every catalogue photo (CLIP image numbers already cached), compares it with
text prompts: one set for cotton, one for many other plants and things. The
zero-shot cotton share is softmax over all prompts summed over the cotton ones.
Prints, per source, the median share and how many photos would pass at a few cut-offs.
No training on the photos is involved, so every source is "unseen" here.
"""
import csv
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V2 = os.path.expanduser('~/Downloads/Cottondataset/v2')
CLIP = os.path.join(ROOT, 'backend', 'cotton', 'models', 'clip-vit-base-patch16')

COTTON = ['a photo of a cotton leaf', 'a photo of a cotton plant', 'a close-up photo of a diseased cotton leaf',
          'a photo of cotton leaves in a field', 'a photo of a cotton leaf with spots']
OTHER_PLANTS = ['cannabis', 'marijuana', 'hemp', 'okra', 'hibiscus', 'pumpkin', 'squash', 'cucumber', 'tomato',
                'potato', 'pepper', 'grape', 'apple', 'cherry', 'peach', 'strawberry', 'raspberry', 'blueberry',
                'soybean', 'corn', 'maize', 'rice', 'wheat', 'sugarcane', 'banana', 'mango', 'papaya', 'guava',
                'lemon', 'orange', 'neem', 'tulsi', 'mint', 'aloe vera', 'betel', 'curry leaf', 'jasmine',
                'rose', 'maple', 'oak', 'ivy', 'fern', 'grass', 'weed', 'castor', 'sunflower', 'groundnut',
                'brinjal', 'eggplant', 'bean', 'pea', 'tobacco', 'tea', 'coffee', 'money plant', 'basil']
OTHER = ([f'a photo of a {p} leaf' for p in OTHER_PLANTS] + [f'a photo of a {p} plant' for p in OTHER_PLANTS]
         + ['a photo of an object', 'a photo of a person', 'a photo of an animal', 'a photo of a room',
            'a photo of food', 'a photo of a car', 'a photo of a building', 'a photo of soil'])


def text_features():
    import torch
    from transformers import CLIPModel, CLIPTokenizer
    m = CLIPModel.from_pretrained(CLIP, local_files_only=True).eval()
    tok = CLIPTokenizer.from_pretrained(CLIP, local_files_only=True)
    with torch.no_grad():
        t = m.get_text_features(**tok(COTTON + OTHER, padding=True, return_tensors='pt')).numpy()
    return t / np.linalg.norm(t, axis=1, keepdims=True), float(m.logit_scale.exp())


def cotton_share(Ximg, T, scale):
    logits = scale * Ximg @ T.T
    logits -= logits.max(1, keepdims=True)
    p = np.exp(logits)
    p /= p.sum(1, keepdims=True)
    return p[:, :len(COTTON)].sum(1)


def main():
    T, scale = text_features()
    rows = [r for r in csv.DictReader(open(os.path.join(V2, 'catalog.csv'))) if r['role'] in ('cotton', 'negative')]
    d = np.load(os.path.join(V2, 'embeddings_clip.npz'))
    idx = {f: i for i, f in enumerate(d['files'])}
    rows = [r for r in rows if r['file'] in idx]
    s = cotton_share(d['X'][[idx[r['file']] for r in rows]], T, scale)
    src = np.array([r['source'] for r in rows])
    role = {r['source']: r['role'] for r in rows}
    print(f'{"source":13s} role      n     median  >=0.1  >=0.3  >=0.5')
    for k in sorted(set(src), key=lambda k: (role[k], k)):
        v = s[src == k]
        print(f'{k:13s} {role[k]:8s} {len(v):5d}  {np.median(v):.3f}  '
              + '  '.join(f'{100 * np.mean(v >= c):5.1f}%' for c in (0.1, 0.3, 0.5)))
    np.save(os.path.join(V2, 'zeroshot_cotton_share.npy'), s)


if __name__ == '__main__':
    sys.exit(main())
