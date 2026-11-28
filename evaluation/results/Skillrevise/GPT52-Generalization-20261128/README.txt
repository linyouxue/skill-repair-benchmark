SkillRevise / GPT-5.2 泛化实验最终汇总

实验范围：Flink repair -> scale/stages/combined；Paper train -> group_01/02/03/04；Reserves train -> group_01/02/03。
状态：3 个任务训练与选版完成，10/10 个泛化组具有有效评分。完成不代表全部任务成功。

训练集原始 Skill -> 最终选定 Skill：
flink-query: 72.51% -> 99.85%；接受首个修复候选。
paper-anonymizer: 94.03% -> 94.03%；修复候选得 92.54%，未接受修改，冻结原始 Skill。
reserves-at-risk-calc: 53.49% -> 100.00%；接受第二个修复候选。

泛化正确率（不是二元通过率）：
Flink scale: 99.70%；stages: 99.85%；combined: 0.00%。
Paper group_01: 95.52%；group_02: 97.22%；group_03: 97.92%；group_04: 97.01%。
Reserves group_01: 100.00%；group_02: 55.81%；group_03: 55.81%。

重要限制与失败记录：
1. Flink combined 的 0 分是有效任务失败。生成程序把 UNBOUNDED source 与 BATCH 执行模式组合，Flink 拒绝执行。verifier 正常产生评分，无 verifier_error。没有根据该测试反馈修改 Skill 或重跑以提高分数。
2. Flink 第二个训练候选遇到 verifier 环境命令 10 秒超时，execution_ok=False、reward=None。它不是有效失败，也未作为最终版本。现存证据不能唯一定位超时的环境命令；不声称这次历史基础设施事件已得到有效补评分。
3. 早期不完整诊断触发启发式回退的尝试已归为历史记录，不纳入当前正式结果。当前正式训练由严格诊断保护：必须完成全部训练证据窗口，否则禁止以回退诊断修复。
4. 所有测试使用各任务训练后冻结的完整 Skill 包；Paper group_04 在 group_01–03 完成后启动。附件保留，方法的修复范围为 SKILL.md。

修复与适配：独立进程隔离各泛化组的镜像清单；APT 证书/HTTPS/下载重试；有界模型传输重试；诊断失败禁止静默回退；相同有效训练基线和成功请求缓存复用。没有改动任务评分标准或参考答案。

证据：final_audit.json 包含精确分数、候选与执行编号、选择决定和已知限制。
审计核验 201 个固定源文件的 Git/SHA256 校验、13 个官方任务导出的可重现性、代码与快照哈希、3 个冻结包、10 组原始执行结果及 Paper 第四组顺序。22 项相关回归测试通过。
数据固定提交：bd120cfadbfee5bdf4ce46e7cc9d0246d45c198c。

完整原始实验目录（Ubuntu WSL）：
/home/eraser/skillrevise-handoff-experiments/runs/generalization-gpt52-20261124-r2
Windows 访问：
\\wsl.localhost\Ubuntu\home\eraser\skillrevise-handoff-experiments\runs\generalization-gpt52-20261124-r2
本目录是轻量汇总，不是全部原始轨迹的第二份拷贝；原始请求、候选和无效尝试仍保留在上述目录。

离线复核（不调用模型）：
wsl -d Ubuntu -- bash -lc 'cd /home/eraser/skillrevise-handoff-experiments && .venv/bin/python scripts/finalize_generalization_audit.py'
回归测试（在项目根目录 PowerShell）：
.venv\Scripts\python.exe -m pytest tests/test_generalization_final_audit.py tests/test_generalization_audit.py tests/test_generalization_isolated.py tests/test_generalization_gpt52.py -q -p no:cacheprovider

本目录仅提供本次实验汇总与离线审计结果，不包含完整原始实验轨迹；完整证据保留在上述 WSL 目录。
