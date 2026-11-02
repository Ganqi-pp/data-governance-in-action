"""单文件治理驾驶舱：离线可打开，图表与血缘图均为内联 SVG，无外部依赖。"""
from __future__ import annotations

import html
import json
import math
from datetime import datetime
from string import Template

from .config import write_text
from .paths import REPORT_DIR

REPO_URL = "https://github.com/Ganqi-pp/data-governance-in-action"

CSS = r"""
:root{
  --ink:#0b1f2a; --ink-2:#12313d; --teal:#0f766e; --teal-2:#14b8a6;
  --mint:#5eead4; --amber:#d97706; --red:#b91c1c; --blue:#0369a1;
  --muted:#64748b; --faint:#94a3b8; --line:#e2e8f0; --bg:#eef3f6; --card:#fff;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:#0f172a;
  font-family:"Microsoft YaHei","PingFang SC","Noto Sans SC",system-ui,-apple-system,sans-serif;
  -webkit-font-smoothing:antialiased;}
.page{max-width:1320px;margin:0 auto;padding:24px 28px 56px}
.hero{position:relative;overflow:hidden;border-radius:26px;padding:30px 38px 58px;color:#e8f6f2;
  background:linear-gradient(120deg,#061a22 0%,#0a2c36 52%,#0b3f3b 100%);}
.hero::before{content:"";position:absolute;inset:-40% -10% auto auto;width:760px;height:760px;
  background:radial-gradient(circle,rgba(20,184,166,.32),transparent 62%);filter:blur(8px);}
.hero::after{content:"";position:absolute;inset:auto auto -260px -120px;width:620px;height:620px;
  background:radial-gradient(circle,rgba(3,105,161,.30),transparent 64%);}
.hero-top{display:flex;justify-content:space-between;align-items:center;gap:20px;position:relative;z-index:2}
.brand{display:flex;align-items:center;gap:10px;font-size:11px;letter-spacing:.2em;color:#8dd8ce;text-transform:uppercase}
.brand .dot{width:8px;height:8px;border-radius:50%;background:var(--mint);box-shadow:0 0 0 5px rgba(94,234,212,.12)}
.meta{font-size:11px;color:#7fa8a5;letter-spacing:.04em;text-align:right;line-height:1.8}
h1{position:relative;z-index:2;margin:22px 0 14px;font-size:42px;line-height:1.22;letter-spacing:-.02em;font-weight:700}
h1 em{font-style:normal;color:var(--mint)}
.lede{position:relative;z-index:2;max-width:860px;margin:0;color:#a9c9c5;font-size:13.5px;line-height:1.95}
.chips{position:relative;z-index:2;display:flex;flex-wrap:wrap;gap:9px;margin-top:24px}
.chips span{font-size:11.5px;color:#d5efeb;border:1px solid rgba(148,208,200,.28);background:rgba(255,255,255,.055);
  padding:6px 12px;border-radius:999px;backdrop-filter:blur(4px)}
.chips b{color:#fff;font-weight:600}
.kpis{position:relative;z-index:3;display:grid;grid-template-columns:repeat(6,1fr);gap:13px;margin:-36px 18px 0}
.kpi{background:var(--card);border:1px solid rgba(226,232,240,.95);border-radius:15px;padding:15px 16px 14px;
  box-shadow:0 8px 24px rgba(8,47,56,.08)}
.kpi .label{font-size:12px;color:var(--muted);letter-spacing:.02em}
.kpi .value{font-size:25px;font-weight:700;margin:7px 0 3px;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.kpi .value small{font-size:12px;color:var(--faint);font-weight:500}
.kpi .sub{font-size:11px;color:var(--faint);line-height:1.5}
.kpi.dark{background:linear-gradient(145deg,#0f766e,#115e59);border-color:transparent;color:#fff}
.kpi.dark .label,.kpi.dark .sub{color:#b8e6df}
.kpi.dark .value small{color:#8fd8ce}
.kpi .up{color:#0f766e;font-weight:600}
.grid{display:grid;grid-template-columns:1.12fr .88fr;gap:16px;margin-top:16px}
.grid.three{grid-template-columns:1.05fr .95fr}
.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:21px 23px;
  box-shadow:0 1px 2px rgba(15,23,42,.035)}
.card-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:4px}
.card h2{font-size:16.5px;margin:0;letter-spacing:-.01em}
.card .hint{font-size:12px;color:var(--faint);line-height:1.7;margin:5px 0 17px}
.tag{font-size:10px;color:var(--teal);background:#ecfdf5;border:1px solid #ccfbf1;border-radius:999px;padding:3px 9px;white-space:nowrap}
.big-row{display:flex;align-items:baseline;gap:8px;margin:2px 0 14px}
.big{font-size:36px;font-weight:700;letter-spacing:-.03em;line-height:1}
.big.teal{color:var(--teal)}
.big small{font-size:13px;font-weight:500;color:var(--faint)}
.delta{font-size:12px;color:var(--teal);background:#ecfdf5;border-radius:6px;padding:3px 7px;font-weight:600}
.bar-row{display:grid;grid-template-columns:92px 1fr 48px;align-items:center;gap:10px;margin:11px 0;font-size:12px}
.bar-row .name{color:#334155}
.bar-row .val{text-align:right;font-variant-numeric:tabular-nums;color:#475569;font-weight:600}
.track{height:8px;border-radius:99px;background:#eef2f6;overflow:hidden;position:relative}
.track .fill{height:100%;border-radius:99px;background:linear-gradient(90deg,#0f766e,#2dd4bf)}
.track .ghost{position:absolute;left:0;top:0;height:100%;border-radius:99px;background:#cbd5e1}
.mini-legend{display:flex;gap:16px;font-size:11px;color:var(--faint);margin-top:12px}
.mini-legend i{display:inline-block;width:9px;height:9px;border-radius:3px;margin-right:5px;vertical-align:-1px}
.radar-wrap{display:flex;align-items:center;justify-content:center;margin-top:-4px}
.legend{display:flex;justify-content:center;gap:20px;font-size:10.5px;color:var(--muted);margin-top:2px}
.legend i{display:inline-block;width:16px;height:3px;border-radius:2px;margin-right:6px;vertical-align:2px}
.status-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin:4px 0 16px}
.status{border-radius:12px;padding:11px 12px;background:#f8fafc;border:1px solid #eef2f6}
.status .n{font-size:22px;font-weight:700;line-height:1.2;font-variant-numeric:tabular-nums}
.status .t{font-size:10.5px;color:var(--faint);margin-top:3px}
.status.fixed .n{color:var(--teal)} .status.iso .n{color:var(--amber)}
.status.open .n{color:var(--red)} .status.obs .n{color:var(--blue)}
.stack{display:flex;height:12px;border-radius:99px;overflow:hidden;background:#eef2f6;margin:4px 0 10px}
.stack span{display:block;height:100%}
.stack-note{font-size:10.5px;color:var(--faint);line-height:1.7}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{text-align:left;color:var(--faint);font-weight:500;padding:8px 8px;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:10px 8px;border-bottom:1px solid #f1f5f9;color:#334155;vertical-align:top}
tr:last-child td{border-bottom:none}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.pill{display:inline-block;font-size:10px;padding:2px 7px;border-radius:999px;white-space:nowrap;border:1px solid transparent}
.pill.high{background:#fef2f2;color:#b91c1c;border-color:#fee2e2}
.pill.mid{background:#fffbeb;color:#b45309;border-color:#fef3c7}
.pill.low{background:#f0f9ff;color:#0369a1;border-color:#e0f2fe}
.pill.ok{background:#ecfdf5;color:#0f766e;border-color:#ccfbf1}
.pill.warn{background:#fffbeb;color:#b45309;border-color:#fde68a}
.pill.bad{background:#fef2f2;color:#b91c1c;border-color:#fecaca}
.pill.gray{background:#f8fafc;color:#64748b;border-color:#e2e8f0}
.metric-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px}
.metric{background:#f8fafc;border:1px solid #eef2f6;border-radius:12px;padding:12px 13px}
.metric .m-name{font-size:10.5px;color:var(--faint)}
.metric .m-val{font-size:23px;font-weight:700;margin:5px 0 2px;font-variant-numeric:tabular-nums}
.metric .m-val small{font-size:11px;color:var(--faint);font-weight:500}
.metric .m-owner{font-size:10px;color:#94a3b8}
.metric:last-child{grid-column:span 2}
.scan-table td{padding:7px 6px}
.scan-table th{padding:6px 6px}
.section-title{display:flex;align-items:center;gap:12px;margin:26px 2px 10px}
.section-title h3{font-size:15px;margin:0;letter-spacing:.02em;color:#1e293b}
.section-title span{font-size:10.5px;color:var(--faint);letter-spacing:.1em;text-transform:uppercase}
.section-title .line{flex:1;height:1px;background:linear-gradient(90deg,#dbe4ea,transparent)}
.asset-table td{font-size:11px}
.lineage-wrap{background:linear-gradient(180deg,#f8fafc,#fff);border:1px solid #eef2f6;border-radius:14px;padding:8px 6px 4px;overflow:hidden}
.issue-tools{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin:4px 0 12px}
.btn{font-size:10.5px;color:#475569;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;
  padding:5px 10px;cursor:pointer;font-family:inherit}
.btn:hover{border-color:#99f6e4;color:#0f766e}
.btn.active{background:#0f766e;border-color:#0f766e;color:#fff}
.search{margin-left:auto;font-size:11px;border:1px solid #e2e8f0;border-radius:8px;padding:6px 10px;width:220px;
  font-family:inherit;color:#334155;outline:none}
.search:focus{border-color:#5eead4;box-shadow:0 0 0 3px rgba(20,184,166,.10)}
.table-scroll{max-height:520px;overflow:auto;border:1px solid #f1f5f9;border-radius:10px}
.table-scroll thead th{position:sticky;top:0;background:#fff;z-index:1}
.issue-id{font-family:Consolas,monospace;font-size:10px;color:#94a3b8}
.empty{text-align:center;color:#94a3b8;padding:28px;font-size:12px}
.footer{margin-top:26px;padding:20px 4px 0;border-top:1px solid #dbe4ea;color:#94a3b8;font-size:11px;line-height:1.9}
.footer a{color:#0f766e;text-decoration:none;border-bottom:1px dotted #99f6e4}
.footer .mono{font-family:Consolas,monospace;background:#f1f5f9;padding:2px 6px;border-radius:4px;color:#475569}
.note{font-size:11px;color:#94a3b8;line-height:1.75;margin-top:9px}
.repairs{margin-top:18px;padding-top:14px;border-top:1px dashed #e2e8f0}
.repairs .r-title{font-size:11px;color:#64748b;margin-bottom:8px;letter-spacing:.02em}
.repairs .bar-row{margin:7px 0;grid-template-columns:150px 1fr 34px}
.repairs .bar-row .name{font-size:11px;color:#64748b}
.repairs .track{height:6px}
.repairs .track .fill{background:linear-gradient(90deg,#bae6fd,#0ea5e9)}
@media (max-width:1080px){
  .kpis{grid-template-columns:repeat(3,1fr);margin:-30px 0 0}
  .grid,.grid.three{grid-template-columns:1fr}
  h1{font-size:31px}
}
@media (max-width:640px){
  .page{padding:14px}
  .hero{padding:22px 20px 50px;border-radius:18px}
  .kpis{grid-template-columns:1fr 1fr}
  h1{font-size:25px}
  .meta{display:none}
  .status-grid{grid-template-columns:1fr 1fr}
}
"""

JS = r"""
const $ = (s) => document.querySelector(s);
let statusFilter = "全部";
let severityFilter = "全部";
let keyword = "";
const issues = DATA.issues || [];

function esc(v){
  return String(v == null ? "" : v).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
}
function statusPill(s){
  const cls = s === "已修复" ? "ok" : s === "已隔离" ? "warn" : s === "待整改" ? "bad" : "gray";
  return `<span class="pill ${cls}">${esc(s)}</span>`;
}
function renderIssues(){
  const body = $("#issue-body");
  const filtered = issues.filter(i =>
    (statusFilter === "全部" || i.status === statusFilter) &&
    (severityFilter === "全部" || i.severity === severityFilter) &&
    (!keyword || (i.rule_id + i.rule_name + i.table + i.field + i.owner + i.evidence).toLowerCase().includes(keyword))
  );
  if(!filtered.length){ body.innerHTML = '<tr><td colspan="9" class="empty">没有匹配的问题记录</td></tr>'; }
  else {
    body.innerHTML = filtered.slice(0, 300).map(i => `
      <tr>
        <td class="issue-id">${esc(i.issue_id)}</td>
        <td><span class="pill ${i.severity === "高" ? "high" : i.severity === "中" ? "mid" : "low"}">${esc(i.severity)}</span></td>
        <td>${statusPill(i.status)}</td>
        <td><b>${esc(i.rule_id)}</b><br><span style="color:#94a3b8">${esc(i.rule_name)}</span></td>
        <td>${esc(i.table)}<br><span style="color:#94a3b8">${esc(i.field || "-")}</span></td>
        <td>${esc(i.evidence)}</td>
        <td>${esc(i.owner)}</td>
        <td class="num">${esc(i.due_date)}</td>
      </tr>`).join("");
  }
  $("#issue-count").textContent = `匹配 ${filtered.length.toLocaleString()} 条 · 页面展示前 ${Math.min(filtered.length, 300)} 条 · 全量见 issue_register.csv`;
}
document.querySelectorAll("[data-status]").forEach(btn => {
  btn.addEventListener("click", () => {
    statusFilter = btn.dataset.status;
    document.querySelectorAll("[data-status]").forEach(b => b.classList.toggle("active", b === btn));
    renderIssues();
  });
});
document.querySelectorAll("[data-sev]").forEach(btn => {
  btn.addEventListener("click", () => {
    severityFilter = btn.dataset.sev;
    document.querySelectorAll("[data-sev]").forEach(b => b.classList.toggle("active", b === btn));
    renderIssues();
  });
});
const search = document.getElementById("issue-search");
if(search){ search.addEventListener("input", e => { keyword = e.target.value.trim().toLowerCase(); renderIssues(); }); }
renderIssues();
"""

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>雄安新区市场主体服务 · 数据治理驾驶舱</title>
<style>%%CSS%%</style>
</head>
<body>
<div class="page">
%%BODY%%
<div class="footer">
  数据治理驾驶舱 · 由 <span class="mono">python run_demo.py</span> 自动生成 ·
  <a href="%%REPO%%/blob/main/reports/quality_report.md">质量报告</a> ·
  <a href="%%REPO%%/blob/main/reports/governance_report.md">治理月报</a> ·
  <a href="%%REPO%%/blob/main/reports/data_catalog.md">数据目录</a> ·
  <a href="%%REPO%%/blob/main/reports/asset_register.md">资产台账</a> ·
  <a href="%%REPO%%/blob/main/reports/lineage.md">数据血缘</a><br>
  数据为固定种子生成的虚构模拟数据，不对应任何真实企业或个人；图表与指标均由脚本实时计算，无手工数字。
  项目仓库：<a href="%%REPO%%">%%REPO%%</a>
</div>
</div>
<script>const DATA = %%DATA%%;</script>
<script>%%JS%%</script>
</body>
</html>
"""


def _pct(value) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "-"


def radar_svg(before: dict, after: dict) -> str:
    dims = ["完整性", "准确性", "一致性", "唯一性", "有效性", "及时性"]
    cx, cy, radius = 190, 165, 108
    angles = [-math.pi / 2 + i * math.pi / 3 for i in range(6)]

    def point(value: float, index: int) -> tuple[float, float]:
        r = radius * max(0, min(100, value)) / 100
        return cx + r * math.cos(angles[index]), cy + r * math.sin(angles[index])

    parts = ['<svg viewBox="0 0 380 330" width="100%" role="img" aria-label="六维质量雷达图">']
    for ring in (25, 50, 75, 100):
        pts = " ".join(f"{cx + radius * ring / 100 * math.cos(a):.1f},{cy + radius * ring / 100 * math.sin(a):.1f}" for a in angles)
        parts.append(f'<polygon points="{pts}" fill="none" stroke="#e2e8f0" stroke-width="1"/>')
    for i, angle in enumerate(angles):
        x, y = cx + radius * math.cos(angle), cy + radius * math.sin(angle)
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#eef2f6" stroke-width="1"/>')
        lx, ly = cx + (radius + 24) * math.cos(angle), cy + (radius + 24) * math.sin(angle)
        anchor = "middle" if abs(math.cos(angle)) < 0.3 else ("start" if math.cos(angle) > 0 else "end")
        parts.append(f'<text x="{lx:.1f}" y="{ly + 4:.1f}" text-anchor="{anchor}" font-size="11" fill="#64748b">{dims[i]}</text>')
    before_pts = " ".join(f"{point(before.get(d, 0), i)[0]:.1f},{point(before.get(d, 0), i)[1]:.1f}" for i, d in enumerate(dims))
    after_pts = " ".join(f"{point(after.get(d, 0), i)[0]:.1f},{point(after.get(d, 0), i)[1]:.1f}" for i, d in enumerate(dims))
    parts.append(f'<polygon points="{before_pts}" fill="rgba(148,163,184,.14)" stroke="#94a3b8" stroke-width="1.4" stroke-dasharray="4 3"/>')
    parts.append(f'<polygon points="{after_pts}" fill="rgba(20,184,166,.18)" stroke="#0f766e" stroke-width="2"/>')
    for i, d in enumerate(dims):
        x, y = point(after.get(d, 0), i)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#0f766e"/>')
    parts.append("</svg>")
    return "".join(parts)


def lineage_svg(lineage: dict) -> str:
    nodes = {n["id"]: n for n in lineage.get("nodes", [])}
    keep = [
        "sys_reg", "sys_credit", "sys_hotline",
        "ods_market_register", "ods_credit_rating", "ods_complaint_case",
        "dwd_market_register", "dwd_credit_rating", "dwd_complaint_case",
        "metric_market_total", "metric_credit_a", "metric_case_close",
        "share_market_register", "share_complaint_case", "report_dashboard",
    ]
    short = {
        "sys_reg": "登记系统", "sys_credit": "信用平台", "sys_hotline": "12345 热线",
        "ods_market_register": "登记贴源表", "ods_credit_rating": "信用贴源表",
        "ods_complaint_case": "工单贴源表",
        "dwd_market_register": "市场主体明细", "dwd_credit_rating": "信用评价明细",
        "dwd_complaint_case": "诉求工单明细",
        "metric_market_total": "市场主体总数", "metric_credit_a": "A 级信用占比",
        "metric_case_close": "诉求办结率",
        "share_market_register": "市场主体共享接口", "share_complaint_case": "诉求共享接口",
        "report_dashboard": "治理驾驶舱",
    }
    columns = {
        "source": 24, "ods": 246, "dwd": 468, "dws": 690, "serving": 912,
    }
    layer_color = {"source": "#334155", "ods": "#0ea5e9", "dwd": "#0f766e", "dws": "#7c3aed", "serving": "#d97706"}
    positions = {}
    for layer, x in columns.items():
        ids = [nid for nid in keep if nodes.get(nid, {}).get("layer") == layer]
        start_y = 66 if len(ids) <= 3 else 52
        gap = 60 if len(ids) <= 3 else 54
        for index, nid in enumerate(ids):
            positions[nid] = (x, start_y + index * gap)
    parts = ['<svg viewBox="0 0 1140 330" width="100%" role="img" aria-label="数据血缘图">']
    parts.append('<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">'
                 '<path d="M0,0 L8,4 L0,8 z" fill="#94a3b8"/></marker></defs>')
    for layer, x in columns.items():
        label = {"source": "源系统", "ods": "ODS 贴源", "dwd": "DWD 明细", "dws": "DWS 指标", "serving": "服务与共享"}[layer]
        parts.append(f'<text x="{x}" y="26" font-size="10.5" fill="#94a3b8" letter-spacing="1">{label}</text>')
        parts.append(f'<line x1="{x}" y1="34" x2="{x + 150}" y2="34" stroke="#e2e8f0"/>')
    for edge in lineage.get("edges", []):
        if edge["from"] not in positions or edge["to"] not in positions:
            continue
        x1, y1 = positions[edge["from"]]
        x2, y2 = positions[edge["to"]]
        sx, sy = x1 + 158, y1 + 18
        tx, ty = x2, y2 + 18
        parts.append(
            f'<path d="M{sx},{sy} C{sx + 42},{sy} {tx - 42},{ty} {tx},{ty}" fill="none" '
            f'stroke="#94a3b8" stroke-width="1.2" opacity=".58" marker-end="url(#arrow)"/>'
        )
    for nid, (x, y) in positions.items():
        node = nodes.get(nid, {})
        color = layer_color.get(node.get("layer"), "#64748b")
        name = short.get(nid, node.get("name", nid))
        parts.append(f'<rect x="{x}" y="{y}" width="158" height="38" rx="9" fill="#fff" stroke="{color}" stroke-width="1.2"/>')
        parts.append(f'<rect x="{x}" y="{y}" width="4" height="38" rx="2" fill="{color}"/>')
        parts.append(f'<text x="{x + 13}" y="{y + 17}" font-size="11.5" fill="#0f172a">{html.escape(name)}</text>')
        if node.get("rows") is not None:
            parts.append(f'<text x="{x + 13}" y="{y + 30}" font-size="9.5" fill="#94a3b8">{node["rows"]:,} 行</text>')
        else:
            parts.append(f'<text x="{x + 13}" y="{y + 30}" font-size="9.5" fill="#94a3b8">{html.escape(node.get("type", ""))}</text>')
    parts.append("</svg>")
    return "".join(parts)


def status_pill(text: str, cls: str) -> str:
    return f'<span class="pill {cls}">{html.escape(text)}</span>'


def build_body(ctx: dict) -> str:
    q = ctx.get("quality", {})
    if not q:
        return '<div class="card">尚未生成质量结果，请先运行 <code>python run_demo.py</code>。</div>'
    before = q["before"]["summary"]
    after = q["after"]["summary"]
    closure = q["closure"]
    cleaning = ctx.get("cleaning", {})
    cls = ctx.get("classification", {})
    cls_sum = cls.get("summary", {})
    scan = cls.get("content_scan", {})
    sharing = cls.get("sharing", {})
    assets = ctx.get("assets", {})
    metrics = ctx.get("metrics", {}).get("metrics", [])
    lineage = ctx.get("lineage", {})
    effective = q.get("effectiveness", {}).get("summary", {})
    delta = after["overall_health"] - before["overall_health"]
    total_issues = closure["raw_issues"]
    fixed_pct = closure["closure_rate"] * 100
    disposition_pct = closure["disposition_rate"] * 100

    kpis = f"""
<header class="hero">
  <div class="hero-top">
    <div class="brand"><span class="dot"></span> Data Governance in Action</div>
    <div class="meta">数据截止 {q['as_of']}<br>生成 {q['generated_at']}</div>
  </div>
  <h1>雄安新区市场主体服务<br><em>数据治理驾驶舱</em></h1>
  <p class="lede">以市场主体登记、信用评价、企业诉求三类数据为对象，把元数据、数据标准、分类分级、质量规则、数据血缘与资产登记串成一条可运行、可验收的治理闭环。每一个数字都能追溯到脚本、配置与问题台账。</p>
  <div class="chips">
    <span>纳管 <b>{before['tables']}</b> 张表 / <b>{before['rows']:,}</b> 条记录</span>
    <span><b>{before['rules']}</b> 条质量规则 · 6 个维度</span>
    <span>个人信息字段 <b>{cls_sum.get('personal_info_fields', 0)}</b> 个</span>
    <span>数据资产 <b>{assets.get('summary', {}).get('assets', 0)}</b> 项</span>
    <span>字段级血缘 <b>{lineage.get('summary', {}).get('field_edges', 0)}</b> 条</span>
  </div>
</header>
<section class="kpis">
  <div class="kpi dark"><div class="label">综合质量健康度</div><div class="value">{before['overall_health']:.1f} <small>→</small> {after['overall_health']:.1f}</div><div class="sub">提升 +{delta:.1f} 分 · 记录级口径</div></div>
  <div class="kpi"><div class="label">规则达标率</div><div class="value">{before['rule_pass_rate']*100:.1f}<small>% → </small>{after['rule_pass_rate']*100:.1f}<small>%</small></div><div class="sub">{after['passed_rules']} / {after['rules']} 条规则达标</div></div>
  <div class="kpi"><div class="label">问题自动修复率</div><div class="value">{fixed_pct:.1f}<small>%</small></div><div class="sub">{closure['fixed']:,} / {total_issues:,} 条复检通过</div></div>
  <div class="kpi"><div class="label">问题处置率</div><div class="value">{disposition_pct:.1f}<small>%</small></div><div class="sub">修复 + 隔离 + 观察 · 待整改 {closure['open']:,} 条</div></div>
  <div class="kpi"><div class="label">数据可用率</div><div class="value">{cleaning.get('availability', 0)*100:.1f}<small>%</small></div><div class="sub">隔离 {cleaning.get('total_quarantined', 0):,} 条 · 单独披露</div></div>
  <div class="kpi"><div class="label">数据资产登记</div><div class="value">{assets.get('summary', {}).get('assets', 0)}<small> 项</small></div><div class="sub">完整率 {assets.get('summary', {}).get('completeness', 0)*100:.0f}% · 全部有 Owner</div></div>
</section>
"""

    repair_labels = {
        "phone:normalized": "手机号格式归一",
        "status:mapped": "经营状态同义词归一",
        "company_name:cleaned": "企业名称清洗",
        "credit_level:recalculated": "信用等级按评分重算",
        "district:corrected": "按住所修正行政区划",
        "email:invalid_nulled": "非法邮箱置空",
        "industry:mapped": "行业名称映射代码",
        "case_type:mapped": "诉求类型归一",
        "status:reopened": "办结时间倒挂状态回退",
        "satisfaction:range_nulled": "越界满意度置空",
    }
    repair_items = sorted(cleaning.get("repairs", {}).items(), key=lambda kv: -kv[1])[:5]
    repair_max = max([v for _, v in repair_items] + [1])
    repair_bars = '<div class="repairs"><div class="r-title">主要治理动作（记录数）</div>'
    for code, count in repair_items:
        label = repair_labels.get(code, code)
        repair_bars += f'<div class="bar-row"><div class="name">{html.escape(label)}</div><div class="track"><div class="fill" style="width:{count / repair_max * 100:.1f}%"></div></div><div class="val">{count}</div></div>'
    repair_bars += '</div>'
    table_rows = ""
    for table, item in q["before"]["tables"].items():
        after_item = q["after"]["tables"][table]
        table_rows += f"""
        <div class="bar-row"><div class="name">{html.escape(table)}</div>
          <div class="track"><div class="ghost" style="width:{item['health']:.1f}%"></div><div class="fill" style="width:{after_item['health']:.1f}%"></div></div>
          <div class="val">{after_item['health']:.1f}</div></div>"""
    scorecard = f"""
    <section class="grid">
      <div class="card">
        <div class="card-head"><h2>质量：治理前后</h2><span class="tag">记录级健康度</span></div>
        <div class="hint">表健康度 = 100 ×（1 − 存在任一质量问题的主键数 ÷ 记录总数），避免用问题条数重复扣分，也不靠删数据刷分。</div>
        <div class="big-row"><div class="big teal">{after['overall_health']:.1f}<small> / 100</small></div><span class="delta">+{delta:.1f}</span></div>
        {table_rows}
        <div class="mini-legend"><span><i style="background:#cbd5e1"></i>治理前</span><span><i style="background:linear-gradient(90deg,#0f766e,#2dd4bf)"></i>治理后</span><span>权重：市场主体 0.5 / 信用 0.3 / 诉求 0.2</span></div>
        <div class="note">治理后仍有 {closure['open']:,} 条待整改、{closure['new_after']:,} 条治理后新发现：集中在联系电话缺失、更新时间滞后、评级机构缺失等需要回源补录的问题，未通过删除数据掩盖。</div>
        {repair_bars}
      </div>
      <div class="card">
        <div class="card-head"><h2>六维质量画像</h2><span class="tag">0—100</span></div>
        <div class="hint">完整性、准确性、一致性、唯一性、有效性、及时性六个维度的加权结果。</div>
        <div class="radar-wrap">{radar_svg(before['dimensions'], after['dimensions'])}</div>
        <div class="legend"><span><i style="background:#94a3b8"></i>治理前</span><span><i style="background:#0f766e"></i>治理后</span></div>
      </div>
    </section>
"""

    status_tiles = f"""
      <div class="status-grid">
        <div class="status fixed"><div class="n">{closure['fixed']:,}</div><div class="t">已修复 · 复检通过</div></div>
        <div class="status iso"><div class="n">{closure['quarantined']:,}</div><div class="t">已隔离 · 待人工</div></div>
        <div class="status open"><div class="n">{closure['open']:,}</div><div class="t">待整改 · 已派单</div></div>
        <div class="status obs"><div class="n">{closure['observe']:,}</div><div class="t">观察项 · 容差内</div></div>
      </div>"""
    total_stack = max(1, closure['fixed'] + closure['quarantined'] + closure['open'] + closure['observe'] + closure['new_after'])
    stack = f"""
      <div class="stack">
        <span style="width:{closure['fixed']/total_stack*100:.2f}%;background:#0f766e"></span>
        <span style="width:{closure['quarantined']/total_stack*100:.2f}%;background:#d97706"></span>
        <span style="width:{closure['open']/total_stack*100:.2f}%;background:#b91c1c"></span>
        <span style="width:{closure['observe']/total_stack*100:.2f}%;background:#0369a1"></span>
        <span style="width:{closure['new_after']/total_stack*100:.2f}%;background:#cbd5e1"></span>
      </div>
      <div class="stack-note">处置链路：规则复检 → 自动修复 → 无法修复转隔离 → 派发工单 → 下月复评。观察项是容差内、纳入监控的记录；验收以“同一规则 + 同一主键”逐条比对，不以报表变绿为准。</div>"""
    top_rules = ""
    for rule in sorted(q["before_rules"], key=lambda r: (-r["failed"], r["id"]))[:6]:
        top_rules += f"""
        <tr><td><b>{rule['id']}</b><br><span style="color:#94a3b8">{html.escape(rule['name'])}</span></td>
        <td>{status_pill(rule['severity'], 'high' if rule['severity']=='高' else 'mid' if rule['severity']=='中' else 'low')}</td>
        <td class="num">{rule['failed']:,}</td><td class="num">{rule['rate']*100:.2f}%</td>
        <td>{html.escape(rule['owner'])}</td></tr>"""
    closure_card = f"""
    <section class="grid">
      <div class="card">
        <div class="card-head"><h2>问题闭环：从发现到验收</h2><span class="tag">同一规则复检</span></div>
        <div class="hint">治理前问题 {total_issues:,} 条，按“规则 + 主键”逐条比对治理结果，而不是只比较总分。</div>
        {status_tiles}
        {stack}
        <table><thead><tr><th>TOP 规则</th><th>级别</th><th class="num">违规</th><th class="num">违规率</th><th>Owner</th></tr></thead><tbody>{top_rules}</tbody></table>
      </div>
      <div class="card">
        <div class="card-head"><h2>规则有效性验证</h2><span class="tag">注入缺陷回放</span></div>
        <div class="hint">造数阶段向 3 张表注入 {effective.get('defect_types', 0)} 类缺陷；用规则检出结果与缺陷清单逐类比对，证明规则“真的能发现问题”。</div>
        <div class="big-row"><div class="big">{effective.get('recall', 0)*100:.1f}<small>% 总检出率</small></div><span class="delta">{effective.get('covered_types', 0)} / {effective.get('defect_types', 0)} 类覆盖</span></div>
        <table><thead><tr><th>缺陷类型</th><th class="num">注入</th><th class="num">检出</th><th class="num">检出率</th></tr></thead><tbody>
        {''.join(f"<tr><td>{html.escape(i['defect_type'])}</td><td class='num'>{i['injected']}</td><td class='num'>{i['detected']}</td><td class='num'>{i['recall']*100:.0f}%</td></tr>" for i in q.get('effectiveness', {}).get('items', [])[:7])}
        </tbody></table>
        <div class="note">未覆盖：企业名称截断等语义错误仅靠格式规则无法识别，已列入人工抽检，不假装 100% 覆盖。</div>
      </div>
    </section>
"""

    level_max = max(list(cls_sum.get("level_counts", {}).values()) + [1])
    level_bars = ""
    for level in ("L1", "L2", "L3", "L4"):
        count = cls_sum.get("level_counts", {}).get(level, 0)
        level_bars += f"""
        <div class="bar-row"><div class="name">{level} {"公开" if level=="L1" else "内部" if level=="L2" else "敏感" if level=="L3" else "核心"}</div>
        <div class="track"><div class="fill" style="width:{count/level_max*100:.1f}%;background:{'#0ea5e9' if level=='L1' else '#0f766e' if level=='L2' else '#d97706' if level=='L3' else '#b91c1c'}"></div></div>
        <div class="val">{count}</div></div>"""
    scan_rows = ""
    for det_id, item in scan.get("by_detector", {}).items():
        scan_rows += f"""
        <tr><td>{html.escape(item['name'])}<br><span style="color:#94a3b8">{det_id}</span></td>
        <td>{status_pill(item['level'], 'high' if item['level']=='L4' else 'mid')}</td>
        <td class="num">{item['rows']}</td><td class="num">{item['matches']}</td>
        <td class="num">{item['recall']*100:.0f}%</td></tr>"""
    classification_card = f"""
    <section class="grid">
      <div class="card">
        <div class="card-head"><h2>分类分级与个人信息保护</h2><span class="tag">字段级 + 内容级</span></div>
        <div class="hint">按《数据安全法》《个人信息保护法》与 GB/T 43697-2024 分级；正文再做内容级识别，避免“字段不分级就以为安全”。</div>
        {level_bars}
        <div class="mini-legend"><span>分类分级覆盖 {cls_sum.get('fields', 0)} 个字段 · 覆盖率 {cls_sum.get('coverage', 0)*100:.0f}%</span><span>L3/L4 字段 {cls_sum.get('level_counts', {}).get('L3', 0) + cls_sum.get('level_counts', {}).get('L4', 0)} 个</span></div>
        <table class="scan-table" style="margin-top:10px"><thead><tr><th>内容识别器</th><th>级别</th><th class="num">命中行</th><th class="num">次数</th><th class="num">检出率</th></tr></thead><tbody>{scan_rows}</tbody></table>
        <div class="note">脱敏共享文件 {len(sharing.get('exports', []))} 个，个人信息残留检测 <b>{sharing.get('residual_total', 0)}</b> 处（目标 0）。</div>
      </div>
      <div class="card">
        <div class="card-head"><h2>核心指标</h2><span class="tag">DWD 层执行</span></div>
        <div class="hint">指标口径、SQL 与看板同源，避免“报表一套、口径一套”。</div>
        <div class="metric-grid">
        {''.join(f"<div class='metric'><div class='m-name'>{html.escape(m['name'])}</div><div class='m-val'>{'-' if m['value'] is None else format(m['value'], ',.2f') if isinstance(m['value'], float) else format(m['value'], ',')}<small> {html.escape(m['unit'])}</small></div><div class='m-owner'>{html.escape(m['owner'])}</div></div>" for m in metrics)}
        </div>
        <div class="note">指标结果来自治理后的 DWD 明细，隔离数据不参与计算，缺失率见质量报告。</div>
      </div>
    </section>
"""

    asset_rows = ""
    for asset in assets.get("assets", []):
        asset_rows += f"""
        <tr><td>{asset['id']}</td><td><b>{html.escape(asset['name'])}</b><br><span style="color:#94a3b8">{html.escape(asset['type'])} · {html.escape(asset['domain'])}</span></td>
        <td>{status_pill(asset['level'], 'high' if asset['level'] in ('L3','L4') else 'low')}</td>
        <td>{html.escape(asset['owner'])}</td><td>{html.escape(asset['sharing'])}</td>
        <td class="num">{'-' if asset['rows'] is None else f"{asset['rows']:,}"}</td>
        <td class="num">{'-' if asset['quality_score'] is None else f"{asset['quality_score']:.1f}"}</td>
        <td class="num">{asset['upstream_count']} / {asset['downstream_count']}</td>
        <td>{status_pill(asset['status'], 'ok' if asset['status']=='在册' else 'warn')}</td></tr>"""
    assets_card = f"""
    <div class="section-title"><h3>数据资产登记</h3><span>Asset Registry</span><div class="line"></div><span>{assets.get('summary', {}).get('assets', 0)} 项 · 完整率 {assets.get('summary', {}).get('completeness', 0)*100:.0f}%</span></div>
    <div class="card">
      <div class="hint">登记要素包括 Owner、Steward、分级、共享属性、更新频率、质量分与血缘上下游；没有 Owner 的资产不允许共享。</div>
      <table class="asset-table"><thead><tr><th>编号</th><th>资产</th><th>级别</th><th>Owner</th><th>共享属性</th><th class="num">行数</th><th class="num">质量分</th><th class="num">上游/下游</th><th>状态</th></tr></thead><tbody>{asset_rows}</tbody></table>
    </div>
"""

    lineage_card = f"""
    <div class="section-title"><h3>数据血缘</h3><span>Lineage</span><div class="line"></div><span>{lineage.get('summary', {}).get('nodes', 0)} 节点 · {lineage.get('summary', {}).get('field_edges', 0)} 条字段级映射</span></div>
    <div class="card">
      <div class="hint">从源系统到贴源、明细、指标与共享接口的加工路径；字段级映射由转换配置自动生成，可用于变更影响分析。</div>
      <div class="lineage-wrap">{lineage_svg(lineage)}</div>
    </div>
"""

    issue_rows = ""
    issue_card = f"""
    <div class="section-title"><h3>问题整改台账</h3><span>Issue Register</span><div class="line"></div><span>全量 {len(ctx.get('issues', [])):,} 条 · 含 Owner / SLA / 整改建议</span></div>
    <div class="card">
      <div class="hint">可按状态、严重度和关键词筛选。每条问题都能定位到表、字段与记录主键，并带整改建议和截止日期。</div>
      <div class="issue-tools">
        <button class="btn active" data-status="全部">全部</button>
        <button class="btn" data-status="待整改">待整改</button>
        <button class="btn" data-status="已修复">已修复</button>
        <button class="btn" data-status="已隔离">已隔离</button>
        <button class="btn" data-status="观察项">观察项</button>
        <span style="width:10px"></span>
        <button class="btn active" data-sev="全部">全部级别</button>
        <button class="btn" data-sev="高">高</button>
        <button class="btn" data-sev="中">中</button>
        <button class="btn" data-sev="低">低</button>
        <input id="issue-search" class="search" placeholder="搜索规则 / 表 / Owner…">
      </div>
      <div id="issue-count" class="note" style="margin:0 0 8px"></div>
      <div class="table-scroll">
        <table><thead><tr><th>编号</th><th>级别</th><th>状态</th><th>规则</th><th>表 / 字段</th><th>问题定位</th><th>Owner</th><th class="num">截止</th></tr></thead>
        <tbody id="issue-body"><tr><td colspan="9" class="empty">加载中…</td></tr></tbody></table>
      </div>
    </div>
"""

    return kpis + scorecard + closure_card + classification_card + assets_card + lineage_card + issue_card


def _issue_subset(issues: list[dict], limit: int = 320) -> list[dict]:
    # 按规则轮转取样，避免默认视图被同一条规则刷屏，便于展示问题分布
    severity = {"高": 0, "中": 1, "低": 2}
    status_rank = {"待整改": 0, "已隔离": 1, "观察项": 2, "已修复": 3}
    groups: dict[str, list[dict]] = {}
    for issue in issues:
        groups.setdefault(issue.get("rule_id", ""), []).append(issue)
    for items in groups.values():
        items.sort(key=lambda i: (status_rank.get(i.get("status", ""), 9), severity.get(i.get("severity", ""), 9), i.get("issue_id", "")))
    ordered = []
    keys = sorted(groups)
    while len(ordered) < len(issues):
        progressed = False
        for key in keys:
            if groups[key]:
                ordered.append(groups[key].pop(0))
                progressed = True
                if len(ordered) >= len(issues):
                    break
        if not progressed:
            break
    return [
        {
            "issue_id": i.get("issue_id", ""),
            "rule_id": i.get("rule_id", ""),
            "rule_name": i.get("rule_name", ""),
            "table": i.get("table", ""),
            "field": i.get("field", ""),
            "severity": i.get("severity", ""),
            "status": i.get("status", ""),
            "evidence": i.get("evidence", ""),
            "owner": i.get("owner", ""),
            "due_date": i.get("due_date", ""),
        }
        for i in ordered[:limit]
    ]


def build(ctx: dict) -> str:
    data = {
        "issues": _issue_subset(ctx.get("issues", [])),
        "quality": {
            "before": ctx.get("quality", {}).get("before", {}).get("summary", {}),
            "after": ctx.get("quality", {}).get("after", {}).get("summary", {}),
        },
    }
    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return (
        HTML.replace("%%CSS%%", CSS)
        .replace("%%BODY%%", build_body(ctx))
        .replace("%%DATA%%", data_json)
        .replace("%%JS%%", JS)
        .replace("%%REPO%%", REPO_URL)
    )


def run(ctx: dict) -> str:
    html_text = build(ctx)
    write_text(REPORT_DIR / "dashboard.html", html_text)
    write_text(REPORT_DIR / ".." / "docs" / "index.html", html_text)
    return html_text
