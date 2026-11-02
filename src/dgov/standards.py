# -*- coding: utf-8 -*-
"""数据标准检查：命名规范、字段类型、码值一致性、元数据完备性。"""
from __future__ import annotations

import re

from .config import REPORT_DIR, load_json


def check(conn, meta: dict) -> dict:
    std = load_json("standards.json")
    violations: list[dict] = []

    def add(table: str, column: str, rule: str, detail: str, suggestion: str):
        violations.append({
            "table": table, "column": column, "rule": rule,
            "detail": detail, "suggestion": suggestion,
        })

    for t in meta["tables"]:
        if not re.match(std["naming"]["table"], t["name"]):
            add(t["name"], "-", "表命名规范", "表名不符合「分层前缀 + 小写下划线」规范", "按 ods_/dwd_/dws_ + 业务域重命名")
        if not t["description"]:
            add(t["name"], "-", "元数据完备性", "缺少表级业务描述", "补充表用途、更新频率与责任人")
        for c in t["columns"]:
            if not re.match(std["naming"]["column"], c["name"]):
                add(t["name"], c["name"], "字段命名规范", "字段名包含大写字母，不符合 snake_case 规范", f"重命名为 {_to_snake(c['name'])}")
            if c["type"] not in std["types"]:
                add(t["name"], c["name"], "数据类型规范", f"类型 {c['type']} 不在标准类型清单内", "统一为 TEXT / INTEGER / REAL / NUMERIC")
            if not c["business_name"]:
                add(t["name"], c["name"], "元数据完备性", "缺少字段业务含义", "补充业务口径与取值说明")

    # 码值一致性：渠道维表必须覆盖标准渠道码
    standard_channels = set(std["codes"]["channel_code"])
    actual_channels = {r[0] for r in conn.execute("SELECT DISTINCT channel_code FROM ods_channel")}
    for code in sorted(standard_channels - actual_channels):
        add("ods_channel", "channel_code", "码值一致性", f"标准渠道码 {code} 在维表中缺失", "补充渠道维表记录")

    report = {
        "total": len(violations),
        "by_rule": _count_by(violations, "rule"),
        "violations": violations,
    }
    _write(report)
    return report


def _count_by(items: list[dict], key: str) -> dict:
    out: dict[str, int] = {}
    for item in items:
        out[item[key]] = out.get(item[key], 0) + 1
    return out


def _to_snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _write(report: dict) -> None:
    lines = [
        "# 数据标准检查报告",
        "",
        "> 检查项：表/字段命名规范、数据类型、码值一致性、元数据完备性。",
        "",
        f"- 违规项：**{report['total']}** 条",
    ]
    for rule, count in report["by_rule"].items():
        lines.append(f"  - {rule}：{count} 条")
    lines += [
        "",
        "| 表 | 字段 | 规则 | 问题描述 | 整改建议 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for v in report["violations"]:
        lines.append(f"| `{v['table']}` | `{v['column']}` | {v['rule']} | {v['detail']} | {v['suggestion']} |")
    lines += [
        "",
        "## 整改闭环",
        "",
        "1. 命名类问题纳入 `dwd/dws` 建模评审，新增表必须通过命名检查才能上线；",
        "2. 元数据缺失项在数据资产登记时补齐，未补齐不予发布；",
        "3. 码值类问题由渠道域 Owner 在 3 个工作日内补齐维表并回归验证。",
    ]
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "standard_check.md").write_text("\n".join(lines), encoding="utf-8")
