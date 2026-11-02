#!/bin/sh
set -eu

: "${OPENAI_API_KEY:?OPENAI_API_KEY is required}"
: "${OPENAI_BASE_URL:?OPENAI_BASE_URL is required}"

if [ -z "${BENCHFLOW_BIN:-}" ]; then
  if [ -x /private/tmp/wml-benchflow-065/bin/bench ]; then
    BENCHFLOW_BIN=/private/tmp/wml-benchflow-065/bin/bench
  else
    BENCHFLOW_BIN="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/benchflow-venv/bin/bench"
  fi
fi

if [ ! -x "${BENCHFLOW_BIN}" ]; then
  echo "BenchFlow runtime missing: ${BENCHFLOW_BIN}" >&2
  exit 127
fi

exec "${BENCHFLOW_BIN}" \
  "$@" \
  --agent-env "BENCHFLOW_PROVIDER_API_KEY=${OPENAI_API_KEY}" \
  --agent-env "BENCHFLOW_PROVIDER_BASE_URL=${OPENAI_BASE_URL}" \
  --agent-env "GIT_CONFIG_COUNT=1" \
  --agent-env "GIT_CONFIG_KEY_0=url.git://host.docker.internal:9418/extensions.insteadOf" \
  --agent-env "GIT_CONFIG_VALUE_0=https://github.com/OpenHands/extensions"
