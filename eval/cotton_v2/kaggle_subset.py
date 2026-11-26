"""Download a sample of files from a big public Kaggle dataset, file by file.

python eval/cotton_v2/kaggle_subset.py OWNER/DATASET OUTNAME --per-folder 40 [--include REGEX] [--exclude REGEX]

Lists every file, keeps images matching --include, takes up to --per-folder
files from each folder (spread evenly over the sorted names), and saves them
under ~/Downloads/Cottondataset/v2/raw/OUTNAME/<folder>/. A manifest.csv records
the dataset, the original path and the size of each file.
"""
import argparse
import csv
import json
import os
import re
import subprocess
import urllib.parse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

RAW = os.path.expanduser('~/Downloads/Cottondataset/v2/raw')
IMG = re.compile(r'\.(jpe?g|png|bmp|webp)$', re.I)


def curl_json(url):
    out = subprocess.run(['curl', '-s', '-m', '60', url], capture_output=True, text=True).stdout
    return json.loads(out)


def list_files(ref):
    files, token = [], None
    while True:
        url = f'https://www.kaggle.com/api/v1/datasets/list/{ref}?pageSize=200'
        if token:
            url += '&pageToken=' + urllib.parse.quote(token)
        d = curl_json(url)
        files += [(f['name'], f.get('totalBytes', 0)) for f in d.get('datasetFiles', [])]
        token = d.get('nextPageTokenNullable')
        if not token:
            return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ref')
    ap.add_argument('outname')
    ap.add_argument('--per-folder', type=int, default=40)
    ap.add_argument('--include', default='')
    ap.add_argument('--exclude', default=r'$^')
    a = ap.parse_args()

    files = [(n, s) for n, s in list_files(a.ref)
             if IMG.search(n) and re.search(a.include, n) and not re.search(a.exclude, n)]
    by_dir = defaultdict(list)
    for n, s in sorted(files):
        by_dir[os.path.dirname(n)].append((n, s))
    print(f'{a.ref}: {len(files)} matching images in {len(by_dir)} folders', flush=True)

    out_root = os.path.join(RAW, a.outname)
    os.makedirs(out_root, exist_ok=True)
    man_path = os.path.join(out_root, 'manifest.csv')
    done = set()
    if os.path.exists(man_path):
        with open(man_path) as fh:
            done = {r['source_path'] for r in csv.DictReader(fh)}
    new_file = not os.path.exists(man_path)
    with open(man_path, 'a', newline='') as fh:
        w = csv.writer(fh)
        if new_file:
            w.writerow(['dataset', 'source_path', 'bytes', 'saved_as'])
        for d, items in sorted(by_dir.items()):
            k = min(a.per_folder, len(items))
            pick = [items[round(i * (len(items) - 1) / max(k - 1, 1))] for i in range(k)] if k else []
            sub = re.sub(r'[^\w.-]+', '_', d)[-80:] or 'root'
            os.makedirs(os.path.join(out_root, sub), exist_ok=True)
            def fetch(item):
                n, s = item
                dest = os.path.join(out_root, sub, re.sub(r'[^\w.-]+', '_', os.path.basename(n)))
                url = (f'https://www.kaggle.com/api/v1/datasets/download/{a.ref}/'
                       + urllib.parse.quote(n, safe=''))
                r = subprocess.run(['curl', '-sL', '--retry', '2', '-m', '120', '-o', dest, url])
                ok = r.returncode == 0 and os.path.exists(dest) and os.path.getsize(dest) > 1000
                return n, s, dest, ok
            todo = [it for it in dict.fromkeys(pick) if it[0] not in done]
            got = 0
            with ThreadPoolExecutor(8) as ex:
                for n, s, dest, ok in ex.map(fetch, todo):
                    if ok:
                        w.writerow([a.ref, n, s, os.path.relpath(dest, out_root)])
                        got += 1
            fh.flush()
            print(f'  {got:4d} new  {d}', flush=True)


if __name__ == '__main__':
    main()
