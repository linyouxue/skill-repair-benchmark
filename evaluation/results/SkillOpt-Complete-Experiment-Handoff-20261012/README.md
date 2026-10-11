# SkillOpt complete experiment handoff

这是 2026-10-12 整理并上传的 SkillOpt 完整实验交付目录，包含：

- GPT-5.2 baseline 的 31-task SkillOpt 修复实验；
- Opus-4.7 baseline 的 15-task SkillOpt 修复实验；
- 标准化 submission、逐轮索引、数据划分和缺失项说明；
- 完整实验目录的分卷压缩包及校验文件。

## 快速查看

- `docs/README.md`：实验材料总说明；
- `docs/ARTIFACT_MAP.md`：候选、执行、验证和选择记录的位置；
- `metadata/TASK_ROUND_INDEX.json`：task → round → proposal → candidate → rollout → verifier → decision 映射；
- `submissions/submission.json`：GPT 31-task 与 Opus 15-task submission 总索引；
- `docs/MISSING_OR_NOT_ENABLED.md`：未保存或未启用的材料说明。

## 恢复完整目录

GitHub 单文件上限不允许直接提交约 551 MiB 的压缩包，因此压缩包被拆成 7 个小于
100 MB 的分卷。请在本目录运行：

```bash
./reassemble.sh
```

脚本会校验所有分卷，合并为 `skillopt-analysis-upload-20261011.tar.zst`，校验完整包，
并解压到当前目录。完整包的 SHA-256 为：

```text
87cf6568df9c58916a613bc302396dd88a998ef7f3d025f80c9a62a35f5d90cd
```

本目录不包含 `.env`、API key、缓存或 Python 字节码。
