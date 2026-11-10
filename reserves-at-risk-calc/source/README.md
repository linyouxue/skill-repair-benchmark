# 数据来源

[snapshot.json](snapshot.json) 记录本次冻结的 IMF SDMX 查询、捕获时间、月度金价及四组储备观测。数值来自 [IMF PCPS](https://data.imf.org/en/Datasets/PCPS) 和 [IMF IRFCL](https://data.imf.org/en/Datasets/IRFCL)。

金价是美元每金衡盎司，每组使用上一年 9 月至目标年 9 月的 13 个月。储备取目标年 12 月，金额换算为百万美元，重量换算为百万金衡盎司。三个 IRFCL 指标分别对应货币黄金市值、货币黄金重量和官方储备资产合计。

两份国家名单固定，保留相同的字段可用性。每组有一国仅提供市值、一国仅提供重量，省略的字段是实验控制，保留的数值为真实观测。两国同时保留市值和重量，验证来源优先顺序。
