# Invalid attempt audit

Total infrastructure-invalid attempts: **15**.
These attempts are excluded from SkillAxe pass-rate denominators.

| Root cause | Attempts | Tasks |
|---|---:|---:|
| `docker_build` | 15 | 1 |

## Mitigations enabled

- Docker build and task containers use the explicit host proxy.
- apt uses a configurable mirror, ten retries, and 60-second I/O timeouts.
- Docker build transient failures use 10/30/60-second backoff.
- Agent installation and verifier timeouts can be raised by environment variables.
- OpenHands uses a host-cached, commit-pinned source archive and a 300-second ACP handshake budget.
- Official task sources, Skill bundles, and verifier scoring logic remain unchanged.
