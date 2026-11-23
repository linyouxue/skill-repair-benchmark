# MMG2Skill 冻结 Skill

从 [A 组 2023 年的原 Skill 失败轨迹](../../diagnosis/README.md)起步，按上一轮 Skill、训练轨迹和评分反馈连续修复。修复与训练评测使用 Tatu GPT-5.2 xhigh。第 5 轮冻结完整 `xlsx` bundle，并在三个泛化组各运行一次。

| 修复轮次 | 训练正确数 | 改写记录 |
|---|---:|---|
| [第 1 轮](evidence/repair/round-01/round.json) | 24/43 | 改写 Skill |
| [第 2 轮](evidence/repair/round-02/round.json) | 17/43 | 改写触及 32,768 tokens，沿用第 1 轮 Skill |
| [第 3 轮](evidence/repair/round-03/round.json) | 24/43 | 改写 Skill |
| [第 4 轮](evidence/repair/round-04/round.json) | 17/43 | 改写 Skill |
| [第 5 轮](evidence/repair/round-05/round.json) | 24/43 | 冻结本轮 Skill |

第 3 至第 5 轮的改写请求使用 128,000 tokens 的输出额度。每轮保留根因分析、模型请求和响应、实际 Excel、轨迹及逐项评分。总成绩表中的训练分数取第 5 轮。

[完整 Skill](skills/xlsx/) · [第 5 轮训练原件](evidence/train/run_01/) · [三组测试](../../evaluation/results/methods/mmg2skill-gpt5.2/README.md)
