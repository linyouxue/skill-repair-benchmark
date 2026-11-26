# WML + GPT-5.2 运行索引

当前仅有一条审计有效结果的每组泛化成绩，不构成重复测量均值。无效 attempt 和 repair 重跑关系也全部列在 `runs.json`。

| 数据集 | 采用结果 | 正确率 |
|---|---|---:|
| `repair` | 无有效结果 | — |
| `scale` | `wml-flink-scale-04` | 72.39% |
| `stages` | `wml-flink-stages-07` | 72.36% |
| `combined` | `wml-flink-combined-04` | 95.77% |
| 三组等权均值 | — | 80.17% |

每个有效运行的 `run.json` 列出该目录中的执行器、verifier、输出和压缩轨迹材料。其他 attempt 保留在 `attempts/` 子目录。repair attempt 及总审计材料见 [结果交付](../../../../result/wml-gpt5.2/README.md)。
