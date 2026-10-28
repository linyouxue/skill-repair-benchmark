# 来源与构建记录

原训练任务和skill来自[SkillsBench固定提交b63b7b2](https://github.com/benchflow-ai/skillsbench/tree/b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af/tasks/flink-query)。原skill、支持文件和许可保留，不因为本仓库Apache许可而重标第三方许可。

数据为Google的[clusterdata-2011-2](https://github.com/google/cluster-data/blob/master/ClusterData2011_2.md)，John Wilkes、Charles Reiss，2011年5月29天集群trace v2.1；数据和文档按[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)署名使用。原对象模板为`https://storage.googleapis.com/clusterdata-2011-2/{job_events|task_events}/part-NNNNN-of-00500.csv.gz`。每组metadata保留原分片、成员、筛选规则和候选计数；未上传全量trace。

诊断来源固定为[index中的GPT-5.2运行](../../diagnosis/index.json)，不是人工Gold修复或已有修好的skill。原运行完整task tree和产物没有归档，历史task_digest仅照录，不能宣称本包整树等同历史工作区。源ACP/LLM/results与固定Git blob一致，正文预载与0次显式skill调用分别记录；公开归档中的redaction保持原样。

data_version=pilot-v2，scoring_version=item-accuracy-v1。三个group的原输入与评分资源均已冻结；无额外付费模型实验。实际执行和评分资源由框架分侧部署，目录名称本身不是权限控制。
