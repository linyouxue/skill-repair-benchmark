# 上传最终冻结的Skill与原题真实执行

每个方法/配置提交一个最终版本，在泛化测试前冻结：

```text
result/
├── README.md                         # 本说明，保留
└── <method_id>__<config_id>/
    ├── skills/                       # 完整13f-analyzer/与fuzzy-name-search/
    ├── README.md                     # 方法、模型配置、版本及必要披露
    └── evidence/                     # 真实修复过程、原题执行及实际answers.json
```

只修改原有SKILL.md正文；支持脚本和其他原文件保持完整。沿用各方法原有adapter与修复记录格式，不新增统一请求格式，不要求正常FAIL必须修到全对才提交。

保留真实诊断/修订/选版的请求响应、配置、候选及选择依据，以及同一冻结完整Skill执行原题的ACP、LLM、运行元数据、实际 `/root/answers.json` 和verifier的accuracy/CTRF/reward。两类过程不互相替代；缺失的原产物如实标明，不由完成声明补造。

执行使用同一个BenchmarkExecutor、60次父迭代及既有completion guard。修复本身的模型/轮次等参数由既定实验协议确定，不因提供GPT-5.2轨迹而自动指定新调用模型。实际模型调用须由实验协调者另行授权。

方法README列明方法与代码版本、修复/执行模型配置、最终bundle版本、材料版本、对应run ID、输出/评分路径及额外数据接触或人工参与。普通FAIL、超时、用量和缺失证据均照实记录。

后续使用evaluation前先冻结完整bundle，不按泛化结果重新选版。泛化输出放[evaluation/results](../evaluation/results/README.md)。从当次指定版本新建自己的分支或fork，保留本说明与其他方法目录，通过PR提交；排除密钥及无关个人信息。
