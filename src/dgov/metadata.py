# -*- coding: utf-8 -*-
"""元数据采集：技术元数据（结构/行数）+ 业务元数据（口径/责任人）+ 分类分级。"""
from __future__ import annotations

from . import db
from .classify import classify_tables
from .config import REPORT_DIR, load_json


def collect(conn) -> dict:
    business = load_json("business_metadata.json")["tables"]
    tables = []
    for name in db.table_names(conn):
        bmeta = business.get(name, {})
        layer = name.split("_")[0]
        columns = []
        for col in db.table_columns(conn, name):
            columns.append({
                "name": col["name"],
                "type": col["type"],
                "notnull": col["notnull"],
                "pk": col["pk"],
                "business_name": bmeta.get("columns", {}).get(col["name"], ""),
                "description": bmeta.get("columns", {}).get(col["name"], ""),
            })
        tables.append({
            "name": name,
            "layer": layer,
            "domain": bmeta.get("domain", "未登记"),
            "owner": bmeta.get("owner", "未登记"),
            "description": bmeta.get("description", ""),
            "update_frequency": bmeta.get("update_frequency", ""),
            "row_count": db.row_count(conn, name),
            "columns": columns,
        })

    level_summary = classify_tables(tables)
    stats = {
        "table_count": len(tables),
        "column_count": sum(len(t["columns"]) for t in tables),
        "row_total": sum(t["row_count"] for t in tables),
        "domain_count": len({t["domain"] for t in tables}),
        "level_summary": level_summary,
        "sensitive_column_count": sum(1 for t in tables for c in t["columns"] if c["level"] in ("L3", "L4")),
    }
    return {"tables": tables, "stats": stats}


def write_catalog(meta: dict) -> str:
    lines = [
        "# 数据目录（Data Catalog）",
        "",
        "> 由 `src/dgov/metadata.py` 自动采集：技术元数据来自 SQLite 系统表，业务元数据来自 `config/business_metadata.json`，"
        "分类分级来自 `config/classification_rules.json`。",
        "",
        f"- 表数量：**{meta['stats']['table_count']}**",
        f"- 字段数量：**{meta['stats']['column_count']}**",
        f"- 业务域：**{meta['stats']['domain_count']}** 个",
        f"- 敏感字段（L3/L4）：**{meta['stats']['sensitive_column_count']}** 个",
        "",
        "## 表清单",
        "",
        "| 表名 | 分层 | 业务域 | Owner | 密级 | 行数 | 更新频率 |",
        "| --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for t in meta["tables"]:
        lines.append(
            f"| `{t['name']}` | {t['layer'].upper()} | {t['domain']} | {t['owner']} | "
            f"{t['level']} {t['level_name']} | {t['row_count']:,} | {t['update_frequency']} |"
        )

    lines += ["", "## 字段级数据字典", ""]
    for t in meta["tables"]:
        lines += [
            f"### {t['name']}（{t['description']}）",
            "",
            "| 字段 | 类型 | 业务含义 | 分类分级 | 脱敏策略 |",
            "| --- | --- | --- | --- | --- |",
        ]
        for c in t["columns"]:
            lines.append(
                f"| `{c['name']}` | {c['type']} | {c['business_name'] or '-'} | "
                f"{c['level']} {c['level_name']} | {c['mask']} |"
            )
        lines.append("")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / "data_catalog.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return str(out)
