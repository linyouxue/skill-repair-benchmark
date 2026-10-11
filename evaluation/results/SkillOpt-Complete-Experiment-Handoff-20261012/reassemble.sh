#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$root_dir"

shasum -a 256 -c PARTS.sha256

archive="skillopt-analysis-upload-20261011.tar.zst"
parts=(archive-parts/skillopt-analysis-upload-20261011.tar.zst.part-*)
cat "${parts[@]}" > "$archive"
shasum -a 256 -c skillopt-analysis-upload-20261011.tar.zst.sha256

if command -v zstd >/dev/null 2>&1; then
  tar --use-compress-program=zstd -xf "$archive"
else
  echo "Archive assembled and verified. Install zstd before extracting it." >&2
fi
