# MMG2Skill × SkillsBench 25 题诊断：可运行压缩包

这个包已包含固定版本的 MMG2Skill 源码、25 题任务提示、可见执行轨迹、诊断脚本和依赖清单。无需访问创建者电脑上的 `/Volumes/...` 或 `CausalFlow-main/...` 路径。压缩包中不含 API key、Gold、verifier、参考修复或已付费的试跑结果。

**研究结论：不建议把它作为 Skill 文件级诊断或修复主实验。** 原版 `ReviserAnalyzer` 不读取 Skill 文件。三题真实试跑的成败判断为 2/3，但没有产生文件级定位；详见 `experiments/skillsbench_cf25/PILOT_REPORT.md`。保留本包供需要纯轨迹诊断消融时复现。

## 运行

需要 macOS/Linux、Python 3.10+、可安装 Python 依赖的网络、OpenRouter 兼容 API key。把 key 用自己的密钥管理方式注入 `OPENROUTER_API_KEY`。解压后进入本目录：

```bash
bash run_all.sh --check                 # 不调用模型，核对 25 题和代码哈希
bash run_all.sh dialogue-parser         # 先跑一题
bash run_all.sh                         # 跑剩余 24 题并汇总
```

`run_all.sh` 首次创建 `.venv` 并安装 `requirements.txt`，然后运行原版 MMG2Skill 的 `ReviserAnalyzer`。已完成且输入、模型、配置相同的题会自动跳过。结果写到 `data/skillsbench_cf25/diagnoses/<task_id>/`，总表写到 `data/skillsbench_cf25/diagnosis_summary.csv`。请回传完整 `data/skillsbench_cf25` 目录；不要只截取总表。

如果 Python 命令名不同，可在运行前设置 `MMG2SKILL_PYTHON`。默认模型为 `openai/gpt-5.2`，默认接口为 OpenRouter。换用其他模型或接口时，分别设置 `MMG2SKILL_MODEL`、`MMG2SKILL_BASE_URL`，并在结果说明中记录；不同配置不能混进同一张比较表。

每题保存源轨迹 SHA-256、转换后的轨迹、发给模型的分段提示、原始 XML 回复、模型返回名、token 和服务商费用。25 题中只有 20 条是不带 completion guard 的 Original-Skill 轨迹；另 5 条在总表中保留条件标记。这个归档与旧版 25 题统一协议的 SkillsBench 快照不同，结果应单独报告。

本包原版源码来自 [NJU-LINK/MMG2Skill](https://github.com/NJU-LINK/MMG2Skill)，固定 commit 见 `UPSTREAM_COMMIT`。上游 MIT 许可见 `LICENSE`；SkillsBench Apache-2.0 许可见 `LICENSE_SkillsBench.txt`。
