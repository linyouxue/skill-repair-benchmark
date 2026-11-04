"""Acquire pinned training bytes and official SEC ZIPs; no model or agent calls."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af"
TASK = "tasks/sec-financial-report/"
SEC = "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/zip,application/octet-stream,*/*",
           "Accept-Encoding": "identity", "Connection": "close"}
SOURCES = [
    ("2025-q2", "environment/13f-2025-q2.zip", f"https://raw.githubusercontent.com/benchflow-ai/skillsbench/{COMMIT}/{TASK}environment/13f-2025-q2.zip", "training"),
    ("2025-q3", "environment/13f-2025-q3.zip", f"https://raw.githubusercontent.com/benchflow-ai/skillsbench/{COMMIT}/{TASK}environment/13f-2025-q3.zip", "training"),
    ("2024-q1", "evaluation/source/archives/2024-q1.zip", SEC + "01mar2024-31may2024_form13f.zip", "group_01"),
    ("2024-q2", "evaluation/source/archives/2024-q2.zip", SEC + "01jun2024-31aug2024_form13f.zip", "group_01"),
    ("2024-q3", "evaluation/source/archives/2024-q3.zip", SEC + "01sep2024-30nov2024_form13f.zip", "group_02"),
    ("2024-q4", "evaluation/source/archives/2024-q4.zip", SEC + "01dec2024-28feb2025_form13f.zip", "group_02"),
    ("2025-q4", "evaluation/source/archives/2025-q4.zip", SEC + "01dec2025-28feb2026_form13f.zip", "group_03"),
    ("2026-q1", "evaluation/source/archives/2026-q1.zip", SEC + "01mar2026-31may2026_form13f.zip", "group_03"),
]


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def acquire(row):
    quarter, relative, url, purpose = row
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        partial = path.with_suffix(path.suffix + ".part")
        last_error = None
        for attempt in range(3):
            fetch_url = url if attempt == 0 else url + f"?download=1&attempt={attempt}"
            try:
                request = urllib.request.Request(fetch_url, headers=HEADERS)
                with urllib.request.urlopen(request, timeout=90) as response, partial.open("wb") as out:
                    shutil.copyfileobj(response, out, length=2 * 1024 * 1024)
                if not zipfile.is_zipfile(partial):
                    raise ValueError("Download is not a complete ZIP: " + quarter)
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(2)
        if last_error is not None:
            raise last_error
        partial.replace(path)
    with zipfile.ZipFile(path) as archive:
        members = [{"name": item.filename, "bytes": item.file_size, "crc32": f"{item.CRC:08x}"}
                   for item in archive.infolist() if not item.is_dir()]
        names = {Path(item["name"]).name.upper() for item in members}
        if not {"SUBMISSION.TSV", "COVERPAGE.TSV", "INFOTABLE.TSV"} <= names:
            raise ValueError("Required SEC tables missing: " + quarter)
    result = {"quarter": quarter, "path": relative, "url": url, "purpose": purpose,
              "bytes": path.stat().st_size, "sha256": sha256(path), "members": members}
    print(json.dumps({"acquired": quarter, "bytes": result["bytes"], "tables": len(members)}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skillsbench", type=Path, required=True)
    args = parser.parse_args()
    repo = args.skillsbench.resolve()
    tree = subprocess.check_output(["git", "ls-tree", "-r", COMMIT, "--", TASK], cwd=repo).decode()
    original = []
    for line in tree.splitlines():
        meta, name = line.split("\t", 1)
        mode, kind, blob = meta.split()
        if kind != "blob":
            continue
        relative = name[len(TASK):]
        original.append({"path": relative, "git_blob": blob, "mode": mode})
        if relative.endswith(".zip"):
            continue
        destination = ("evaluation/source/original_verifier/" + Path(relative).name
                       if relative in {"verifier/test.sh", "verifier/test_outputs.py"} else relative)
        path = ROOT / destination
        data = subprocess.check_output(["git", "show", COMMIT + ":" + name], cwd=repo)
        if path.exists() and path.read_bytes() != data:
            raise ValueError("Refusing to replace an edited upstream file: " + relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    records = []
    errors = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(acquire, row): row for row in SOURCES}
        for future in as_completed(futures):
            try:
                records.append(future.result())
            except Exception as exc:
                errors.append({"quarter": futures[future][0], "error_type": type(exc).__name__, "message": str(exc)})
                print(json.dumps(errors[-1]), flush=True)
    for record in records:
        if record["purpose"] == "training":
            path = ROOT / record["path"]
            expected = next(r["git_blob"] for r in original if r["path"] == record["path"])
            h = hashlib.sha1(f"blob {path.stat().st_size}\0".encode())
            with path.open("rb") as f:
                for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
                    h.update(chunk)
            if h.hexdigest() != expected:
                raise ValueError("Original ZIP differs from pinned Git blob")
            record["verified_original_git_blob"] = expected
    metadata = {"skillsbench_commit": COMMIT, "original_files": original,
                "archives": sorted(records, key=lambda x: x["quarter"]), "errors": errors,
                "model_calls": 0, "docker_runs": 0}
    destination = ROOT / "evaluation/source/SOURCES.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
