# 数据分类分级与个人信息保护报告

> 依据：《中华人民共和国数据安全法》、《中华人民共和国个人信息保护法》、GB/T 43697-2024《数据安全技术 数据分类分级规则》、GB/T 35273-2020《信息安全技术 个人信息安全规范》。自动生成于 2026-11-02 13:00:45。

## 一、分级结果

| 级别 | 含义 | 字段数 | 管控要求 |
| :---: | --- | ---: | --- |
| L1 | 公开数据 | 7 | 对外发布前做一致性校验，保留发布记录。 |
| L2 | 内部数据 | 18 | 按需授权，禁止外传；跨部门共享需审批。 |
| L3 | 敏感数据 | 4 | 最小必要、脱敏后共享、访问留痕、定期复核授权。 |
| L4 | 核心数据 | 0 | 专库加密存储、双人授权、禁止出域、全量审计。 |

分类分级覆盖 **29** 个字段，覆盖率 **100%**；识别个人信息字段 **4** 个，其中潜在敏感个人信息字段 **1** 个。

## 二、表级分级与共享策略

| 表 | 中文名 | 表级 | 分类 | 共享策略 | 判定依据 |
| --- | --- | :---: | :---: | --- | --- |
| `market_register` | 市场主体登记信息 | L3 | C01 | 有条件共享 | 以企业登记信息为主，含法定代表人、联系电话等个人信息，表级按最高字段级别定为 L3。 |
| `credit_rating` | 市场主体信用评价 | L2 | C03 | 有条件共享 | 信用评分与等级属于企业信用信息，供内部监管与服务场景使用。 |
| `complaint_case` | 企业诉求工单 | L3 | C04 | 脱敏后共享 | 诉求正文可能包含身份证号、银行账号等敏感个人信息，须内容级扫描与脱敏。 |

## 三、字段级分类分级清单

| 表 | 字段 | 中文名 | 分类 | 级别 | 个人信息 | 敏感 | 脱敏策略 |
| --- | --- | --- | :---: | :---: | :---: | :---: | --- |
| `market_register` | `reg_id` | 登记流水号 | C01 | L2 | 否 | 否 | - |
| `market_register` | `unified_social_credit_code` | 统一社会信用代码 | C01 | L1 | 否 | 否 | - |
| `market_register` | `company_name` | 企业名称 | C01 | L1 | 否 | 否 | - |
| `market_register` | `reg_date` | 注册日期 | C01 | L1 | 否 | 否 | - |
| `market_register` | `reg_capital_wan` | 注册资本（万元） | C01 | L1 | 否 | 否 | - |
| `market_register` | `industry_code` | 行业代码 | C01 | L1 | 否 | 否 | - |
| `market_register` | `district_code` | 行政区划代码 | C01 | L1 | 否 | 否 | - |
| `market_register` | `address` | 住所 | C01 | L2 | 否 | 否 | address_mask |
| `market_register` | `legal_person` | 法定代表人 | C02 | L3 | 是 | 否 | name_mask |
| `market_register` | `contact_phone` | 联系电话 | C02 | L3 | 是 | 否 | phone_mask |
| `market_register` | `contact_email` | 电子邮箱 | C02 | L3 | 是 | 否 | email_mask |
| `market_register` | `status` | 经营状态 | C01 | L1 | 否 | 否 | - |
| `market_register` | `update_time` | 更新时间 | C05 | L2 | 否 | 否 | - |
| `credit_rating` | `rating_id` | 评价记录号 | C03 | L2 | 否 | 否 | - |
| `credit_rating` | `unified_social_credit_code` | 统一社会信用代码 | C03 | L2 | 否 | 否 | - |
| `credit_rating` | `credit_score` | 信用评分 | C03 | L2 | 否 | 否 | - |
| `credit_rating` | `credit_level` | 信用等级 | C03 | L2 | 否 | 否 | - |
| `credit_rating` | `rating_date` | 评级日期 | C03 | L2 | 否 | 否 | - |
| `credit_rating` | `rating_agency` | 评级机构 | C03 | L2 | 否 | 否 | - |
| `credit_rating` | `update_time` | 更新时间 | C03 | L2 | 否 | 否 | - |
| `complaint_case` | `case_id` | 工单编号 | C04 | L2 | 否 | 否 | - |
| `complaint_case` | `unified_social_credit_code` | 统一社会信用代码 | C04 | L2 | 否 | 否 | - |
| `complaint_case` | `case_type` | 诉求类型 | C04 | L2 | 否 | 否 | - |
| `complaint_case` | `submit_time` | 提交时间 | C04 | L2 | 否 | 否 | - |
| `complaint_case` | `content` | 诉求内容 | C04 | L3 | 是 | 是 | content_redact |
| `complaint_case` | `handling_dept` | 承办部门 | C04 | L2 | 否 | 否 | - |
| `complaint_case` | `status` | 工单状态 | C04 | L2 | 否 | 否 | - |
| `complaint_case` | `satisfaction` | 满意度 | C04 | L2 | 否 | 否 | - |
| `complaint_case` | `close_time` | 办结时间 | C04 | L2 | 否 | 否 | - |

## 四、内容级个人信息扫描

扫描 `complaint_case.content` 共 **1,500** 行，命中 **150** 行（10.0%），共 **150** 处个人信息。

| 识别器 | 类型 | 级别 | 命中行数 | 命中次数 | 注入行数 | 检出率 |
| --- | --- | :---: | ---: | ---: | ---: | ---: |
| PII-MOBILE | 手机号 | L3 | 37 | 37 | 37 | 100% |
| PII-IDCARD | 身份证号 | L4 | 37 | 37 | 37 | 100% |
| PII-EMAIL | 电子邮箱 | L3 | 37 | 37 | 37 | 100% |
| PII-BANKCARD | 银行卡号 | L4 | 39 | 39 | 39 | 100% |

> 检出率 = 命中注入缺陷的行数 ÷ 注入缺陷行数，用于证明识别规则确实生效，而不是只做字段名判断。

## 五、脱敏共享与残留检查

| 输出文件 | 来源表 | 行数 |
| --- | --- | ---: |
| `data/serving/share_market_register.csv` | `dwd_market_register` | 1,139 |
| `data/serving/share_complaint_case.csv` | `dwd_complaint_case` | 1,443 |

共享文件个人信息残留扫描：**0** 处命中（目标为 0）。手机号、身份证号、邮箱、银行卡号均已按策略替换。

## 六、共享审批与使用要求

1. L3/L4 数据对外共享须由数据 Owner 提出、安全合规岗审批，明确使用目的、范围与期限；
2. 共享出口只提供脱敏后的最小字段集，禁止回传原始明文；
3. 接收方须签署数据使用承诺书，保存访问日志不少于 3 年；
4. 发生主体授权撤回或目的完成后，应在 5 个工作日内删除或匿名化；
5. 每季度复核一次分级结果与授权清单，字段新增或用途变化时重新评估。
