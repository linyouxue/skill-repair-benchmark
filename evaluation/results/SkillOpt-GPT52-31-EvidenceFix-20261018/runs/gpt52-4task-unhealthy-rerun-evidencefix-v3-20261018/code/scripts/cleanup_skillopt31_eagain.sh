#!/bin/bash
# Reclaim processes/Docker after the 5-worker EAGAIN pileup, then archive
# infra-failed SkillOpt task dirs so they can be retried.
set -u
ROOT="/Users/elsie/Desktop/SkillOpt-eva"
RUN_ID="skillsbench87-gpt52-skillopt-n3L4R2-20260920T130308Z"
RUN="$ROOT/experiments/$RUN_ID"
SO="$RUN/methods/skillopt"

echo "== leftover experiment processes =="
pgrep -fl "$RUN_ID" || echo none
pgrep -fl "run_method.py --run-id $RUN_ID" || true
pgrep -fl "parallel_phase.py --run-id $RUN_ID" || true

for pat in \
  "run_method.py --run-id $RUN_ID" \
  "parallel_phase.py --run-id $RUN_ID" \
  "$RUN_ID"
do
  pkill -f "$pat" 2>/dev/null || true
done
sleep 2
left=$(pgrep -f "$RUN_ID" || true)
if [ -n "${left:-}" ]; then
  echo "force-killing: $left"
  kill -9 $left 2>/dev/null || true
fi
echo "remaining experiment pids:"
pgrep -fl "$RUN_ID" || echo none

echo "== docker containers (skillopt / benchflow) =="
if command -v docker >/dev/null 2>&1; then
  docker ps -a --format '{{.ID}} {{.Names}}' | sed -n '1,80p' || true
  # Remove compose/task containers from this wave; do not prune images.
  ids=$(docker ps -aq --filter "name=skillopt" 2>/dev/null || true)
  if [ -n "${ids:-}" ]; then
    echo "removing skillopt containers"
    docker rm -f $ids || true
  fi
  # benchflow project names are task-id-skillopt-timestamp
  more=$(docker ps -aq --filter "name=-skillopt-" 2>/dev/null || true)
  if [ -n "${more:-}" ]; then
    echo "removing -skillopt- containers"
    docker rm -f $more || true
  fi
else
  echo "docker CLI not available (Desktop may be quit); skip container rm"
fi

echo "== archive infra-failed method dirs =="
mkdir -p "$SO"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
ARCH="$SO/_archived_infra_$STAMP"
mkdir -p "$ARCH"
moved=0
for t in dialogue-parser exoplanet-detection-period python-scala-translation sec-financial-report software-dependency-audit; do
  if [ -e "$SO/$t" ]; then
    mv "$SO/$t" "$ARCH/$t"
    echo "moved $t"
    moved=$((moved + 1))
  fi
done
echo "archived $moved dirs -> $ARCH"

if [ -d "$RUN/queue" ]; then
  : > "$RUN/queue/skillopt.done"
  : > "$RUN/queue/skillopt.failures"
fi

echo "== process pressure =="
ps -ax -o pid= 2>/dev/null | wc -l || true
echo DONE
