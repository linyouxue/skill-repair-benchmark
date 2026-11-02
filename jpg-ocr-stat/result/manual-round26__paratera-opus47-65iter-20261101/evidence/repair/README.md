# 人工主线 Round26 修复来源

这是一份已有人工修复候选，原样冻结后复测；不是 SkillHone 等自动方法新生成的 Skill。`annotation.md` 是实际保留的主线人工修复记录，记录至 Round20；其中历史模型、任务修改和预算按原记录保留。后续 Round21–26 没有同样完整的修复对话，不能声称这里保存了完整的逐轮人工/Codex聊天或全部修复模型调用。历次辅助模型身份未完整留证，未知；不把历史运行器日志冒充修复端对话。

已有公开[历史索引、全部尝试及轨迹](https://github.com/linyouxue/skill-repair-benchmark/tree/6adffb1e027b55b8b08650cc44811177838bc196/evaluation/results/%E5%AF%B9%E4%BA%8Ejpg-ocr-stat%E7%9A%84%E5%B0%9D%E8%AF%95)、[真实修订说明](https://github.com/linyouxue/skill-repair-benchmark/tree/6adffb1e027b55b8b08650cc44811177838bc196/evaluation/results/%E5%AF%B9%E4%BA%8Ejpg-ocr-stat%E7%9A%84%E5%B0%9D%E8%AF%95/skills/round_notes)、[Round26完整冻结输入](https://github.com/linyouxue/skill-repair-benchmark/tree/6adffb1e027b55b8b08650cc44811177838bc196/evaluation/results/%E5%AF%B9%E4%BA%8Ejpg-ocr-stat%E7%9A%84%E5%B0%9D%E8%AF%95/skills/bundles/round-26/bundle/skills)提供可追溯来源。本次五Skill共18文件与该公开Round26及三次实际输入逐文件一致；相对任务原版只有`image-ocr/SKILL.md`改变，支持文件及许可不变。`diff-vs-original.patch`是本次发布时生成的两版本差异，非伪称历史原始补丁。历史80步运行不计入本次65步三次均值。

修复材料实际包含原22票、原Task及主线早期诊断/反馈；不能声称仅使用后来发布的单个diagnosis S0包。历史记录明确包含离线oracle字段核对，不能声明修复组织者严格未接触参考答案。主线候选筛选时也已知部分group2成绩；Round26在本次复测前已存在，由用户在另一人工候选Round5的结果已知后指定。此次只发布冻结产物，不据此宣称严格未见泛化数据或无选择影响。

样本专门化披露：`image-ocr/SKILL.md`的Receipt Extraction Patterns、Numeric Normalization及Structured-Value Extraction Self-Check包含日期候选日/月含数字8时的实际看图门槛、最终实付/舍入裁决与结果保护等人工规则，并有数值归一化示例。全部原样保留，不把这些规则描述为从未见过原题的自动方法输出。

三次最终执行显式`n_skill_invocations=0`；执行器完整正文预载已核验。正文可见不证明每条指导都被遵循，也不证明单条规则的因果效果。实际执行中的图片块/裁剪以每次完整LLM、ACP及`agent/jpg-vision-audit.jsonl`为证据，不用本地路径列表冒充已传图；缺失的修复聊天不能据此补造。
