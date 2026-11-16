#!/usr/bin/env python3
"""Fetch the user-specified JPG task inputs at a pinned GitHub commit, without answers/holdout data."""
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "SkillRevise-JPG-adapter"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ref", default="main")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Output exists; use a fresh directory to retain immutable package provenance")
    api = "https://api.github.com/repos/linyouxue/skill-repair-benchmark"
    commit = json.loads(fetch(f"{api}/commits/{args.ref}"))["sha"]
    top = json.loads(fetch(f"{api}/git/trees/{commit}"))
    task_tree = next(entry["sha"] for entry in top["tree"] if entry["path"] == "jpg-ocr-stat")
    tree = json.loads(fetch(f"{api}/git/trees/{task_tree}?recursive=1"))
    if tree.get("truncated"):
        raise SystemExit("GitHub tree truncated; refusing partial package")
    selected = []
    for entry in tree["tree"]:
        if entry["type"] != "blob":
            continue
        relative = entry["path"]
        if (relative.startswith(("diagnosis/", "environment/"))
                or relative in ("tools/diagnosis_io.py", "README.md", "result/README.md", "task.md")):
            selected.append((entry, relative))
    if not any(relative == "tools/diagnosis_io.py" for _, relative in selected):
        raise SystemExit("No diagnosis_io.py in the requested package")
    args.output.mkdir(parents=True)
    manifest = []
    for index, (entry, relative) in enumerate(selected, 1):
        raw = fetch(f"https://raw.githubusercontent.com/linyouxue/skill-repair-benchmark/{commit}/jpg-ocr-stat/{entry['path']}")
        git_hash = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if git_hash != entry["sha"]:
            raise RuntimeError(f"Git blob hash mismatch: {relative}")
        destination = args.output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        manifest.append({"path": relative, "git_blob": git_hash, "sha256": hashlib.sha256(raw).hexdigest()})
        if index % 25 == 0:
            print(f"Fetched {index}/{len(selected)} files", flush=True)
    (args.output / "source_manifest.json").write_text(json.dumps({
        "repository": "https://github.com/linyouxue/skill-repair-benchmark",
        "commit": commit, "scope": "diagnosis and original environment only; no verifier/oracle/heldout",
        "files": manifest,
    }, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"Pinned source commit: {commit}; files: {len(manifest)}; output: {args.output}")


if __name__ == "__main__":
    main()
