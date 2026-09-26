# 上传说明（尚未执行）

目标仓库：`https://github.com/linyouxue/skill-repair-benchmark`。
目标目录：`evaluation/results/SkillAdaptor-GPT41-SkillsBench31-20260923/`。

当前 `STATUS.json.status=incomplete`、`publication_ready=false`。GitHub写入凭据尚未配置，当前目录没有上传。

正式发布前完成以下具体工作：

1. 冻结修复后的executor配置，显式输出预算，全部31任务统一重跑；历史默认1024的generation保持作废。
2. 保存每条最终选定运行的请求、配置、轨迹、verifier、结果与input/protocol证据；基础设施失败单列，禁止reward择优。
3. 使用官方评测脚本接入最终executor证据，更新VFR、coverage、invalid/missing、逐任务时间与usage。
4. 更新README、STATUS、source配置hash及FILE_MANIFEST；所有bundle须仍与 `metadata/remote_bundle_hashes.json` 匹配。
5. 由有写入权限的用户配置 `gh auth login` 或Git凭据管理器。不要在命令、结果或仓库中写入密钥。

从干净的独立工作区创建分支，复制本目录至目标路径，检查diff后提交。示意命令（需由主任务执行，不自动执行）：

```bash
git clone https://github.com/linyouxue/skill-repair-benchmark.git skill-repair-benchmark-upload
cd skill-repair-benchmark-upload
git switch -c results/skilladaptor-gpt41-skillsbench31-20260923
# 将完成后的整个结果目录复制到 evaluation/results/ 下。
git add evaluation/results/SkillAdaptor-GPT41-SkillsBench31-20260923
git diff --cached --stat
git commit -m "Add SkillAdaptor GPT-4.1 SkillsBench31 repair evaluation"
git push -u origin results/skilladaptor-gpt41-skillsbench31-20260923
```

PR正文必须明确这是一轮proposal-stage adaptation而非完整held-out Validator复现，列出三个模型角色、端到端通过率及分母、人工对比结果、实际货币成本未知，以及58项低置信度判断未人工复核。若没有主仓库写权限，推到有权限的fork并创建PR。主任务创建PR后应将其关联到当前Codex任务。
