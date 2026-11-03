# SkillAxe / Claude 4.7

- 最终 Skill 版本：`skillaxe-jpg-multimodal-20261021`，已冻结；5-Skill bundle 位于 `skills/`，SHA-256 为 `e39e41fca5d0044d7b5dd4eb05551759871d187c5f85aa6b437f8bc097323aa8`。
- 方法与代码版本：SkillAxe 顺序诊断/迭代修复机制，基于仓库 commit `66cdaa260c1bd2155102f0f4d98c566a07682a76`；adapter 为 `jpg-ocr-stat/tools/skillaxe_adapter.py`（SHA-256 `64b590ac940994351b79c9e74f90e001518a92be15c4e945e15c4051a5c9e4a9`）。
- 实际模型与配置：修复模型为 `gpt-5.2@AZUREOPENAI-default`（Tatumass）；三次最终执行均为 `paratera/Claude-Opus-4.7`、OpenHands CLI ACP、BenchFlow `v0.6.7`，每次最多 65 次 parent iteration。具体配置见各 run 的 `config.json` 和 `executor_request.json`。
- 修复材料与版本：使用 `jpg-ocr-stat/diagnosis` 提供的原任务、37 个诊断窗口和 22 张原始票据图；真实请求、响应、重试、用量和图片哈希见 `evidence/repair/`。
- 方法内部新增执行：无额外任务 rollout；保留 SkillAxe 的顺序 current-candidate/history 迭代过程。
- 三次最终执行与原 Excel：`original22_run_01-attempt-06`（41/44，65/65，`max_iterations`）、`original22_run_02-attempt-02`（43/44，65/65，`max_iterations`）、`original22_run_03-attempt-01`（43/44，57/65，`end_turn`）。原 Excel 分别位于 `evidence/final_runs/run_01/artifacts/stat_ocr.xlsx`、`run_02/...` 和 `run_03/...`，评分位于各 run 的 `verifier/`。
- 必要披露：未读取 oracle 解法、参考答案值或 verifier 断言；冻结前未使用 group2 泛化数据，泛化成绩不用于修改或重选 Skill；方法输出后未人工修改 Skill。基础设施失败与错误协议尝试未计入三次最终执行，但保留在原始实验工作区，不用其成绩替代有效运行。
- 证据入口：`evidence/README.md`。大轨迹以 gzip 无损压缩；每个 run 的 `PACKAGING_MANIFEST.json` 记录源相对路径和解压后 SHA-256。

| 评测集合 | 第1次字段正确率 | 第2次 | 第3次 | 三次均值 |
|---|---:|---:|---:|---:|
| 原22张小票（每次44字段） | 41/44（93.18%） | 43/44（97.73%） | 43/44（97.73%） | 42.3333/44（96.21%） |
