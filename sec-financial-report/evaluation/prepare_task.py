"""Export a single SEC v2 split for the existing BenchmarkExecutor."""

import argparse
import json
from pathlib import Path
import re
import shutil

PACKAGE = Path(__file__).resolve().parents[1]
EVALUATION = PACKAGE / "evaluation"
SOURCE = EVALUATION / "source"
SPLITS = ("train", "group_01", "group_02", "group_03")


def split_paths(split):
    if split not in SPLITS:
        raise ValueError(f"Unknown split: {split}")
    if split == "train":
        return SOURCE / "train_queries.json", PACKAGE / "verifier/expected_output.json"
    folder = EVALUATION / split
    return folder / "inputs/queries.json", folder / "verifier/expected_output.json"


def source_archives(archives_dir, periods):
    manifest = json.loads((EVALUATION / "manifest.json").read_text(encoding="utf-8"))
    paths = {}
    for period in periods:
        record = manifest["source"][period]
        relative = Path(record["path"])
        archive = PACKAGE / relative if archives_dir is None else Path(archives_dir) / relative.name
        if not archive.is_file():
            raise FileNotFoundError(f"Complete SEC archive required: {archive} ({record['url']})")
        if archive.stat().st_size != record["bytes"]:
            raise ValueError(f"Unexpected SEC archive size: {archive}")
        paths[period] = archive
    return paths


def render_task(query):
    classes = json.loads((SOURCE / "stock_classes.json").read_text(encoding="utf-8"))
    previous, current = query["baseline"], query["current"]
    cases = "\n".join(
        f"| {c['id']} | {c['manager']['name']} | {c['security']['issuer']} | {c['security']['title']} |"
        for c in query["cases"]
    )
    substitutions = {"BASELINE": previous, "CURRENT": current, "CASES": cases,
                     "CLASSES": ", ".join(f"`{c}`" for c in classes)}
    task = (SOURCE / "task_template.md").read_text(encoding="utf-8")
    return re.sub(r"\{\{([A-Z]+)\}\}", lambda m: substitutions[m[1]], task)


def render_dockerfile(query):
    previous, current = query["baseline"], query["current"]
    return f"""FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y python3 python3-pip python3-venv wget unzip && rm -rf /var/lib/apt/lists/*
WORKDIR /root
RUN pip3 install --break-system-packages pandas==2.3.3 rapidfuzz==3.14.3
COPY {previous}.zip {current}.zip /root/archives/
RUN mkdir /root/{previous} /root/{current} \
    && unzip -q -j /root/archives/{previous}.zip -d /root/{previous} \
    && unzip -q -j /root/archives/{current}.zip -d /root/{current}
RUN ln -s /root/{current} /root/2025-q2 && ln -s /root/{current}/INFOTABLE.tsv /root/INFOTABLE.tsv
"""


def prepare(split, output, archives_dir=None):
    query_path, reference = split_paths(split)
    output = Path(output).resolve()
    if output.is_relative_to(PACKAGE):
        raise ValueError("Export to a new path outside the package")
    query = json.loads(query_path.read_text(encoding="utf-8"))
    archives = source_archives(archives_dir, (query["baseline"], query["current"]))
    if not reference.is_file():
        raise FileNotFoundError(reference)
    output.mkdir(parents=True, exist_ok=False)
    (output / "task.md").write_text(render_task(query), encoding="utf-8", newline="\n")
    env = output / "environment"
    shutil.copytree(PACKAGE / "environment/skills", env / "skills")
    for period, source in archives.items():
        shutil.copyfile(source, env / f"{period}.zip")
    (env / "Dockerfile").write_text(render_dockerfile(query), encoding="utf-8", newline="\n")
    verifier = output / "verifier"
    shutil.copytree(PACKAGE / "verifier", verifier, ignore=shutil.ignore_patterns("expected_output.json", "__pycache__"))
    shutil.copyfile(reference, verifier / "expected_output.json")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=SPLITS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archives-dir", type=Path)
    args = parser.parse_args()
    print(prepare(args.group, args.output, args.archives_dir))
