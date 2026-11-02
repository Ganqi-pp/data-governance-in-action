-- 核心指标口径
-- 与 config/metrics.json 保持一致；指标必须在 DWD 明细层执行。

-- MKT-TOTAL 市场主体总数（存续 + 在业）
SELECT COUNT(*) AS value
FROM dwd_market_register
WHERE status IN ('存续', '在业');

-- MKT-ACTIVE 市场主体活跃率
SELECT ROUND(
    100.0 * SUM(CASE WHEN status IN ('存续', '在业') THEN 1 ELSE 0 END) / COUNT(*),
    2
) AS value
FROM dwd_market_register;

-- CRE-A A 级信用企业占比
SELECT ROUND(
    100.0 * SUM(CASE WHEN credit_level = 'A' THEN 1 ELSE 0 END)
    / NULLIF(COUNT(credit_level), 0),
    2
) AS value
FROM dwd_credit_rating;

-- CASE-CLOSE 企业诉求办结率
SELECT ROUND(
    100.0 * SUM(CASE WHEN status IN ('已办结', '已回访') THEN 1 ELSE 0 END) / COUNT(*),
    2
) AS value
FROM dwd_complaint_case;

-- CASE-SAT 平均满意度（只统计 1—5 分）
SELECT ROUND(AVG(satisfaction), 2) AS value
FROM dwd_complaint_case
WHERE satisfaction BETWEEN 1 AND 5;

-- ---------------------------------------------------------------------------
-- 质量规则示例：问题定位到主键，直接支撑工单派发
-- ---------------------------------------------------------------------------
-- 联系电话格式不合规
SELECT reg_id AS record_key, contact_phone AS evidence
FROM dwd_market_register
WHERE contact_phone IS NOT NULL
  AND TRIM(contact_phone) <> ''
  AND contact_phone NOT GLOB '1[3-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]';

-- 地址与区划代码不一致（以住所中的县名为准）
SELECT reg_id AS record_key, '区划与住所不一致' AS evidence
FROM dwd_market_register
WHERE address IS NOT NULL AND address <> ''
  AND (
      (address LIKE '%容城县%' AND district_code <> '130629')
   OR (address LIKE '%安新县%' AND district_code <> '130632')
   OR (address LIKE '%雄县%'   AND district_code <> '130638')
   OR (address LIKE '%启动区%' AND district_code <> '133100')
  );

-- 已办结但缺少办结时间
SELECT case_id AS record_key, '已办结但办结时间为空' AS evidence
FROM dwd_complaint_case
WHERE status IN ('已办结', '已回访')
  AND (close_time IS NULL OR TRIM(close_time) = '');
