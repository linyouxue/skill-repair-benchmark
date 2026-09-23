#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v uv >/dev/null 2>&1; then
  echo "未找到 uv。请先安装：https://docs.astral.sh/uv/" >&2
  exit 1
fi

uv venv --python 3.12 "$ROOT/.venv"
uv pip install --python "$ROOT/.venv/bin/python" -r "$ROOT/requirements.txt"
uv pip install --python "$ROOT/.venv/bin/python" -e "$ROOT/skill-repair-benchmark"

echo "环境已安装：$ROOT/.venv"
echo "下一步：cp '$ROOT/.env.example' '$ROOT/.env'，填写 key 后运行 check。"
