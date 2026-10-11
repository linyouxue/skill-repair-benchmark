# Three-terminal launch commands for both experiments

Each terminal first runs its disjoint GPT-5.2-baseline partition, then its disjoint Opus-4.7-baseline partition. This keeps total concurrency at three tasks while preserving complete data isolation.

```bash
/bin/bash /Users/elsie/Desktop/SkillOpt-eva/experiments/submissions-dual-skillopt-20261008/commands/run_worker.sh 0 3
```

```bash
/bin/bash /Users/elsie/Desktop/SkillOpt-eva/experiments/submissions-dual-skillopt-20261008/commands/run_worker.sh 1 3
```

```bash
/bin/bash /Users/elsie/Desktop/SkillOpt-eva/experiments/submissions-dual-skillopt-20261008/commands/run_worker.sh 2 3
```
