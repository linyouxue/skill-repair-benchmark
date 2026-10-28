# 来源与构建记录

原训练任务和skill来自[SkillsBench固定提交b63b7b2](https://github.com/benchflow-ai/skillsbench/tree/b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af/tasks/pddl-airport-planning)。原skill、支持文件和许可保留，不因为本仓库Apache许可而重标第三方许可。

同源输入来自[potassco/pddl-instances固定提交](https://github.com/potassco/pddl-instances/tree/cf19edf7c53d1540ddbb396c642595e0926ee552/ipc-2004/domains/airport-nontemporal-strips)，IPC2004机场地面交通规划系列。原文件中的Sebastian Trueg / Astras署名及第三方skill许可原样保留。只整理路径与problem.json，不改domain/problem内容。策展见证不是官方最优答案，也不用于字面匹配。

诊断来源固定为[index中的GPT-5.2运行](../../diagnosis/index.json)，不是人工Gold修复或已有修好的skill。原运行完整task tree和产物没有归档，历史task_digest仅照录，不能宣称本包整树等同历史工作区。源ACP/LLM/results与固定Git blob一致，正文预载与0次显式skill调用分别记录；公开归档中的redaction保持原样。

data_version=pilot-v2，scoring_version=item-accuracy-v1。三个group的原输入与评分资源均已冻结；无额外付费模型实验。实际执行和评分资源由框架分侧部署，目录名称本身不是权限控制。
