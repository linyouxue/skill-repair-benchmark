# 四条审计问题的历史记录与重跑结果

本组是原 55 条中的 4 个条目，已包含在 controlled22 / shared_controls33 中，不额外计数。manifest.json 给出每条旧尝试、新采用结果、模型配置、轨迹与修后 Skill 的相对路径。新结果沿用原目录保存，避免多份结果混淆。

| 问题条目 | 旧问题 | 重跑采用结果 |
|---|---|---|
| flink-query__all_faults | API / ACP 异常 | 有效失败，0 |
| single-manufacturing-equipment-maintenance-RI-001__condition_baseline | 工具 JSON 文本化、提前结束 | 有效失败，0 |
| single-manufacturing-equipment-maintenance-RI-002 | 工具 JSON 文本化、提前结束 | 有效通过，1 |
| location-data-to-d3 | SVG inner_text 兼容异常 | 授权修正 verifier、参考验收后重跑，有效通过，1 |

prior_selections/ 保留对应原始尝试和问题确认尝试的 result、JSONL 轨迹、verifier、运行日志及可取得的元数据。这里只复制原有文件，不补造未归档产物；原尝试的其他大体积运行文件仍在原本机 work 归档。旧异常记录不计入有效模型失败。D3 原 verifier、原分数、兼容差异及验收证据位于 evidence/source_package/evidence/。
