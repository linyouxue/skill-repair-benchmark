#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
workspace=$(cd "$script_dir/../../.." && pwd)
executor_root="$workspace/skill-repair-benchmark"
python_bin="$executor_root/.venv/bin/python"
export PYTHONPATH="$script_dir/source/MMG2Skill_SkillsBench25_diagnosis:$script_dir/../../causalflow_runs/opus47-gold15-20260922/.deps:$executor_root/src"
export BENCHMARK_EXECUTOR_OPENHANDS_RUNTIME_ARCHIVE="/home/linyuanjing/.cache/benchmark-executor/openhands-cli/2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271/openhands-runtime-linux-x86_64.tar.gz"
export HTTP_PROXY="http://127.0.0.1:7890"
export HTTPS_PROXY="$HTTP_PROXY" http_proxy="$HTTP_PROXY" https_proxy="$HTTP_PROXY"
export NO_PROXY="localhost,127.0.0.1,::1,host.docker.internal,main"
export no_proxy="$NO_PROXY" AIOHTTP_TRUST_ENV=true
export BENCHMARK_EXECUTOR_CONTAINER_PROXY_URL="http://host.docker.internal:7890"
export BENCHMARK_EXECUTOR_CONTAINER_NO_PROXY="$NO_PROXY"
export BENCHMARK_EXECUTOR_BUILD_PROXY_URL="$BENCHMARK_EXECUTOR_CONTAINER_PROXY_URL"
export BENCHMARK_EXECUTOR_BUILD_CONTROL_PROXY_URL="$HTTP_PROXY"
export BENCHMARK_EXECUTOR_UBUNTU_APT_MIRROR_HOST="mirrors.tuna.tsinghua.edu.cn"
export BENCHMARK_EXECUTOR_INFRA_PROXY_MODE=explicit
export BENCHMARK_EXECUTOR_INFRA_HTTP_PROXY="$BENCHMARK_EXECUTOR_CONTAINER_PROXY_URL"
export BENCHMARK_EXECUTOR_INFRA_HTTPS_PROXY="$BENCHMARK_EXECUTOR_CONTAINER_PROXY_URL"
export BENCHMARK_EXECUTOR_INFRA_NO_PROXY="$NO_PROXY"
export BENCHMARK_EXECUTOR_VERIFIER_PROXY_MODE=explicit
export BENCHMARK_EXECUTOR_VERIFIER_HTTP_PROXY="$BENCHMARK_EXECUTOR_CONTAINER_PROXY_URL"
export BENCHMARK_EXECUTOR_VERIFIER_HTTPS_PROXY="$BENCHMARK_EXECUTOR_CONTAINER_PROXY_URL"
export BENCHMARK_EXECUTOR_VERIFIER_NO_PROXY="$NO_PROXY"
export LLM_MAX_OUTPUT_TOKENS=32768
unset LLM_REASONING_EFFORT
export PYTHONUNBUFFERED=1
test -x "$python_bin"
cd "$executor_root"
if [[ "${1:-}" == --run || "${1:-}" == --resume-pre-model || "${1:-}" == --resume-queue || "${1:-}" == --resume-fresh-queue ]]; then
  setsid --fork "$python_bin" "$script_dir/experiment.py" "$@" >> "$script_dir/batch.log" 2>&1 < /dev/null
else
  exec "$python_bin" "$script_dir/experiment.py" "$@"
fi
