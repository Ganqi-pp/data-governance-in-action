# -*- coding: utf-8 -*-
"""数据质量引擎：规则配置化、事前基线 / 事后复检、行级质量分与整改台账。"""
from __future__ import annotations

import json
from datetime import date, timedelta

from .config import REPORT_DIR, SEVERITY_WEIGHT, load_json

STAGE_TABLES = {
    "before": {"order": "ods_order", "user": "ods_user", "product": "ods_product"},
    "after": {"order": "dwd_order_detail", "user": "dwd_user_profile", "product": "dwd_product_dim"},
}

DIMENSIONS = ["完整性", "唯一性", "有效性", "一致性", "及时性"]


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _table_of(rule: dict, stage: str) -> str:
    return STAGE_TABLES[stage][rule["dataset"]]


def _failing_condition(rule: dict, stage: str) -> tuple[str, list]:
    col = _q(rule["column"])
    table = _q(_table_of(rule, stage))
    params = rule.get("params", {})
    rtype = rule["type"]

    if rtype == "unique":
        return (
            f"{col} IN (SELECT {col} FROM {table} GROUP BY {col} HAVING COUNT(*) > 1)",
            [],
        )
    if rtype == "not_null":
        return f"({col} IS NULL OR TRIM(CAST({col} AS TEXT)) = '')", []
    if rtype == "enum":
        values = params["values"]
        placeholders = ",".join("?" for _ in values)
        return f"({col} IS NOT NULL AND {col} NOT IN ({placeholders}))", list(values)
    if rtype == "regex":
        return f"({col} IS NOT NULL AND REGEXP(?, {col}) = 0)", [params["pattern"]]
    if rtype == "expression":
        return f"(({params['expr']}) = 0)", []
    if rtype == "referential":
        ref = params["ref_before_table"] if stage == "before" else params["ref_after_table"]
        return (
            f"({col} IS NOT NULL AND NOT EXISTS (SELECT 1 FROM {_q(ref)} r WHERE r.{col} = t.{col}))",
            [],
        )
    if rtype == "freshness":
        lag = int(params.get("max_lag_hours", 24))
        return (
            f"(datetime({col}) > datetime((SELECT MAX({col}) FROM {table}), '+{lag} hours'))",
            [],
        )
    raise ValueError(f"未知规则类型: {rtype}")


def check_rule(conn, rule: dict, stage: str) -> dict:
    table = _q(_table_of(rule, stage))
    total = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    cond, args = _failing_condition(rule, stage)

    failed = int(conn.execute(f"SELECT COUNT(*) FROM {table} t WHERE {cond}", args).fetchone()[0])
    rows = conn.execute(f"SELECT * FROM {table} t WHERE {cond} LIMIT 3", args).fetchall() if failed else []
    sample = [{k: r[k] for k in list(r.keys())[:5]} for r in rows]

    return {
        "rule_id": rule["id"],
        "dataset": rule["dataset"],
        "table": _table_of(rule, stage),
        "name": rule["name"],
        "column": rule["column"],
        "dimension": rule["dimension"],
        "type": rule["type"],
        "severity": rule["severity"],
        "owner": rule["owner"],
        "sla_hours": rule.get("sla_hours", 24),
        "total": total,
        "failed": failed,
        "pass_rate": (total - failed) / total if total else 1.0,
        "sample": sample,
    }


def _bad_rows(conn, rules: list[dict], stage: str) -> tuple[int, int]:
    """返回 (总行数, 至少命中一条规则的行数)，即行级质量分的计算基础。"""
    if not rules:
        return 0, 0
    dataset = rules[0]["dataset"]
    table = _q(_table_of(rules[0], stage))
    total = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    conditions, args = [], []
    for rule in rules:
        cond, cond_args = _failing_condition(rule, stage)
        conditions.append(f"({cond})")
        args.extend(cond_args)
    bad = int(conn.execute(
        f"SELECT COUNT(*) FROM {table} t WHERE " + " OR ".join(conditions), args
    ).fetchone()[0])
    return total, bad


def run_stage(conn, stage: str) -> dict:
    rules = load_json("quality_rules.json")["rules"]
    results = [check_rule(conn, rule, stage) for rule in rules]

    by_dimension = {}
    total_rows = 0
    total_bad = 0
    for dim in DIMENSIONS:
        subset = [r for r in rules if r["dimension"] == dim]
        if not subset:
            continue
        dim_total = 0
        dim_bad = 0
        for dataset in {r["dataset"] for r in subset}:
            ds_rules = [r for r in subset if r["dataset"] == dataset]
            t, b = _bad_rows(conn, ds_rules, stage)
            dim_total += t
            dim_bad += b
        by_dimension[dim] = {
            "score": round(100.0 * (1 - dim_bad / dim_total), 2) if dim_total else 100.0,
            "rules": len(subset),
            "bad_rows": dim_bad,
        }

    by_table = {}
    for dataset in ("order", "user", "product"):
        ds_rules = [r for r in rules if r["dataset"] == dataset]
        t, b = _bad_rows(conn, ds_rules, stage)
        total_rows += t
        total_bad += b
        by_table[dataset] = {"score": round(100.0 * (1 - b / t), 2) if t else 100.0, "rows": t, "bad_rows": b}

    overall = round(100.0 * (1 - total_bad / total_rows), 2) if total_rows else 100.0
    return {
        "stage": stage,
        "rules": results,
        "score": overall,
        "rows": total_rows,
        "bad_rows": total_bad,
        "by_dimension": by_dimension,
        "by_table": by_table,
    }


def compare(conn) -> dict:
    before = run_stage(conn, "before")
    after = run_stage(conn, "after")
    after_index = {r["rule_id"]: r for r in after["rules"]}

    issues = []
    for r in after["rules"]:
        if r["failed"] > 0:
            issues.append({
                "issue_id": f"DQ-{r['rule_id'].split('-')[-1]}-{date.today().strftime('%Y%m%d')}",
                "rule_id": r["rule_id"],
                "table": r["table"],
                "dimension": r["dimension"],
                "severity": r["severity"],
                "failed": r["failed"],
                "owner": r["owner"],
                "due_date": (date.today() + timedelta(hours=r["sla_hours"])).strftime("%Y-%m-%d"),
                "status": "待整改",
                "sample": r["sample"],
            })

    fixed = sum(1 for r in before["rules"] if r["failed"] > 0 and after_index[r["rule_id"]]["failed"] == 0)
    failing_before = sum(1 for r in before["rules"] if r["failed"] > 0)

    summary = {
        "before_score": before["score"],
        "after_score": after["score"],
        "improvement": round(after["score"] - before["score"], 2),
        "rule_count": len(before["rules"]),
        "before_failing_rules": failing_before,
        "fixed_rules": fixed,
        "open_issues": len(issues),
        "checked_rows": after["rows"],
        "before": before,
        "after": after,
        "issues": issues,
    }
    _write_report(summary)
    return summary


def _write_report(summary: dict) -> None:
    before, after = summary["before"], summary["after"]
    lines = [
        "# 数据质量报告",
        "",
        f"> 规则集：`config/quality_rules.json`（{summary['rule_count']} 条），"
        f"覆盖 3 个数据集、{summary['checked_rows']:,} 行数据；质量分按「未命中任何规则的行占比」计算。",
        "",
        f"**治理前质量分：{summary['before_score']:.2f} → 治理后：{summary['after_score']:.2f}"
        f"（+{summary['improvement']:.2f}）**",
        "",
        "## 一、分维度得分",
        "",
        "| 维度 | 治理前 | 治理后 | 问题行数（治理前 → 后） |",
        "| --- | ---: | ---: | ---: |",
    ]
    for dim in DIMENSIONS:
        b = before["by_dimension"].get(dim)
        a = after["by_dimension"].get(dim)
        if not b or not a:
            continue
        lines.append(f"| {dim} | {b['score']:.2f} | {a['score']:.2f} | {b['bad_rows']} → {a['bad_rows']} |")

    lines += [
        "",
        "## 二、规则明细",
        "",
        "| 规则 | 表 | 字段 | 维度 | 严重度 | 治理前通过率 | 治理后通过率 | 责任人 |",
        "| --- | --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for b in before["rules"]:
        a = next(x for x in after["rules"] if x["rule_id"] == b["rule_id"])
        lines.append(
            f"| {b['rule_id']} {b['name']} | `{b['table']}` | `{b['column']}` | {b['dimension']} | "
            f"{b['severity']} | {b['pass_rate'] * 100:.2f}% | {a['pass_rate'] * 100:.2f}% | {b['owner']} |"
        )

    lines += ["", "## 三、问题定位与整改台账", ""]
    if summary["issues"]:
        lines += [
            "| 问题编号 | 规则 | 表 | 失败行数 | 责任人 | 整改期限 | 状态 |",
            "| --- | --- | --- | ---: | --- | --- | --- |",
        ]
        for i in summary["issues"]:
            lines.append(
                f"| {i['issue_id']} | {i['rule_id']} | `{i['table']}` | {i['failed']} | "
                f"{i['owner']} | {i['due_date']} | {i['status']} |"
            )
        lines += ["", "### 问题样本（用于定位上游）", ""]
        for i in summary["issues"]:
            lines.append(f"- **{i['rule_id']} {i['table']}**：`{json.dumps(i['sample'][:2], ensure_ascii=False)}`")
    else:
        lines.append("本轮复检无遗留问题，全部规则通过。")

    lines += [
        "",
        "## 四、结论与下一步",
        "",
        f"1. 治理前共 **{summary['before_failing_rules']}** 条规则未通过，清洗后 **{summary['fixed_rules']}** 条已闭环；",
        f"2. 剩余 **{summary['open_issues']}** 项遗留问题已进入整改台账，按责任人 SLA 跟踪；",
        "3. 建议将高频失败规则固化为每日巡检任务，并将质量分纳入数据资产健康度评分。",
    ]

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "quality_report.md").write_text("\n".join(lines), encoding="utf-8")
    (REPORT_DIR / "quality_summary.json").write_text(
        json.dumps({k: v for k, v in summary.items() if k not in ("before", "after")}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
