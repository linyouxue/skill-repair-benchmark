"""Export a single SEC v2 split for the existing BenchmarkExecutor."""

import argparse
import json
from pathlib import Path
import re
import shutil

PACKAGE = Path(__file__).resolve().parents[1]
SPLITS = ("train", "test_period", "test_entity", "test_both")
DEFAULT_ARCHIVES = PACKAGE / "data/archives"


def source_archives(archives_dir, periods):
    manifest = json.loads((PACKAGE / "data/manifest.json").read_text(encoding="utf-8"))
    paths = {}
    for period in periods:
        record = manifest["source"][period]
        archive = Path(archives_dir) / Path(record["path"]).name
        if not archive.is_file():
            raise FileNotFoundError(f"Complete SEC archive required: {archive} ({record['url']})")
        if archive.stat().st_size != record["bytes"]:
            raise ValueError(f"Unexpected SEC archive size: {archive}")
        paths[period] = archive
    return paths


def prepare(split, output, archives_dir=DEFAULT_ARCHIVES):
    if split not in SPLITS:
        raise ValueError(f"Unknown split: {split}")
    output = Path(output).resolve()
    if output.is_relative_to(PACKAGE):
        raise ValueError("Export to a new path outside the package")
    selected = PACKAGE / "data" / split
    query = json.loads((selected / "queries.json").read_text(encoding="utf-8"))
    classes = json.loads((PACKAGE / "stock_classes.json").read_text(encoding="utf-8"))
    previous, current = query["baseline"], query["current"]
    archives = source_archives(archives_dir, (previous, current))
    cases = "\n".join(
        f"| {c['id']} | {c['manager']['name']} | {c['security']['issuer']} | {c['security']['title']} |"
        for c in query["cases"]
    )
    substitutions = {"BASELINE": previous, "CURRENT": current, "CASES": cases,
                     "CLASSES": ", ".join(f"`{c}`" for c in classes)}
    task = (PACKAGE / "task.md").read_text(encoding="utf-8")
    task = re.sub(r"\{\{([A-Z]+)\}\}", lambda m: substitutions[m[1]], task)
    output.mkdir(parents=True, exist_ok=False)
    (output / "task.md").write_text(task, encoding="utf-8", newline="\n")
    env = output / "environment"
    shutil.copytree(PACKAGE / "environment/skills", env / "skills")
    (env / "data").mkdir()
    for period, source in archives.items():
        shutil.copyfile(source, env / "data" / f"{period}.zip")
    dockerfile = f"""FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y python3 python3-pip python3-venv wget unzip && rm -rf /var/lib/apt/lists/*
WORKDIR /root
RUN pip3 install --break-system-packages pandas==2.3.3 rapidfuzz==3.14.3
COPY data/ /root/archives/
RUN mkdir /root/{previous} /root/{current} \
    && unzip -q -j /root/archives/{previous}.zip -d /root/{previous} \
    && unzip -q -j /root/archives/{current}.zip -d /root/{current}
RUN ln -s /root/{current} /root/2025-q2 && ln -s /root/{current}/INFOTABLE.tsv /root/INFOTABLE.tsv
"""
    (env / "Dockerfile").write_text(dockerfile, encoding="utf-8", newline="\n")
    verifier = output / "verifier"
    shutil.copytree(PACKAGE / "verifier", verifier)
    shutil.copyfile(selected / "verifier/expected_output.json", verifier / "expected_output.json")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=SPLITS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archives-dir", type=Path, default=DEFAULT_ARCHIVES)
    args = parser.parse_args()
    print(prepare(args.group, args.output, args.archives_dir))
