#!/bin/bash
set -euo pipefail

# Native SkillsBench paths. Never reuse a reward from an earlier verification.
mkdir -p /logs/verifier
rm -f /logs/verifier/reward.txt /logs/verifier/reward.json \
  /logs/verifier/ctrf.json /logs/verifier/accuracy.json

# Original task dependency versions are retained.
apt-get update
apt-get install -y curl
curl -LsSf https://astral.sh/uv/0.9.7/install.sh | sh
source "$HOME/.local/bin/env"

status=0
uvx \
  --with pytest==8.4.1 \
  --with pytest-json-ctrf==0.3.5 \
  --with openpyxl==3.1.5 \
  pytest --ctrf /logs/verifier/ctrf.json /verifier/test_outputs.py -rA --tb=short \
  || status=$?

# Exit 1 means completed correctness failures. Other exits are infrastructure
# errors and must not be published as an ordinary zero accuracy.
if [ "$status" -ne 0 ] && [ "$status" -ne 1 ]; then
  exit "$status"
fi
python3 /verifier/write_reward.py
