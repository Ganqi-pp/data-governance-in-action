"""数据血缘：表级拓扑 + 字段级映射 + 变更影响分析。"""
from __future__ import annotations

import json
from collections import defaultdict, deque

from . import db
from .config import load_config, write_json, write_text
from .paths import REPORT_DIR


def _load() -> tuple[dict, dict]:
    return load_config("lineage.json"), load_config("transformations.json")


def _node_map(config: dict) -> dict[str, dict]:
    return {node["id"]: dict(node) for node in config["nodes"]}


def build_graph(conn) -> dict:
    config, transforms = _load()
    nodes = _node_map(config)
    # 表节点补充行数与分级
    classification = load_config("classification_rules.json")
    for node in nodes.values():
        table = node.get("table")
        if table and db.table_exists(conn, table):
            node["rows"] = db.row_count(conn, table)
            base = table.split("_", 1)[1] if "_" in table else table
            rule = classification["table_rules"].get(base)
            node["level"] = rule["level"] if rule else "L1"
        else:
            node["rows"] = None
            node["level"] = None

    edges = []
    for edge in config["edges"]:
        if edge["from"] not in nodes or edge["to"] not in nodes:
            raise ValueError(f"血缘边引用了不存在的节点：{edge}")
        edges.append(dict(edge))

    field_edges = []
    for base, spec in transforms["tables"].items():
        source = spec["source_table"]
        target = spec["target_table"]
        for field in spec["fields"]:
            for source_field in field.get("sources", []):
                field_edges.append(
                    {
                        "from_table": source,
                        "from_field": source_field,
                        "to_table": target,
                        "to_field": field["target"],
                        "rule": field["rule"],
                    }
                )

    # 指标/共享接口对字段的依赖（补充非转换类血缘）
    node_field_deps = defaultdict(list)
    for dep in config.get("field_dependencies", []):
        for field in dep["fields"]:
            table, column = field.split(".", 1)
            node_field_deps[dep["target"]].append({"table": table, "field": column})

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "field_edges": field_edges,
        "node_field_deps": dict(node_field_deps),
    }


def downstream_tables(graph: dict, table: str) -> list[str]:
    adjacency = defaultdict(list)
    for edge in graph["edges"]:
        adjacency[edge["from"]].append(edge["to"])
    seen = {table}
    queue = deque([table])
    order = []
    while queue:
        current = queue.popleft()
        for nxt in adjacency.get(current, []):
            if nxt not in seen:
                seen.add(nxt)
                order.append(nxt)
                queue.append(nxt)
    return order


def impact(graph: dict, field: str) -> dict:
    nodes = {node["id"]: node for node in graph["nodes"]}
    query_table, query_field = (field.split(".", 1) + [None])[:2] if "." in field else (None, field)
    direct_tables = set()
    for edge in graph["field_edges"]:
        if edge["to_field"] != query_field and edge["from_field"] != query_field:
            continue
        if query_table and edge["from_table"] != query_table and edge["to_table"] != query_table:
            continue
        direct_tables.add(edge["from_table"])
        direct_tables.add(edge["to_table"])
    if not direct_tables:
        return {"field": field, "found": False, "tables": [], "assets": [], "path": []}
    all_tables = set()
    for table in direct_tables:
        all_tables.add(table)
        all_tables.update(t for t in downstream_tables(graph, table) if nodes.get(t, {}).get("type") == "table")
    assets = []
    for table in direct_tables:
        for target_id, deps in graph["node_field_deps"].items():
            if any(dep["table"] == table and dep["field"] == query_field for dep in deps):
                node = nodes.get(target_id, {})
                assets.append({"id": target_id, "name": node.get("name", target_id), "type": node.get("type")})
    # 资产影响只认字段级依赖，避免把“同表下游”全部算成该字段的影响
    for target_id, deps in graph["node_field_deps"].items():
        if any(dep["table"] in direct_tables and dep["field"] == query_field for dep in deps):
            node = nodes.get(target_id, {})
            item = {"id": target_id, "name": node.get("name", target_id), "type": node.get("type")}
            if item not in assets:
                assets.append(item)
    return {
        "field": field,
        "found": True,
        "direct_tables": sorted(direct_tables),
        "tables": sorted(all_tables),
        "assets": assets,
    }


def render_mermaid(graph: dict) -> str:
    layer_order = ["source", "ods", "dwd", "dws", "serving", "governance"]
    layer_names = {"source": "源系统层", "ods": "贴源层 ODS", "dwd": "明细层 DWD",
                   "dws": "指标层 DWS", "serving": "共享与服务层", "governance": "治理与运维"}
    lines = ["flowchart LR"]
    grouped = defaultdict(list)
    for node in graph["nodes"]:
        grouped[node["layer"]].append(node)
    for layer in layer_order:
        items = grouped.get(layer, [])
        if not items:
            continue
        lines.append(f'  subgraph {layer}["{layer_names[layer]}"]')
        for node in items:
            label = node["name"].replace('"', "'")
            lines.append(f'    {node["id"]}["{label}"]')
        lines.append("  end")
    for edge in graph["edges"]:
        label = edge.get("label", "").replace('"', "'")
        lines.append(f'  {edge["from"]} -->|"{label}"| {edge["to"]}')
    return "\n".join(lines)


def render_markdown(graph: dict) -> str:
    nodes = {node["id"]: node for node in graph["nodes"]}
    examples = []
    for item in _load()[0].get("impact_examples", []):
        result = impact(graph, item["field"])
        examples.append((item, result))
    lines = [
        "# 数据血缘与影响分析报告",
        "",
        "> 血缘由转换配置与指标依赖自动生成，表级拓扑用于变更评审，字段级映射用于影响分析。",
        "",
        "## 一、表级血缘",
        "",
        "```mermaid",
        render_mermaid(graph),
        "```",
        "",
        "## 二、字段级血缘（示例）",
        "",
        "| 源表 | 源字段 | 目标表 | 目标字段 | 转换规则 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for edge in graph["field_edges"]:
        if edge["to_field"] in ("contact_phone", "status", "content", "credit_level", "district_code"):
            lines.append(
                f"| `{edge['from_table']}` | `{edge['from_field']}` | `{edge['to_table']}` | "
                f"`{edge['to_field']}` | {edge['rule']} |"
            )
    lines += [
        "",
        "## 三、变更影响分析",
        "",
    ]
    for item, result in examples:
        lines += [
            f"### 变更：`{item['field']}` — {item['change']}",
            "",
            f"- 预期影响：{item['expected_impact']}；",
            f"- 直接涉及表：{', '.join('`' + t + '`' for t in result.get('direct_tables', [])) or '-'}；",
            f"- 下游表：{', '.join('`' + t + '`' for t in result.get('tables', [])) or '-'}；",
            f"- 影响资产：{', '.join(a['name'] for a in result.get('assets', [])) or '-'}。",
            "",
        ]
    lines += [
        "## 四、血缘治理规则",
        "",
        "1. 新增字段必须同时更新 `config/transformations.json` 与 `config/lineage.json`，CI 校验映射完整性；",
        "2. 删除/重命名字段前必须执行影响分析，通知下游资产 Owner 并保留变更窗口；",
        "3. 指标口径变更须同步更新 `config/metrics.json`，并重跑回归；",
        "4. 共享接口字段变更须经安全合规岗复核，确认脱敏策略仍然有效；",
        "5. 每季度核对一次血缘与实际加工逻辑，发现漂移在 5 个工作日内修复。",
        "",
    ]
    return "\n".join(lines)


def run(conn) -> dict:
    graph = build_graph(conn)
    result = {
        "summary": {
            "nodes": len(graph["nodes"]),
            "table_nodes": sum(1 for n in graph["nodes"] if n["type"] == "table"),
            "edges": len(graph["edges"]),
            "field_edges": len(graph["field_edges"]),
        },
        **graph,
    }
    write_json(REPORT_DIR / "lineage.json", result)
    write_text(REPORT_DIR / "lineage.mmd", render_mermaid(graph))
    write_text(REPORT_DIR / "lineage.md", render_markdown(graph))
    return result


def impact_cli(conn, field: str) -> dict:
    graph = build_graph(conn)
    return impact(graph, field)
