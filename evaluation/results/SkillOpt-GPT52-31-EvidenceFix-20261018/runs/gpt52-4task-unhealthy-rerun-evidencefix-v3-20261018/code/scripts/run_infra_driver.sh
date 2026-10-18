#!/bin/bash
set -euo pipefail
cd /Users/elsie/Desktop/SkillOpt-eva
set -a; source .env; set +a
export PATH="/opt/homebrew/opt/python@3.12/libexec/bin:/opt/homebrew/bin:$PATH"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/private/tmp/skillopt-eva-uv-cache}"
export PYTHONUNBUFFERED=1
LOG=experiments/liveboards/gpt52-hyperparam-suite/infra_rerun.log
log(){ echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }

run_arm(){
  local RID=$1 N=$2 L=$3 R=$4 W=$5 LABEL=$6
  export SKILLOPT_EVA_DIAGNOSIS_N=$N SKILLOPT_EVA_EDIT_BUDGET_L=$L SKILLOPT_EVA_REPAIR_ROUNDS_R=$R
  unset SKILLOPT_EVA_SMOKE DEBUG || true
  mkdir -p "experiments/${RID}/logs"
  for attempt in 1 2 3; do
    /opt/homebrew/bin/python3.12 - <<PY
import shutil, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,'scripts')
from run_hyperparam_suite_supervisor import load_tasks, is_infra_contaminated
rid='$RID'
so=Path('experiments')/rid/'methods'/'skillopt'
ti,cl,ms=[],[],[]
for t in load_tasks():
  d=so/t
  if not (d/'method_result.json').is_file():
    ms.append(t)
    if d.is_dir():
      stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
      arch=so/f'_archived_partial_{stamp}'; arch.mkdir(parents=True, exist_ok=True)
      dest=arch/t
      if dest.exists(): dest=arch/f'{t}__again'
      shutil.move(str(d), str(dest))
    continue
  (ti if is_infra_contaminated(d) else cl).append(t)
if ti:
  stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
  arch=so/f'_archived_infra_{stamp}'; arch.mkdir(parents=True, exist_ok=True)
  for t in ti:
    shutil.move(str(so/t), str(arch/t))
pending=list(dict.fromkeys(ti+ms))
q=Path('experiments')/rid/'queue'
(q/'skillopt.txt').write_text('\\n'.join(pending)+('\\n' if pending else ''))
(q/'skillopt.done').write_text('\\n'.join(cl)+('\\n' if cl else ''))
(q/'skillopt.failures').write_text('')
print(rid, 'attempt', $attempt, 'pending', len(pending), pending, 'clean', len(cl))
Path('/tmp/skillopt_pending_count_$LABEL').write_text(str(len(pending)))
PY
    pending=$(cat /tmp/skillopt_pending_count_$LABEL)
    if [ "$pending" = "0" ]; then
      log "$LABEL: cleared"
      break
    fi
    if ! docker info >/dev/null 2>&1; then open -a Docker; sleep 30; fi
    log "$LABEL: launch attempt=$attempt workers=$W pending=$pending"
    /opt/homebrew/bin/python3.12 -u scripts/parallel_phase.py --run-id "$RID" --phase skillopt --workers "$W" \
      >> "experiments/${RID}/logs/infra_rerun_phase.log" 2>&1 || true
    log "$LABEL: phase exited attempt=$attempt"
  done
}

log "driver start n5 then n3 (continue finished at 05:24:15)"
run_arm core25-gpt52-skillopt-n5L4R2-20260919 5 4 2 1 n5L4R2
run_arm core25-gpt52-skillopt-n3L4R5-20260919 3 4 5 5 n3L4R5

/opt/homebrew/bin/python3.12 - <<'PY'
import json,sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,'scripts')
from run_hyperparam_suite_supervisor import load_tasks, is_infra_contaminated, method_done_count, refresh_liveboard
ROOT=Path('.')
def classify(rid):
  so=ROOT/'experiments'/rid/'methods'/'skillopt'
  ti,cl,ms=[],[],[]
  for t in load_tasks():
    d=so/t
    if not (d/'method_result.json').is_file(): ms.append(t); continue
    (ti if is_infra_contaminated(d) else cl).append(t)
  return ti,cl,ms
def passed(rid):
  so=ROOT/'experiments'/rid/'methods'/'skillopt'
  n=0
  for t in load_tasks():
    p=so/t/'method_result.json'
    if not p.is_file(): continue
    try:
      if json.loads(p.read_text()).get('task_passed') is True: n+=1
    except: pass
  return n
stamp=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
lines=['', f'## Rerun results ({stamp})', '']
for rid,lab in [('core25-gpt52-skillopt-n3L4R5-20260919','n3L4R5'),('core25-gpt52-skillopt-n5L4R2-20260919','n5L4R2')]:
  ti,cl,ms=classify(rid)
  lines += [f'### {lab}', f'- clean_done: {len(cl)}/25', f'- leftover_infra: {ti}', f'- leftover_missing: {ms}', f'- method_done: {method_done_count(rid)}/25', f'- passed_among_results: {passed(rid)}', '']
  print(lab, 'clean',len(cl),'infra',ti,'missing',ms,'passed',passed(rid))
report=ROOT/'experiments/liveboards/gpt52-hyperparam-suite/infra_audit_report.md'
report.write_text(report.read_text().rstrip()+'\n'+'\n'.join(lines)+'\n', encoding='utf-8')
refresh_liveboard()
PY
log "driver ALL DONE"
