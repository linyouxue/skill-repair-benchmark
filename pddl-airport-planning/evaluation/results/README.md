# 提交真实泛化结果

本目录当前只有提交说明，没有新方法成绩或虚构baseline。先按[原任务result说明](../../result/README.md)冻结完整skill及真实修复/原题执行证据，再按协调者确定的组与重复次数运行。

在本目录提交`<method_id>__<config_id>/README.md`和`evidence/`。README指出原任务result中的同一冻结skill版本、实际模型/执行器/数据/评分版本、group、每次独立run ID及分数。evidence保留每次执行的完整ACP和LLM、原生配置/元数据、实际计划原文件、accuracy/CTRF/reward与用量；允许无损压缩或可访问归档引用。不要从摘要重建产物，不只挑最好一次；正常FAIL计入并保留，infra单列且不伪造分数。

不同协议/版本的分数分开呈现。不得用测试反馈继续改skill；若改了，作为另一个版本重新安排，不能继续称原冻结版。无需重复上传原输入、诊断包或skill全副本；通过固定仓库commit/相对路径关联。上传前移除凭据，提交面向main的PR，不直接覆盖他人结果。
