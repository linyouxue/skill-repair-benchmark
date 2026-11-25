"""Verify delivered file bytes with Python3 standard library; no API/network/write actions."""
import sys,json,hashlib
from pathlib import Path
root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[2]
manifest=json.loads((root/'MANIFEST_SHA256.json').read_text());failures=[]
for rel,expected in manifest.items():
 p=root/rel
 if not p.is_file():failures.append({'file':rel,'problem':'missing'});continue
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 if h.hexdigest()!=expected:failures.append({'file':rel,'problem':'sha256 mismatch'})
print(json.dumps({'checked_files':len(manifest),'failed_files':failures,'file_integrity_passed':not failures,'scope':'File integrity only; does not certify model success or resolve documented evidence gaps.'},ensure_ascii=False,indent=2));sys.exit(1 if failures else 0)
