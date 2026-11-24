"""
Step 1 of the outside-photo tests: read photos and write 224x224 PNG copies.

No model, no scikit-learn needed (only numpy and OpenCV), so it can run on any
machine that can see the photos. It never changes the originals.

For each photo it records the md5 of the original bytes, original width/height
and file size, then saves a lossless 224x224 PNG made the same way
backend/cotton/features.py makes it (cv2 decode, which applies EXIF rotation,
then cv2.resize to 224x224 with the default bilinear setting). Feature
extraction later reads these PNGs, and the resize inside features.py is then a
no-op, so the numbers equal what the live app would compute.

Sources (all read-only):
  own614        the project's own photos (two Google Drive zips, 614 files)
  own296        the first, partial Drive export (md5 only, to prove it is a subset)
  eastwest      East West 2025 originals zip
  severity      Severity Levels originals zip
  ayaz_valtest  Ayaz 2024 Validation-Testing folder (all)
  ayaz_train    Ayaz 2024 Training Data folder (random sample per class)
  sarcld_aug    SAR-CLD augmented folder (random sample per class; augmented only)

Run:
  python eval/cotton_external/prep_images.py --downloads ~/mnt/Downloads --data ~/mnt/Cottondataset --out ~/mnt/Cottondataset/_work
Re-running resumes: photos already in manifest.csv are skipped.
"""
import argparse
import csv
import hashlib
import os
import random
import sys
import zipfile
from multiprocessing import Pool

import cv2
import numpy as np

VALID_EXT = ('.jpg', '.jpeg', '.png', '.bmp')
COLS = ['source', 'cls', 'sub', 'name', 'relpath', 'md5', 'bytes', 'width', 'height', 'png', 'status']
SAMPLE_SEED = 0

_ZIPS = {}


def _zip(path):
    if path not in _ZIPS:
        _ZIPS[path] = zipfile.ZipFile(path)
    return _ZIPS[path]


def read_bytes(task):
    if task['kind'] == 'zip':
        return _zip(task['path']).read(task['member'])
    with open(task['path'], 'rb') as fh:
        return fh.read()


def process(task):
    row = {k: '' for k in COLS}
    row.update(source=task['source'], cls=task['cls'], sub=task['sub'], name=task['name'],
               relpath=task['relpath'], png=task['png'] or '')
    try:
        data = read_bytes(task)
        row['md5'] = hashlib.md5(data).hexdigest()
        row['bytes'] = len(data)
        if not task['png']:
            row['status'] = 'hash_only'
            return row
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            row['status'] = 'unreadable'
            row['png'] = ''
            return row
        row['height'], row['width'] = img.shape[:2]
        if task.get('pre_shrink'):   # experiment: pretend the photo came from a smaller camera or an app
            scale = task['pre_shrink'] / max(img.shape[:2])
            if scale < 1:
                img = cv2.resize(img, (round(img.shape[1] * scale), round(img.shape[0] * scale)), interpolation=cv2.INTER_AREA)
        small = cv2.resize(img, (224, 224))
        out = task['png_abs']
        os.makedirs(os.path.dirname(out), exist_ok=True)
        cv2.imwrite(out, small, [cv2.IMWRITE_PNG_COMPRESSION, 3])
        row['status'] = 'ok'
    except Exception as e:  # unreadable or damaged file
        row['status'] = 'error: ' + str(e)[:80]
        row['png'] = ''
    return row


def _clean(s):
    return ' '.join(s.split())


def zip_tasks(source, zip_paths, strip, class_level, sub_level, png=True, cap=None):
    items = []
    for zp in zip_paths:
        z = zipfile.ZipFile(zp)
        for info in z.infolist():
            if info.is_dir() or not info.filename.lower().endswith(VALID_EXT):
                continue
            parts = info.filename.split('/')[strip:]
            if parts[0].startswith('.') or '__MACOSX' in info.filename:
                continue
            cls = _clean(parts[class_level])
            sub = _clean(parts[sub_level]) if sub_level is not None and len(parts) > sub_level + 1 else ''
            items.append(dict(source=source, kind='zip', path=zp, member=info.filename, cls=cls, sub=sub,
                              name=parts[-1], relpath=os.path.basename(zp) + '::' + info.filename, want_png=png))
    return cap_items(items, cap)


def folder_tasks(source, root, png=True, cap=None):
    items = []
    for cls_dir in sorted(os.listdir(root)):
        full = os.path.join(root, cls_dir)
        if not os.path.isdir(full) or cls_dir.startswith('.'):
            continue
        for f in sorted(os.listdir(full)):
            if f.lower().endswith(VALID_EXT) and not f.startswith('.'):
                items.append(dict(source=source, kind='file', path=os.path.join(full, f), member='',
                                  cls=_clean(cls_dir), sub='', name=f,
                                  relpath=os.path.join(os.path.basename(root), cls_dir, f), want_png=png))
    return cap_items(items, cap)


def cap_items(items, cap):
    if not cap:
        return items
    by = {}
    for it in items:
        by.setdefault(it['cls'], []).append(it)
    out = []
    for cls in sorted(by):
        group = sorted(by[cls], key=lambda t: t['relpath'])
        rng = random.Random(f'{SAMPLE_SEED}-{cls}')
        out.extend(group if len(group) <= cap else sorted(rng.sample(group, cap), key=lambda t: t['relpath']))
    return out


def build_tasks(downloads, data, only=None, cap=150):
    drive = 'Cotton Data set Man Mohan-20261120T'
    tasks = []
    want = lambda name: only is None or name in only
    if want('own614'):
        tasks += zip_tasks('own614', [os.path.join(downloads, drive + '184005Z-1-001.zip'),
                                      os.path.join(downloads, drive + '184005Z-1-002.zip')], 1, 0, None)
    if want('own296'):
        tasks += zip_tasks('own296', [os.path.join(downloads, drive + '154939Z-1-001.zip')], 1, 0, None, png=False)
    if want('eastwest'):
        tasks += zip_tasks('eastwest', [os.path.join(data, 'Cotton Leaf Image Dataset for Disease Classificati',
                                                     'Cotton_Original_Dataset.zip')], 1, 0, None)
    if want('severity'):
        tasks += zip_tasks('severity', [os.path.join(data, 'Cotton Leaf Disease Dataset with Severity Levels',
                                                     'Cotton-Original.zip')], 1, 0, 1)
    ayaz = os.path.join(data, 'A Dataset of Cotton Leaf Images for Disease Detection and Classification')
    if want('ayaz_valtest'):
        tasks += folder_tasks('ayaz_valtest', os.path.join(ayaz, 'Validation-Testing Data'))
    if want('ayaz_train'):
        tasks += folder_tasks('ayaz_train', os.path.join(ayaz, 'Training Data'), cap=cap)
    if want('sarcld_aug'):
        tasks += folder_tasks('sarcld_aug', os.path.join(data, 'Augmented Dataset'), cap=cap)
    return tasks


def selfcheck(tasks):
    checked = 0
    for t in tasks:
        if t['kind'] != 'file':
            continue
        a = cv2.imread(t['path'])
        b = cv2.imdecode(np.frombuffer(read_bytes(t), np.uint8), cv2.IMREAD_COLOR)
        assert a is not None and b is not None and a.shape == b.shape and np.array_equal(a, b), t['path']
        checked += 1
        if checked == 25:
            break
    print(f'selfcheck: imread and imdecode agree on {checked} files')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--downloads', required=True)
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--only', default='')
    ap.add_argument('--cap', type=int, default=150, help='photos per class for the sampled sources')
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--pre-shrink', type=int, default=0, help='experiment: shrink the longest side to this many pixels before the 224x224 resize')
    args = ap.parse_args()

    only = set(s for s in args.only.split(',') if s) or None
    tasks = build_tasks(os.path.expanduser(args.downloads), os.path.expanduser(args.data), only, args.cap)
    out = os.path.expanduser(args.out)
    os.makedirs(out, exist_ok=True)
    manifest = os.path.join(out, 'manifest.csv')
    done = set()
    if os.path.exists(manifest):
        with open(manifest, newline='') as fh:
            done = {(r['source'], r['relpath']) for r in csv.DictReader(fh) if r['status'] in ('ok', 'hash_only', 'unreadable')}
    selfcheck(tasks)
    todo = []
    for i, t in enumerate(tasks):
        if (t['source'], t['relpath']) in done:
            continue
        t['png'] = os.path.join(t['source'], hashlib.md5(t['relpath'].encode()).hexdigest()[:12] + '.png') if t.pop('want_png') else ''
        t['png_abs'] = os.path.join(out, 'png224', t['png']) if t['png'] else ''
        t['pre_shrink'] = args.pre_shrink
        todo.append(t)
    print(f'{len(tasks)} photos listed, {len(done)} already done, {len(todo)} to do', flush=True)
    new_file = not os.path.exists(manifest)
    with open(manifest, 'a', newline='') as fh, Pool(args.workers) as pool:
        w = csv.DictWriter(fh, fieldnames=COLS)
        if new_file:
            w.writeheader()
        for n, row in enumerate(pool.imap_unordered(process, todo, chunksize=4), 1):
            w.writerow(row)
            if n % 100 == 0:
                fh.flush()
                print(f'  {n}/{len(todo)}', flush=True)
    print('finished', flush=True)


if __name__ == '__main__':
    main()
