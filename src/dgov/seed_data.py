# -*- coding: utf-8 -*-
"""生成可复现的示例数据，并按比例注入典型数据质量问题。

数据规模：60,000 订单 / 8,000 用户 / 120 商品 / 6 渠道 / 8 活动 / 约 3.6 万物流单。
所有缺陷都是"故意"注入的，用于演示质量规则能否准确发现并定位问题。
"""
from __future__ import annotations

import random
import sqlite3
from datetime import datetime, timedelta

SEED = 20260801
BASE_DATE = datetime(2026, 7, 1, 0, 0, 0)
DAYS = 90
ORDER_COUNT = 60_000
USER_COUNT = 8_000
PRODUCT_COUNT = 120

PROVINCES = {
    "河北省": ["石家庄市", "保定市", "唐山市", "廊坊市"],
    "北京市": ["朝阳区", "海淀区", "丰台区"],
    "天津市": ["和平区", "南开区", "河西区"],
    "山东省": ["济南市", "青岛市", "烟台市"],
    "河南省": ["郑州市", "洛阳市", "新乡市"],
    "辽宁省": ["沈阳市", "大连市", "鞍山市"],
}

CATEGORIES = [
    ("C01", "女装"),
    ("C02", "男装"),
    ("C03", "鞋靴"),
    ("C04", "箱包"),
    ("C05", "配饰"),
    ("C06", "家居"),
]

CHANNELS = [
    ("APP", "自营 APP", "自营", 1),
    ("WEB", "官方商城", "自营", 1),
    ("MINI", "微信小程序", "自营", 1),
    ("TMALL", "天猫旗舰店", "平台", 1),
    ("JD", "京东旗舰店", "平台", 1),
    ("OFFLINE", "线下门店", "线下", 0),
]

CARRIERS = ["顺丰", "中通", "圆通", "京东物流"]

STATUS_LIST = ["待支付", "已支付", "已发货", "已完成", "已取消", "退款中", "已退款"]
STATUS_WEIGHTS = [8, 20, 15, 40, 7, 3, 7]

MEMBER_LEVELS = ["普通", "银卡", "金卡", "黑卡"]
MEMBER_WEIGHTS = [62, 24, 11, 3]


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _rand_dt(rng: random.Random) -> datetime:
    day = rng.randrange(DAYS)
    sec = rng.randrange(24 * 3600)
    return BASE_DATE + timedelta(days=day, seconds=sec)


def _phone(rng: random.Random) -> str:
    prefix = rng.choice(["130", "131", "133", "135", "136", "137", "138", "139", "150",
                         "151", "152", "155", "156", "157", "158", "159", "180", "181",
                         "182", "183", "185", "186", "187", "188", "189", "199"])
    return prefix + "".join(str(rng.randrange(10)) for _ in range(8))


def _id_card(rng: random.Random) -> str:
    return "130681" + "".join(str(rng.randrange(10)) for _ in range(12))


def generate(conn: sqlite3.Connection) -> dict:
    rng = random.Random(SEED)

    # ---------- 渠道 ----------
    channel_rows = [(c[0], c[1], c[2], c[3]) for c in CHANNELS]
    conn.executemany("INSERT INTO ods_channel VALUES (?,?,?,?)", channel_rows)

    # ---------- 商品 ----------
    products = []
    for i in range(PRODUCT_COUNT):
        cid, cname = CATEGORIES[i % len(CATEGORIES)]
        price = round(rng.uniform(49, 1299), 2)
        products.append({
            "product_id": f"P{i + 1:04d}",
            "product_name": f"{cname}商品{i + 1:03d}",
            "category_code": cid,
            "category_name": cname,
            "price": price,
            "status": rng.choices(["在售", "下架", "预售"], [88, 8, 4])[0],
            "brand": rng.choice(["自有品牌", "品牌 A", "品牌 B", "品牌 C"]),
            "supplier": rng.choice(["供应商甲", "供应商乙", "供应商丙"]),
        })
    conn.executemany(
        "INSERT INTO ods_product VALUES (:product_id,:product_name,:category_code,"
        ":category_name,:price,:status,:brand,:supplier)",
        products,
    )

    # ---------- 用户 ----------
    users = []
    for i in range(USER_COUNT):
        province = rng.choice(list(PROVINCES))
        city = rng.choice(PROVINCES[province])
        reg = BASE_DATE - timedelta(days=rng.randrange(30, 900))
        users.append({
            "user_id": f"U{i + 1:06d}",
            "user_name": rng.choice(["张", "李", "王", "刘", "陈", "赵"]) + rng.choice(["伟", "敏", "静", "磊", "洋", "强"]),
            "phone": _phone(rng),
            "email": f"user{i + 1:06d}@example.com",
            "id_card": _id_card(rng),
            "register_time": _ts(reg),
            "city": city,
            "member_level": rng.choices(MEMBER_LEVELS, MEMBER_WEIGHTS)[0],
            "age": rng.randrange(18, 60),
            "gender": rng.choice(["男", "女"]),
        })
    conn.executemany(
        "INSERT INTO ods_user VALUES (:user_id,:user_name,:phone,:email,:id_card,"
        ":register_time,:city,:member_level,:age,:gender)",
        users,
    )

    # ---------- 订单 ----------
    orders = []
    for i in range(ORDER_COUNT):
        p = rng.choice(products)
        province = rng.choice(list(PROVINCES))
        city = rng.choice(PROVINCES[province])
        qty = rng.choices([1, 2, 3], [82, 14, 4])[0]
        amount = round(p["price"] * qty, 2)
        coupon = round(amount * rng.choice([0, 0, 0, 0.05, 0.1]), 2)
        pay = round(amount - coupon, 2)
        status = rng.choices(STATUS_LIST, STATUS_WEIGHTS)[0]
        create = _rand_dt(rng)
        pay_time = None
        if status in ("已支付", "已发货", "已完成", "退款中", "已退款"):
            pay_time = create + timedelta(minutes=rng.randrange(1, 180))
        if status == "待支付":
            pay = 0.0
        orders.append({
            "order_id": f"SO{create.strftime('%Y%m%d')}{i + 1:07d}",
            "user_id": users[i % USER_COUNT]["user_id"],
            "product_id": p["product_id"],
            "channel_code": rng.choice([c[0] for c in CHANNELS]),
            "order_amount": amount,
            "pay_amount": pay,
            "coupon_amount": coupon,
            "order_status": status,
            "province": province,
            "city": city,
            "phone": users[i % USER_COUNT]["phone"],
            "address": f"{province}{city}{rng.choice(['中山路', '建设大街', '人民路'])}{rng.randrange(1, 300)}号",
            "create_time": _ts(create),
            "pay_time": _ts(pay_time) if pay_time else None,
            "source": rng.choice(["交易系统", "门店 POS"]),
        })

    # ---------- 注入缺陷 ----------
    def mutate(prob: float, fn) -> int:
        hit = 0
        for row in orders:
            if rng.random() < prob:
                fn(row)
                hit += 1
        return hit

    stats = {}
    stats["重复订单号"] = 0
    duplicates = [dict(o) for o in rng.sample(orders, 600)]
    for dup in duplicates:
        dup["pay_amount"] = round(dup["pay_amount"] * rng.choice([0.5, 1.0, 2.0]), 2)
    orders.extend(duplicates)
    stats["重复订单号"] = len(duplicates)

    stats["用户 ID 为空"] = mutate(0.005, lambda o: o.update(user_id=None))
    stats["渠道编码为空"] = mutate(0.004, lambda o: o.update(channel_code=None))
    stats["下单时间为空"] = mutate(0.002, lambda o: o.update(create_time=None))
    stats["手机号格式异常"] = mutate(0.02, lambda o: o.update(phone=rng.choice([
        "1381234567", "138-1234-5678", "abcdefghijk", "13812345678x"])))
    stats["支付金额为负"] = mutate(0.006, lambda o: o.update(pay_amount=-abs(o["pay_amount"])))
    stats["订单状态非法"] = mutate(0.008, lambda o: o.update(order_status=rng.choice(["PAID", "paid", "未知"])))
    stats["渠道编码脏值"] = mutate(0.012, lambda o: o.update(channel_code=rng.choice([" app", "App", "WEB ", "mini"])))
    stats["支付时间早于下单"] = mutate(0.003, lambda o: o.update(
        pay_time=_ts(datetime.strptime(o["create_time"], "%Y-%m-%d %H:%M:%S") - timedelta(hours=2))
        if o["create_time"] else None))
    stats["已支付缺支付时间"] = mutate(0.005, lambda o: o.update(pay_time=None) if o["order_status"] == "已支付" else None)
    stats["商品 ID 不可关联"] = mutate(0.003, lambda o: o.update(product_id="P9999"))

    conn.executemany(
        "INSERT INTO ods_order VALUES (:order_id,:user_id,:product_id,:channel_code,"
        ":order_amount,:pay_amount,:coupon_amount,:order_status,:province,:city,"
        ":phone,:address,:create_time,:pay_time,:source)",
        orders,
    )

    # ---------- 物流 ----------
    logistics = []
    idx = 0
    for o in orders:
        if o["order_status"] in ("已发货", "已完成", "退款中", "已退款") and o["create_time"]:
            idx += 1
            ship = datetime.strptime(o["create_time"], "%Y-%m-%d %H:%M:%S") + timedelta(hours=rng.randrange(6, 48))
            receive = ship + timedelta(days=rng.randrange(1, 5))
            logistics.append((
                f"LG{idx:08d}", o["order_id"], rng.choice(CARRIERS),
                "已签收" if o["order_status"] == "已完成" else "运输中",
                _ts(ship), _ts(receive) if o["order_status"] == "已完成" else None,
            ))
    conn.executemany("INSERT INTO ods_logistics VALUES (?,?,?,?,?,?)", logistics)

    # ---------- 营销活动（含历史驼峰命名，作为标准整改样例） ----------
    campaigns = []
    for i in range(8):
        start = BASE_DATE + timedelta(days=i * 7)
        campaigns.append((
            f"CMP{i + 1:03d}",
            f"2026 年 {i + 7} 月大促活动",
            CHANNELS[i % len(CHANNELS)][0],
            round(rng.uniform(50_000, 200_000), 2),
            _ts(start),
            _ts(start + timedelta(days=7)),
        ))
    conn.executemany("INSERT INTO ods_campaign VALUES (?,?,?,?,?,?)", campaigns)

    conn.commit()

    stats["订单总数"] = len(orders)
    stats["用户总数"] = len(users)
    stats["商品总数"] = len(products)
    stats["物流单数"] = len(logistics)
    return stats
