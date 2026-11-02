#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键运行数据治理全流程：造数 → 清洗 → 元数据 → 标准 → 血缘 → 质量 → 资产 → 看板。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from dgov import assets, cleanse, config, db, lineage, metadata, quality, report, seed_data, standards  # noqa: E402


def main() -> None:
    started = time.time()
    if config.DB_PATH.exists():
        config.DB_PATH.unlink()

    conn = db.connect()
    db.init_schema(conn)

    print("[1/8] 生成示例数据 ...")
    seed_stats = seed_data.generate(conn)
    print(f"      订单 {seed_stats['订单总数']:,} / 用户 {seed_stats['用户总数']:,} / 物流 {seed_stats['物流单数']:,}")

    print("[2/8] 执行清洗与标准化（ODS → DWD）...")
    clean_stats = cleanse.build_dwd(conn)
    cleanse.build_dws(conn)
    print(f"      去重 {clean_stats['duplicates_removed']:,} 条，写入明细 {clean_stats['orders_written']:,} 条")

    print("[3/8] 采集元数据并生成数据目录 ...")
    meta = metadata.collect(conn)
    catalog = metadata.write_catalog(meta)
    print(f"      表 {meta['stats']['table_count']} / 字段 {meta['stats']['column_count']} → {catalog}")

    print("[4/8] 数据标准检查 ...")
    std = standards.check(conn, meta)
    print(f"      违规 {std['total']} 项")

    print("[5/8] 解析数据血缘 ...")
    lin = lineage.build()
    print(f"      节点 {len(lin['nodes'])} / 边 {len(lin['edges'])}")

    print("[6/8] 质量规则巡检（治理前 / 治理后）...")
    q = quality.compare(conn)
    print(f"      质量分 {q['before_score']:.2f} → {q['after_score']:.2f}（+{q['improvement']:.2f}）")

    print("[7/8] 数据资产登记 ...")
    asset = assets.build(meta, q)
    print(f"      资产 {asset['count']} 项")

    print("[8/8] 生成治理看板 ...")
    dashboard = report.build(meta, q, lin, asset, clean_stats)

    print("\n完成，用时 %.1fs" % (time.time() - started))
    print(f"  看板：{dashboard}")
    print(f"  质量报告：{config.REPORT_DIR / 'quality_report.md'}")
    print(f"  数据目录：{catalog}")
    print(f"  资产清单：{asset['csv']}")


if __name__ == "__main__":
    main()
