"""数据标准符合性检查：结构、命名、元数据完整性、码表引用与长度约束。"""
from __future__ import annotations

import csv
import re
from datetime import datetime

from . import db
from .config import load_config, write_json, write_text
from .paths import REPORT_DIR


def _finding(check_id, table, obj, name, status, severity, detail, suggestion) -> dict:
    return {
        "check_id": check_id,
        "table": table,
        "object": obj,
        "name": name,
        "status": status,
        "severity": severity,
        "detail": detail,
        "suggestion": suggestion,
    }


def check(conn) -> dict:
    standards = load_config("standards.json")
    findings = []
    naming = standards["naming"]
    table_pattern = re.compile(naming["table_pattern"])
    field_pattern = re.compile(naming["field_pattern"])
    for base, spec in standards["tables"].items():
        table = f"ods_{base}"
        if not db.table_exists(conn, table):
            findings.append(_finding("STD-001", table, table, "标准表已落地", "fail", "高", "数据库中不存在该表", "按标准建表并接入数据"))
            continue
        findings.append(_finding("STD-001", table, table, "标准表已落地", "pass", "高", f"行数 {db.row_count(conn, table):,}", "-"))
        actual = db.columns(conn, table)
        expected = list(spec["fields"].keys())
        missing = [f for f in expected if f not in actual]
        extra = [f for f in actual if f not in expected]
        findings.append(
            _finding("STD-002", table, table, "标准字段齐全", "fail" if missing else "pass", "高",
                     f"缺失字段：{', '.join(missing)}" if missing else f"{len(expected)} 个标准字段全部存在",
                     "补齐缺失字段并重跑落标检查")
        )
        findings.append(
            _finding("STD-003", table, table, "无未登记字段", "fail" if extra else "pass", "中",
                     f"未登记字段：{', '.join(extra)}" if extra else "所有物理字段均已在标准中登记",
                     "在标准中登记字段或下线冗余字段")
        )
        bad_names = [f for f in actual if not field_pattern.match(f)]
        findings.append(
            _finding("STD-004", table, table, "字段命名符合规范", "fail" if bad_names else "pass", "中",
                     f"不合规字段：{', '.join(bad_names)}" if bad_names else f"正则 {naming['field_pattern']} 全部通过",
                     "按 snake_case 重命名并同步上下游")
        )
        if not table_pattern.match(table):
            findings.append(_finding("STD-005", table, table, "表命名符合规范", "fail", "低", table, "按分层前缀规范重命名"))
        else:
            findings.append(_finding("STD-005", table, table, "表命名符合规范", "pass", "低", table, "-"))

        # 字段元数据完整性
        incomplete = []
        for field, meta in spec["fields"].items():
            for key in ("name_zh", "type", "description", "standard_no"):
                if not meta.get(key):
                    incomplete.append(f"{field}.{key}")
        findings.append(
            _finding("STD-006", table, table, "字段元数据完整", "fail" if incomplete else "pass", "中",
                     f"缺失：{', '.join(incomplete)}" if incomplete else "中文名/类型/说明/标准编号齐全",
                     "补齐字段元数据")
        )
        # 表级管理元数据
        missing_meta = [k for k in ("owner", "steward", "update_frequency", "description") if not spec.get(k)]
        findings.append(
            _finding("STD-007", table, table, "表级管理元数据完整", "fail" if missing_meta else "pass", "低",
                     f"缺失：{', '.join(missing_meta)}" if missing_meta else "Owner/Steward/更新频率/说明齐全",
                     "补齐管理元数据")
        )
        # 主键存在
        pk = spec.get("primary_key")
        ok_pk = bool(pk and pk in actual)
        findings.append(
            _finding("STD-008", table, pk or "-", "主键已声明且存在", "pass" if ok_pk else "fail", "高",
                     f"主键 {pk}" if ok_pk else "主键缺失或未在表中落地", "声明主键并保证唯一")
        )
        # 码表引用可解析
        for field, meta in spec["fields"].items():
            ref = meta.get("ref")
            if not ref:
                continue
            exists = db.table_exists(conn, f"ref_{ref}")
            findings.append(
                _finding("STD-009", table, field, "码表引用可解析", "pass" if exists else "fail", "中",
                         f"{field} → ref_{ref}" + (" 可访问" if exists else " 不存在"),
                         "补齐码表或修正引用")
            )
        # 长度约束（按字符数）
        for field, meta in spec["fields"].items():
            limit = meta.get("length")
            if not limit or field not in actual:
                continue
            row = db.fetch_one(conn, f'SELECT MAX(LENGTH("{field}")) AS n FROM "{table}"')
            longest = int((row or {}).get("n") or 0)
            findings.append(
                _finding("STD-010", table, field, "实际长度不超过标准长度", "fail" if longest > limit else "pass", "低",
                         f"最长 {longest} / 标准 {limit}", "截断或扩展标准长度并评审")
            )

    passed = sum(1 for f in findings if f["status"] == "pass")
    failed = len(findings) - passed
    summary = {
        "checks": len(findings),
        "passed": passed,
        "failed": failed,
        "compliance_rate": round(passed / len(findings), 4) if findings else 0,
        "high_failures": sum(1 for f in findings if f["status"] == "fail" and f["severity"] == "高"),
        "generated_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        "standard_version": standards.get("version"),
    }
    return {"summary": summary, "findings": findings}


def render_markdown(result: dict) -> str:
    s = result["summary"]
    lines = [
        "# 数据标准符合性检查报告",
        "",
        f"> 标准版本 {s['standard_version']}；自动生成于 {s['generated_at']}。"
        f"共执行 **{s['checks']}** 项检查，通过 **{s['passed']}** 项，"
        f"符合率 **{s['compliance_rate'] * 100:.1f}%**，高严重度失败 **{s['high_failures']}** 项。",
        "",
        "## 一、检查结论",
        "",
        "| 表 | 检查项 | 通过 | 失败 | 结论 |",
        "| --- | ---: | ---: | ---: | :---: |",
    ]
    tables = sorted({f["table"] for f in result["findings"]})
    for table in tables:
        items = [f for f in result["findings"] if f["table"] == table]
        p = sum(1 for f in items if f["status"] == "pass")
        lines.append(
            f"| `{table}` | {len(items)} | {p} | {len(items) - p} | "
            f"{'符合' if p == len(items) else '需整改'} |"
        )
    lines += [
        "",
        "## 二、检查项说明",
        "",
        "| 编号 | 检查项 | 目的 |",
        "| --- | --- | --- |",
        "| STD-001 | 标准表已落地 | 标准中的表是否真实存在 |",
        "| STD-002 | 标准字段齐全 | 防止实现漏字段 |",
        "| STD-003 | 无未登记字段 | 防止“影子字段”绕过标准 |",
        "| STD-004/005 | 命名规范 | 统一表名、字段名风格 |",
        "| STD-006 | 字段元数据完整 | 中文名、类型、说明、标准编号可追溯 |",
        "| STD-007 | 表级管理元数据完整 | 明确 Owner、Steward、更新频率 |",
        "| STD-008 | 主键声明 | 保证记录可唯一定位 |",
        "| STD-009 | 码表引用可解析 | 行业、区划等码表可访问 |",
        "| STD-010 | 长度约束 | 防止超长值破坏下游模型 |",
        "",
        "## 三、失败明细",
        "",
    ]
    failures = [f for f in result["findings"] if f["status"] == "fail"]
    if failures:
        lines += ["| 编号 | 表 | 对象 | 问题 | 严重度 | 建议 |", "| --- | --- | --- | --- | :---: | --- |"]
        for f in failures:
            lines.append(f"| {f['check_id']} | `{f['table']}` | `{f['object']}` | {f['detail']} | {f['severity']} | {f['suggestion']} |")
    else:
        lines.append("本次检查未发现失败项。标准落地情况良好，可将检查结果作为版本发布依据。")
    lines += [
        "",
        "## 四、落标流程",
        "",
        "1. **立项**：业务提出字段需求，数据 Steward 评估是否已有标准可复用；",
        "2. **评审**：涉及跨部门共享的字段，提交数据治理委员会评审，安全合规岗评估个人信息风险；",
        "3. **发布**：更新 `config/standards.json` 并递增版本号，记录变更说明；",
        "4. **落标**：开发按标准建表/改表，CI 执行本检查，失败则阻断发布；",
        "5. **复核**：每季度抽样核对标准与实现的一致性，差异纳入整改台账。",
        "",
    ]
    return "\n".join(lines)


def export_csv(result: dict) -> None:
    path = REPORT_DIR / "standard_check.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["检查编号", "表", "对象", "检查项", "状态", "严重度", "详情", "建议"])
        for f in result["findings"]:
            writer.writerow([f["check_id"], f["table"], f["object"], f["name"], f["status"], f["severity"], f["detail"], f["suggestion"]])


def run(conn) -> dict:
    result = check(conn)
    write_json(REPORT_DIR / "standard_check.json", result)
    write_text(REPORT_DIR / "standard_check.md", render_markdown(result))
    export_csv(result)
    return result
