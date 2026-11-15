# SkillAxe / Claude 4.7 / 泛化评测

- Skill 版本：沿用 `jpg-ocr-stat/result/skillaxe-claude4.7/skills/` 的冻结版本；5-Skill bundle SHA-256 为 `e39e41fca5d0044d7b5dd4eb05551759871d187c5f85aa6b437f8bc097323aa8`，未根据泛化成绩修改或重新选择。
- 数据版本：`jpg-ocr-stat-error-selected-challenge-v2` 的 `group_02`，20 张小票、每次固定 40 个日期/金额字段；manifest 冻结日期为 2026-10-25，仓库版本 `f65bc27d9fe078e7faee8c3bb7a143f4a5934d44`，该组标记为与 v1 一致。
- 执行配置：`paratera/Claude-Opus-4.7`、BenchFlow `aadad44acf27f193df98f438443116d514f51fb8`、OpenHands CLI `2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271`；每次最多 65 次 parent iteration，completion guard 共用剩余额度。
- 三次均从任务初始状态独立执行。每个 run 保存原生 `result.json`、`benchmark_result.json`、配置、完整 ACP/LLM 轨迹、verifier 原始输出和真实 `stat_ocr.xlsx`；超过 1 MiB 的文本轨迹使用 gzip 无损压缩，`PACKAGING_MANIFEST.json` 记录解压后 SHA-256。
- group1/group3 是后续按用户明确要求追加的泛化运行；未根据任何泛化成绩修改或重选 Skill。其完整说明与证据限制见 `GROUP13_README.md`、`GROUP13_AUDIT.json`。六次运行的 verifier 均成功完成评分，但执行器没有导出原 `stat_ocr.xlsx`，因此只作为明确披露缺失 Excel 的运行证据提交，没有伪造或重建 Excel。
- 早期 `group02_run_01-attempt-01` 虽有有效评分但执行器未保留原 Excel，故不计入 group2 三次交付，并如实保存在 `incomplete_runs/group02_run_01-missing-excel/`。

| 组别 | 第1次 | 第2次 | 第3次 | 均值 |
|---|---:|---:|---:|---:|
| group_02 | 97.50%（39/40） | 70.00%（28/40） | 92.50%（37/40） | **86.67%（104/120）** |
| group_01 | 65.00%（26/40） | 55.00%（22/40） | 62.50%（25/40） | **60.83%（73/120）** |
| group_03 | 80.00%（32/40） | 85.00%（34/40） | 85.00%（34/40） | **83.33%（100/120）** |

| 运行目录 | 原生 run ID | 已用父步/65 | 终止原因 | Excel SHA-256 |
|---|---|---:|---|---|
| `group_02/run_01` | `group02_run_02-attempt-16` | 46/65 | `end_turn` | `62e22b947420aba13478c1dc896f8c08b33fffa243d43027a169c3313a9084e9` |
| `group_02/run_02` | `group02_run_03-attempt-01` | 31/65 | `end_turn` | `7a093572e0d25abb55a840d658e4dadc17927fce85bcf64c95ec74b78f18d1a5` |
| `group_02/run_03` | `group02_run_04-attempt-01` | 50/65 | `end_turn` | `42814f6e6732c6ab205d145b2f6bcac5967a2e971c0087bacf0593a3d1de38e0` |

group1/group3 的 run ID、迭代数、终止原因、无损轨迹哈希及 Excel 缺失状态详见 `GROUP13_README.md` 和 `GROUP13_AUDIT.json`。
