# 模拟原始数据说明

本目录数据由 `python run_demo.py seed` 按固定随机种子生成，**全部为虚构内容**，不对应任何真实企业或个人。

| 文件 | 内容 | 行数 |
| --- | --- | ---: |
| `market_register.csv` | 市场主体登记信息 | 1240 |
| `credit_rating.csv` | 市场主体信用评价 | 950 |
| `complaint_case.csv` | 企业诉求工单（12345） | 1500 |
| `_defect_manifest.json` | 注入缺陷清单（用于计算规则检出率） | - |

缺陷类型、影响行号与对应规则见 `_defect_manifest.json`；质量报告中的“规则有效性验证”即基于该清单计算。
