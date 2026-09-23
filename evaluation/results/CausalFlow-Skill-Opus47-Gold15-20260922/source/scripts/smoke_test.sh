#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "请先运行 bash scripts/setup.sh" >&2
  exit 1
fi

cd "$ROOT"
"$PYTHON" -m compileall -q \
  causal_attribution.py causal_flow.py causal_graph.py counterfactual_repair.py \
  llm_client.py replay_graph skillsbench_replay repro_wrappers scripts
"$PYTHON" -m unittest -q \
  tests.test_text_processor \
  tests.test_replay_graph \
  tests.test_repair_context \
  tests.test_llm_client_limits

echo "离线 smoke test 通过。"
