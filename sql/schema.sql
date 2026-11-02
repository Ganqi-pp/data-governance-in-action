-- 数据治理实战项目：示例数仓（SQLite）
-- 分层：ODS（贴源）→ DWD（明细）→ DWS（汇总）

DROP TABLE IF EXISTS ods_order;
CREATE TABLE ods_order (
    order_id       TEXT,
    user_id        TEXT,
    product_id     TEXT,
    channel_code   TEXT,
    order_amount   REAL,
    pay_amount     REAL,
    coupon_amount  REAL,
    order_status   TEXT,
    province       TEXT,
    city           TEXT,
    phone          TEXT,
    address        TEXT,
    create_time    TEXT,
    pay_time       TEXT,
    source         TEXT
);

DROP TABLE IF EXISTS ods_user;
CREATE TABLE ods_user (
    user_id        TEXT,
    user_name      TEXT,
    phone          TEXT,
    email          TEXT,
    id_card        TEXT,
    register_time  TEXT,
    city           TEXT,
    member_level   TEXT,
    age            INTEGER,
    gender         TEXT
);

DROP TABLE IF EXISTS ods_product;
CREATE TABLE ods_product (
    product_id     TEXT,
    product_name   TEXT,
    category_code  TEXT,
    category_name  TEXT,
    price          REAL,
    status         TEXT,
    brand          TEXT,
    supplier       TEXT
);

DROP TABLE IF EXISTS ods_channel;
CREATE TABLE ods_channel (
    channel_code   TEXT,
    channel_name   TEXT,
    channel_type   TEXT,
    online_flag    INTEGER
);

DROP TABLE IF EXISTS ods_logistics;
CREATE TABLE ods_logistics (
    logistics_id   TEXT,
    order_id       TEXT,
    carrier        TEXT,
    status         TEXT,
    ship_time      TEXT,
    receive_time   TEXT
);

DROP TABLE IF EXISTS ods_campaign;
CREATE TABLE ods_campaign (
    campaign_id    TEXT,
    campaignName   TEXT,
    channel_code   TEXT,
    budget         REAL,
    startTime      TEXT,
    endTime        TEXT
);

DROP TABLE IF EXISTS dwd_order_detail;
CREATE TABLE dwd_order_detail (
    order_id       TEXT,
    user_id        TEXT,
    product_id     TEXT,
    channel_code   TEXT,
    order_amount   REAL,
    pay_amount     REAL,
    order_status   TEXT,
    province       TEXT,
    city           TEXT,
    phone          TEXT,
    address_masked TEXT,
    create_time    TEXT,
    pay_time       TEXT,
    order_date     TEXT,
    is_valid       INTEGER
);

DROP TABLE IF EXISTS dwd_user_profile;
CREATE TABLE dwd_user_profile (
    user_id        TEXT,
    user_name      TEXT,
    phone          TEXT,
    email          TEXT,
    city           TEXT,
    member_level   TEXT,
    register_time  TEXT,
    user_level     TEXT
);

DROP TABLE IF EXISTS dwd_product_dim;
CREATE TABLE dwd_product_dim (
    product_id     TEXT,
    product_name   TEXT,
    category_code  TEXT,
    category_name  TEXT,
    price          REAL,
    status         TEXT,
    brand          TEXT
);

DROP TABLE IF EXISTS dws_channel_daily;
CREATE TABLE dws_channel_daily (
    stat_date        TEXT,
    channel_code     TEXT,
    order_cnt        INTEGER,
    pay_cnt          INTEGER,
    gmv              REAL,
    refund_cnt       INTEGER,
    avg_order_amount REAL
);

DROP TABLE IF EXISTS dws_category_daily;
CREATE TABLE dws_category_daily (
    stat_date        TEXT,
    category_code    TEXT,
    order_cnt        INTEGER,
    gmv              REAL,
    buyer_cnt        INTEGER
);

DROP TABLE IF EXISTS dws_campaign_daily;
CREATE TABLE dws_campaign_daily (
    stat_date      TEXT,
    campaign_id    TEXT,
    order_cnt      INTEGER,
    gmv            REAL,
    roi            REAL
);
