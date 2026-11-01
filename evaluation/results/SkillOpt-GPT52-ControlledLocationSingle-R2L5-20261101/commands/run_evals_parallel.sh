#!/usr/bin/env bash
set -u -o pipefail
RUN="/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-skillopt-controlled-location-single-r2l5-v2-20261027"
# BenchFlow currently gives every Docker build the global image tag
# bf__task:latest. Multiple local eval workers can overwrite each other's
# architecture/task image manifests, so Docker evaluation is intentionally
# serialized even though candidate generation remains parallel.
"$RUN/commands/run_eval_worker.sh" 0 1

