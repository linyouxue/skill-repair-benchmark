# 上传真实泛化结果

使用result中已经冻结的完整Skill，在三个测试任务中沿用同一个公共执行接口。每个方法/配置单独建目录，保留本说明和其他方法目录：

```text
results/
├── README.md
└── <method_id>__<config_id>/
    ├── README.md              # 冻结版本、模型/预算、批次和各次真实分数
    └── evidence/              # 每次执行的原生记录、实际answers.json和评分
```

每次保留完整ACP和LLM请求响应、配置/运行元数据、真实answers.json、accuracy.json、CTRF和reward。注明group、唯一run ID、与原题相同的冻结bundle及实际模型配置。正常FAIL、缺输出、超时和基础设施异常分别照实记录，不为低分替换有效运行。

按正式协议报告每批分数和重复次数；没有指定重复次数时先由协调者确定。不可根据这三批的结果修改Skill或重新选版。不要重复上传原始输入、完整原题失败轨迹或GT，也不提交空成绩表。
