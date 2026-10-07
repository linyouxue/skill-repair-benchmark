#!/usr/bin/env bash
set -euo pipefail
revision_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
container_id=6f7a78f160b4
rollout_id=latex-formula-extraction-opus47-manual-round-1-r001-recovery002
test "$(docker inspect "$container_id" --format '{{index .Config.Labels "com.docker.compose.project"}}')" = "$rollout_id"
test "$(docker inspect "$container_id" --format '{{index .Config.Labels "com.docker.compose.service"}}')" = main
test "$(docker inspect "$container_id" --format '{{.State.Running}}')" = false
docker inspect "$container_id" --format '{{json .State}}' > "$revision_root/container-before.json"
exec 9>/tmp/skillrepair-expanded-docker-start.lock
flock -n 9
docker start "$container_id" >/dev/null
flock -u 9
trap 'docker stop --time 10 "$container_id" >/dev/null' EXIT
docker exec -u 0 "$container_id" mkdir -p /tmp/verifier-revision-v1 /logs/verifier-revision-v1
docker cp "$revision_root/test_outputs.py" "$container_id:/tmp/verifier-revision-v1/test_outputs.py"
docker exec -u 0 \
  -e HTTP_PROXY=http://host.docker.internal:7890 \
  -e HTTPS_PROXY=http://host.docker.internal:7890 \
  "$container_id" bash -c 'set +e; export PATH=/usr/local/bin:$PATH; uvx --with pytest==8.4.1 --with pytest-json-ctrf==0.3.5 --with pillow==10.4.0 --with playwright==1.57.0 pytest --ctrf /logs/verifier-revision-v1/ctrf.json /tmp/verifier-revision-v1/test_outputs.py -rA -v > /logs/verifier-revision-v1/test-stdout.txt 2>&1; code=$?; echo "$code" > /logs/verifier-revision-v1/exit-code.txt; if [ "$code" = 0 ]; then echo 1; else echo 0; fi > /logs/verifier-revision-v1/reward.txt'
docker cp "$container_id:/logs/verifier-revision-v1/ctrf.json" "$revision_root/ctrf.json"
docker cp "$container_id:/logs/verifier-revision-v1/test-stdout.txt" "$revision_root/test-stdout.txt"
docker cp "$container_id:/logs/verifier-revision-v1/reward.txt" "$revision_root/reward.txt"
docker cp "$container_id:/logs/verifier-revision-v1/exit-code.txt" "$revision_root/exit-code.txt"
docker cp "$container_id:/root/latex_formula_extraction.md" "$revision_root/actual-after-reverification.md"
docker cp "$container_id:/root/latex_paper.pdf" "$revision_root/public-pdf-after-reverification.pdf"
echo 'One separate verifier evaluation finished; zero model calls.'
