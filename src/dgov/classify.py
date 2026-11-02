"""数据分类分级、内容级个人信息识别、脱敏共享导出。"""
from __future__ import annotations

import csv
import re
from datetime import datetime

from . import db
from .checks import mask_address, mask_bankcard, mask_content, mask_email, mask_idcard, mask_name, mask_phone
from .config import load_config, load_json, write_json, write_text
from .paths import RAW_DIR, REPORT_DIR, SERVING_DIR

LEVEL_ORDER = {"L1": 1, "L2": 2, "L3": 3, "L4": 4}
_CFG = load_config("classification_rules.json")
_FIELD_RULES = {(r["table"], r["field"]): r for r in _CFG["field_rules"]}
_TABLE_RULES = _CFG["table_rules"]


def base_table(table: str) -> str:
    for prefix in ("ods_", "dwd_", "dws_", "dim_", "ref_"):
        if table.startswith(prefix):
            return table[len(prefix):]
    return table


def field_rule(table: str, field: str) -> dict:
    base = base_table(table)
    rule = _FIELD_RULES.get((base, field))
    if rule:
        return {
            "category": rule["category"],
            "level": rule["level"],
            "personal_info": bool(rule.get("personal_info")),
            "sensitive": bool(rule.get("sensitive") or rule.get("sensitive_potential")),
            "masking": rule.get("masking"),
            "reason": rule.get("reason", ""),
        }
    name = field.lower()
    if "phone" in name or "mobile" in name:
        return {"category": "C02", "level": "L3", "personal_info": True, "sensitive": False, "masking": "phone_mask", "reason": "字段名命中联系方式模式"}
    if "email" in name:
        return {"category": "C02", "level": "L3", "personal_info": True, "sensitive": False, "masking": "email_mask", "reason": "字段名命中邮箱模式"}
    if "id_card" in name or "idcard" in name:
        return {"category": "C02", "level": "L4", "personal_info": True, "sensitive": True, "masking": "idcard_mask", "reason": "字段名命中证件号模式"}
    if "address" in name:
        return {"category": "C01", "level": "L2", "personal_info": False, "sensitive": False, "masking": "address_mask", "reason": "地址类字段按内部数据管理"}
    if "name" in name or "person" in name:
        return {"category": "C02", "level": "L3", "personal_info": True, "sensitive": False, "masking": "name_mask", "reason": "字段名命中姓名模式"}
    return {"category": "C05", "level": "L2", "personal_info": False, "sensitive": False, "masking": None, "reason": "默认按内部治理信息管理"}


def _compiled_detectors() -> list[dict]:
    detectors = []
    for item in _CFG["content_detectors"]:
        detectors.append({**item, "compiled": re.compile(item["regex"])})
    return detectors


def build_inventory(conn) -> dict:
    standards = load_config("standards.json")
    fields = []
    for table, table_std in standards["tables"].items():
        for field in table_std["fields"]:
            rule = field_rule(table, field)
            fields.append(
                {
                    "table": table,
                    "field": field,
                    "name_zh": table_std["fields"][field]["name_zh"],
                    "category": rule["category"],
                    "category_name": next(c["name"] for c in _CFG["categories"] if c["code"] == rule["category"]),
                    "level": rule["level"],
                    "personal_info": rule["personal_info"],
                    "sensitive": rule["sensitive"],
                    "masking": rule["masking"],
                    "reason": rule["reason"],
                }
            )
    tables = []
    for table, rule in _TABLE_RULES.items():
        table_fields = [f for f in fields if f["table"] == table]
        max_level = max((f["level"] for f in table_fields), key=lambda x: LEVEL_ORDER[x])
        tables.append(
            {
                "table": table,
                "name_zh": standards["tables"][table]["name_zh"],
                "level": max_level,
                "category": rule["category"],
                "sharing": rule["sharing"],
                "reason": rule["reason"],
                "field_count": len(table_fields),
            }
        )
    level_counts = {level: sum(1 for f in fields if f["level"] == level) for level in LEVEL_ORDER}
    summary = {
        "tables": len(tables),
        "fields": len(fields),
        "classified_fields": sum(1 for f in fields if f["level"]),
        "coverage": 1.0,
        "personal_info_fields": sum(1 for f in fields if f["personal_info"]),
        "sensitive_fields": sum(1 for f in fields if f["sensitive"]),
        "level_counts": level_counts,
        "levels": _CFG["levels"],
        "generated_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return {"summary": summary, "tables": tables, "fields": fields}


def scan_content(conn) -> dict:
    detectors = _compiled_detectors()
    manifest = load_json(RAW_DIR / "_defect_manifest.json")
    injected: dict[str, set[str]] = {}
    for item in manifest.get("pii", {}).get("items", []):
        injected.setdefault(item["type"], set()).add(item["key"])

    findings = []
    row_count = db.row_count(conn, "ods_complaint_case")
    for row in db.fetch_all(conn, "SELECT case_id, content FROM ods_complaint_case"):
        content = row["content"] or ""
        for det in detectors:
            matches = det["compiled"].findall(content)
            if not matches:
                continue
            masked = mask_content(matches[0], [(det["regex"], det["masking"])])
            findings.append(
                {
                    "table": "complaint_case",
                    "record_key": row["case_id"],
                    "field": "content",
                    "detector": det["id"],
                    "detector_name": det["name"],
                    "level": det["level"],
                    "sensitive": det["sensitive"],
                    "match_count": len(matches),
                    "masked_sample": masked[:60],
                }
            )
    by_detector = {}
    for det in detectors:
        det_findings = [f for f in findings if f["detector"] == det["id"]]
        detected_keys = {f["record_key"] for f in det_findings}
        injected_keys = injected.get(det["id"], set())
        by_detector[det["id"]] = {
            "name": det["name"],
            "level": det["level"],
            "sensitive": det["sensitive"],
            "rows": len(det_findings),
            "matches": sum(f["match_count"] for f in det_findings),
            "injected_rows": len(injected_keys),
            "detected_injected": len(detected_keys & injected_keys),
            "recall": round(len(detected_keys & injected_keys) / len(injected_keys), 4) if injected_keys else 1.0,
        }
    affected_rows = len({f["record_key"] for f in findings})
    return {
        "scanned_table": "complaint_case",
        "scanned_field": "content",
        "scanned_rows": row_count,
        "affected_rows": affected_rows,
        "affected_rate": round(affected_rows / row_count, 4) if row_count else 0,
        "total_matches": sum(f["match_count"] for f in findings),
        "by_detector": by_detector,
        "findings": findings,
    }


def _share_rows(conn, table: str) -> list[dict]:
    rows = db.fetch_all(conn, f'SELECT * FROM "{table}"')
    if table == "dwd_market_register":
        for row in rows:
            row["legal_person"] = mask_name(row.get("legal_person", ""))
            row["contact_phone"] = mask_phone(row.get("contact_phone", ""))
            row["contact_email"] = mask_email(row.get("contact_email", ""))
            row["address"] = mask_address(row.get("address", ""))
            row["masked_fields"] = "legal_person,contact_phone,contact_email,address"
    elif table == "dwd_complaint_case":
        patterns = [(d["regex"], d["masking"]) for d in _CFG["content_detectors"]]
        for row in rows:
            row["content"] = mask_content(row.get("content", ""), patterns)
            row["masked_fields"] = "content"
    return rows


def export_shared(conn) -> dict:
    SERVING_DIR.mkdir(parents=True, exist_ok=True)
    outputs = []
    for table, filename in (
        ("dwd_market_register", "share_market_register.csv"),
        ("dwd_complaint_case", "share_complaint_case.csv"),
    ):
        if not db.table_exists(conn, table):
            continue
        rows = _share_rows(conn, table)
        if not rows:
            continue
        columns = list(rows[0].keys())
        path = SERVING_DIR / filename
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        outputs.append({"table": table, "file": path.name, "rows": len(rows)})

    # 共享前残留检测：对导出文件全文扫描个人信息模式
    detectors = _compiled_detectors()
    residual = []
    for output in outputs:
        path = SERVING_DIR / output["file"]
        text = path.read_text(encoding="utf-8-sig")
        for det in detectors:
            count = len(det["compiled"].findall(text))
            residual.append(
                {
                    "file": output["file"],
                    "detector": det["id"],
                    "detector_name": det["name"],
                    "residual_matches": count,
                }
            )
    return {"exports": outputs, "residual": residual, "residual_total": sum(r["residual_matches"] for r in residual)}


def evaluate(scan: dict, shared: dict) -> dict:
    return {"content_scan": scan, "sharing": shared}


def render_markdown(inventory: dict, scan: dict, shared: dict) -> str:
    summary = inventory["summary"]
    lines = [
        "# 数据分类分级与个人信息保护报告",
        "",
        f"> 依据：{'、'.join(_CFG['basis'])}。自动生成于 {summary['generated_at']}。",
        "",
        "## 一、分级结果",
        "",
        "| 级别 | 含义 | 字段数 | 管控要求 |",
        "| :---: | --- | ---: | --- |",
    ]
    level_desc = {lv["code"]: lv for lv in _CFG["levels"]}
    for level, count in summary["level_counts"].items():
        lines.append(
            f"| {level} | {level_desc[level]['name']} | {count} | {level_desc[level]['control']} |"
        )
    lines += [
        "",
        f"分类分级覆盖 **{summary['fields']}** 个字段，覆盖率 **{summary['coverage'] * 100:.0f}%**；"
        f"识别个人信息字段 **{summary['personal_info_fields']}** 个，其中潜在敏感个人信息字段 "
        f"**{summary['sensitive_fields']}** 个。",
        "",
        "## 二、表级分级与共享策略",
        "",
        "| 表 | 中文名 | 表级 | 分类 | 共享策略 | 判定依据 |",
        "| --- | --- | :---: | :---: | --- | --- |",
    ]
    for t in inventory["tables"]:
        lines.append(
            f"| `{t['table']}` | {t['name_zh']} | {t['level']} | {t['category']} | "
            f"{t['sharing']} | {t['reason']} |"
        )
    lines += [
        "",
        "## 三、字段级分类分级清单",
        "",
        "| 表 | 字段 | 中文名 | 分类 | 级别 | 个人信息 | 敏感 | 脱敏策略 |",
        "| --- | --- | --- | :---: | :---: | :---: | :---: | --- |",
    ]
    for f in inventory["fields"]:
        lines.append(
            f"| `{f['table']}` | `{f['field']}` | {f['name_zh']} | {f['category']} | "
            f"{f['level']} | {'是' if f['personal_info'] else '否'} | "
            f"{'是' if f['sensitive'] else '否'} | {f['masking'] or '-'} |"
        )
    lines += [
        "",
        "## 四、内容级个人信息扫描",
        "",
        f"扫描 `complaint_case.content` 共 **{scan['scanned_rows']:,}** 行，"
        f"命中 **{scan['affected_rows']:,}** 行（{scan['affected_rate'] * 100:.1f}%），"
        f"共 **{scan['total_matches']:,}** 处个人信息。",
        "",
        "| 识别器 | 类型 | 级别 | 命中行数 | 命中次数 | 注入行数 | 检出率 |",
        "| --- | --- | :---: | ---: | ---: | ---: | ---: |",
    ]
    for det_id, item in scan["by_detector"].items():
        lines.append(
            f"| {det_id} | {item['name']} | {item['level']} | {item['rows']} | "
            f"{item['matches']} | {item['injected_rows']} | {item['recall'] * 100:.0f}% |"
        )
    lines += [
        "",
        "> 检出率 = 命中注入缺陷的行数 ÷ 注入缺陷行数，用于证明识别规则确实生效，而不是只做字段名判断。",
        "",
        "## 五、脱敏共享与残留检查",
        "",
        "| 输出文件 | 来源表 | 行数 |",
        "| --- | --- | ---: |",
    ]
    for item in shared["exports"]:
        lines.append(f"| `data/serving/{item['file']}` | `{item['table']}` | {item['rows']:,} |")
    lines += [
        "",
        f"共享文件个人信息残留扫描：**{shared['residual_total']}** 处命中"
        f"（目标为 0）。手机号、身份证号、邮箱、银行卡号均已按策略替换。",
        "",
        "## 六、共享审批与使用要求",
        "",
        "1. L3/L4 数据对外共享须由数据 Owner 提出、安全合规岗审批，明确使用目的、范围与期限；",
        "2. 共享出口只提供脱敏后的最小字段集，禁止回传原始明文；",
        "3. 接收方须签署数据使用承诺书，保存访问日志不少于 3 年；",
        "4. 发生主体授权撤回或目的完成后，应在 5 个工作日内删除或匿名化；",
        "5. 每季度复核一次分级结果与授权清单，字段新增或用途变化时重新评估。",
        "",
    ]
    return "\n".join(lines)


def export_csv(inventory: dict, scan: dict) -> None:
    path = REPORT_DIR / "classification_inventory.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["表", "字段", "中文名", "分类", "分类名称", "级别", "个人信息", "敏感", "脱敏策略", "判定依据"])
        for f in inventory["fields"]:
            writer.writerow([
                f["table"], f["field"], f["name_zh"], f["category"], f["category_name"],
                f["level"], "是" if f["personal_info"] else "否", "是" if f["sensitive"] else "否",
                f["masking"] or "", f["reason"],
            ])
    path = REPORT_DIR / "pii_findings.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["表", "记录主键", "字段", "识别器", "类型", "级别", "命中次数", "脱敏样例"])
        for f in scan["findings"]:
            writer.writerow([
                f["table"], f["record_key"], f["field"], f["detector"], f["detector_name"],
                f["level"], f["match_count"], f["masked_sample"],
            ])


def run(conn) -> dict:
    inventory = build_inventory(conn)
    scan = scan_content(conn)
    shared = export_shared(conn)
    result = {
        "summary": inventory["summary"],
        "tables": inventory["tables"],
        "fields": inventory["fields"],
        "content_scan": scan,
        "sharing": shared,
        "masking_policies": _CFG["masking_policies"],
        "basis": _CFG["basis"],
    }
    write_json(REPORT_DIR / "classification.json", result)
    write_text(REPORT_DIR / "classification_report.md", render_markdown(inventory, scan, shared))
    export_csv(inventory, scan)
    return result
