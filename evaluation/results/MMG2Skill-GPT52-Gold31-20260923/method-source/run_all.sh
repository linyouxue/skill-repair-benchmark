#!/usr/bin/env bash
set -euo pipefail

package_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$package_root"
input_dir=data/skillsbench_cf25
adapter=experiments/skillsbench_cf25/run_diagnosis.py

python_cmd=${MMG2SKILL_PYTHON:-}
if [[ -z "$python_cmd" ]]; then
  for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      python_cmd=$candidate
      break
    fi
  done
fi
if [[ -z "$python_cmd" ]]; then
  echo "Python 3.10+ is required. Set MMG2SKILL_PYTHON to its executable." >&2
  exit 2
fi
if [[ "${1:-}" == "--check" ]]; then
  "$python_cmd" "$adapter" verify --output "$input_dir"
  exit 0
fi

if ! "$python_cmd" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
  echo "MMG2SKILL_PYTHON must point to Python 3.10+." >&2
  exit 2
fi

if [[ -z "${OPENROUTER_API_KEY:-}" && -z "${OPENAI_API_KEY:-}" ]]; then
  echo "Set OPENROUTER_API_KEY or OPENAI_API_KEY before running." >&2
  exit 2
fi

python3 "$adapter" verify --output "$input_dir"

if [[ ! -x .venv/bin/python ]]; then
  "$python_cmd" -m venv .venv
fi

if [[ ! -f .venv/.mmg2skill_deps_ready ]]; then
  .venv/bin/python -m pip install -r requirements.txt
  touch .venv/.mmg2skill_deps_ready
fi

task_args=()
for task_id in "$@"; do
  task_args+=(--task "$task_id")
done

.venv/bin/python "$adapter" run \
  --output "$input_dir" \
  --model "${MMG2SKILL_MODEL:-openai/gpt-5.2}" \
  --base-url "${MMG2SKILL_BASE_URL:-https://openrouter.ai/api/v1}" \
  --resume "${task_args[@]}"

.venv/bin/python "$adapter" summarize --output "$input_dir"

echo "Results: $package_root/$input_dir/diagnosis_summary.csv"
