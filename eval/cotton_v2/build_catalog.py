"""
Step 1 of the v2 classifier: pull every photo we use out of the downloaded
archives into one folder of small copies, with one catalogue row per photo.

    python eval/cotton_v2/build_catalog.py            (resumable)

Output (under ~/Downloads/Cottondataset/v2/):
  img/<source>/<n>.jpg   copy with the shorter side resized to 288 px, EXIF rotation applied
  catalog.csv            source, original path, raw label, unified label, role, sha1 of the original bytes

role = 'cotton'   : a cotton leaf or plant photo; label = the disease (or '' if the set does not say)
role = 'negative' : not cotton (other crops, weeds, cannabis, objects); used only by the cotton/not-cotton gate
role = 'skip'     : known to be unusable (augmented copies, boll photos, duplicate Boll/Root rot folders)

Sources, licences and what each holds are in eval/cotton_v2/SOURCES.md.
"""

import csv
import hashlib
import io
import os
import random
import re
import sys
import tarfile
import zipfile
import zlib

from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = 200_000_000

HOME = os.path.expanduser('~')
V2 = os.path.join(HOME, 'Downloads', 'Cottondataset', 'v2')
RAW = os.path.join(V2, 'raw')
OLD = os.path.join(HOME, 'Downloads', 'Cottondataset')
OWN = os.path.join(HOME, 'VS CODE', 'Cotton Data set Man Mohan')
IMG_DIR = os.path.join(V2, 'img')
CATALOG = os.path.join(V2, 'catalog.csv')
SHORT_SIDE = 288
IMG_RE = re.compile(r'\.(jpe?g|png|bmp|webp)$', re.I)

# Unified cotton labels. Keys are lower-case patterns matched against the folder path.
COTTON_LABELS = [
    (r'bacterial[ _-]*(leaf[ _-]*)?blight', 'Bacterial leaf blight'),
    (r'curl', 'Cotton leaf curl virus disease'),
    (r'fus+arium', 'Fusarium wilt'),
    (r'verticillium', 'Verticillium wilt'),
    (r'alternaria', 'Alternaria leaf spot'),
    (r'target[ _-]*spot', 'Target spot'),
    (r'powdery[ _-]*mildew', 'Powdery mildew'),
    (r'aphid', 'Aphids'),
    (r'army[ _-]*worm', 'Army worm'),
    (r'jassid|leaf[ _-]*hopper', 'Leaf hopper (jassids)'),
    (r'herbicide', 'Herbicide damage'),
    (r'redd?ing', 'Leaf reddening'),
    (r'variegation', 'Leaf variegation'),
    (r'myrothecium', 'Myrothecium leaf spot'),
    (r'sooty', 'Sooty mould disease'),
    (r'anthracnose', 'Anthracnose'),
    (r'leaf[ _-]*enation', 'Leaf enation'),
    (r'healthy|fresh', 'Healthy'),
]


def cotton_label(path):
    p = path.lower()
    if 'diseased cotton' in p:
        return ''          # janmejaybhoi: diseased, disease not named
    for pat, lab in COTTON_LABELS:
        if re.search(pat, p):
            return lab
    return None


def every(items, k, seed):
    items = sorted(items)
    if k is None or len(items) <= k:
        return items
    return sorted(random.Random(seed).sample(items, k))


# (source id, archive path or folder, include regex on member path, exclude regex,
#  role, per-folder cap, label function)
def specs():
    def neg(_):
        return 'not_cotton'
    S = []
    for part in ('001', '002'):   # the full 614-file export (the loose folder is a partial copy)
        S.append(('own', f'{HOME}/Downloads/Cotton Data set Man Mohan-20261120T184005Z-1-{part}.zip',
                  r'', r'Boll rot|Root rot', 'cotton', None, cotton_label))
    S.append(('eastwest', f'{OLD}/Cotton Leaf Image Dataset for Disease Classificati/Cotton_Original_Dataset.zip',
              r'', r'$^', 'cotton', None, cotton_label))
    S.append(('severity', f'{OLD}/Cotton Leaf Disease Dataset with Severity Levels/Cotton-Original.zip',
              r'', r'$^', 'cotton', None, cotton_label))
    S.append(('ayaz', f'{OLD}/A Dataset of Cotton Leaf Images for Disease Detection and Classification',
              r'', r'[Bb]oll', 'cotton', 400, cotton_label))
    S.append(('sarcld', f'{RAW}/mendeley_b3jy2p6k8w_Original_Dataset.zip', r'', r'$^', 'cotton', None, cotton_label))
    S.append(('cosev', f'{RAW}/mendeley_y7544ghy3y_CoSev.zip', r'', r'\+', 'cotton', None, cotton_label))
    S.append(('janmejay', f'{RAW}/janmejaybhoi_cotton-disease-dataset.zip', r'', r'$^', 'cotton', None, cotton_label))
    S.append(('seroshkarim', f'{RAW}/seroshkarim_cotton-leaf-disease-dataset.zip', r'', r'$^', 'cotton', None, cotton_label))
    S.append(('raaavan', f'{RAW}/raaavan_cottonleafinfection.zip', r'', r'$^', 'cotton', None, cotton_label))
    S.append(('fatimacurl', f'{RAW}/fatimashakeel1_cottonleafcurl-dataset.zip', r'', r'$^', 'cotton', None, cotton_label))
    S.append(('dhamur', f'{RAW}/dhamur_cotton-plant-disease.zip', r'Main dataset|Cotton plant disease/',
              r'Black and white|HOG|40 Images', 'cotton', 300, cotton_label))
    # not cotton
    S.append(('plantvillage', f'{RAW}/mohitsingh1804_plantvillage.zip', r'/train/', r'$^', 'negative', 45, neg))
    S.append(('imagenette', f'{RAW}/imagenette2-160.tgz', r'/train/', r'$^', 'negative', 90, neg))
    S.append(('rice', f'{RAW}/vbookshelf_rice-leaf-diseases.zip', r'', r'$^', 'negative', None, neg))
    S.append(('pumpkin', f'{RAW}/tahmidmir_pumpkin-leaf-diseases-dataset-from-bangladesh.zip', r'', r'$^', 'negative', 60, neg))
    S.append(('hibiscus', f'{RAW}/sayooj98_hibiscus-leaf-dataset-small.zip', r'', r'$^', 'negative', 150, neg))
    S.append(('cottonweeds', f'{RAW}/mrumakantamaharana_cottonweedid15-resized-balanced.zip', r'', r'$^', 'negative', 30, neg))
    S.append(('deepweeds', f'{RAW}/imsparsh_deepweeds.zip', r'', r'$^', 'negative', 600, neg))
    S.append(('bpld', f'{RAW}/tinnybiswas_bangladeshi-plant-leave-dataset-bpld.zip', r'', r'$^', 'negative', 40, neg))
    S.append(('cannabis', f'{RAW}/cannabis_sample', r'', r'$^', 'negative', None, neg))
    S.append(('okra', f'{RAW}/okra_sample', r'', r'$^', 'negative', None, neg))
    S.append(('medicinal', f'{RAW}/medicinal_sample', r'', r'$^', 'negative', None, neg))
    return S


def members(src):
    """Yield (member path, opener) for every image in a zip, tgz or folder."""
    if os.path.isdir(src):
        for root, _, files in os.walk(src):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, src)
                if IMG_RE.search(f):
                    yield rel, (lambda full=full: open(full, 'rb').read())
    elif src.endswith('.zip'):
        z = zipfile.ZipFile(src)
        for n in z.namelist():
            if IMG_RE.search(n) and not os.path.basename(n).startswith('._') and '__MACOSX' not in n:
                yield n, (lambda n=n: z.read(n))
    else:
        t = tarfile.open(src)
        for m in t.getmembers():
            if m.isfile() and IMG_RE.search(m.name):
                yield m.name, (lambda m=m: t.extractfile(m).read())


def small_copy(data, dest):
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert('RGB')
    w, h = img.size
    s = SHORT_SIDE / min(w, h)
    if s < 1:
        img = img.resize((max(1, round(w * s)), max(1, round(h * s))), Image.BILINEAR)
    img.save(dest, 'JPEG', quality=90)
    return w, h


def main():
    only = set(sys.argv[1:])
    done = set()
    if os.path.exists(CATALOG):
        with open(CATALOG) as fh:
            done = {(r['source'], r['source_path']) for r in csv.DictReader(fh)}
    new = not os.path.exists(CATALOG)
    fh = open(CATALOG, 'a', newline='')
    w = csv.writer(fh)
    if new:
        w.writerow(['file', 'source', 'source_path', 'raw_label', 'label', 'role', 'sha1', 'orig_w', 'orig_h'])
    for sid, src, inc, exc, role, cap, labf in specs():
        if only and sid not in only:
            continue
        if not os.path.exists(src):
            print(f'MISSING {sid}: {src}', flush=True)
            continue
        by_dir = {}
        for n, opener in members(src):
            if re.search(inc, n) and not re.search(exc, n):
                by_dir.setdefault(os.path.dirname(n), []).append((n, opener))
        os.makedirs(os.path.join(IMG_DIR, sid), exist_ok=True)
        added = bad = 0
        for d, items in sorted(by_dir.items()):
            keep = {n for n in every([n for n, _ in items], cap, zlib.crc32((sid + d).encode()))}
            for n, opener in items:
                if n not in keep or (sid, n) in done:
                    continue
                lab = labf(n)
                r = role
                if lab is None:
                    r, lab = 'skip', ''
                data = opener()
                sha1 = hashlib.sha1(data).hexdigest()
                rel = os.path.join(sid, f'{sha1[:16]}.jpg')
                dest = os.path.join(IMG_DIR, rel)
                try:
                    ow, oh = small_copy(data, dest) if not os.path.exists(dest) else (0, 0)
                except Exception:
                    bad += 1
                    continue
                w.writerow([rel, sid, n, d, lab, r, sha1, ow, oh])
                added += 1
        fh.flush()
        print(f'{sid:13s} +{added} photos ({bad} unreadable)', flush=True)
    fh.close()


if __name__ == '__main__':
    main()
