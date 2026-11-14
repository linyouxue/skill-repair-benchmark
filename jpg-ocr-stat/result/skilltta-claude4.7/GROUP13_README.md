# SkillTTA / Claude-Opus-4.7：group1 与 group3 泛化实验

本目录仅包含 `group_01` 和 `group_03` 泛化实验结果。两组均严格沿用 group2 协议：同一冻结 Skill、OpenHands/BenchFlow、单并发、每次最多 65 次 parent iteration，每组独立运行 3 次。

- 模型：`Claude-Opus-4.7`
- 服务地址：`https://llmapi.paratera.com`
- 冻结 Skill SHA-256：`sha256:3b08efcd569bf2ce7819d884a0772e921cc155b3a0b259b5bc0a83ce296f2e35`
- API key 未写入提交材料。
- 未根据泛化结果修改或重新选择 Skill，未读取 oracle。

| 组别 | 第 1 次 | 第 2 次 | 第 3 次 | 三次均值 |
|---|---:|---:|---:|---:|
| group_01 | 29/40 = 72.5% | 30/40 = 75.0% | 25/40 = 62.5% | 84/120 = 70.0% |
| group_03 | 25/40 = 62.5% | 34/40 = 85.0% | 34/40 = 85.0% | 93/120 = 77.5% |

每个 `run_0N/` 均包含原始 Excel、评分文件、执行器配置与结果、ACP 轨迹、模型轨迹和 `strict_verification.json`。为满足 GitHub 单文件大小限制，模型轨迹保存为：

```text
trajectory/llm_trajectory.jsonl.gz.part-00
trajectory/llm_trajectory.jsonl.gz.part-01
...
```

恢复完整 gzip 文件：

```bash
cat trajectory/llm_trajectory.jsonl.gz.part-* > trajectory/llm_trajectory.jsonl.gz
gzip -t trajectory/llm_trajectory.jsonl.gz
```

机器可核验汇总见 `GROUP13_AUDIT.json`。
