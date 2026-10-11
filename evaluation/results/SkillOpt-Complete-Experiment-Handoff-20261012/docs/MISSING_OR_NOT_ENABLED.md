# Missing, deleted, or not enabled

以下项目必须按“没有保存”或“没有启用”理解，不能从现有文件反推为完整原始记录。

## 没有启用

- 独立 train/validation/test task split：没有启用。
- held-out validation set：没有启用。
- 独立 final-test rerun：没有启用。
- 跨任务训练：没有启用；所有优化均按任务独立进行。
- 每个 diagnosis sample 各自生成一个 Skill 候选：没有启用。N=3 的诊断先合并，
  再生成该轮唯一候选 Skill。

## 没有完整保存

- 精确的、单文件形式的完整 optimizer HTTP request body/prompt：没有单独保存。
  可从 task context、Skill bundle、`evidence_bundle.json`、diagnosis/rewrite 输出和适配代码
  重建其来源，但不能保证逐字节还原当时请求。
- 85 个轮次中，54 个轮次保留了 162 个独立 `sample_*.json`；另外 31 个早期轮次
  没有单独样本文件，只保留合并后的 `diagnosis.json`、`diagnosis_raw.json` 和 rewrite。

## 按此前实验要求删除

- 硬件、网络、余额/API、Docker、依赖安装等无关因素导致的无效临时 method/job 目录，
  在重跑前按要求删除，因此不能提供已删除目录中的候选 Skill 和完整执行文件。
- 对应终端错误仍保存在 `runs/<run>/logs/terminal-*.log`。
- `bike-rebalance` 的最新无效修复候选没有保留为 method bundle；标准 submission 使用
  Original Skill fallback，并在 `run_status.json` 标记为 `original_skill_fallback`。

## 当前仍不健康但已保留的记录

- `fix-build-agentops`：round 2 verifier timeout；
- `fix-build-google-auto`：round 2 verifier timeout；
- `simpo-code-reproduction`：两轮 verifier dependency installation failure；
- `bike-rebalance`：Docker `iptables/NET_ADMIN` 权限问题，method 目录已按重跑规则清理。

这些任务都进入 GPT 31-task submission，但 `run_status.json` 保持不健康标记，不作为
可信的完整健康结果使用。

