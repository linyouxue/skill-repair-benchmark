# Rerun-only infrastructure and validation patches

- `bike-rebalance/environment/docker-compose.yaml`: grants `NET_ADMIN` so the
  executor can install per-agent egress-blocking iptables rules. The task stays
  in `no-network` mode.
- `simpo-code-reproduction/verifier/test.sh`: adds uv
  `--index-strategy unsafe-best-match` because the pinned
  `torch==2.1.2+cpu` wheel is on the PyTorch CPU index while other verifier
  dependencies are on PyPI.
- `adapters/common/bounded_edit.py`: dry-runs each complete edit sequence before
  accepting it. Sequential anchor conflicts are recorded as rejected attempts
  and regenerated within the existing three-attempt limit.
