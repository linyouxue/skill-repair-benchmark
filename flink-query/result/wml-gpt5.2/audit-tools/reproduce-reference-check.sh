#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
for split in "$@"; do
  out="$PWD/audit/reference-$split-reproduction"
  mkdir -p "$out"
  task="$PWD/exports/$split/tasks/flink-query"
  archive="flink-human-r2-$split-r01/workspace"
  if test "$split" = stages; then archive="flink-human-r2-stages-r03/workspace"; fi
  mkdir -p "$out/reference"
  tar -xJf audit/reference.tar.xz -C "$out/reference" "$archive/src" "$archive/pom.xml"
  cmp "$out/reference/$archive/pom.xml" "$task/environment/workspace/pom.xml"
  tag="flink-generalization:7621ba5-$split"
  printf 'FROM flink-generalization:7621ba5-base\nCOPY workspace /app/workspace\nWORKDIR /app/workspace\n' |
    sudo -n docker build -f - -t "$tag" "$task/environment" > "$out/build.log" 2>&1
  sudo -n docker image inspect "$tag" --format '{{.Id}} {{.Architecture}} {{.Os}} {{json .RootFS.Layers}}' > "$out/image.txt"
  cname=$(sudo -n docker create --network none --cpus 2 --memory 4g --hostname flink-reference --add-host flink-reference:127.0.0.1 --mount "type=bind,src=$task/verifier,dst=/verifier,readonly" --mount "type=bind,src=$out,dst=/logs/verifier" --entrypoint bash "$tag" -ec 'java -version; mvn -version; /opt/flink/bin/flink --version; bash /verifier/test.sh')
  trap 'sudo -n docker rm -f "$cname" >/dev/null' EXIT
  sudo -n docker cp "$out/reference/$archive/src/." "$cname:/app/workspace/src"
  rc=0
  sudo -n docker start -a "$cname" > "$out/verifier.log" 2>&1 || rc=$?
  sudo -n docker inspect "$cname" --format '{{.State.ExitCode}} {{.Image}} {{.State.OOMKilled}}' > "$out/container.txt"
  printf '%s\n' "$rc" > "$out/exit"
  sudo -n docker rm "$cname" >/dev/null
  trap - EXIT
  (cd "$out"; find . -maxdepth 1 -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum) > "$out/SHA256SUMS"
  python3 - "$out" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])
d=json.loads((p/'accuracy.json').read_text())
assert (p/'exit').read_text().strip()=='0'
assert d['task_passed'] and d['accuracy']==1.0, d['accuracy']
print(p.name, d['accuracy'], flush=True)
PY
done
