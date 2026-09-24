"""Restore lossless publication files. No model calls or experiment execution."""
import argparse, gzip, hashlib, json, os, shutil, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if os.name == 'nt' and not str(ROOT).startswith('\\\\?\\'):
    ROOT = Path('\\\\?\\' + str(ROOT))

def target(name):
    p = (ROOT / name).resolve()
    p.relative_to(ROOT.resolve())
    return p

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(4*1024*1024), b''): h.update(b)
    return h.hexdigest()

def restore(row, download=False):
    dest = target(row['path'])
    if dest.exists():
        if dest.stat().st_size != row['bytes'] or sha(dest) != row['sha256']:
            raise RuntimeError('Existing file differs: ' + row['path'])
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + '.partial')
    if download:
        url = row['url']
        if not url.startswith('https://github.com/linyouxue/skill-repair-benchmark/releases/download/'):
            raise ValueError('Unexpected asset URL')
        source = urllib.request.urlopen(url)
    else:
        source = gzip.open(target(row['stored_path']), 'rb')
    with source as inp, tmp.open('wb') as out: shutil.copyfileobj(inp, out)
    if tmp.stat().st_size != row['bytes'] or sha(tmp) != row['sha256']:
        raise RuntimeError('Checksum mismatch: ' + row['path'])
    tmp.replace(dest)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download-assets', action='store_true')
    args = parser.parse_args()
    manifest = json.loads((ROOT/'large-files.json').read_text(encoding='utf-8'))
    for row in manifest['compressed_text']: restore(row)
    if args.download_assets:
        for row in manifest['assets']: restore(row, True)
    print('Verified and restored requested files.')
