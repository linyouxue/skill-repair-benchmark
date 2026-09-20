from pathlib import Path
import gzip, json, hashlib, os
root = Path(__file__).resolve().parent
if os.name == 'nt':
    root = Path(chr(92)*2 + '?' + chr(92) + str(root))
for item in json.loads((root / "FILE_MANIFEST.json").read_text(encoding="utf-8")):
    if not item["gzip"]:
        continue
    packed = b"".join((root / p).read_bytes() for p in item["gzip_parts"]) if item.get("gzip_parts") else (root / item["published_path"]).read_bytes()
    data = gzip.decompress(packed)
    assert hashlib.sha256(data).hexdigest() == item["sha256"]
    dest = root / item["source_path"]
    if dest.exists():
        assert dest.read_bytes() == data
    else:
        dest.write_bytes(data)
print("All compressed trajectories restored.")
