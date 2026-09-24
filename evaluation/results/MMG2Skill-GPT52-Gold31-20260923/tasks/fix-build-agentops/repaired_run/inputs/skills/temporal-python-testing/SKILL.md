---
name: temporal-python-testing
description: Test Temporal workflows with pytest, time-skipping, and mocking strategies
  (unit, integration, replay).
---

## Steps
1. Choose the testing level based on scope:
   - Unit: workflow logic with time-skipping; activities in isolation.
   - Integration: worker + workflow with mocked activities/external boundaries.
   - Replay: validate determinism against recorded histories.
2. For workflow tests, start a time-skipping `WorkflowEnvironment`, run a `Worker`, then execute the workflow and assert results.
3. Mock only external boundaries (activities/external clients), and keep workflow logic deterministic.
4. Use replay tests before/when changing workflow code paths that may affect determinism.
5. Keep tests fast and isolated; ensure environment/workers are properly shut down.
## Expected Result
Reliable, deterministic Temporal tests that run quickly and catch workflow regressions without flakiness.
