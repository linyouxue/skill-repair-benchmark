# 完整 LLM 轨迹下载

大轨迹由交付 ZIP 的 gzip 日志转为无损 XZ，发布在 [GitHub Release](https://github.com/linyouxue/skill-repair-benchmark/releases/tag/jpg-skillaxe-claude47-20261103)；已逐字节核对 XZ 与原 gzip 解压后的全部日志内容一致，未改写轨迹或运行记录。

下载后，将每个文件放入下表对应的 `trajectory/` 目录，文件名使用 `llm_trajectory.jsonl.xz`。表中原交付路径的 `.gz` 对应现在的 `.xz`；原归档清单对解压后日志的记录保持有效。其余 ACP 轨迹、运行元数据、原 Excel、评分与已有归档清单随本提交保存。

| 仓库相对路径 | 下载 | 字节数 |
|---|---|---:|
| `jpg-ocr-stat/evaluation/results/methods/skillaxe-claude4.7/group_02/run_01/trajectory/llm_trajectory.jsonl.gz` | [skillaxe-claude47-group02-run_01-llm_trajectory.jsonl.xz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/jpg-skillaxe-claude47-20261103/skillaxe-claude47-group02-run_01-llm_trajectory.jsonl.xz) | 10890736 |
| `jpg-ocr-stat/evaluation/results/methods/skillaxe-claude4.7/group_02/run_02/trajectory/llm_trajectory.jsonl.gz` | [skillaxe-claude47-group02-run_02-llm_trajectory.jsonl.xz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/jpg-skillaxe-claude47-20261103/skillaxe-claude47-group02-run_02-llm_trajectory.jsonl.xz) | 157792 |
| `jpg-ocr-stat/evaluation/results/methods/skillaxe-claude4.7/group_02/run_03/trajectory/llm_trajectory.jsonl.gz` | [skillaxe-claude47-group02-run_03-llm_trajectory.jsonl.xz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/jpg-skillaxe-claude47-20261103/skillaxe-claude47-group02-run_03-llm_trajectory.jsonl.xz) | 3419696 |
| `jpg-ocr-stat/evaluation/results/methods/skillaxe-claude4.7/incomplete_runs/group02_run_01-missing-excel/trajectory/llm_trajectory.jsonl.gz` | [skillaxe-claude47-incomplete-group02-group02_run_01-missing-excel-llm_trajectory.jsonl.xz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/jpg-skillaxe-claude47-20261103/skillaxe-claude47-incomplete-group02-group02_run_01-missing-excel-llm_trajectory.jsonl.xz) | 5462560 |

提交来源：用户提供的 `jpg-ocr-stat.zip`。仅排除 macOS 的 `.DS_Store` 和 `__MACOSX/._*` 资源分叉；已有 README、Skill、原 Excel、评分和元数据保持原样。

六次正式运行的 `n_skill_invocations` 均为 0；执行器记录 `skill_context_preload_observed=true`，并记录完整五份 Skill 正文预载。证据使用的是正文预载方式。

冻结 Skill：本提交的 [`jpg-ocr-stat/result/skillaxe-claude4.7/skills/`](../../../../result/skillaxe-claude4.7/skills/)，原任务与泛化目录在同一 Git 提交中冻结。

另保留 `incomplete_runs/group02_run_01-missing-excel/` 的真实记录；该次缺少原 Excel，未计入三次交付均值。
