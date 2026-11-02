# -*- coding: utf-8 -*-
"""数据资产登记：把表登记为可管理、可追溯的数据资产，并输出登记清单。"""
from __future__ import annotations

import csv

from .config import REPORT_DIR, load_json


def build(meta: dict, quality_summary: dict) -> dict:
    config = load_json("assets.json")
    health = quality_summary["after"]["by_table"]
    tables = {t["name"]: t for t in meta["tables"]}

    assets = []
    for item in config["assets"]:
        t = tables.get(item["table"], {})
        ds = item["table"].split("_")[0]
        dataset = {"ods": None, "dwd": None, "dws": None}.get(ds)
        score = None
        if item["table"].startswith("dwd_order") or item["table"].startswith("ods_order"):
            score = health.get("order", {}).get("score")
        elif item["table"].startswith("dwd_user") or item["table"].startswith("ods_user"):
            score = health.get("user", {}).get("score")
        elif item["table"].startswith("dwd_product") or item["table"].startswith("ods_product"):
            score = health.get("product", {}).get("score")

        assets.append({
            **item,
            "row_count": t.get("row_count", 0),
            "column_count": len(t.get("columns", [])),
            "quality_score": round(score, 2) if score is not None else "",
            "owner": t.get("owner", ""),
            "layer": t.get("layer", "").upper(),
        })

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = REPORT_DIR / "asset_register.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "table", "name", "domain", "layer", "level", "owner", "row_count",
            "column_count", "quality_score", "update_frequency", "sla", "scene", "consumer",
        ])
        writer.writeheader()
        for a in assets:
            writer.writerow({k: a.get(k, "") for k in writer.fieldnames})

    lines = [
        "# 数据资产登记清单",
        "",
        "> 资产登记字段：资产名称、所属域、分层、密级、Owner、行数、字段数、质量分、更新频率、SLA、使用场景。",
        "",
        "| 资产 | 表 | 域 | 层 | 密级 | Owner | 行数 | 字段 | 质量分 | 更新频率 |",
        "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for a in assets:
        lines.append(
            f"| {a['name']} | `{a['table']}` | {a['domain']} | {a['layer']} | {a['level']} | "
            f"{a['owner']} | {a['row_count']:,} | {a['column_count']} | {a['quality_score'] or '-'} | {a['update_frequency']} |"
        )
    lines += [
        "",
        "## 登记规则",
        "",
        "1. 新表上线前必须完成资产登记，缺少 Owner、更新频率、使用场景的不予发布；",
        "2. 密级由分类分级结果自动带入，L4 资产默认收紧访问权限并开启审计；",
        "3. 质量分低于 98 分的资产标记为「亚健康」，需在两周内完成整改并复检。",
    ]
    (REPORT_DIR / "asset_register.md").write_text("\n".join(lines), encoding="utf-8")

    return {"assets": assets, "count": len(assets), "csv": str(csv_path)}
