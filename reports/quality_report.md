# 数据质量报告

> 规则集：`config/quality_rules.json`（22 条），覆盖 3 个数据集、67,721 行数据；质量分按「未命中任何规则的行占比」计算。

**治理前质量分：92.88 → 治理后：99.40（+6.52）**

## 一、分维度得分

| 维度 | 治理前 | 治理后 | 问题行数（治理前 → 后） |
| --- | ---: | ---: | ---: |
| 完整性 | 99.06 | 100.00 | 649 → 0 |
| 唯一性 | 98.25 | 100.00 | 1200 → 0 |
| 有效性 | 95.99 | 99.65 | 2757 → 235 |
| 一致性 | 99.33 | 99.71 | 406 → 173 |
| 及时性 | 100.00 | 100.00 | 0 → 0 |

## 二、规则明细

| 规则 | 表 | 字段 | 维度 | 严重度 | 治理前通过率 | 治理后通过率 | 责任人 |
| --- | --- | --- | --- | --- | ---: | ---: | --- |
| DQ-ORD-001 订单号唯一 | `ods_order` | `order_id` | 唯一性 | high | 98.02% | 100.00% | 订单域数据 Owner |
| DQ-ORD-002 订单号非空 | `ods_order` | `order_id` | 完整性 | high | 100.00% | 100.00% | 订单域数据 Owner |
| DQ-ORD-003 用户 ID 非空 | `ods_order` | `user_id` | 完整性 | high | 99.51% | 100.00% | 用户域数据 Owner |
| DQ-ORD-004 渠道编码非空 | `ods_order` | `channel_code` | 完整性 | medium | 99.60% | 100.00% | 渠道域数据 Owner |
| DQ-ORD-005 下单时间非空 | `ods_order` | `create_time` | 完整性 | high | 99.81% | 100.00% | 订单域数据 Owner |
| DQ-ORD-006 订单状态取值合法 | `ods_order` | `order_status` | 有效性 | medium | 99.21% | 100.00% | 订单域数据 Owner |
| DQ-ORD-007 渠道编码符合标准 | `ods_order` | `channel_code` | 有效性 | medium | 98.76% | 99.61% | 渠道域数据 Owner |
| DQ-ORD-008 收货手机号格式合法 | `ods_order` | `phone` | 有效性 | medium | 97.96% | 100.00% | 用户域数据 Owner |
| DQ-ORD-009 支付金额非负 | `ods_order` | `pay_amount` | 有效性 | high | 99.46% | 100.00% | 订单域数据 Owner |
| DQ-ORD-010 订单金额非负 | `ods_order` | `order_amount` | 有效性 | high | 100.00% | 100.00% | 订单域数据 Owner |
| DQ-ORD-011 支付时间不早于下单时间 | `ods_order` | `pay_time` | 一致性 | high | 99.73% | 100.00% | 订单域数据 Owner |
| DQ-ORD-012 已支付订单必须有支付时间 | `ods_order` | `pay_time` | 一致性 | high | 99.89% | 100.00% | 订单域数据 Owner |
| DQ-ORD-013 商品 ID 可关联 | `ods_order` | `product_id` | 一致性 | high | 99.71% | 99.71% | 商品域数据 Owner |
| DQ-ORD-014 下单时间无未来时间 | `ods_order` | `create_time` | 及时性 | medium | 100.00% | 100.00% | 订单域数据 Owner |
| DQ-USR-001 用户 ID 唯一 | `ods_user` | `user_id` | 唯一性 | high | 100.00% | 100.00% | 用户域数据 Owner |
| DQ-USR-002 注册手机号格式合法 | `ods_user` | `phone` | 有效性 | high | 100.00% | 100.00% | 用户域数据 Owner |
| DQ-USR-003 注册时间非空 | `ods_user` | `register_time` | 完整性 | medium | 100.00% | 100.00% | 用户域数据 Owner |
| DQ-USR-004 会员等级取值合法 | `ods_user` | `member_level` | 有效性 | medium | 100.00% | 100.00% | 用户域数据 Owner |
| DQ-PRD-001 商品 ID 唯一 | `ods_product` | `product_id` | 唯一性 | high | 100.00% | 100.00% | 商品域数据 Owner |
| DQ-PRD-002 类目编码非空 | `ods_product` | `category_code` | 完整性 | high | 100.00% | 100.00% | 商品域数据 Owner |
| DQ-PRD-003 商品价格非负 | `ods_product` | `price` | 有效性 | medium | 100.00% | 100.00% | 商品域数据 Owner |
| DQ-PRD-004 商品状态取值合法 | `ods_product` | `status` | 有效性 | low | 100.00% | 100.00% | 商品域数据 Owner |

## 三、问题定位与整改台账

| 问题编号 | 规则 | 表 | 失败行数 | 责任人 | 整改期限 | 状态 |
| --- | --- | --- | ---: | --- | --- | --- |
| DQ-007-20261102 | DQ-ORD-007 | `dwd_order_detail` | 235 | 渠道域数据 Owner | 2026-11-04 | 待整改 |
| DQ-013-20261102 | DQ-ORD-013 | `dwd_order_detail` | 173 | 商品域数据 Owner | 2026-11-04 | 待整改 |

### 问题样本（用于定位上游）

- **DQ-ORD-007 dwd_order_detail**：`[{"order_id": "SO202609130000102", "user_id": "U000102", "product_id": "P0077", "channel_code": "UNKNOWN", "order_amount": 1072.75}, {"order_id": "SO202608100000677", "user_id": "U000677", "product_id": "P0008", "channel_code": "UNKNOWN", "order_amount": 872.77}]`
- **DQ-ORD-013 dwd_order_detail**：`[{"order_id": "SO202607130000208", "user_id": "U000208", "product_id": "P9999", "channel_code": "JD", "order_amount": 1223.88}, {"order_id": "SO202607270000225", "user_id": "U000225", "product_id": "P9999", "channel_code": "OFFLINE", "order_amount": 728.09}]`

## 四、结论与下一步

1. 治理前共 **11** 条规则未通过，清洗后 **9** 条已闭环；
2. 剩余 **2** 项遗留问题已进入整改台账，按责任人 SLA 跟踪；
3. 建议将高频失败规则固化为每日巡检任务，并将质量分纳入数据资产健康度评分。