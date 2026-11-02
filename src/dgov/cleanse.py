# -*- coding: utf-8 -*-
"""清洗与标准化：ODS → DWD（去重、码值标准化、时序修复、脱敏、分层标记）。"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from . import db
from .config import load_json

PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
PAID_STATUS = {"已支付", "已发货", "已完成", "退款中", "已退款"}
STATUS_MAP = {"PAID": "已支付", "paid": "已支付", "未知": "待支付"}
CHANNELS = {"APP", "WEB", "MINI", "TMALL", "JD", "OFFLINE"}
USER_LEVEL = {"普通": "普通用户", "银卡": "潜力用户", "金卡": "高价值用户", "黑卡": "核心用户"}


def mask_phone(phone: str | None) -> str | None:
    if not phone or len(phone) != 11:
        return phone
    return phone[:3] + "****" + phone[-4:]


def mask_name(name: str | None) -> str | None:
    if not name:
        return name
    return name[0] + "*" * max(len(name) - 1, 1)


def mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    return (local[0] if local else "*") + "***@" + domain


def mask_address(province: str | None, city: str | None) -> str:
    return f"{province or ''}{city or ''}***"


def _parse(ts: str | None):
    if not ts:
        return None
    try:
        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def build_dwd(conn) -> dict:
    stats = {
        "orders_read": 0, "duplicates_removed": 0, "rejected_no_time": 0,
        "rejected_no_user": 0, "channel_unknown": 0, "channel_normalized": 0,
        "status_invalid": 0, "phone_invalid": 0, "pay_amount_fixed": 0,
        "pay_time_fixed": 0, "pay_time_filled": 0, "product_unknown": 0,
        "orders_written": 0,
    }

    rows = conn.execute("SELECT * FROM ods_order").fetchall()
    stats["orders_read"] = len(rows)

    product_ids = {r[0] for r in conn.execute("SELECT product_id FROM ods_product")}

    # 去重：同一订单号保留记录最完整、下单时间最新的一条
    dedup: dict[str, dict] = {}
    for r in rows:
        row = dict(r)
        key = (row["order_id"] or "").strip()
        if not key:
            continue
        stats["duplicates_removed"] += 1 if key in dedup else 0
        prev = dedup.get(key)
        if prev is None:
            dedup[key] = row
            continue
        prev_key = (prev.get("create_time") or "", len(str(prev)))
        new_key = (row.get("create_time") or "", len(str(row)))
        if new_key > prev_key:
            dedup[key] = row

    out = []
    for row in dedup.values():
        create = _parse(row["create_time"])
        if create is None:
            stats["rejected_no_time"] += 1
            continue
        if not (row["user_id"] or "").strip():
            stats["rejected_no_user"] += 1
            continue

        channel = (row["channel_code"] or "").strip().upper()
        if channel not in CHANNELS:
            channel = "UNKNOWN"
            stats["channel_unknown"] += 1
        elif channel != (row["channel_code"] or ""):
            stats["channel_normalized"] += 1

        status = (row["order_status"] or "").strip()
        if status not in set(load_json("standards.json")["codes"]["order_status"]):
            status = STATUS_MAP.get(status, "待支付")
            stats["status_invalid"] += 1
            valid = 0
        else:
            valid = 1

        pay_amount = float(row["pay_amount"] or 0)
        if pay_amount < 0:
            pay_amount = abs(pay_amount)
            stats["pay_amount_fixed"] += 1
            valid = 0
        if status in ("待支付", "已取消"):
            pay_amount = 0.0

        pay_time = _parse(row["pay_time"])
        if pay_time and pay_time < create:
            pay_time = None
            stats["pay_time_fixed"] += 1
            valid = 0
        if status in PAID_STATUS and pay_time is None:
            pay_time = create + timedelta(minutes=30)
            stats["pay_time_filled"] += 1
            valid = 0

        phone = (row["phone"] or "").strip()
        if phone and not PHONE_RE.match(phone):
            stats["phone_invalid"] += 1
            valid = 0
            phone = None

        product_id = row["product_id"]
        if product_id not in product_ids:
            stats["product_unknown"] += 1
            valid = 0

        out.append((
            row["order_id"], row["user_id"], product_id, channel,
            float(row["order_amount"] or 0), round(pay_amount, 2), status,
            row["province"], row["city"], phone,
            mask_address(row["province"], row["city"]),
            create.strftime("%Y-%m-%d %H:%M:%S"),
            pay_time.strftime("%Y-%m-%d %H:%M:%S") if pay_time else None,
            create.strftime("%Y-%m-%d"), valid,
        ))

    conn.executemany(
        "INSERT INTO dwd_order_detail VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", out
    )
    stats["orders_written"] = len(out)

    # ---------- 用户画像 ----------
    users = conn.execute("SELECT * FROM ods_user").fetchall()
    seen = set()
    user_rows = []
    for u in users:
        if u["user_id"] in seen:
            continue
        seen.add(u["user_id"])
        phone = (u["phone"] or "").strip()
        if phone and not PHONE_RE.match(phone):
            phone = None
        user_rows.append((
            u["user_id"], mask_name(u["user_name"]), phone, mask_email(u["email"]),
            u["city"], u["member_level"], u["register_time"],
            USER_LEVEL.get(u["member_level"], "普通用户"),
        ))
    conn.executemany("INSERT INTO dwd_user_profile VALUES (?,?,?,?,?,?,?,?)", user_rows)

    # ---------- 商品维度 ----------
    products = conn.execute("SELECT * FROM ods_product").fetchall()
    prod_rows = []
    for p in products:
        price = float(p["price"] or 0)
        price = abs(price) if price < 0 else price
        status = p["status"] if p["status"] in ("在售", "下架", "预售") else "下架"
        prod_rows.append((p["product_id"], p["product_name"], p["category_code"],
                          p["category_name"], price, status, p["brand"]))
    conn.executemany("INSERT INTO dwd_product_dim VALUES (?,?,?,?,?,?,?)", prod_rows)

    conn.commit()
    return stats


def build_dws(conn) -> None:
    db.run_sql_file(conn, "build_dws.sql")
