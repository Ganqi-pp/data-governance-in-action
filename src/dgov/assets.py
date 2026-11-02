"""数据资产登记：台账、Owner、分级、共享属性、质量分与血缘上下游。"""
from __future__ import annotations

import csv
from datetime import datetime

from . import db
from .config import load_config, write_json, write_text
from .lineage import build_graph
from .paths import REPORT_DIR

REQUIRED_FIELDS = ["name", "type", "domain", "owner", "steward", "level", "sharing", "update_frequency", "description"]


def _quality_index() -> dict:
    path = REPORT_DIR / "quality_result.json"
    if not path.exists():
        return {}
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    index = {}
    for table, item in data.get("before", {}).get("tables", {}).items():
        index[f"ods_{table}"] = item["health"]
    for table, item in data.get("after", {}).get("tables", {}).items():
        index[f"dwd_{table}"] = item["health"]
    return index


def build(conn) -> dict:
    config = load_config("assets.json")
    classification = load_config("classification_rules.json")
    graph = build_graph(conn)
    nodes = {node["id"]: node for node in graph["nodes"]}
    up = {node_id: [] for node_id in nodes}
    down = {node_id: [] for node_id in nodes}
    for edge in graph["edges"]:
        up[edge["to"]].append(edge["from"])
        down[edge["from"]].append(edge["to"])
    quality = _quality_index()
    assets = []
    findings = []
    for asset in config["assets"]:
        item = dict(asset)
        missing = [f for f in REQUIRED_FIELDS if not item.get(f)]
        if item.get("node_id") and item["node_id"] not in nodes:
            findings.append({"asset": item["id"], "severity": "高", "message": f"血缘节点 {item['node_id']} 不存在"})
        table = item.get("table")
        rows = db.row_count(conn, table) if table and db.table_exists(conn, table) else None
        base = table.split("_", 1)[1] if table and "_" in table else table
        rule = classification["table_rules"].get(base) if base else None
        computed_level = rule["level"] if rule else item.get("level")
        level = max([item.get("level") or "L1", computed_level or "L1"], key=lambda x: {"L1": 1, "L2": 2, "L3": 3, "L4": 4}.get(x, 0))
        if level != item.get("level"):
            findings.append({"asset": item["id"], "severity": "中", "message": f"资产登记级别 {item.get('level')} 低于字段分级 {level}，已按就高原则修正"})
        item.update(
            {
                "rows": rows,
                "level": level,
                "quality_score": quality.get(table) if table else None,
                "upstream_count": len(up.get(item.get("node_id"), [])),
                "downstream_count": len(down.get(item.get("node_id"), [])),
                "upstream": [nodes[n]["name"] for n in up.get(item.get("node_id"), [])],
                "downstream": [nodes[n]["name"] for n in down.get(item.get("node_id"), [])],
                "status": "在册" if not missing else "待补充",
                "missing_fields": missing,
            }
        )
        if missing:
            findings.append({"asset": item["id"], "severity": "高", "message": f"登记要素缺失：{', '.join(missing)}"})
        assets.append(item)

    total_rows = sum(a["rows"] or 0 for a in assets if a.get("table"))
    summary = {
        "assets": len(assets),
        "by_type": {},
        "registered_complete": sum(1 for a in assets if a["status"] == "在册"),
        "completeness": round(sum(1 for a in assets if a["status"] == "在册") / len(assets), 4) if assets else 0,
        "with_owner": sum(1 for a in assets if a.get("owner")),
        "with_quality_score": sum(1 for a in assets if a.get("quality_score") is not None),
        "level_distribution": {},
        "total_rows": total_rows,
        "generated_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        "findings": findings,
    }
    for asset in assets:
        summary["by_type"][asset["type"]] = summary["by_type"].get(asset["type"], 0) + 1
        summary["level_distribution"][asset["level"]] = summary["level_distribution"].get(asset["level"], 0) + 1
    return {"summary": summary, "assets": assets}


def render_markdown(result: dict) -> str:
    summary = result["summary"]
    lines = [
        "# 数据资产登记台账",
        "",
        f"> 自动生成于 {summary['generated_at']}。共登记 **{summary['assets']}** 项资产，"
        f"登记完整率 **{summary['completeness'] * 100:.0f}%**，有明确 Owner **{summary['with_owner']}** 项。",
        "",
        "## 一、资产总览",
        "",
        "| 编号 | 资产名称 | 类型 | 域 | 层级 | 级别 | Owner | 共享属性 | 行数 | 质量分 | 上游 | 下游 | 状态 |",
        "| --- | --- | --- | --- | --- | :---: | --- | --- | ---: | ---: | ---: | ---: | :---: |",
    ]
    for a in result["assets"]:
        lines.append(
            f"| {a['id']} | {a['name']} | {a['type']} | {a['domain']} | {a['layer']} | {a['level']} | "
            f"{a['owner']} | {a['sharing']} | {a['rows'] if a['rows'] is not None else '-'} | "
            f"{a['quality_score'] if a['quality_score'] is not None else '-'} | "
            f"{a['upstream_count']} | {a['downstream_count']} | {a['status']} |"
        )
    lines += [
        "",
        "## 二、登记要素说明",
        "",
        "| 要素 | 说明 | 示例 |",
        "| --- | --- | --- |",
        "| 资产编号 | 全局唯一，登记后不变 | DA-004 |",
        "| 资产名称 | 业务可理解的中文名 | 市场主体登记明细 |",
        "| 类型 | 数据表 / 指标 / 接口 / 报告 / 码表 | 数据表 |",
        "| 级别 | 按分类分级结果就高登记 | L3 |",
        "| Owner | 对数据内容与共享范围负责的业务负责人 | 市场服务部登记注册科 |",
        "| Steward | 负责日常治理执行的岗位 | 数据管理岗 |",
        "| 共享属性 | 公开 / 内部共享 / 有条件共享 / 脱敏共享 / 不共享 | 有条件共享 |",
        "| 质量分 | 来自最近一次质量评估 | 85.5 |",
        "| 血缘 | 自动计算的直接上下游数量 | 2 / 3 |",
        "",
        "## 三、登记检查与整改",
        "",
    ]
    if summary["findings"]:
        lines += ["| 资产 | 严重度 | 问题 |", "| --- | :---: | --- |"]
        for finding in summary["findings"]:
            lines.append(f"| {finding['asset']} | {finding['severity']} | {finding['message']} |")
    else:
        lines.append("本次登记检查未发现缺失项。")
    lines += [
        "",
        "## 四、资产运营机制",
        "",
        "1. **新增**：系统上线或数据产品发布前 5 个工作日提交登记，未登记不得共享；",
        "2. **变更**：表结构、口径、Owner、共享范围变化时同步更新台账，保留变更记录；",
        "3. **下架**：连续 6 个月无访问且无业务依赖的资产，经 Owner 确认后归档；",
        "4. **价值评估**：每季度按使用频次、支撑业务数、质量分、共享收益四个维度评估；",
        "5. **审计**：每半年核对资产台账与实际库表、接口、报表的一致性。",
        "",
    ]
    return "\n".join(lines)


def export_csv(result: dict) -> None:
    path = REPORT_DIR / "asset_register.csv"
    fields = ["id", "name", "type", "domain", "layer", "table", "owner", "steward", "level",
              "sharing", "update_frequency", "criticality", "rows", "quality_score",
              "upstream_count", "downstream_count", "status", "description", "registered_at"]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(result["assets"])


def run(conn) -> dict:
    result = build(conn)
    write_json(REPORT_DIR / "asset_register.json", result)
    write_text(REPORT_DIR / "asset_register.md", render_markdown(result))
    export_csv(result)
    return result
