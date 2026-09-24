# MMG2Skill Analyzer × SkillsBench：真实模型三题试跑

日期：2026-09-20。上游 MMG2Skill commit：`c12d8b1e8998ed76bad2ab85425959f44ca085b8`。模型：OpenRouter `openai/gpt-5.2`，服务端返回同名模型。每次模型调用最多输出 2,048 token，未指定额外 reasoning 或 temperature 参数。输入为现有代表性归档的任务提示及可见 ACP 工具轨迹。脚本未把归档 PASS/FAIL、verifier、Gold 或 Skill 正文发送给诊断器。模型输出后，才离线对照归档结果和已发布的 Gold。

| 题目 | 归档结果 | Analyzer 自评 | 观察 |
| --- | --- | --- | --- |
| `dialogue-parser` | FAIL，reward 0.833 | `likely_success` | **误判**。两条 issue 都是随后已纠正的工具调用错误。轨迹中出现自动创建 `End` 节点，但诊断器没有指出它导致的图可达性错误。归档 verifier 的 6 项中有 1 项失败，失败断言是 `End` 节点不可达；已发布 Gold 将终止节点语义列为 Skill 缺陷。 |
| `video-silence-remover` | FAIL | `likely_failure` | 成败判断正确。诊断器指出任务提前结束、缺少输出文件；没有定位到已发布的时间对齐、区间合并或阈值说明缺陷。这条轨迹没有走到足以观察这些缺陷的阶段。 |
| `suricata-custom-exfil` | PASS | `likely_success` | 成败判断正确。三条 issue 是执行中遇到并已绕过的配置或规则写法问题。 |

三题成败自评为 **2/3**，只说明这三条轨迹的粗粒度判断。两条失败题都没有文件级 Skill 定位输出；这是原版 Analyzer 的设计边界。它不读取 Skill 正文，`issues` 字段也没有文件位置。视频题的“未完成”诊断有用，但无法直接转成 Skill 修复候选。对我们当前的文件级诊断和修复主实验，**不建议继续委托同学把这个适配器跑满 25 题**。如果后续需要独立研究“无评分轨迹自评”，可以继续使用脚本，结果应单列为辅助消融。

本次共 4 次模型调用，输入 21,790 token，输出 3,274 token；服务商返回费用合计约 **$0.084**。逐题原始 XML、请求审计和用量保存在创建者本地的 `runs/pilot-20260920/`；交接 ZIP 不包含这次付费试跑的输出。同学运行后会在 ZIP 内自己的 `data/skillsbench_cf25/diagnoses/` 得到同结构结果。本次未执行 MMG2Skill 的教程提取、Refiner 修订或新一轮 SkillsBench agent/verifier 运行。现有归档与旧统一 25 题协议快照也不一致，因此这些数字不应并入旧协议主表。
