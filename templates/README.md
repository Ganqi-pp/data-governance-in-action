# 可复用模板

> 这些模板来自本项目实际运行产物，去掉具体数字后可直接用于其他数据域。
> 建议先跑一遍 `python run_demo.py`，对照 `reports/` 中的真实报告理解每个字段。

| 模板 | 用途 | 对应产物 |
| --- | --- | --- |
| [`数据质量报告模板.md`](数据质量报告模板.md) | 月度/季度质量报告 | `reports/quality_report.md` |
| [`整改工单模板.md`](整改工单模板.md) | 问题派单、整改、复检 | `reports/issue_register.csv` |
| [`数据资产登记模板.md`](数据资产登记模板.md) | 新增表/指标/接口登记 | `reports/asset_register.md` |
| [`分类分级清单模板.md`](分类分级清单模板.md) | 字段级定级与共享审批 | `reports/classification_report.md` |
| [`数据治理制度模板.md`](数据治理制度模板.md) | 编写专项管理办法 | `docs/01`—`docs/06` |

## 怎么复用到新业务域

1. **换数据**：修改 `src/dgov/seed_data.py` 或直接替换 `data/raw/*.csv`；
2. **换标准**：改 `config/standards.json` 的表、字段、类型、码表；
3. **换规则**：改 `config/quality_rules.json`，新增规则只需加 JSON；
4. **换分级**：改 `config/classification_rules.json` 的字段规则与识别器；
5. **换血缘**：改 `config/transformations.json` 与 `config/lineage.json`；
6. **换资产/指标**：改 `config/assets.json`、`config/metrics.json`；
7. **保留引擎**：`src/dgov/` 的采集、评分、闭环、报告、看板逻辑不需要重写。

## 使用建议

- 模板中的 `<...>` 必须替换，不要原样提交；
- 数字必须来自脚本或 SQL，不要手填；
- 报告中的“未达标/未覆盖”要保留，否则会失去可信度；
- 制度模板发布前请法务/合规审核，不要直接当正式制度使用。
