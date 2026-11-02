"""指标口径执行：在 DWD 层运行指标 SQL，保证口径与看板一致。"""
from __future__ import annotations

from datetime import datetime

from . import db
from .config import load_config, write_json, write_text
from .paths import REPORT_DIR


def run(conn) -> dict:
    config = load_config("metrics.json")
    items = []
    for metric in config["metrics"]:
        row = db.fetch_one(conn, metric["sql"])
        value = row.get("value") if row else None
        items.append({**metric, "value": value})
    result = {
        "generated_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        "metrics": items,
    }
    write_json(REPORT_DIR / "metrics.json", result)
    lines = [
        "# 核心指标口径与结果",
        "",
        f"> 自动生成于 {result['generated_at']}。全部指标在 DWD 明细层执行，SQL 见 `config/metrics.json`。",
        "",
        "| 指标 | 口径 | 结果 | 单位 | Owner | 注意事项 |",
        "| --- | --- | ---: | :---: | --- | --- |",
    ]
    for item in items:
        value = "-" if item["value"] is None else f"{item['value']:,}"
        lines.append(
            f"| {item['name']} | {item['definition']} | {value} | {item['unit']} | "
            f"{item['owner']} | {item['caveat']} |"
        )
    lines += [
        "",
        "## 口径管理规则",
        "",
        "1. 指标口径由业务 Owner 提出，数据 Steward 审核 SQL 实现，双方签字后发布；",
        "2. 同一指标只允许一个权威口径，派生指标须引用原子指标，不得各算各的；",
        "3. 口径变更须走影响分析，同步更新看板、月报和共享接口；",
        "4. 指标下线前保留 12 个月历史数据，避免同比/环比断档。",
        "",
    ]
    write_text(REPORT_DIR / "metrics.md", "\n".join(lines))
    return result
