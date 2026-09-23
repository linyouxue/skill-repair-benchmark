# WML results

This directory packages the WML GPT-5.2 experiment. `submission.json` contains the currently published Core-25 evaluation subset. `experiment_manifest.json` inventories all 39 WML-repaired tasks and the verified original-pass task required by that Core-25 submission.

Each repaired task contains the complete final repaired Skill bundle, the preserved source-run evidence, and the canonical valid method-skill rollout. The source evidence release contains `result.json`, prompts, verifier output, and ACP trajectory; it did not publish synthetic `executor_request.json` or `benchmark_result.json`, so none were invented.
