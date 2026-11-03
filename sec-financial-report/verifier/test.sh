#!/bin/bash
# SEC package: replace the original binary reward with answer-item accuracy.
# The untouched original tests and GT remain in the recorded source material.
set -euo pipefail
python3 /verifier/native_grade.py
