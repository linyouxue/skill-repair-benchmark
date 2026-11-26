# Combined attempts

| Attempt | GPT-5.2 deployment | Outcome |
| --- | --- | --- |
| [Original](skillaxe-flink-group3/run.json) | AZUREOPENAI-default | Score 0, empty output. |
| r02 | AZUREOPENAI-default | HTTP 500 followed by executor idle timeout. |
| r03 | AZUREOPENAI-default | Stopped when the deployment was switched. |
| r04 | AIHUBMIX-default | Score 0, nonserializable source, missing output. |
| r05 | AIHUBMIX-default | Score 0, source type inference error, missing output. |
| [r06](skillaxe-flink-group3-audit-r06/run.json) | AIHUBMIX-default | Adopted valid failure, score 0.95770. |

The task, frozen Skill, verifier, and execution budget were reused. The r06 score was reproduced by rescoring the actual output. The full intermediate attempt records are retained in the cloud audit directory.
