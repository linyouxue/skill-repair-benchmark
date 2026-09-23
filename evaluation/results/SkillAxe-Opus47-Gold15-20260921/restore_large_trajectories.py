"""Restore the exact JSONL bytes archived with gzip for GitHub's size limit."""
import gzip
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
manifest = json.loads((root / 'compressed-trajectories.json').read_text(encoding='utf-8'))
for row in manifest['files']:
    source = (root / row['path']).resolve()
    target = (root / row['restored_path']).resolve()
    assert source.is_relative_to(root) and target.is_relative_to(root)
    body = gzip.decompress(source.read_bytes())
    assert len(body) == row['uncompressed_bytes']
    assert hashlib.sha256(body).hexdigest() == row['sha256']
    if target.exists():
        assert target.read_bytes() == body, f'Refusing to replace a modified file: {target}'
    else:
        target.write_bytes(body)
    print(target.relative_to(root))
