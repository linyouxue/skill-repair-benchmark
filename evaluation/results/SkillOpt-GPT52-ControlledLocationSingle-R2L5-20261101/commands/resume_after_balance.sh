#!/usr/bin/env bash
set -euo pipefail
ROOT="/Users/elsie/Desktop/SkillOpt-eva"
RUN="/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-skillopt-controlled-location-single-r2l5-v2-20261027"
source "$RUN/commands/env.sh"

# Refuse to create another formal attempt while the provider is unfunded.
"$ROOT/skill-repair-benchmark/.venv/bin/python" -B "$RUN/commands/probe_ai360.py"

# Completed candidates are skipped. Infrastructure-failed trials receive a new
# attempt-NNN directory, preserving the failed attempt and its error evidence.
"$RUN/commands/run_repairs_parallel.sh"
"$RUN/commands/prepare_completed.sh"
"$RUN/commands/run_evals_parallel.sh"

# Controls and semantic review remain separate phases. Run
# prepare_controls.py + run_control_evals_parallel.sh only when fresh controls
# are wanted for this experiment, then complete semantic-review.json before
# building the final scorecard.
python3 -B "$RUN/commands/refresh_code_snapshot.py"

