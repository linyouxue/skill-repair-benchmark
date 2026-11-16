#!/bin/bash
# Keep hyperparam suite supervisor alive until it finishes all arms.
set -euo pipefail
ROOT="/Users/elsie/Desktop/SkillOpt-eva"
LOGDIR="$ROOT/experiments/liveboards/gpt52-hyperparam-suite"
LOG="$LOGDIR/watchdog.log"
SUP_LOG="$LOGDIR/supervisor.log"
MARKER="$LOGDIR/supervisor.finished"

mkdir -p "$LOGDIR"
cd "$ROOT"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }

is_sup_running() {
  pgrep -f 'scripts/run_hyperparam_suite_supervisor.py' >/dev/null 2>&1
}

suite_finished() {
  grep -q 'supervisor: all arms finished' "$SUP_LOG" 2>/dev/null
}

launch_sup() {
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
  export PATH="/opt/homebrew/opt/python@3.12/libexec/bin:/opt/homebrew/bin:$PATH"
  export UV_CACHE_DIR="${UV_CACHE_DIR:-/private/tmp/skillopt-eva-uv-cache}"
  export PYTHONUNBUFFERED=1
  nohup /opt/homebrew/bin/python3.12 -u "$ROOT/scripts/run_hyperparam_suite_supervisor.py" \
    --workers 5 \
    --max-infra-sweeps 3 \
    --refresh-sec 180 \
    >>"$SUP_LOG" 2>&1 &
  log "launched supervisor pid=$!"
}

ensure_docker() {
  if docker info >/dev/null 2>&1; then
    return 0
  fi
  log "docker down; opening Docker Desktop"
  open -a Docker >/dev/null 2>&1 || true
}

log "watchdog start"
while true; do
  if suite_finished; then
    touch "$MARKER"
    log "suite finished; watchdog exit"
    exit 0
  fi
  ensure_docker
  if ! is_sup_running; then
    log "supervisor missing; relaunching"
    launch_sup
  fi
  # opportunistic liveboard refresh (supervisor also refreshes)
  /opt/homebrew/bin/python3.12 "$ROOT/scripts/export_liveboard.py" \
    --suite "$ROOT/configs/gpt52_hyperparam_suite.json" \
    >>"$LOGDIR/refresh.log" 2>&1 || true
  sleep 180
done
