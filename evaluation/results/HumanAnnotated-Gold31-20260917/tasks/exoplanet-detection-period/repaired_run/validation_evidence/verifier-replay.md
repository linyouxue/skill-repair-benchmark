# r006 verifier-only diagnostic replay

## Status boundary

- The original automated rollout remains an infrastructure-invalid result:
  `execution_ok=false`, `comparable=false`, `task_passed=null`, and
  `reward=null` in `result.json`.
- This replay does **not** overwrite or reclassify that automated result as a
  formally comparable benchmark rollout.
- It does establish that the frozen task output produced by the completed
  Agent run passes the unmodified official verifier.

## Recovered frozen output

- Original rollout: `exoplanet-detection-period-round-1-r006`
- Original container ID:
  `074dbb1310befe17785c7ebf9c4e87bd3b633c0aad607ec3a8d6ee53a86de2dc`
- Container source: `/root/period.txt`
- Recovered host copy: `recovered/root/period.txt`
- Content: `5.35892\n` (8 bytes)
- The source and recovered copy were checked byte-for-byte with `cmp -s`
  before Docker Desktop was restarted and the residual container was removed.
- The ACP trajectory independently records the completed write command and the
  same final value.

## Failure and recovery procedure

1. The Agent completed with `end_turn` after 26 of 60 allowed iterations and
   wrote `/root/period.txt`.
2. Before the verifier started, the redundant mounted-log publication command
   `mkdir -p /logs/agent` timed out after 10 seconds because the Ubuntu WSL
   Docker Desktop control-plane bridge was intermittently stalled.
3. Automatic `docker compose down` and project force-cleanup also failed through
   the same degraded Docker API path, leaving the task container behind.
4. The output was extracted directly from the original container filesystem.
5. Docker Desktop was restarted; the same stopped container and writable layer
   were retained. The official task verifier directory was copied into
   `/verifier` without modification and `/verifier/test.sh` was executed in the
   original container with `/root/period.txt` unchanged.
6. After the verifier evidence was persisted, the exact residual container and
   its project network were removed. The built task image was retained.

## Diagnostic replay result

| Field | Result |
|---|---:|
| Model/provider calls during replay | 0 |
| Official verifier tests | 4 |
| Passed | 4 |
| Failed | 0 |
| Skipped | 0 |
| `reward.txt` | `1` |

Evidence:

- `recovered/root/period.txt`
- `verifier/ctrf.json`
- `verifier/reward.txt`
- `trajectory/acp_trajectory.jsonl`
- `result.json` (preserved original infrastructure-invalid result)

The task environment used the separately recorded task-local TUNA Debian mirror
and APT retry patch. Because that patch changes the task digest, every formally
compared condition must use the same environment patch.

