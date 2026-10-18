# 仅供最终评测的材料

此目录随本版本公开，包含评测图片、既有运行和GT，但按实验协议禁止进入人工或模型的修复上下文。修复容器只挂载`../train/`；不要把整个数据集目录挂进去。这里的目录划分不是访问控制，也不能据此把公开GT称为未公开隐藏测试。

- `test1/`：原test，40张固定图片、既有三遍baseline记录和真实产物。
- `test2/`：原validation，40张固定图片、既有三遍baseline记录和真实产物。其用途改为最终评测，不再选版本。
- `runtime/`：原grader、oracle、冻结manifest及原免费评分工具的复制件。保留旧split名`train/validation/test`，通过包根`split_aliases.json`映射新用途；不得把这里的标签或断言传给Diagnoser。

原baseline报告沿用既有成绩，其“validation”等旧名称不被改写；仅将已交付产物链接适配为包内路径，未交付的历史源文件保留文字说明。当前使用规则以包根protocol为准，历史机器汇总中的绝对路径只表达来源，实际运行和归档位置以MANIFEST为准。

新的候选评测必须先冻结最终Skill，并另获执行授权。现有baseline不重跑；收到最终评测反馈后不能继续改Skill再把同一集合叫作未见测试。
