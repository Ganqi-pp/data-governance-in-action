"""数据清洗与标准化：校验、去重、码值归一、隔离与修复留痕。"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime

from . import db
from .checks import (
    clean_text,
    is_valid_email,
    is_valid_uscc,
    normalize_phone,
    parse_date,
    parse_datetime,
)
from .config import load_config, write_json
from .paths import REPORT_DIR

STATUS_MAP = {
    "正常": "存续",
    "在营": "在业",
    "开业": "存续",
    "经营中": "在业",
    "存续经营": "存续",
    "处理中": "办理中",
    "已完成": "已办结",
    "待处理": "待受理",
    "已回复": "已回访",
}
CASE_TYPE_MAP = {"咨询": "政策咨询", "投诉建议": "市场监管", "其他问题": "其他"}


class Cleaner:
    def __init__(self, conn, as_of: date):
        self.conn = conn
        self.as_of = as_of
        self.stats: dict[str, dict] = {}
        self.quarantine_rows: list[tuple] = []
        self.created_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
        self.divisions = {
            row["code"]: row["name"]
            for row in db.fetch_all(conn, "SELECT code, name, level FROM ref_administrative_divisions")
        }
        self.valid_districts = {
            row["code"]
            for row in db.fetch_all(
                conn, "SELECT code FROM ref_administrative_divisions WHERE level IN ('县','功能区')"
            )
        }
        self.industry_by_code = {
            row["code"]: row["name"] for row in db.fetch_all(conn, "SELECT code, name FROM ref_industry_codes")
        }
        self.industry_by_name = {
            row["name"]: row["code"] for row in db.fetch_all(conn, "SELECT code, name FROM ref_industry_codes")
        }

    def quarantine(self, table: str, key: str, code: str, desc: str, row: dict) -> None:
        self.quarantine_rows.append(
            (table, key, code, desc, json.dumps(row, ensure_ascii=False), self.created_at)
        )

    def _finish_stats(self, table: str, input_rows: int, output_rows: int, repairs: Counter) -> None:
        self.stats[table] = {
            "input_rows": input_rows,
            "output_rows": output_rows,
            "quarantined": input_rows - output_rows,
            "repairs": dict(sorted(repairs.items())),
        }

    # ------------------------------------------------------------------
    # 市场主体
    # ------------------------------------------------------------------
    def clean_market(self) -> list[dict]:
        source = db.fetch_all(self.conn, "SELECT * FROM ods_market_register")
        repairs = Counter()
        prepared = []
        for row in source:
            reg_id = clean_text(row["reg_id"])
            uscc = clean_text(row["unified_social_credit_code"]).upper()
            if not uscc:
                self.quarantine("market_register", reg_id, "USCC_MISSING", "统一社会信用代码为空", row)
                continue
            if not is_valid_uscc(uscc):
                self.quarantine("market_register", reg_id, "USCC_INVALID", "统一社会信用代码校验位错误", row)
                continue

            flags = []
            name = clean_text(row["company_name"])
            if name != (row["company_name"] or ""):
                flags.append("company_name:cleaned")
                repairs["company_name:cleaned"] += 1

            reg_date = parse_date(row["reg_date"])
            if reg_date is None:
                self.quarantine("market_register", reg_id, "DATE_MISSING", "注册日期缺失或无法解析，不能进入时间序列", row)
                continue
            if reg_date > self.as_of:
                self.quarantine("market_register", reg_id, "DATE_FUTURE", "注册日期晚于数据截止日，回源核实后再用", row)
                continue

            capital = None
            raw_capital = clean_text(row["reg_capital_wan"])
            if raw_capital:
                try:
                    capital = float(raw_capital)
                    if capital < 0:
                        flags.append("capital:negative_nulled")
                        repairs["capital:negative_nulled"] += 1
                        capital = None
                except ValueError:
                    flags.append("capital:invalid_nulled")
                    repairs["capital:invalid_nulled"] += 1

            industry = clean_text(row["industry_code"])
            if industry in self.industry_by_code:
                pass
            elif industry in self.industry_by_name:
                industry = self.industry_by_name[industry]
                flags.append("industry:mapped")
                repairs["industry:mapped"] += 1
            else:
                flags.append("industry:invalid_nulled")
                repairs["industry:invalid_nulled"] += 1
                industry = None

            address = clean_text(row["address"])
            district = clean_text(row["district_code"])
            district_from_address = None
            if "容城" in address:
                district_from_address = "130629"
            elif "安新县" in address:
                district_from_address = "130632"
            elif "雄县" in address:
                district_from_address = "130638"
            elif "启动区" in address:
                district_from_address = "133100"
            if district_from_address:
                if district != district_from_address:
                    flags.append("district:corrected")
                    repairs["district:corrected"] += 1
                district = district_from_address
            elif district not in self.valid_districts:
                flags.append("district:unresolved")
                repairs["district:unresolved"] += 1
                district = None

            phone_raw = clean_text(row["contact_phone"])
            phone = normalize_phone(phone_raw)
            if phone_raw and phone is None:
                flags.append("phone:invalid_nulled")
                repairs["phone:invalid_nulled"] += 1
            elif phone and phone != phone_raw:
                flags.append("phone:normalized")
                repairs["phone:normalized"] += 1

            email_raw = clean_text(row["contact_email"]).lower()
            email = email_raw if email_raw and is_valid_email(email_raw) else None
            if email_raw and email is None:
                flags.append("email:invalid_nulled")
                repairs["email:invalid_nulled"] += 1
            elif email and email != (row["contact_email"] or ""):
                flags.append("email:normalized")
                repairs["email:normalized"] += 1

            status_raw = clean_text(row["status"])
            status = STATUS_MAP.get(status_raw, status_raw)
            if status != status_raw:
                flags.append("status:mapped")
                repairs["status:mapped"] += 1
            elif status not in {"存续", "在业", "注销", "吊销", "迁出"}:
                flags.append("status:unmapped")
                repairs["status:unmapped"] += 1

            update_time = parse_datetime(row["update_time"])
            if update_time is None:
                flags.append("update_time:missing")
                repairs["update_time:missing"] += 1
            elif update_time[:10] > self.as_of.isoformat():
                flags.append("update_time:future_nulled")
                repairs["update_time:future_nulled"] += 1
                update_time = None

            prepared.append(
                {
                    "reg_id": reg_id,
                    "unified_social_credit_code": uscc,
                    "company_name": name,
                    "reg_date": reg_date.isoformat() if reg_date else None,
                    "reg_capital_wan": f"{capital:.2f}" if capital is not None else None,
                    "industry_code": industry,
                    "district_code": district,
                    "address": address or None,
                    "legal_person": clean_text(row["legal_person"]) or None,
                    "contact_phone": phone,
                    "contact_email": email,
                    "status": status or None,
                    "update_time": update_time,
                    "dq_flags": ";".join(flags),
                }
            )

        # 按业务主键去重：保留更新时间最新的一条
        groups: dict[str, list[dict]] = {}
        for row in prepared:
            groups.setdefault(row["unified_social_credit_code"], []).append(row)
        deduped = []
        for uscc, group in groups.items():
            group.sort(key=lambda r: (r["update_time"] or "", r["reg_id"]), reverse=True)
            deduped.append(group[0])
            for duplicate in group[1:]:
                self.quarantine(
                    "market_register", duplicate["reg_id"], "DUPLICATE",
                    f"业务主键 {uscc} 重复，保留最新记录 {group[0]['reg_id']}",
                    {"reg_id": duplicate["reg_id"], "uscc": uscc},
                )
        deduped.sort(key=lambda r: r["reg_id"])
        self._finish_stats("market_register", len(source), len(deduped), repairs)
        self.kept_uscc = {row["unified_social_credit_code"] for row in deduped}
        return deduped

    # ------------------------------------------------------------------
    # 信用评价
    # ------------------------------------------------------------------
    def clean_credit(self) -> list[dict]:
        source = db.fetch_all(self.conn, "SELECT * FROM ods_credit_rating")
        repairs = Counter()
        rows = []
        for row in source:
            rating_id = clean_text(row["rating_id"])
            uscc = clean_text(row["unified_social_credit_code"]).upper()
            if not uscc:
                self.quarantine("credit_rating", rating_id, "USCC_MISSING", "信用记录缺少统一社会信用代码", row)
                continue
            if uscc not in getattr(self, "kept_uscc", set()):
                self.quarantine("credit_rating", rating_id, "ORPHAN", "信用记录无法关联市场主体", row)
                continue
            flags = []
            score = None
            raw_score = clean_text(row["credit_score"])
            if raw_score:
                try:
                    value = int(float(raw_score))
                    if 0 <= value <= 100:
                        score = value
                    else:
                        flags.append("credit_score:range_nulled")
                        repairs["credit_score:range_nulled"] += 1
                except ValueError:
                    flags.append("credit_score:invalid_nulled")
                    repairs["credit_score:invalid_nulled"] += 1
            level_raw = clean_text(row["credit_level"]).upper()
            level = level_raw if level_raw in {"A", "B", "C", "D"} else None
            if score is not None:
                expected = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D"
                if level != expected:
                    flags.append("credit_level:recalculated")
                    repairs["credit_level:recalculated"] += 1
                level = expected
            elif level is None:
                flags.append("credit_level:invalid_nulled")
                repairs["credit_level:invalid_nulled"] += 1
            rating_date = parse_date(row["rating_date"])
            if rating_date is None or rating_date > self.as_of:
                self.quarantine("credit_rating", rating_id, "DATE_INVALID", "评级日期缺失、非法或晚于截止日", row)
                continue
            agency = clean_text(row["rating_agency"]) or None
            update_time = parse_datetime(row["update_time"])
            if update_time is None:
                flags.append("update_time:missing")
                repairs["update_time:missing"] += 1
            rows.append(
                {
                    "rating_id": rating_id,
                    "unified_social_credit_code": uscc,
                    "credit_score": str(score) if score is not None else None,
                    "credit_level": level,
                    "rating_date": rating_date.isoformat() if rating_date else None,
                    "rating_agency": agency,
                    "update_time": update_time,
                    "dq_flags": ";".join(flags),
                }
            )
        rows.sort(key=lambda r: r["rating_id"])
        self._finish_stats("credit_rating", len(source), len(rows), repairs)
        return rows

    # ------------------------------------------------------------------
    # 企业诉求
    # ------------------------------------------------------------------
    def clean_case(self) -> list[dict]:
        source = db.fetch_all(self.conn, "SELECT * FROM ods_complaint_case")
        repairs = Counter()
        rows = []
        kept_uscc = getattr(self, "kept_uscc", set())
        for row in source:
            case_id = clean_text(row["case_id"])
            uscc = clean_text(row["unified_social_credit_code"]).upper()
            if uscc and uscc not in kept_uscc:
                self.quarantine("complaint_case", case_id, "ORPHAN", "诉求工单无法关联市场主体", row)
                continue
            flags = []
            case_type_raw = clean_text(row["case_type"])
            case_type = CASE_TYPE_MAP.get(case_type_raw, case_type_raw)
            if case_type != case_type_raw:
                flags.append("case_type:mapped")
                repairs["case_type:mapped"] += 1
            elif case_type not in {"登记注册", "税务办理", "社保缴纳", "政策咨询", "融资服务", "市场监管", "其他"}:
                flags.append("case_type:unmapped")
                repairs["case_type:unmapped"] += 1
            submit_time = parse_datetime(row["submit_time"])
            if submit_time is None or submit_time[:10] > self.as_of.isoformat():
                self.quarantine("complaint_case", case_id, "DATE_INVALID", "提交时间缺失、非法或晚于截止日", row)
                continue
            status_raw = clean_text(row["status"])
            status = STATUS_MAP.get(status_raw, status_raw)
            if status != status_raw:
                flags.append("status:mapped")
                repairs["status:mapped"] += 1
            elif status not in {"待受理", "办理中", "已办结", "已回访"}:
                flags.append("status:unmapped")
                repairs["status:unmapped"] += 1
            satisfaction = None
            raw_sat = clean_text(row["satisfaction"])
            if raw_sat:
                try:
                    value = int(float(raw_sat))
                    if 1 <= value <= 5:
                        satisfaction = value
                    else:
                        flags.append("satisfaction:range_nulled")
                        repairs["satisfaction:range_nulled"] += 1
                except ValueError:
                    flags.append("satisfaction:invalid_nulled")
                    repairs["satisfaction:invalid_nulled"] += 1
            close_time = parse_datetime(row["close_time"])
            if close_time and submit_time and close_time < submit_time:
                flags.append("close_time:order_nulled")
                repairs["close_time:order_nulled"] += 1
                close_time = None
                if status in ("已办结", "已回访"):
                    status = "办理中"
                    flags.append("status:reopened")
                    repairs["status:reopened"] += 1
            rows.append(
                {
                    "case_id": case_id,
                    "unified_social_credit_code": uscc or None,
                    "case_type": case_type or None,
                    "submit_time": submit_time,
                    "content": clean_text(row["content"]) or None,
                    "handling_dept": clean_text(row["handling_dept"]) or None,
                    "status": status or None,
                    "satisfaction": str(satisfaction) if satisfaction is not None else None,
                    "close_time": close_time,
                    "dq_flags": ";".join(flags),
                }
            )
        rows.sort(key=lambda r: r["case_id"])
        self._finish_stats("complaint_case", len(source), len(rows), repairs)
        return rows

    # ------------------------------------------------------------------
    # 写库
    # ------------------------------------------------------------------
    def _create_dwd(self, table: str, fields: list[str]) -> None:
        columns = ", ".join(f'"{f}" TEXT' for f in fields)
        self.conn.execute(f'DROP TABLE IF EXISTS "{table}"')
        self.conn.execute(f'CREATE TABLE "{table}" ({columns})')

    def _insert(self, table: str, fields: list[str], rows: list[dict]) -> None:
        placeholders = ", ".join("?" for _ in fields)
        quoted = ", ".join(f'"{f}"' for f in fields)
        self.conn.executemany(
            f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders})',
            [tuple(row.get(f) for f in fields) for row in rows],
        )
        self.conn.commit()

    def run(self) -> dict:
        standards = load_config("standards.json")
        self.conn.execute("DROP TABLE IF EXISTS quarantine_records")
        self.conn.execute(
            "CREATE TABLE quarantine_records (id INTEGER PRIMARY KEY AUTOINCREMENT, table_name TEXT, "
            "record_key TEXT, reason_code TEXT, reason_desc TEXT, raw_json TEXT, created_at TEXT)"
        )
        market = self.clean_market()
        credit = self.clean_credit()
        cases = self.clean_case()
        for logical, rows in (("market_register", market), ("credit_rating", credit), ("complaint_case", cases)):
            fields = list(standards["tables"][logical]["fields"].keys()) + ["dq_flags"]
            dwd_table = db.DWD_TABLES[logical]
            self._create_dwd(dwd_table, fields)
            self._insert(dwd_table, fields, rows)
        if self.quarantine_rows:
            self.conn.executemany(
                "INSERT INTO quarantine_records (table_name, record_key, reason_code, reason_desc, raw_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                self.quarantine_rows,
            )
            self.conn.commit()
        total_in = sum(s["input_rows"] for s in self.stats.values())
        total_out = sum(s["output_rows"] for s in self.stats.values())
        result = {
            "as_of": self.as_of.isoformat(),
            "tables": self.stats,
            "total_input": total_in,
            "total_output": total_out,
            "total_quarantined": total_in - total_out,
            "availability": round(total_out / total_in, 4) if total_in else 0,
            "quarantine_reasons": self._reason_counts(),
            "repairs": self._repair_totals(),
            "generated_at": self.created_at,
        }
        write_json(REPORT_DIR / "cleaning_stats.json", result)
        return result

    def _reason_counts(self) -> dict:
        counter = Counter()
        for row in self.quarantine_rows:
            counter[row[2]] += 1
        return dict(sorted(counter.items()))

    def _repair_totals(self) -> dict:
        counter = Counter()
        for stats in self.stats.values():
            counter.update(stats["repairs"])
        return dict(sorted(counter.items()))


def run(conn, as_of: date) -> dict:
    return Cleaner(conn, as_of).run()
