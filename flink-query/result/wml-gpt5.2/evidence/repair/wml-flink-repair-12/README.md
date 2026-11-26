# WML Flink repair-12

| 项目 | 结果 |
|---|---|
| 任务 | `flink-query / repair` |
| 模型路由 | `gpt-5.2@AIHUBMIX-default` |
| 连续正确率 | **95.92%（1270/1324）** |
| 审计判定 | 有效失败 |
| 运行状态 | 51 次请求均返回 HTTP 200，轨迹完整，执行器退出码为 0 |

644 个应输出作业全部正确。680 个应排除作业中正确排除了 626 个，额外输出了 54 个，因此未达到严格通过标准。官方评分器复算与原始评分一致。

本次沿用 WML 冻结 Skill、OpenHands 和 60 次父迭代预算，模型路由由 Azure 切换至 AIHUBMIX。仓库既有三组泛化成绩使用 Azure 路由。

- [运行索引与源证据哈希](run.json)
- [实际输出](verifier/actual-flink.txt) · [正式评分](verifier/accuracy.json) · [测试结果](verifier/ctrf.json)
- [ACP 轨迹](trajectory/acp_trajectory.jsonl.xz) · [模型请求轨迹](trajectory/llm_trajectory.jsonl.xz) · [ATIF 轨迹](trainer/atif.json.xz)
- [本次审计](audit/outcome.json) · [同镜像参考验收](audit/reference-repair-11/accuracy.json)
- [repair-10 审计](audit/repair-10-outcome.json) · [repair-11 审计](audit/repair-11-outcome.json)

执行器留存了 verifier 生成的正式输出。独立 Java 工作区和 JAR 未导出。
