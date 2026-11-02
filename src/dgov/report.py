# -*- coding: utf-8 -*-
"""作品展示：生成单文件 HTML 治理看板（离线可打开、可直接截图）。"""
from __future__ import annotations

import html
from datetime import datetime

from .config import REPORT_DIR

CSS = """
:root{
  --navy:#0f2742; --navy2:#173a5e; --ink:#1b2430; --muted:#5b6b7c;
  --line:#e3e9f0; --bg:#f4f7fb; --card:#ffffff; --accent:#2f6fed;
  --good:#1f9d6b; --warn:#d98324; --bad:#c8453c;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-family:"Microsoft YaHei","PingFang SC","Segoe UI",sans-serif;line-height:1.55}
.wrap{max-width:1180px;margin:0 auto;padding:28px 24px 40px}
.hero{background:linear-gradient(135deg,#0f2742 0%,#1c4a7a 55%,#2f6fed 100%);color:#fff;border-radius:18px;padding:30px 34px;position:relative;overflow:hidden}
.hero:after{content:"";position:absolute;right:-60px;top:-80px;width:280px;height:280px;border-radius:50%;background:rgba(255,255,255,.08)}
.eyebrow{font-size:12px;letter-spacing:.18em;text-transform:uppercase;opacity:.78}
.hero h1{font-size:34px;font-weight:700;margin:8px 0 6px;letter-spacing:.02em}
.hero p{opacity:.9;font-size:14px}
.hero .meta{margin-top:14px;font-size:12px;opacity:.75}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin:18px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px}
.kpi .label{font-size:12px;color:var(--muted)}
.kpi .value{font-size:27px;font-weight:700;color:var(--navy);margin-top:4px;font-variant-numeric:tabular-nums}
.kpi .sub{font-size:11px;color:var(--muted);margin-top:2px}
.kpi.accent .value{color:var(--accent)}
.kpi.good .value{color:var(--good)}
.grid2{display:grid;grid-template-columns:1.05fr .95fr;gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px 22px;margin-bottom:16px}
.card h2{font-size:15px;color:var(--navy);margin-bottom:4px}
.card .hint{font-size:12px;color:var(--muted);margin-bottom:14px}
.bar-row{display:grid;grid-template-columns:96px 1fr 64px;align-items:center;gap:10px;margin:9px 0;font-size:12px}
.bar{height:12px;border-radius:6px;background:#eef2f7;overflow:hidden;position:relative}
.bar span{display:block;height:100%;position:absolute;left:0;top:0}
.bar .before{background:repeating-linear-gradient(45deg,#8ea6bf,#8ea6bf 4px,transparent 4px,transparent 8px);opacity:.65;z-index:2}
.bar .after{background:linear-gradient(90deg,#2f6fed,#1f9d6b)}
.num{text-align:right;color:var(--muted);font-variant-numeric:tabular-nums}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{color:var(--muted);font-weight:600;text-align:left;padding:8px 6px;border-bottom:1px solid var(--line)}
td{padding:8px 6px;border-bottom:1px solid #f0f4f9;vertical-align:top}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.tag{display:inline-block;padding:1px 7px;border-radius:999px;font-size:11px;background:#eef4ff;color:#2f6fed}
.tag.good{background:#e8f6ef;color:#1f9d6b}
.tag.warn{background:#fdf1e3;color:#b56a12}
.tag.bad{background:#fbeceb;color:#b83b33}
pre{background:#0f2742;color:#dce8f5;padding:16px 18px;border-radius:12px;font-size:12px;overflow:auto;line-height:1.55}
.foot{margin-top:18px;color:var(--muted);font-size:11.5px;text-align:center}
.legend{display:flex;gap:14px;font-size:11.5px;color:var(--muted);margin-top:6px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px}
.minis{display:grid;grid-template-columns:repeat(6,1fr);gap:12px}
.mini{background:#f7f9fc;border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.mv{font-size:21px;font-weight:700;color:var(--navy);font-variant-numeric:tabular-nums}
.ml{font-size:11.5px;color:var(--muted);margin-top:2px}
@media (max-width:900px){.kpis{grid-template-columns:repeat(2,1fr)}.grid2{grid-template-columns:1fr}}
"""


def _bar(label: str, before: float, after: float, maxv: float = 100.0) -> str:
    return f"""
    <div class="bar-row">
      <div>{html.escape(label)}</div>
      <div class="bar">
        <span class="before" style="width:{max(2, before / maxv * 100):.1f}%"></span>
        <span class="after" style="width:{max(2, after / maxv * 100):.1f}%;opacity:.9"></span>
      </div>
      <div class="num">{after:.2f}</div>
    </div>"""


def build(meta: dict, quality: dict, lin: dict, asset: dict, clean_stats: dict | None = None) -> str:
    stats = meta["stats"]
    q0 = quality["before_score"]
    q1 = quality["after_score"]
    issues = quality["issues"]
    level_summary = stats["level_summary"]

    kpis = f"""
  <div class="kpi"><div class="label">治理范围</div><div class="value">{stats['table_count']}</div><div class="sub">张表 · {stats['column_count']} 字段</div></div>
  <div class="kpi"><div class="label">质量规则</div><div class="value">{quality['rule_count']}</div><div class="sub">5 个维度 · 配置化</div></div>
  <div class="kpi good"><div class="label">治理后质量分</div><div class="value">{q1:.2f}</div><div class="sub">治理前 {q0:.2f} · +{quality['improvement']:.2f}</div></div>
  <div class="kpi"><div class="label">数据资产</div><div class="value">{asset['count']}</div><div class="sub">已登记 · 100% 有 Owner</div></div>
  <div class="kpi accent"><div class="label">待整改问题</div><div class="value">{len(issues)}</div><div class="sub">按 SLA 跟踪</div></div>"""

    dims = "".join(
        _bar(dim, quality["before"]["by_dimension"][dim]["score"], quality["after"]["by_dimension"][dim]["score"])
        for dim in ["完整性", "唯一性", "有效性", "一致性", "及时性"]
        if dim in quality["after"]["by_dimension"]
    )

    health_rows = "".join(
        f"<tr><td>{name}</td><td class='num'>{v['rows']:,}</td>"
        f"<td class='num'>{v['bad_rows']:,}</td><td class='num'>{v['score']:.2f}</td>"
        f"<td><span class='tag {'good' if v['score'] >= 99.5 else 'warn'}'>{'健康' if v['score'] >= 99.5 else '亚健康'}</span></td></tr>"
        for name, v in quality["after"]["by_table"].items()
    )

    issue_rows = "".join(
        f"<tr><td>{i['rule_id']}</td><td>{html.escape(i['table'])}</td><td>{i['dimension']}</td>"
        f"<td class='num'>{i['failed']:,}</td><td>{html.escape(i['owner'])}</td>"
        f"<td><span class='tag warn'>{i['status']}</span></td></tr>"
        for i in issues
    ) or "<tr><td colspan='6'>无遗留问题，全部规则通过</td></tr>"

    level_total = sum(level_summary.values()) or 1
    level_bars = ""
    for lv, cnt in level_summary.items():
        name = {"L1": "L1 公开", "L2": "L2 内部", "L3": "L3 敏感", "L4": "L4 核心"}[lv]
        pct = cnt / level_total * 100
        level_bars += (
            f"<div class='bar-row'><div>{name}</div><div class='bar'>"
            f"<span class='after' style='width:{max(1.5, pct):.1f}%'></span></div>"
            f"<div class='num'>{cnt}</div></div>"
        )

    asset_rows = "".join(
        f"<tr><td>{html.escape(a['name'])}</td><td>{html.escape(a['table'])}</td>"
        f"<td>{a['domain']}</td><td>{a['level']}</td><td class='num'>{a['row_count']:,}</td>"
        f"<td class='num'>{a['quality_score'] if a['quality_score'] != '' else '—'}</td></tr>"
        for a in asset["assets"]
    )

    edge_lines = "\n".join(f"{s} --> {t}" for s, t, _ in lin["edges"][:18])

    cs = clean_stats or {}
    actions = [
        ("订单去重", cs.get("duplicates_removed", 0)),
        ("渠道码值纠正", cs.get("channel_normalized", 0)),
        ("手机号修复", cs.get("phone_invalid", 0)),
        ("状态纠正", cs.get("status_invalid", 0)),
        ("时序修复", cs.get("pay_time_fixed", 0) + cs.get("pay_time_filled", 0)),
        ("明细落库", cs.get("orders_written", 0)),
    ]
    action_items = "".join(
        f'<div class="mini"><div class="mv">{v:,}</div><div class="ml">{k}</div></div>' for k, v in actions
    )

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    html_text = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>数据治理看板 · data-governance-in-action</title>
<style>{CSS}</style></head>
<body><div class="wrap">
  <header class="hero">
    <div class="eyebrow">Data Governance in Action</div>
    <h1>电商数据治理看板</h1>
    <p>数据目录 · 标准与分级 · 质量规则 · 血缘 · 资产登记，一条流水线跑通治理闭环</p>
    <div class="meta">数据周期 2026-07-01 ~ 2026-09-28 · 生成时间 {now} · 全部指标由脚本自动计算</div>
  </header>

  <section class="kpis">{kpis}</section>

  <div class="grid2">
    <div class="card">
      <h2>质量分：治理前 vs 治理后</h2>
      <div class="hint">按「未命中任何质量规则的行占比」计算，行级口径，避免被规则数量稀释</div>
      {_bar("整体质量分", q0, q1)}
      {dims}
      <div class="legend"><span><i class="dot" style="background:#c9d6e6"></i>治理前</span><span><i class="dot" style="background:#2f6fed"></i>治理后</span></div>
    </div>
    <div class="card">
      <h2>数据分类分级分布</h2>
      <div class="hint">按字段自动识别，L4 核心字段强制脱敏 + 访问审批</div>
      {level_bars}
      <div class="hint" style="margin-top:14px">敏感字段（L3/L4）共 <b>{stats['sensitive_column_count']}</b> 个，已生成脱敏规则与最小权限策略。</div>
    </div>
  </div>

  <div class="card">
    <h2>核心表健康度</h2>
    <div class="hint">质量分 ≥ 99.5 记为健康，低于阈值自动进入整改台账</div>
    <table><thead><tr><th>数据集</th><th class="num">校验行数</th><th class="num">问题行数</th><th class="num">质量分</th><th>状态</th></tr></thead>
    <tbody>{health_rows}</tbody></table>
  </div>

  <div class="card">
    <h2>本次治理动作</h2>
    <div class="hint">从贴源层到明细层，脚本自动完成清洗、标准化与修复，每个动作都有计数可追溯</div>
    <div class="minis">{action_items}</div>
  </div>

  <div class="grid2">
    <div class="card">
      <h2>问题整改台账</h2>
      <div class="hint">问题带责任人、SLA 期限与样本数据，可直接派单</div>
      <table><thead><tr><th>规则</th><th>表</th><th>维度</th><th class="num">失败行</th><th>责任人</th><th>状态</th></tr></thead>
      <tbody>{issue_rows}</tbody></table>
    </div>
    <div class="card">
      <h2>数据资产（示例）</h2>
      <div class="hint">资产登记包含 Owner、密级、SLA、使用场景与质量分</div>
      <table><thead><tr><th>资产</th><th>表</th><th>域</th><th>密级</th><th class="num">行数</th><th class="num">质量分</th></tr></thead>
      <tbody>{asset_rows}</tbody></table>
    </div>
  </div>

  <div class="card">
    <h2>表级血缘（节选）</h2>
    <div class="hint">由清洗作业配置与 DWS 聚合 SQL 自动解析，可用于变更影响分析</div>
    <pre>{html.escape(edge_lines)}</pre>
  </div>

  <div class="foot">data-governance-in-action · 生成脚本 run_demo.py · 数据为可复现的模拟数据</div>
</div></body></html>"""

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / "dashboard.html"
    out.write_text(html_text, encoding="utf-8")
    return str(out)
