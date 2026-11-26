"""Download chosen files of public Mendeley Data sets. Usage: python download_mendeley.py ID:REGEX ..."""
import json, os, re, sys, urllib.request, subprocess
OUT = os.path.expanduser('~/Downloads/Cottondataset/v2/raw')
os.makedirs(OUT, exist_ok=True)
for arg in sys.argv[1:]:
    ds, pat = arg.split(':', 1)
    meta = json.loads(subprocess.run(['curl', '-s', '-m', '30', f'https://data.mendeley.com/public-api/datasets/{ds}'], capture_output=True, text=True).stdout)
    print(ds, meta['name'], 'v', meta['version'], (meta.get('data_licence') or {}).get('short_name'), flush=True)
    for f in meta['files']:
        if not re.search(pat, f['filename']):
            continue
        dest = os.path.join(OUT, f'mendeley_{ds}_' + re.sub(r'[^\w.]+', '_', f['filename']))
        if os.path.exists(dest + '.done'):
            print('  skip', f['filename']); continue
        print('  get', f['filename'], round(f['size'] / 1e6), 'MB', flush=True)
        r = subprocess.run(['curl', '-sL', '--retry', '3', '-C', '-', '-o', dest, f['content_details']['download_url']])
        if r.returncode == 0 and os.path.getsize(dest) == f['size']:
            open(dest + '.done', 'w').write(f['content_details'].get('sha256_hash', ''))
            print('  done', f['filename'], flush=True)
        else:
            print('  FAIL', f['filename'], flush=True)
