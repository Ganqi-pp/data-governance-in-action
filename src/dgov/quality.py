"""数据质量规则引擎：SQL 规则执行、记录级评分、整改闭环与规则有效性验证。"""
from __future__ import annotations

import csv
import re
import sqlite3
from datetime import datetime, timedelta

from . import db
from .checks import is_valid_uscc
from .config import load_config, load_json, write_json, write_text
from .paths import RAW_DIR, REPORT_DIR

SEVERITY_ORDER = {"高": 0, "中": 1, "低": 2}
PK_FIELDS = {"market_register": "reg_id", "credit_rating": "rating_id", "complaint_case": "case_id"}
REF_TABLES = {"administrative_divisions", "industry_codes", "market_status_codes", "credit_levels"}


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _lit(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _register_functions(conn: sqlite3.Connection) -> None:
    conn.create_function("uscc_valid", 1, lambda value: 1 if is_valid_uscc(str(value or "")) else 0)
    conn.create_function("regexp", 2, lambda pattern, value: 1 if value is not None and re.search(pattern, str(value)) else 0)


def _table_for(stage: str, logical: str) -> str:
    if logical in REF_TABLES:
        return f"ref_{logical}"
    return f"{stage}_{logical}"


def _compile(rule: dict, stage: str, as_of: str) -> tuple[str, dict, str]:
    """返回 (SQL, 参数字典, 校验口径 WHERE)。"""
    table = _table_for(stage, rule["table"])
    pk = PK_FIELDS[rule["table"]]
    field = rule.get("field")
    qf = _q(field) if field else None
    typ = rule["type"]
    params = {"as_of": as_of}
    key_expr = f"c.{_q(pk)}" if typ == "referential" else _q(pk)

    if typ == "not_null":
        where = f"({qf} IS NULL OR TRIM({qf}) = '')"
        sql = f"SELECT {key_expr} AS record_key, {_lit(field + ' 为空')} AS evidence FROM {_q(table)} c WHERE {where}" if typ == "referential" else \
              f"SELECT {key_expr} AS record_key, {_lit(field + ' 为空')} AS evidence FROM {_q(table)} WHERE {where}"
        checked = "1=1"
    elif typ == "unique":
        key = rule["params"]["key"]
        where = (
            f"{_q(key)} IS NOT NULL AND TRIM({_q(key)}) <> '' AND {_q(key)} IN ("
            f"SELECT {_q(key)} FROM {_q(table)} WHERE {_q(key)} IS NOT NULL AND TRIM({_q(key)}) <> '' "
            f"GROUP BY {_q(key)} HAVING COUNT(*) > 1)"
        )
        sql = f"SELECT {_q(pk)} AS record_key, {_lit('业务主键重复：' + key)} || ' ' || {_q(key)} AS evidence FROM {_q(table)} WHERE {where}"
        checked = f"{_q(key)} IS NOT NULL AND TRIM({_q(key)}) <> ''"
    elif typ == "uscc":
        where = f"{qf} IS NOT NULL AND TRIM({qf}) <> '' AND uscc_valid({qf}) = 0"
        sql = f"SELECT {key_expr} AS record_key, {_lit('统一社会信用代码校验位错误')} AS evidence FROM {_q(table)} WHERE {where}"
        checked = f"{qf} IS NOT NULL AND TRIM({qf}) <> ''"
    elif typ == "regex":
        params["pattern"] = rule["params"]["pattern"]
        where = f"{qf} IS NOT NULL AND TRIM({qf}) <> '' AND NOT regexp(:pattern, {qf})"
        sql = f"SELECT {key_expr} AS record_key, {_lit(field + ' 不符合格式规范')} AS evidence FROM {_q(table)} WHERE {where}"
        checked = f"{qf} IS NOT NULL AND TRIM({qf}) <> ''"
    elif typ == "enum":
        values = rule["params"]["values"]
        in_list = ", ".join(_lit(v) for v in values)
        where = f"{qf} IS NOT NULL AND TRIM({qf}) <> '' AND {qf} NOT IN ({in_list})"
        sql = f"SELECT {key_expr} AS record_key, {_lit(field + ' 值不在标准码表：')} || {qf} AS evidence FROM {_q(table)} WHERE {where}"
        checked = f"{qf} IS NOT NULL AND TRIM({qf}) <> ''"
    elif typ == "range":
        low, high = rule["params"]["min"], rule["params"]["max"]
        where = f"{qf} IS NOT NULL AND TRIM({qf}) <> '' AND (CAST({qf} AS REAL) < {low} OR CAST({qf} AS REAL) > {high})"
        sql = f"SELECT {key_expr} AS record_key, {_lit(field + ' 超出允许范围：')} || {qf} AS evidence FROM {_q(table)} WHERE {where}"
        checked = f"{qf} IS NOT NULL AND TRIM({qf}) <> ''"
    elif typ == "date_valid":
        where = f"{qf} IS NOT NULL AND TRIM({qf}) <> '' AND date({qf}) IS NULL"
        sql = f"SELECT {key_expr} AS record_key, {_lit(field + ' 不是合法日期')} AS evidence FROM {_q(table)} WHERE {where}"
        checked = f"{qf} IS NOT NULL AND TRIM({qf}) <> ''"
    elif typ == "date_not_future":
        where = f"{qf} IS NOT NULL AND date({qf}) IS NOT NULL AND date({qf}) > date(:as_of)"
        sql = f"SELECT {key_expr} AS record_key, {_lit(field + ' 晚于数据截止日')} AS evidence FROM {_q(table)} WHERE {where}"
        checked = f"{qf} IS NOT NULL AND date({qf}) IS NOT NULL"
    elif typ == "date_order":
        start = rule["params"]["start_field"]
        end = rule["params"]["end_field"]
        where = (
            f"{_q(start)} IS NOT NULL AND TRIM({_q(start)}) <> '' AND {_q(end)} IS NOT NULL AND TRIM({_q(end)}) <> '' "
            f"AND date({_q(start)}) IS NOT NULL AND date({_q(end)}) IS NOT NULL AND date({_q(end)}) < date({_q(start)})"
        )
        sql = f"SELECT {key_expr} AS record_key, {_lit(end + ' 早于 ' + start)} AS evidence FROM {_q(table)} WHERE {where}"
        checked = f"{_q(start)} IS NOT NULL AND {_q(end)} IS NOT NULL AND TRIM({_q(end)}) <> ''"
    elif typ == "conditional_not_null":
        values = rule["params"]["values"]
        condition_field = rule["params"]["condition_field"]
        in_list = ", ".join(_lit(v) for v in values)
        where = f"{_q(condition_field)} IN ({in_list}) AND ({qf} IS NULL OR TRIM({qf}) = '')"
        sql = f"SELECT {key_expr} AS record_key, {_lit(field + ' 在特定状态下必填')} AS evidence FROM {_q(table)} WHERE {where}"
        checked = f"{_q(condition_field)} IN ({in_list})"
    elif typ == "referential":
        ref_table = _table_for(stage, rule["params"]["ref_table"])
        ref_field = rule["params"]["ref_field"]
        ref_filter = rule["params"].get("ref_filter", "1=1")
        where = (
            f"c.{qf} IS NOT NULL AND TRIM(c.{qf}) <> '' AND NOT EXISTS ("
            f"SELECT 1 FROM {_q(ref_table)} p WHERE p.{_q(ref_field)} = c.{qf} AND ({ref_filter}))"
        )
        sql = f"SELECT c.{_q(pk)} AS record_key, {_lit('关联主体或码值不存在：')} || c.{qf} AS evidence FROM {_q(table)} c WHERE {where}"
        checked = f"c.{qf} IS NOT NULL AND TRIM(c.{qf}) <> ''"
    elif typ == "freshness":
        params["days"] = rule["params"]["days"]
        where = f"{qf} IS NOT NULL AND date({qf}) IS NOT NULL AND julianday(:as_of) - julianday(date({qf})) > :days"
        sql = f"SELECT {key_expr} AS record_key, {_lit(field + ' 超过 ' + str(params['days']) + ' 天未更新')} AS evidence FROM {_q(table)} WHERE {where}"
        checked = f"{qf} IS NOT NULL AND date({qf}) IS NOT NULL"
    elif typ == "custom_sql":
        sql = rule["params"]["sql"].replace("{table}", _q(table))
        checked = rule["params"].get("scope", "1=1")
    else:
        raise ValueError(f"未知规则类型：{typ}")
    return sql, params, checked


def _execute_rule(conn, rule: dict, stage: str, as_of: str, table_rows: int) -> dict:
    sql, params, checked_sql = _compile(rule, stage, as_of)
    table = _table_for(stage, rule["table"])
    checked_row = db.fetch_one(conn, f"SELECT COUNT(*) AS n FROM {_q(table)} c WHERE {checked_sql}", params)
    checked = int((checked_row or {}).get("n") or 0)
    rows = db.fetch_all(conn, sql, params)
    seen = set()
    failures = []
    for row in rows:
        key = row.get("record_key")
        if key in seen:
            continue
        seen.add(key)
        failures.append({"record_key": str(key), "evidence": str(row.get("evidence") or "")[:200]})
    failed = len(failures)
    rate = round(failed / checked, 6) if checked else 0.0
    tolerance = float(rule.get("tolerance", 0))
    return {
        "id": rule["id"],
        "name": rule["name"],
        "table": rule["table"],
        "field": rule.get("field", ""),
        "dimension": rule["dimension"],
        "severity": rule["severity"],
        "owner": rule["owner"],
        "sla_days": rule["sla_days"],
        "standard_ref": rule.get("standard_ref", ""),
        "remediation": rule.get("remediation", ""),
        "checked": checked,
        "failed": failed,
        "rate": rate,
        "tolerance": tolerance,
        "passed": rate <= tolerance,
        "failures": failures,
    }


def evaluate_stage(conn, stage: str, as_of: str, rules_cfg: dict | None = None) -> dict:
    _register_functions(conn)
    cfg = rules_cfg or load_config("quality_rules.json")
    table_rows = {t: db.row_count(conn, f"{stage}_{t}") for t in ("market_register", "credit_rating", "complaint_case")}
    rules = []
    for rule in cfg["rules"]:
        rules.append(_execute_rule(conn, rule, stage, as_of, table_rows[rule["table"]]))

    row_keys = {t: set() for t in table_rows}
    dim_keys = {t: {} for t in table_rows}
    for rule in rules:
        for failure in rule["failures"]:
            row_keys[rule["table"]].add(failure["record_key"])
            dim_keys[rule["table"]].setdefault(rule["dimension"], set()).add(failure["record_key"])

    tables = {}
    for table, rows in table_rows.items():
        bad = len(row_keys[table])
        dims = {}
        for dimension in cfg["scoring"]["dimension_weights"]:
            dim_bad = len(dim_keys[table].get(dimension, set()))
            dims[dimension] = round(100 * (1 - dim_bad / rows), 2) if rows else 100.0
        table_rules = [r for r in rules if r["table"] == table]
        tables[table] = {
            "rows": rows,
            "bad_rows": bad,
            "health": round(100 * (1 - bad / rows), 2) if rows else 100.0,
            "dimensions": dims,
            "rules": len(table_rules),
            "passed_rules": sum(1 for r in table_rules if r["passed"]),
            "issues": sum(r["failed"] for r in table_rules),
        }

    weights = cfg["scoring"]["table_weights"]
    total_weight = sum(weights.values())
    overall = round(sum(weights[t] * tables[t]["health"] for t in tables) / total_weight, 2)
    dimensions = {}
    for dimension in cfg["scoring"]["dimension_weights"]:
        numerator = sum(weights[t] * tables[t]["dimensions"][dimension] for t in tables)
        dimensions[dimension] = round(numerator / total_weight, 2)
    passed_rules = sum(1 for r in rules if r["passed"])
    summary = {
        "stage": stage,
        "rows": sum(table_rows.values()),
        "tables": len(tables),
        "rules": len(rules),
        "passed_rules": passed_rules,
        "rule_pass_rate": round(passed_rules / len(rules), 4) if rules else 0,
        "issues": sum(r["failed"] for r in rules),
        "high_issues": sum(r["failed"] for r in rules if r["severity"] == "高"),
        "overall_health": overall,
        "dimensions": dimensions,
        "table_weights": weights,
        "as_of": as_of,
        "generated_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return {"summary": summary, "tables": tables, "rules": rules}


def load_quarantine(conn) -> set[tuple[str, str]]:
    if not db.table_exists(conn, "quarantine_records"):
        return set()
    return {
        (row["table_name"], str(row["record_key"]))
        for row in db.fetch_all(conn, "SELECT table_name, record_key FROM quarantine_records")
    }


def _issue_status(raw_issue, clean_index, after_rules, quarantine) -> tuple[str, str]:
    rule_id, table, key = raw_issue["rule_id"], raw_issue["table"], raw_issue["record_key"]
    if (table, key) in quarantine:
        return "已隔离", "数据无法自动修复，已进入隔离区等待人工处理"
    if (rule_id, table, key) not in clean_index:
        return "已修复", "治理后同一规则复检通过"
    rule = after_rules.get(rule_id)
    if rule and rule["passed"]:
        return "观察项", "规则整体已达标，个别记录进入持续观察"
    return "待整改", "治理后仍不满足规则要求"


def effectiveness(conn, before: dict) -> dict:
    manifest_path = RAW_DIR / "_defect_manifest.json"
    if not manifest_path.exists():
        return {"summary": {}, "items": []}
    manifest = load_json(manifest_path)
    issue_index = {}
    for rule in before["rules"]:
        for failure in rule["failures"]:
            issue_index[(rule["id"], rule["table"], failure["record_key"])] = failure
    items = []
    total_injected = 0
    total_detected = 0
    for table, table_manifest in manifest["tables"].items():
        for defect in table_manifest.get("defects", []):
            keys = defect["keys"]
            expected = defect.get("expected_rules", [])
            detected = 0
            for key in keys:
                if any((rule_id, table, key) in issue_index for rule_id in expected):
                    detected += 1
            total_injected += len(keys)
            total_detected += detected
            items.append(
                {
                    "table": table,
                    "defect_type": defect["type"],
                    "field": defect["field"],
                    "injected": len(keys),
                    "detected": detected,
                    "recall": round(detected / len(keys), 4) if keys else 0,
                    "expected_rules": expected,
                    "covered": bool(expected),
                }
            )
    covered = sum(1 for item in items if item["covered"])
    return {
        "summary": {
            "defect_types": len(items),
            "covered_types": covered,
            "coverage_rate": round(covered / len(items), 4) if items else 0,
            "injected_records": total_injected,
            "detected_records": total_detected,
            "recall": round(total_detected / total_injected, 4) if total_injected else 0,
        },
        "items": items,
    }


def _issue_rows(stage_result: dict, status: str | None = None) -> list[dict]:
    rows = []
    for rule in stage_result["rules"]:
        for failure in rule["failures"]:
            rows.append(
                {
                    "rule_id": rule["id"],
                    "rule_name": rule["name"],
                    "table": rule["table"],
                    "field": rule["field"],
                    "dimension": rule["dimension"],
                    "severity": rule["severity"],
                    "owner": rule["owner"],
                    "sla_days": rule["sla_days"],
                    "record_key": failure["record_key"],
                    "evidence": failure["evidence"],
                    "remediation": rule["remediation"],
                    "standard_ref": rule["standard_ref"],
                    "status": status or "待整改",
                }
            )
    return rows


def finalize(conn, as_of: str, before: dict) -> dict:
    after = evaluate_stage(conn, "dwd", as_of)
    quarantine = load_quarantine(conn)
    clean_index = {
        (rule["id"], rule["table"], failure["record_key"])
        for rule in after["rules"]
        for failure in rule["failures"]
    }
    after_rules = {rule["id"]: rule for rule in after["rules"]}
    raw_issues = _issue_rows(before)
    merged = []
    raw_status = {"已修复": 0, "已隔离": 0, "待整改": 0, "观察项": 0}
    for issue in raw_issues:
        status, resolution = _issue_status(issue, clean_index, after_rules, quarantine)
        raw_status[status] += 1
        issue = {**issue, "status": status, "resolution": resolution}
        merged.append(issue)
    raw_keys = {(i["rule_id"], i["table"], i["record_key"]) for i in raw_issues}
    new_issues = []
    for issue in _issue_rows(after):
        key = (issue["rule_id"], issue["table"], issue["record_key"])
        if key in raw_keys:
            continue
        rule = after_rules.get(issue["rule_id"])
        status = "观察项" if rule and rule["passed"] else "待整改"
        issue = {**issue, "status": status, "resolution": "治理后新发现，需纳入整改"}
        new_issues.append(issue)
    merged.extend(new_issues)
    merged.sort(key=lambda x: (SEVERITY_ORDER.get(x["severity"], 9), x["status"], x["rule_id"], x["record_key"]))
    for index, issue in enumerate(merged, start=1):
        issue["issue_id"] = f"ISS-{index:05d}"
        issue["due_date"] = (
            datetime.strptime(as_of, "%Y-%m-%d") + timedelta(days=int(issue["sla_days"]))
        ).strftime("%Y-%m-%d")

    counts = {status: sum(1 for i in merged if i["status"] == status) for status in ("已修复", "已隔离", "待整改", "观察项")}
    closure = {
        "raw_issues": len(raw_issues),
        "total_issues": len(merged),
        "fixed": raw_status["已修复"],
        "quarantined": raw_status["已隔离"],
        "open": raw_status["待整改"],
        "observe": raw_status["观察项"],
        "new_after": len(new_issues),
        "closure_rate": round(raw_status["已修复"] / len(raw_issues), 4) if raw_issues else 0,
        "containment_rate": round((raw_status["已修复"] + raw_status["已隔离"]) / len(raw_issues), 4) if raw_issues else 0,
        "disposition_rate": round(
            (raw_status["已修复"] + raw_status["已隔离"] + raw_status["观察项"]) / len(raw_issues), 4
        ) if raw_issues else 0,
        "verified": raw_status["已修复"],
    }
    eff = effectiveness(conn, before)
    scorecard = []
    for table in before["tables"]:
        scorecard.append(
            {
                "table": table,
                "dimension": "整体",
                "before": before["tables"][table]["health"],
                "after": after["tables"][table]["health"],
                "delta": round(after["tables"][table]["health"] - before["tables"][table]["health"], 2),
            }
        )
        for dimension in before["tables"][table]["dimensions"]:
            scorecard.append(
                {
                    "table": table,
                    "dimension": dimension,
                    "before": before["tables"][table]["dimensions"][dimension],
                    "after": after["tables"][table]["dimensions"][dimension],
                    "delta": round(
                        after["tables"][table]["dimensions"][dimension]
                        - before["tables"][table]["dimensions"][dimension],
                        2,
                    ),
                }
            )

    result = {
        "as_of": as_of,
        "before": {k: v for k, v in before.items() if k != "rules"},
        "after": {k: v for k, v in after.items() if k != "rules"},
        "before_rules": before["rules"],
        "after_rules": after["rules"],
        "closure": closure,
        "effectiveness": eff,
        "scorecard": scorecard,
        "issue_counts": counts,
        "generated_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
    }
    write_json(REPORT_DIR / "quality_result.json", result)
    write_json(REPORT_DIR / "quality_before.json", before)
    write_json(REPORT_DIR / "quality_after.json", after)
    _export_issues(merged)
    _export_scorecard(scorecard)
    _export_rules(before["rules"], after["rules"])
    _export_effectiveness(eff)
    return result


def _export_issues(issues: list[dict]) -> None:
    path = REPORT_DIR / "issue_register.csv"
    fields = ["issue_id", "rule_id", "rule_name", "table", "field", "dimension", "severity",
              "record_key", "evidence", "status", "resolution", "owner", "sla_days", "due_date",
              "remediation", "standard_ref"]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(issues)


def _export_scorecard(scorecard: list[dict]) -> None:
    path = REPORT_DIR / "quality_scorecard.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["表", "维度", "治理前", "治理后", "提升"])
        for row in scorecard:
            writer.writerow([row["table"], row["dimension"], row["before"], row["after"], row["delta"]])


def _export_rules(before_rules: list[dict], after_rules: list[dict]) -> None:
    after_index = {r["id"]: r for r in after_rules}
    path = REPORT_DIR / "quality_rules_result.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["规则编号", "规则名称", "表", "字段", "维度", "严重度", "校验记录", "治理前违规", "治理前违规率", "治理前达标", "治理后违规", "治理后违规率", "治理后达标", "Owner"])
        for rule in before_rules:
            after = after_index.get(rule["id"], {})
            writer.writerow([
                rule["id"], rule["name"], rule["table"], rule["field"], rule["dimension"],
                rule["severity"], rule["checked"], rule["failed"], f"{rule['rate'] * 100:.2f}%",
                "是" if rule["passed"] else "否", after.get("failed", 0),
                f"{after.get('rate', 0) * 100:.2f}%", "是" if after.get("passed") else "否", rule["owner"],
            ])


def _export_effectiveness(eff: dict) -> None:
    path = REPORT_DIR / "rule_effectiveness.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["表", "缺陷类型", "字段", "注入记录", "检出记录", "检出率", "对应规则", "是否覆盖"])
        for item in eff["items"]:
            writer.writerow([
                item["table"], item["defect_type"], item["field"], item["injected"], item["detected"],
                f"{item['recall'] * 100:.1f}%", ",".join(item["expected_rules"]) or "-",
                "是" if item["covered"] else "否",
            ])


def baseline(conn, as_of: str) -> dict:
    result = evaluate_stage(conn, "ods", as_of)
    write_json(REPORT_DIR / "quality_before.json", result)
    return result
