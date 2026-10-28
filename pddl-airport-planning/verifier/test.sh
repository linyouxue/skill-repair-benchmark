#!/usr/bin/env bash
set -euo pipefail
python3 -m pip install --quiet --break-system-packages unified-planning==1.3.0
python3 /verifier/native_grade.py pddl-airport-planning
