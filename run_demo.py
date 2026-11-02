#!/usr/bin/env python3
"""一键运行数据治理全流程。

用法：
    python run_demo.py                  # 造数 + 治理 + 报告 + 看板
    python run_demo.py seed             # 只生成模拟数据
    python run_demo.py impact status    # 查询字段变更影响
    python run_demo.py verify           # 校验治理结果是否达到项目验收线
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from dgov import assets, classify, cleanse, dashboard, db, lineage, metadata, metrics, quality, report, standards  # noqa: E402
from dgov.config import load_json  # noqa: E402
from dgov.paths import AS_OF_DEFAULT, DB_PATH, RAW_DIR, REPORT_DIR, SEED_DEFAULT  # noqa: E402
from dgov import seed_data  # noqa: E402


def step(index: int, total: int, text: str) -> None:
    print(f"[{index:02d}/{total}] {text}", flush=True)


def ensure_data(as_of: str, seed: int, reseed: bool) -> None:
    manifest = RAW_DIR / "_defect_manifest.json"
    if reseed or not manifest.exists():
        result = seed_data.generate(as_of, seed)
        rows = sum(item["rows"] for item in result["tables"].values())
        print(f"       已生成 {rows:,} 行模拟数据（seed={seed}, as_of={as_of}）")
    else:
        print("       复用已有原始数据（--reseed 可强制重生成）")


def command_all(args) -> int:
    started = time.time()
    as_of = args.as_of
    ensure_data(as_of, args.seed, args.reseed)
    conn = db.connect(reset=True)
    db.load_reference(conn)
    counts = db.load_raw(conn)
    total_rows = sum(counts.values())
    print(f"       贴源层装载：{total_rows:,} 行 / {len(counts)} 张表")

    step(2, 9, "数据标准符合性检查")
    std = standards.run(conn)
    print(f"       检查 {std['summary']['checks']} 项，符合率 {std['summary']['compliance_rate']*100:.1f}%")

    step(3, 9, "治理前质量基线评估")
    before = quality.baseline(conn, as_of)
    print(f"       综合健康度 {before['summary']['overall_health']:.2f}，问题 {before['summary']['issues']:,} 条")

    step(4, 9, "数据清洗、标准化与隔离")
    cleaning = cleanse.run(conn, date.fromisoformat(as_of))
    print(
        f"       可用率 {cleaning['availability']*100:.1f}%，隔离 {cleaning['total_quarantined']:,} 条，"
        f"修复动作 {sum(cleaning['repairs'].values()):,} 次"
    )

    step(5, 9, "元数据采集与数据目录")
    catalog = metadata.run(conn)
    print(f"       纳管 {catalog['summary']['tables']} 张表 / {catalog['summary']['fields']} 个字段")

    step(6, 9, "分类分级、内容扫描与脱敏共享")
    classification = classify.run(conn)
    print(
        f"       个人信息字段 {classification['summary']['personal_info_fields']} 个，"
        f"内容命中 {classification['content_scan']['affected_rows']:,} 行，"
        f"共享残留 {classification['sharing']['residual_total']} 处"
    )

    step(7, 9, "治理后复检、整改验收与规则有效性验证")
    result = quality.finalize(conn, as_of, before)
    after = result["after"]["summary"]
    closure = result["closure"]
    print(
        f"       综合健康度 {after['overall_health']:.2f}（+{after['overall_health']-before['summary']['overall_health']:.2f}），"
        f"修复 {closure['fixed']:,} / 待整改 {closure['open']:,} / 隔离 {closure['quarantined']:,}"
    )

    step(8, 9, "血缘、资产与指标")
    graph = lineage.run(conn)
    asset_result = assets.run(conn)
    metric_result = metrics.run(conn)
    print(
        f"       血缘 {graph['summary']['nodes']} 节点 / {graph['summary']['field_edges']} 条字段映射；"
        f"资产 {asset_result['summary']['assets']} 项；指标 {len(metric_result['metrics'])} 个"
    )

    step(9, 9, "生成治理报告与驾驶舱")
    ctx = report.run()
    dashboard.run(ctx)
    print(f"       报告目录：{REPORT_DIR}")
    print(f"       驾驶舱：{REPORT_DIR / 'dashboard.html'}")
    print(f"       总耗时 {time.time() - started:.1f}s")
    print("")
    print("治理结果摘要")
    print(f"  综合健康度：{before['summary']['overall_health']:.2f} -> {after['overall_health']:.2f}")
    print(f"  规则达标率：{before['summary']['rule_pass_rate']*100:.1f}% -> {after['rule_pass_rate']*100:.1f}%")
    print(f"  数据可用率：{cleaning['availability']*100:.1f}%")
    print(f"  问题修复：{closure['fixed']:,} 条；待整改：{closure['open']:,} 条")
    print(f"  规则检出率：{result['effectiveness']['summary']['recall']*100:.1f}%")
    conn.close()
    return 0


def command_seed(args) -> int:
    ensure_data(args.as_of, args.seed, True)
    return 0


def command_impact(args) -> int:
    if not DB_PATH.exists():
        print("尚未生成治理结果，请先运行：python run_demo.py", file=sys.stderr)
        return 1
    conn = db.connect()
    result = lineage.impact_cli(conn, args.field)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    conn.close()
    return 0


def command_verify(args) -> int:
    result_path = REPORT_DIR / "quality_result.json"
    if not result_path.exists():
        print("缺少 quality_result.json，请先运行 python run_demo.py", file=sys.stderr)
        return 1
    result = load_json(result_path)
    classification = load_json(REPORT_DIR / "classification.json")
    assets_result = load_json(REPORT_DIR / "asset_register.json")
    before = result["before"]["summary"]["overall_health"]
    after = result["after"]["summary"]["overall_health"]
    recall = result["effectiveness"]["summary"]["recall"]
    residual = classification["sharing"]["residual_total"]
    completeness = assets_result["summary"]["completeness"]
    checks = [
        ("治理后健康度提升 ≥ 8 分", after - before >= 8, f"{before:.2f} -> {after:.2f}"),
        ("规则对注入缺陷检出率 ≥ 90%", recall >= 0.9, f"{recall*100:.1f}%"),
        ("共享文件个人信息残留 = 0", residual == 0, f"{residual} 处"),
        ("资产登记完整率 = 100%", completeness >= 1, f"{completeness*100:.0f}%"),
        ("存在自动修复的问题", result["closure"]["fixed"] > 0, f"{result['closure']['fixed']} 条"),
        ("治理后仍有待整改问题（不是全部删库）", result["closure"]["open"] > 0, f"{result['closure']['open']} 条"),
    ]
    failed = 0
    for name, ok, detail in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name}  ({detail})")
        failed += 0 if ok else 1
    if failed:
        print(f"\n{failed} 项验收未通过", file=sys.stderr)
        return 1
    print("\n全部验收项通过")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="雄安新区市场主体服务数据治理项目")
    sub = parser.add_subparsers(dest="command")
    for name, help_text in (
        ("all", "运行完整治理流程（默认）"),
        ("seed", "重新生成模拟数据"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--as-of", default=AS_OF_DEFAULT, help="数据截止日 YYYY-MM-DD")
        p.add_argument("--seed", type=int, default=SEED_DEFAULT, help="随机种子")
        p.add_argument("--reseed", action="store_true", help="强制重新生成数据")
    impact_parser = sub.add_parser("impact", help="查询字段变更影响")
    impact_parser.add_argument("field", help="字段名，如 contact_phone 或 dwd_market_register.status")
    sub.add_parser("verify", help="校验治理结果")
    args = parser.parse_args()

    if args.command in (None, "all"):
        if not hasattr(args, "as_of"):
            args.as_of = AS_OF_DEFAULT
            args.seed = SEED_DEFAULT
            args.reseed = False
        return command_all(args)
    if args.command == "seed":
        return command_seed(args)
    if args.command == "impact":
        return command_impact(args)
    if args.command == "verify":
        return command_verify(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
