# SkillRevise — Opus 4.7 控制变量实验

## 执行结果

22/22 条件已有有效结果：14 个起始通过而未修订、1 个修订后通过、7 个有效失败。第一组5条件，第二组12个留一+5个全缺陷条件。不能把15个最终通过都算为修复成功。目标缺陷修复与其他修复保留情况均待人工核查。

完整Gold对照8/8最新有效结果通过；Google Auto原Gold失败受Maven下载影响，原记录与成功补跑均保留。原回流焊all的APT 502无效结果不计有效分母，使用补跑结果，补跑起始就通过。详见summary.json的all_attempts。

## 方法与限制

原有SkillRevise bundle选择、诊断、通用种子原则BM25检索、每文件最多3轮修订、执行反馈和版本选择；最多3个目标文件，允许不降分修改。仅修改SKILL.md，不改随附脚本。起始通过即跳过修订，此为原有方法门控，不是22次强制修复。独立进程和原则库，无跨条件学习。修复提示不注入任务执行侧task.md。

修复API为塔图云Anthropic claude-opus-4-7，high、thinking disabled、32768输出上限；执行模型tatu-anthropic/claude-opus-4-7，ACP effort选项省略。具体命令见各trial/command.json与source代码快照。原始设置不根据上传仓库的新默认配置追溯修改。

## 文件

- summary.json / summary.csv：22条件结果、来源批次、旧失败记录。
- submission_controlled22.json：带trial_id的诊断和完整候选索引；不是Gold31评测输入，同一task有多条件，禁止去重混入旧submission.json。
- trials/：单条件输入、完整候选Skill包、全部候选版本、结果和选择依据、before/selected完整文本轨迹。起始通过的candidate是未修改输入副本，不宣称repaired。
- evidence/：每条件压缩的完整请求/回复、执行日志和分项检查；包含基础设施失败。包内路径均相对对应条件；原结果中的主机绝对路径仅为历史记录，不要求本机存在。
- gold_controls/：完整Gold独立执行，含原失败与补跑。
- source/：实际方法与启动器快照及校验值，不含本地密钥配置。

## 数据来源与复现

输入release为skill-repair-controlled-datasets-20261020（658文件），每条件state.json固定发布包SHA256SUMS摘要，input/INPUT_SHA256.json固定该条件输入，images.json固定镜像。原任务数据、oracle和verifier不重复上传；数据包位于本次实验提供的skill-repair-controlled-datasets-20261020，相关原始来源Gold c9ca883d1af68fe12bb7e07275999543bd1cd963、SkillsBench b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af，具体路径见state.json。复现需先获取同一release；不得让repairer读取Gold或其他条件。

本次仅上传已有结果，没有新增模型调用。没有训练loss，没有新增人工标注评测或修复语义审核结论。
