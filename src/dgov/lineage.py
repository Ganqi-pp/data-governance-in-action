# -*- coding: utf-8 -*-
"""数据血缘：汇总清洗作业配置与 DWS 聚合 SQL，生成表级血缘图。"""
from __future__ import annotations

import re

from .config import REPORT_DIR, SQL_DIR

# Python 清洗作业（ODS → DWD）的血缘关系，与 cleanse.py 中的建模逻辑一一对应
JOB_EDGES = [
    ("ods_order", "dwd_order_detail", "清洗作业：去重、码值标准化、时序校验、脱敏"),
    ("ods_user", "dwd_user_profile", "清洗作业：手机号标准化、姓名/邮箱脱敏、会员分层"),
    ("ods_product", "dwd_product_dim", "清洗作业：价格校验、类目补全"),
    ("ods_channel", "dwd_order_detail", "码值映射：渠道编码标准化"),
]

TABLE_PATTERN = re.compile(r"\b(?:FROM|JOIN)\s+(\w+)", re.IGNORECASE)
INSERT_PATTERN = re.compile(r"INSERT\s+INTO\s+(\w+)", re.IGNORECASE)


def parse_sql_edges() -> list[tuple[str, str, str]]:
    edges = []
    sql = (SQL_DIR / "build_dws.sql").read_text(encoding="utf-8")
    matches = list(INSERT_PATTERN.finditer(sql))
    for i, m in enumerate(matches):
        target = m.group(1)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(sql)
        segment = sql[m.end():end]
        for src in sorted(set(TABLE_PATTERN.findall(segment))):
            if src != target:
                edges.append((src, target, "SQL 聚合：按日期/维度汇总"))
    return edges


def build() -> dict:
    edges = list(JOB_EDGES) + parse_sql_edges()
    nodes = sorted({n for e in edges for n in e[:2]})
    layers = {n: n.split("_")[0].upper() for n in nodes}

    lines = ["# 数据血缘（表级）", "", "```mermaid", "graph LR"]
    for src, tgt, _ in edges:
        lines.append(f"    {src} --> {tgt}")
    lines += ["```", "", "| 上游 | 下游 | 加工方式 |", "| --- | --- | --- |"]
    for src, tgt, how in edges:
        lines.append(f"| `{src}` | `{tgt}` | {how} |")
    lines += [
        "",
        "## 影响分析示例",
        "",
        "- 修改 `ods_order.order_status` 码值 → 影响 `dwd_order_detail` 状态标准化、`dws_channel_daily` 支付/退款口径；",
        "- 下线 `ods_channel` → 影响渠道码值映射与渠道日报，需提前通知数据分析组；",
        "- 调整 `dwd_user_profile.phone` 脱敏规则 → 影响用户触达与合规审计，需走变更审批。",
    ]
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "lineage.md").write_text("\n".join(lines), encoding="utf-8")
    (REPORT_DIR / "lineage.mmd").write_text("\n".join(lines[3:]), encoding="utf-8")

    return {"nodes": nodes, "edges": edges, "layers": layers}
