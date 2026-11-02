"""元数据采集与数据目录：自动采集结构、行数、空值率、基数和高频值。"""
from __future__ import annotations

from datetime import datetime

from . import db
from .classify import field_rule
from .config import load_config, write_json, write_text
from .paths import REPORT_DIR, TABLE_TITLES

LAYER_LABEL = {"ods": "贴源层", "dwd": "明细层", "dws": "指标层", "ref": "参考层"}


def logical_name(table: str) -> str:
    for prefix in ("ods_", "dwd_", "dws_", "dim_", "ref_"):
        if table.startswith(prefix):
            return table[len(prefix):]
    return table


def layer_of(table: str) -> str:
    if table.startswith("ods_"):
        return "ODS"
    if table.startswith("dwd_"):
        return "DWD"
    if table.startswith("dws_"):
        return "DWS"
    if table.startswith("ref_"):
        return "REF"
    return "OTHER"


def profile_table(conn, table: str) -> dict:
    total = db.row_count(conn, table)
    fields = []
    for col in db.columns(conn, table):
        q = f'"{col}"'
        stats = db.fetch_one(
            conn,
            f'SELECT SUM(CASE WHEN {q} IS NULL OR TRIM({q}) = \'\' THEN 1 ELSE 0 END) AS nulls, '
            f'COUNT(DISTINCT {q}) AS distinct_count, MAX(LENGTH({q})) AS max_length '
            f'FROM "{table}"',
        ) or {}
        nulls = int(stats.get("nulls") or 0)
        field = {
            "field": col,
            "null_count": nulls,
            "null_rate": round(nulls / total, 4) if total else 0,
            "distinct_count": int(stats.get("distinct_count") or 0),
            "max_length": int(stats.get("max_length") or 0),
        }
        distinct = field["distinct_count"]
        if 0 < distinct <= 12:
            top = db.fetch_all(
                conn,
                f'SELECT {q} AS value, COUNT(*) AS count FROM "{table}" '
                f"WHERE {q} IS NOT NULL AND TRIM({q}) <> '' GROUP BY {q} ORDER BY count DESC, value LIMIT 5",
            )
            field["top_values"] = [
                {"value": str(r["value"])[:40], "count": int(r["count"])} for r in top
            ]
        fields.append(field)
    return {"table": table, "row_count": total, "field_count": len(fields), "fields": fields}


def build_catalog(conn, include_dwd: bool = True) -> dict:
    standards = load_config("standards.json")
    tables = []
    targets = ["ods_market_register", "ods_credit_rating", "ods_complaint_case"]
    if include_dwd:
        targets += ["dwd_market_register", "dwd_credit_rating", "dwd_complaint_case"]
    for table in targets:
        if not db.table_exists(conn, table):
            continue
        base = logical_name(table)
        std_table = standards["tables"].get(base, {})
        profile = profile_table(conn, table)
        field_map = {f["field"]: f for f in profile["fields"]}
        enriched = []
        for col in db.columns(conn, table):
            std = std_table.get("fields", {}).get(col)
            rule = field_rule(base, col)
            if std:
                name_zh = std.get("name_zh", col)
                type_name = std.get("type", "string")
                length = std.get("length") or std.get("precision")
                nullable = std.get("nullable", True)
                standard_no = std.get("standard_no", "")
                description = std.get("description", "")
            else:
                name_zh = "数据质量标记" if col == "dq_flags" else col
                type_name = "string"
                length = None
                nullable = True
                standard_no = ""
                description = "记录本条数据的清洗与修复动作。" if col == "dq_flags" else ""
            enriched.append(
                {
                    "field": col,
                    "name_zh": name_zh,
                    "type": type_name,
                    "length": length,
                    "nullable": nullable,
                    "standard_no": standard_no,
                    "description": description,
                    "level": rule["level"],
                    "category": rule["category"],
                    "personal_info": rule["personal_info"],
                    "masking": rule.get("masking"),
                    **{k: v for k, v in field_map[col].items() if k != "field"},
                }
            )
        tables.append(
            {
                "table": table,
                "name_zh": TABLE_TITLES.get(table, std_table.get("name_zh", table)),
                "layer": layer_of(table),
                "owner": std_table.get("owner", ""),
                "steward": std_table.get("steward", ""),
                "description": std_table.get("description", ""),
                "row_count": profile["row_count"],
                "field_count": len(enriched),
                "level": max((f["level"] for f in enriched), default="L1"),
                "fields": enriched,
            }
        )

    all_fields = [f for t in tables for f in t["fields"]]
    summary = {
        "tables": len(tables),
        "fields": len(all_fields),
        "documented_fields": sum(1 for f in all_fields if f["standard_no"]),
        "pii_fields": sum(1 for f in all_fields if f["personal_info"]),
        "documented_rate": round(
            sum(1 for f in all_fields if f["standard_no"]) / len(all_fields), 4
        ) if all_fields else 0,
        "generated_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return {"summary": summary, "tables": tables}


def render_markdown(catalog: dict) -> str:
    summary = catalog["summary"]
    lines = [
        "# 数据目录与元数据报告",
        "",
        f"> 自动生成于 {summary['generated_at']}；共纳管 **{summary['tables']} 张表 / "
        f"{summary['fields']} 个字段**，标准文档覆盖率 **{summary['documented_rate'] * 100:.0f}%**，"
        f"个人信息字段 **{summary['pii_fields']}** 个。",
        "",
        "## 一、目录概览",
        "",
        "| 表 | 中文名 | 分层 | 行数 | 字段数 | 表级 | Owner |",
        "| --- | --- | --- | ---: | ---: | :---: | --- |",
    ]
    for t in catalog["tables"]:
        lines.append(
            f"| `{t['table']}` | {t['name_zh']} | {t['layer']} | {t['row_count']:,} | "
            f"{t['field_count']} | {t['level']} | {t['owner'] or '-'} |"
        )
    lines += ["", "## 二、字段级数据字典", ""]
    for t in catalog["tables"]:
        lines += [
            f"### `{t['table']}` · {t['name_zh']}",
            "",
            f"{t['description']}（{t['row_count']:,} 行，{t['layer']} 层）",
            "",
            "| 字段 | 中文名 | 类型 | 可空 | 分级 | 空值率 | 基数 | 标准编号 | 说明 |",
            "| --- | --- | --- | :---: | :---: | ---: | ---: | --- | --- |",
        ]
        for f in t["fields"]:
            type_text = f["type"] + (f"({f['length']})" if f.get("length") else "")
            lines.append(
                f"| `{f['field']}` | {f['name_zh']} | {type_text} | {'是' if f['nullable'] else '否'} | "
                f"{f['level']} | {f['null_rate'] * 100:.1f}% | {f['distinct_count']:,} | "
                f"{f['standard_no'] or '-'} | {f['description']} |"
            )
        lines.append("")
    lines += [
        "## 三、元数据采集说明",
        "",
        "1. 结构元数据：表名、字段名、字段顺序、行数、字段数由脚本直接读取 SQLite 系统表；",
        "2. 业务元数据：中文名、类型、长度、是否可空、标准编号来自 `config/standards.json`；",
        "3. 统计元数据：空值率、基数、最长值、高频值由 SQL 聚合实时剖析；",
        "4. 安全元数据：分级、分类、个人信息标识来自 `config/classification_rules.json`；",
        "5. 管理元数据：Owner、Steward、更新频率来自数据标准配置。",
        "",
    ]
    return "\n".join(lines)


def export_csv(catalog: dict):
    import csv

    path = REPORT_DIR / "data_catalog.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["表", "中文名", "分层", "字段", "中文名", "类型", "长度", "可空", "分级",
             "分类", "个人信息", "空值率", "基数", "标准编号", "说明"]
        )
        for t in catalog["tables"]:
            for f in t["fields"]:
                writer.writerow([
                    t["table"], t["name_zh"], t["layer"], f["field"], f["name_zh"],
                    f["type"], f.get("length") or "", "是" if f["nullable"] else "否",
                    f["level"], f["category"], "是" if f["personal_info"] else "否",
                    f['null_rate'], f["distinct_count"], f["standard_no"], f["description"],
                ])


def run(conn, include_dwd: bool = True) -> dict:
    catalog = build_catalog(conn, include_dwd=include_dwd)
    write_json(REPORT_DIR / "data_catalog.json", catalog)
    write_text(REPORT_DIR / "data_catalog.md", render_markdown(catalog))
    export_csv(catalog)
    return catalog
