# Evidence index

- `repair/`：生成顶层冻结 Skill 的真实 SkillAxe 诊断与迭代修复记录。包含 37 个窗口的请求审计、响应、失败重试、图片哈希、history、coverage 和模型调用归档；`PACKAGING_MANIFEST.json` 为逐文件 SHA-256 清单。
- `final_runs/run_01/`：`original22_run_01-attempt-06`，41/44，65/65 parent iterations，`max_iterations`。
- `final_runs/run_02/`：`original22_run_02-attempt-02`，43/44，65/65 parent iterations，`max_iterations`。
- `final_runs/run_03/`：`original22_run_03-attempt-01`，43/44，57/65 parent iterations，`end_turn`。

三次最终运行均保存执行器原生 `result.json`、`benchmark_result.json`、配置、完整 ACP/LLM 轨迹、verifier 记录和实际生成的原 Excel。为便于上传，超过 1 MiB 的文本/JSON 日志可能保存为 `.gz`；`PACKAGING_MANIFEST.json` 给出原始相对路径及解压后 SHA-256。`artifacts/stat_ocr.xlsx` 是从每次 verifier 输入的真实 Excel 逐字节复制，并与 `verifier/stat_ocr.xlsx` 校验一致。
