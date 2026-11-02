-- DWS 层聚合：由 DWD 明细汇总，用于血缘解析演示
INSERT INTO dws_channel_daily (stat_date, channel_code, order_cnt, pay_cnt, gmv, refund_cnt, avg_order_amount)
SELECT
    o.order_date                                   AS stat_date,
    o.channel_code                                 AS channel_code,
    COUNT(*)                                       AS order_cnt,
    SUM(CASE WHEN o.pay_time IS NOT NULL THEN 1 ELSE 0 END) AS pay_cnt,
    ROUND(SUM(CASE WHEN o.pay_time IS NOT NULL THEN o.pay_amount ELSE 0 END), 2) AS gmv,
    SUM(CASE WHEN o.order_status = '已退款' THEN 1 ELSE 0 END) AS refund_cnt,
    ROUND(AVG(o.pay_amount), 2)                    AS avg_order_amount
FROM dwd_order_detail o
WHERE o.is_valid = 1
GROUP BY o.order_date, o.channel_code;

INSERT INTO dws_category_daily (stat_date, category_code, order_cnt, gmv, buyer_cnt)
SELECT
    o.order_date                                   AS stat_date,
    p.category_code                                AS category_code,
    COUNT(*)                                       AS order_cnt,
    ROUND(SUM(CASE WHEN o.pay_time IS NOT NULL THEN o.pay_amount ELSE 0 END), 2) AS gmv,
    COUNT(DISTINCT o.user_id)                      AS buyer_cnt
FROM dwd_order_detail o
JOIN dwd_product_dim p ON o.product_id = p.product_id
WHERE o.is_valid = 1
GROUP BY o.order_date, p.category_code;

INSERT INTO dws_campaign_daily (stat_date, campaign_id, order_cnt, gmv, roi)
SELECT
    o.order_date                                   AS stat_date,
    c.campaign_id                                  AS campaign_id,
    COUNT(*)                                       AS order_cnt,
    ROUND(SUM(CASE WHEN o.pay_time IS NOT NULL THEN o.pay_amount ELSE 0 END), 2) AS gmv,
    ROUND(SUM(CASE WHEN o.pay_time IS NOT NULL THEN o.pay_amount ELSE 0 END) / NULLIF(c.budget, 0), 2) AS roi
FROM dwd_order_detail o
JOIN ods_campaign c ON o.channel_code = c.channel_code
WHERE o.is_valid = 1
GROUP BY o.order_date, c.campaign_id;
