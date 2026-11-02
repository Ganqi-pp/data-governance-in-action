-- 雄安新区市场主体服务数据治理 · 核心表结构
-- 说明：SQLite 沙箱中所有字段以 TEXT 存储，质量规则通过 CAST/date() 做类型判断；
-- 生产环境建议按注释中的类型建表，并增加分区、主键、外键与审计字段。

-- ---------------------------------------------------------------------------
-- ODS 贴源层：保留原始值，不做任何修复
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ods_market_register (
    reg_id                      TEXT PRIMARY KEY,   -- 登记流水号
    unified_social_credit_code  TEXT,               -- 统一社会信用代码（原始值，可能非法）
    company_name                TEXT,               -- 企业名称
    reg_date                    TEXT,               -- 注册日期（原始格式）
    reg_capital_wan             TEXT,               -- 注册资本（万元）
    industry_code               TEXT,               -- 行业代码/名称（可能非标准）
    district_code               TEXT,               -- 行政区划代码
    address                     TEXT,               -- 住所
    legal_person                TEXT,               -- 法定代表人
    contact_phone               TEXT,               -- 联系电话
    contact_email               TEXT,               -- 电子邮箱
    status                      TEXT,               -- 经营状态（可能为别名）
    update_time                 TEXT                -- 更新时间
);

CREATE TABLE IF NOT EXISTS ods_credit_rating (
    rating_id                   TEXT PRIMARY KEY,
    unified_social_credit_code  TEXT,
    credit_score                TEXT,
    credit_level                TEXT,
    rating_date                 TEXT,
    rating_agency               TEXT,
    update_time                 TEXT
);

CREATE TABLE IF NOT EXISTS ods_complaint_case (
    case_id                     TEXT PRIMARY KEY,
    unified_social_credit_code  TEXT,
    case_type                   TEXT,
    submit_time                 TEXT,
    content                     TEXT,               -- 可能含个人信息
    handling_dept               TEXT,
    status                      TEXT,
    satisfaction                TEXT,
    close_time                  TEXT
);

-- ---------------------------------------------------------------------------
-- DWD 明细层：清洗、标准化、去重后；dq_flags 记录修复动作
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwd_market_register (
    reg_id                      TEXT PRIMARY KEY,
    unified_social_credit_code  TEXT NOT NULL,
    company_name                TEXT NOT NULL,
    reg_date                    TEXT,
    reg_capital_wan             TEXT,
    industry_code               TEXT,
    district_code               TEXT,
    address                     TEXT,
    legal_person                TEXT,
    contact_phone               TEXT,
    contact_email               TEXT,
    status                      TEXT,
    update_time                 TEXT,
    dq_flags                    TEXT
);

CREATE TABLE IF NOT EXISTS dwd_credit_rating (
    rating_id                   TEXT PRIMARY KEY,
    unified_social_credit_code  TEXT NOT NULL,
    credit_score                TEXT,
    credit_level                TEXT,
    rating_date                 TEXT,
    rating_agency               TEXT,
    update_time                 TEXT,
    dq_flags                    TEXT
);

CREATE TABLE IF NOT EXISTS dwd_complaint_case (
    case_id                     TEXT PRIMARY KEY,
    unified_social_credit_code  TEXT,
    case_type                   TEXT,
    submit_time                 TEXT,
    content                     TEXT,
    handling_dept               TEXT,
    status                      TEXT,
    satisfaction                TEXT,
    close_time                  TEXT,
    dq_flags                    TEXT
);

-- ---------------------------------------------------------------------------
-- 隔离区：无法自动修复的记录，保留原始行与原因
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quarantine_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name      TEXT NOT NULL,
    record_key      TEXT NOT NULL,
    reason_code     TEXT NOT NULL,
    reason_desc     TEXT,
    raw_json        TEXT,
    created_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_quarantine_table_key
    ON quarantine_records (table_name, record_key);

-- ---------------------------------------------------------------------------
-- 参考码表
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ref_administrative_divisions (
    code        TEXT PRIMARY KEY,
    name        TEXT,
    level       TEXT,
    parent_code TEXT
);

CREATE TABLE IF NOT EXISTS ref_industry_codes (
    code    TEXT PRIMARY KEY,
    name    TEXT,
    section TEXT
);

CREATE TABLE IF NOT EXISTS ref_market_status_codes (
    code TEXT PRIMARY KEY,
    name TEXT
);

CREATE TABLE IF NOT EXISTS ref_credit_levels (
    code      TEXT PRIMARY KEY,
    name      TEXT,
    score_min TEXT,
    score_max TEXT
);
