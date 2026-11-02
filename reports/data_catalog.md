# 数据目录（Data Catalog）

> 由 `src/dgov/metadata.py` 自动采集：技术元数据来自 SQLite 系统表，业务元数据来自 `config/business_metadata.json`，分类分级来自 `config/classification_rules.json`。

- 表数量：**12**
- 字段数量：**96**
- 业务域：**6** 个
- 敏感字段（L3/L4）：**11** 个

## 表清单

| 表名 | 分层 | 业务域 | Owner | 密级 | 行数 | 更新频率 |
| --- | --- | --- | --- | --- | ---: | --- |
| `dwd_order_detail` | DWD | 交易 | 订单域数据 Owner | L4 核心 | 59,601 | 每小时 |
| `dwd_product_dim` | DWD | 商品 | 商品域数据 Owner | L2 内部 | 120 | 每日 |
| `dwd_user_profile` | DWD | 用户 | 用户域数据 Owner | L4 核心 | 8,000 | 每日 |
| `dws_campaign_daily` | DWS | 营销 | 营销域数据 Owner | L2 内部 | 720 | 每日 |
| `dws_category_daily` | DWS | 商品 | 数据分析组 | L2 内部 | 540 | 每日 |
| `dws_channel_daily` | DWS | 交易 | 数据分析组 | L2 内部 | 625 | 每日 |
| `ods_campaign` | ODS | 营销 | 营销域数据 Owner | L2 内部 | 8 | 每日 |
| `ods_channel` | ODS | 渠道 | 渠道域数据 Owner | L1 公开 | 6 | 每周 |
| `ods_logistics` | ODS | 履约 | 履约域数据 Owner | L1 公开 | 38,764 | 每小时 |
| `ods_order` | ODS | 交易 | 订单域数据 Owner | L4 核心 | 60,600 | 每小时 |
| `ods_product` | ODS | 商品 | 商品域数据 Owner | L2 内部 | 120 | 每小时 |
| `ods_user` | ODS | 用户 | 用户域数据 Owner | L4 核心 | 8,000 | 每日 |

## 字段级数据字典

### dwd_order_detail（订单明细层，完成去重、标准码值转换、时序校验与敏感字段脱敏）

| 字段 | 类型 | 业务含义 | 分类分级 | 脱敏策略 |
| --- | --- | --- | --- | --- |
| `order_id` | TEXT | 订单号 | L1 公开 | 无需脱敏 |
| `user_id` | TEXT | 用户 ID | L1 公开 | 无需脱敏 |
| `product_id` | TEXT | 商品 ID | L1 公开 | 无需脱敏 |
| `channel_code` | TEXT | 渠道编码（标准码值） | L1 公开 | 无需脱敏 |
| `order_amount` | REAL | 订单金额（元） | L2 内部 | 无需脱敏，禁止外发 |
| `pay_amount` | REAL | 实付金额（元） | L2 内部 | 无需脱敏，禁止外发 |
| `order_status` | TEXT | 订单状态（标准码值） | L1 公开 | 无需脱敏 |
| `province` | TEXT | 收货省份 | L1 公开 | 无需脱敏 |
| `city` | TEXT | 收货城市 | L1 公开 | 无需脱敏 |
| `phone` | TEXT | 收货手机号（标准化） | L4 核心 | 保留前 3 位与后 4 位，如 138****1234 |
| `address_masked` | TEXT | 收货地址（脱敏） | L3 敏感 | 仅保留省/市，详细地址以 *** 代替 |
| `create_time` | TEXT | 下单时间 | L1 公开 | 无需脱敏 |
| `pay_time` | TEXT | 支付时间 | L1 公开 | 无需脱敏 |
| `order_date` | TEXT | 下单日期分区 | L1 公开 | 无需脱敏 |
| `is_valid` | INTEGER | 是否通过治理校验 | L1 公开 | 无需脱敏 |

### dwd_product_dim（商品维度层，补齐类目与价格校验）

| 字段 | 类型 | 业务含义 | 分类分级 | 脱敏策略 |
| --- | --- | --- | --- | --- |
| `product_id` | TEXT | 商品 ID | L1 公开 | 无需脱敏 |
| `product_name` | TEXT | 商品名称 | L1 公开 | 无需脱敏 |
| `category_code` | TEXT | 类目编码 | L1 公开 | 无需脱敏 |
| `category_name` | TEXT | 类目名称 | L1 公开 | 无需脱敏 |
| `price` | REAL | 商品价格（元） | L2 内部 | 无需脱敏，禁止外发 |
| `status` | TEXT | 商品状态 | L1 公开 | 无需脱敏 |
| `brand` | TEXT | 品牌 | L1 公开 | 无需脱敏 |

### dwd_user_profile（用户画像明细层，手机号/姓名/邮箱按分类分级要求脱敏）

| 字段 | 类型 | 业务含义 | 分类分级 | 脱敏策略 |
| --- | --- | --- | --- | --- |
| `user_id` | TEXT | 用户 ID | L1 公开 | 无需脱敏 |
| `user_name` | TEXT | 用户姓名（脱敏） | L3 敏感 | 保留姓氏，其余以 * 代替 |
| `phone` | TEXT | 手机号（标准化） | L4 核心 | 保留前 3 位与后 4 位，如 138****1234 |
| `email` | TEXT | 邮箱（脱敏） | L3 敏感 | 保留邮箱首字母与域名 |
| `city` | TEXT | 常住城市 | L1 公开 | 无需脱敏 |
| `member_level` | TEXT | 会员等级 | L1 公开 | 无需脱敏 |
| `register_time` | TEXT | 注册时间 | L1 公开 | 无需脱敏 |
| `user_level` | TEXT | 用户价值分层 | L1 公开 | 无需脱敏 |

### dws_campaign_daily（活动日汇总，用于投放 ROI 复盘）

| 字段 | 类型 | 业务含义 | 分类分级 | 脱敏策略 |
| --- | --- | --- | --- | --- |
| `stat_date` | TEXT | 统计日期 | L1 公开 | 无需脱敏 |
| `campaign_id` | TEXT | 活动 ID | L1 公开 | 无需脱敏 |
| `order_cnt` | INTEGER | 订单数 | L1 公开 | 无需脱敏 |
| `gmv` | REAL | 成交金额（元） | L2 内部 | 无需脱敏，禁止外发 |
| `roi` | REAL | 投入产出比 | L2 内部 | 无需脱敏，禁止外发 |

### dws_category_daily（类目日汇总）

| 字段 | 类型 | 业务含义 | 分类分级 | 脱敏策略 |
| --- | --- | --- | --- | --- |
| `stat_date` | TEXT | 统计日期 | L1 公开 | 无需脱敏 |
| `category_code` | TEXT | 类目编码 | L1 公开 | 无需脱敏 |
| `order_cnt` | INTEGER | 订单数 | L1 公开 | 无需脱敏 |
| `gmv` | REAL | 成交金额（元） | L2 内部 | 无需脱敏，禁止外发 |
| `buyer_cnt` | INTEGER | 购买用户数 | L1 公开 | 无需脱敏 |

### dws_channel_daily（渠道日汇总，统一 GMV、支付订单数等指标口径）

| 字段 | 类型 | 业务含义 | 分类分级 | 脱敏策略 |
| --- | --- | --- | --- | --- |
| `stat_date` | TEXT | 统计日期 | L1 公开 | 无需脱敏 |
| `channel_code` | TEXT | 渠道编码 | L1 公开 | 无需脱敏 |
| `order_cnt` | INTEGER | 订单数 | L1 公开 | 无需脱敏 |
| `pay_cnt` | INTEGER | 支付订单数 | L1 公开 | 无需脱敏 |
| `gmv` | REAL | 成交金额（元） | L2 内部 | 无需脱敏，禁止外发 |
| `refund_cnt` | INTEGER | 退款订单数 | L1 公开 | 无需脱敏 |
| `avg_order_amount` | REAL | 平均客单价（元） | L2 内部 | 无需脱敏，禁止外发 |

### ods_campaign（营销活动贴源表（历史遗留字段命名，作为标准整改样例））

| 字段 | 类型 | 业务含义 | 分类分级 | 脱敏策略 |
| --- | --- | --- | --- | --- |
| `campaign_id` | TEXT | 活动 ID | L1 公开 | 无需脱敏 |
| `campaignName` | TEXT | 活动名称（历史驼峰命名） | L1 公开 | 无需脱敏 |
| `channel_code` | TEXT | 投放渠道编码 | L1 公开 | 无需脱敏 |
| `budget` | REAL | 活动预算（元） | L2 内部 | 无需脱敏，禁止外发 |
| `startTime` | TEXT | 活动开始时间（历史驼峰命名） | L1 公开 | 无需脱敏 |
| `endTime` | TEXT | 活动结束时间 | L1 公开 | 无需脱敏 |

### ods_channel（渠道维表，定义线上/线下渠道标准码值）

| 字段 | 类型 | 业务含义 | 分类分级 | 脱敏策略 |
| --- | --- | --- | --- | --- |
| `channel_code` | TEXT | 渠道编码 | L1 公开 | 无需脱敏 |
| `channel_name` | TEXT | 渠道名称 | L1 公开 | 无需脱敏 |
| `channel_type` | TEXT | 渠道类型 | L1 公开 | 无需脱敏 |
| `online_flag` | INTEGER | 是否线上渠道 | L1 公开 | 无需脱敏 |

### ods_logistics（物流贴源表，来自履约系统）

| 字段 | 类型 | 业务含义 | 分类分级 | 脱敏策略 |
| --- | --- | --- | --- | --- |
| `logistics_id` | TEXT | 物流单号 | L1 公开 | 无需脱敏 |
| `order_id` | TEXT | 订单号 | L1 公开 | 无需脱敏 |
| `carrier` | TEXT | 承运商 | L1 公开 | 无需脱敏 |
| `status` | TEXT | 物流状态 | L1 公开 | 无需脱敏 |
| `ship_time` | TEXT | 发货时间 | L1 公开 | 无需脱敏 |
| `receive_time` | TEXT | 签收时间 | L1 公开 | 无需脱敏 |

### ods_order（订单贴源表，来自交易系统订单库，保留原始字段与异常值）

| 字段 | 类型 | 业务含义 | 分类分级 | 脱敏策略 |
| --- | --- | --- | --- | --- |
| `order_id` | TEXT | 订单号 | L1 公开 | 无需脱敏 |
| `user_id` | TEXT | 用户 ID | L1 公开 | 无需脱敏 |
| `product_id` | TEXT | 商品 ID | L1 公开 | 无需脱敏 |
| `channel_code` | TEXT | 渠道编码 | L1 公开 | 无需脱敏 |
| `order_amount` | REAL | 订单金额（元） | L2 内部 | 无需脱敏，禁止外发 |
| `pay_amount` | REAL | 实付金额（元） | L2 内部 | 无需脱敏，禁止外发 |
| `coupon_amount` | REAL | 优惠金额（元） | L2 内部 | 无需脱敏，禁止外发 |
| `order_status` | TEXT | 订单状态 | L1 公开 | 无需脱敏 |
| `province` | TEXT | 收货省份 | L1 公开 | 无需脱敏 |
| `city` | TEXT | 收货城市 | L1 公开 | 无需脱敏 |
| `phone` | TEXT | 收货手机号 | L4 核心 | 保留前 3 位与后 4 位，如 138****1234 |
| `address` | TEXT | 收货详细地址 | L3 敏感 | 仅保留省/市，详细地址以 *** 代替 |
| `create_time` | TEXT | 下单时间 | L1 公开 | 无需脱敏 |
| `pay_time` | TEXT | 支付时间 | L1 公开 | 无需脱敏 |
| `source` | TEXT | 订单来源系统 | L1 公开 | 无需脱敏 |

### ods_product（商品贴源表，来自商品中心）

| 字段 | 类型 | 业务含义 | 分类分级 | 脱敏策略 |
| --- | --- | --- | --- | --- |
| `product_id` | TEXT | 商品 ID | L1 公开 | 无需脱敏 |
| `product_name` | TEXT | 商品名称 | L1 公开 | 无需脱敏 |
| `category_code` | TEXT | 类目编码 | L1 公开 | 无需脱敏 |
| `category_name` | TEXT | 类目名称 | L1 公开 | 无需脱敏 |
| `price` | REAL | 商品价格（元） | L2 内部 | 无需脱敏，禁止外发 |
| `status` | TEXT | 商品状态 | L1 公开 | 无需脱敏 |
| `brand` | TEXT | 品牌 | L1 公开 | 无需脱敏 |
| `supplier` | TEXT | 供应商 | L1 公开 | 无需脱敏 |

### ods_user（用户贴源表，来自会员系统，含个人身份与联系方式字段）

| 字段 | 类型 | 业务含义 | 分类分级 | 脱敏策略 |
| --- | --- | --- | --- | --- |
| `user_id` | TEXT | 用户 ID | L1 公开 | 无需脱敏 |
| `user_name` | TEXT | 用户姓名 | L3 敏感 | 保留姓氏，其余以 * 代替 |
| `phone` | TEXT | 注册手机号 | L4 核心 | 保留前 3 位与后 4 位，如 138****1234 |
| `email` | TEXT | 注册邮箱 | L3 敏感 | 保留邮箱首字母与域名 |
| `id_card` | TEXT | 证件号码 | L4 核心 | 保留前 6 位与后 4 位 |
| `register_time` | TEXT | 注册时间 | L1 公开 | 无需脱敏 |
| `city` | TEXT | 常住城市 | L1 公开 | 无需脱敏 |
| `member_level` | TEXT | 会员等级 | L1 公开 | 无需脱敏 |
| `age` | INTEGER | 年龄 | L1 公开 | 无需脱敏 |
| `gender` | TEXT | 性别 | L1 公开 | 无需脱敏 |
