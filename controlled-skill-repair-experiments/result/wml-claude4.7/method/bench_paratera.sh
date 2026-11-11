#!/bin/sh
set -eu

: "${PARATERA_API_KEY:?PARATERA_API_KEY is required}"
: "${PARATERA_BASE_URL:?PARATERA_BASE_URL is required}"

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/../../.." && pwd)"

if [ -z "${BENCHFLOW_BIN:-}" ]; then
  BENCHFLOW_BIN="${REPO_ROOT}/work/skill-repair-benchmark-upload/.venv/bin/bench"
fi

if [ -z "${BENCHFLOW_SOURCE:-}" ]; then
  BENCHFLOW_SOURCE="${REPO_ROOT}/work/skill-repair-benchmark-upload/src"
fi

if [ ! -x "${BENCHFLOW_BIN}" ]; then
  echo "BenchFlow runtime missing: ${BENCHFLOW_BIN}" >&2
  exit 127
fi

if [ ! -f "${BENCHFLOW_SOURCE}/benchflow/benchmark_executor.py" ]; then
  echo "Auditable BenchFlow source missing: ${BENCHFLOW_SOURCE}" >&2
  exit 127
fi

export PYTHONPATH="${BENCHFLOW_SOURCE}${PYTHONPATH:+:${PYTHONPATH}}"

VERSION="$(${BENCHFLOW_BIN} --version 2>/dev/null || true)"
case "${VERSION}" in
  "benchflow 0.6.7"*) ;;
  *)
    echo "BenchFlow 0.6.7 with persistent Skill preload evidence is required; got: ${VERSION}" >&2
    exit 126
    ;;
esac

exec "${BENCHFLOW_BIN}" \
  "$@" \
  --agent-env "GIT_CONFIG_COUNT=1" \
  --agent-env "GIT_CONFIG_KEY_0=url.git://host.docker.internal:9418/extensions.insteadOf" \
  --agent-env "GIT_CONFIG_VALUE_0=https://github.com/OpenHands/extensions"
