# 数据血缘与影响分析报告

> 血缘由转换配置与指标依赖自动生成，表级拓扑用于变更评审，字段级映射用于影响分析。

## 一、表级血缘

```mermaid
flowchart LR
  subgraph source["源系统层"]
    sys_reg["市场监督管理局登记系统"]
    sys_credit["公共信用信息平台"]
    sys_hotline["12345 政务服务便民热线"]
    sys_code_division["行政区划代码表"]
    sys_code_industry["行业代码表（GB/T 4754）"]
  end
  subgraph ods["贴源层 ODS"]
    ods_market_register["ods_market_register"]
    ods_credit_rating["ods_credit_rating"]
    ods_complaint_case["ods_complaint_case"]
  end
  subgraph dwd["明细层 DWD"]
    dwd_market_register["dwd_market_register"]
    dwd_credit_rating["dwd_credit_rating"]
    dwd_complaint_case["dwd_complaint_case"]
  end
  subgraph dws["指标层 DWS"]
    metric_market_total["市场主体总数"]
    metric_market_active["市场主体活跃率"]
    metric_credit_a["A 级信用企业占比"]
    metric_case_close["诉求办结率"]
    metric_satisfaction["平均满意度"]
  end
  subgraph serving["共享与服务层"]
    share_market_register["市场主体共享接口（脱敏）"]
    share_complaint_case["企业诉求共享接口（脱敏）"]
    report_dashboard["治理驾驶舱"]
    report_quality["数据质量报告"]
  end
  subgraph governance["治理与运维"]
    quarantine["数据隔离区"]
  end
  sys_reg -->|"T+1 批量抽取"| ods_market_register
  sys_credit -->|"每月增量推送"| ods_credit_rating
  sys_hotline -->|"实时接口同步"| ods_complaint_case
  sys_code_division -->|"区划码表校验"| ods_market_register
  sys_code_industry -->|"行业码表校验"| ods_market_register
  ods_market_register -->|"清洗·标准化·去重"| dwd_market_register
  ods_credit_rating -->|"校验·等级重算"| dwd_credit_rating
  ods_complaint_case -->|"清洗·状态归一"| dwd_complaint_case
  ods_market_register -->|"信用代码失败/重复记录"| quarantine
  ods_credit_rating -->|"关联主体失败"| quarantine
  ods_complaint_case -->|"关联主体失败"| quarantine
  dwd_market_register -->|"按状态统计"| metric_market_total
  dwd_market_register -->|"存续+在业占比"| metric_market_active
  dwd_credit_rating -->|"A 级占比"| metric_credit_a
  dwd_complaint_case -->|"办结/回访占比"| metric_case_close
  dwd_complaint_case -->|"有效满意度均值"| metric_satisfaction
  dwd_market_register -->|"字段级脱敏后共享"| share_market_register
  dwd_complaint_case -->|"正文内容识别与脱敏"| share_complaint_case
  metric_market_active -->|"指标展示"| report_dashboard
  metric_case_close -->|"指标展示"| report_dashboard
  metric_satisfaction -->|"指标展示"| report_dashboard
  dwd_market_register -->|"规则校验结果"| report_quality
  dwd_credit_rating -->|"规则校验结果"| report_quality
  dwd_complaint_case -->|"规则校验结果"| report_quality
  quarantine -->|"隔离数据统计"| report_quality
```

## 二、字段级血缘（示例）

| 源表 | 源字段 | 目标表 | 目标字段 | 转换规则 |
| --- | --- | --- | --- | --- |
| `ods_market_register` | `district_code` | `dwd_market_register` | `district_code` | 按住所中的县级行政区名修正区划代码 |
| `ods_market_register` | `address` | `dwd_market_register` | `district_code` | 按住所中的县级行政区名修正区划代码 |
| `ods_market_register` | `contact_phone` | `dwd_market_register` | `contact_phone` | 去分隔符与 +86、全角转半角，按手机号规则校验；不合规置空 |
| `ods_market_register` | `status` | `dwd_market_register` | `status` | 同义词映射为标准状态码；无法映射置空 |
| `ods_credit_rating` | `credit_level` | `dwd_credit_rating` | `credit_level` | 去空格转大写；按分数区间重算标准等级 |
| `ods_credit_rating` | `credit_score` | `dwd_credit_rating` | `credit_level` | 去空格转大写；按分数区间重算标准等级 |
| `ods_complaint_case` | `content` | `dwd_complaint_case` | `content` | 去首尾空白；保留原文供内部办理，共享时按内容识别结果脱敏 |
| `ods_complaint_case` | `status` | `dwd_complaint_case` | `status` | 同义词映射为标准状态码；无法映射保留原值 |

## 三、变更影响分析

### 变更：`contact_phone` — 手机号标准由 11 位调整为支持固话

- 预期影响：市场主体共享接口、企业服务触达清单、质量规则 DQ-REG-010；
- 直接涉及表：`dwd_market_register`, `ods_market_register`；
- 下游表：`dwd_market_register`, `ods_market_register`, `quarantine`；
- 影响资产：市场主体共享接口（脱敏）。

### 变更：`status` — 经营状态码表新增“歇业”

- 预期影响：市场主体活跃率、治理驾驶舱、共享接口；
- 直接涉及表：`dwd_complaint_case`, `dwd_market_register`, `ods_complaint_case`, `ods_market_register`；
- 下游表：`dwd_complaint_case`, `dwd_market_register`, `ods_complaint_case`, `ods_market_register`, `quarantine`；
- 影响资产：市场主体总数, 市场主体活跃率, 诉求办结率。

## 四、血缘治理规则

1. 新增字段必须同时更新 `config/transformations.json` 与 `config/lineage.json`，CI 校验映射完整性；
2. 删除/重命名字段前必须执行影响分析，通知下游资产 Owner 并保留变更窗口；
3. 指标口径变更须同步更新 `config/metrics.json`，并重跑回归；
4. 共享接口字段变更须经安全合规岗复核，确认脱敏策略仍然有效；
5. 每季度核对一次血缘与实际加工逻辑，发现漂移在 5 个工作日内修复。
