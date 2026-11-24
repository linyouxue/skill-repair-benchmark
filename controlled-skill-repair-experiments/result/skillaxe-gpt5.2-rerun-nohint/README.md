# SkillAxe GPT-5.2 原题补项与无提示对照

按 2026-11-23 实验清单归集。原题补项共 3 题，无提示对照共 5 题；回流焊同时属于两项。

| 任务 | 原题补项 | 无提示对照 | 证据状态 | reward | 选定运行 |
|---|---|---|---|---|---|
| bike-rebalance | 是 |  | complete | 1.0 | bike-rebalance-a12 |
| data-to-d3 |  | 是 | complete | 0.0 | data-to-d3-a09 |
| dialogue-parser |  | 是 | complete | 1.0 | dialogue-parser-a01 |
| flink-query |  | 是 | complete | 0.0 | flink-query-a01 |
| manufacturing-equipment-maintenance | 是 | 是 | complete | 0.0 | manufacturing-equipment-maintenance-completion-a01 |
| multilingual-video-dubbing | 是 |  | complete | 1.0 | multilingual-video-dubbing-a16 |
| pddl-airport-planning |  | 是 | complete | 1.0 | pddl-airport-planning-a11 |

来源见各任务 PROVENANCE.json。每题 repaired_skill 为冻结修后包，repaired_run 保存最终执行记录及 verifier 结果。

单车调运与多语言配音来自本地 Skillaxe2 发布副本；其有效运行分别为 a12、a16。
其余四条已有无提示对照从当前 GitHub 发布结果读取；Flink 采用 SkillAxe-Infra-Rerun 的正式补跑记录。
历史汇总记录回流焊 a26 为有效 FAIL，但其独立运行证据缺失，因此不以汇总替代执行证据。回流焊使用哈希匹配历史导出的冻结 Skill 补执行。
回流焊 completion-a01 完成后，原 verifier 因 Debian 代理 502 安装失败。独立补评分使用保留的模型输出和未修改 verifier；原始 benchmark_result.json 保留 execution_ok=false，最终登记见 selected-result.json 和 VERIFIER_RECOVERY.json。
无提示对照指修复阶段无位置提示，任务执行仍提供修后 Skill。正常 verifier FAIL 计为有效完成。
