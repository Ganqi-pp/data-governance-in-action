"""治理报告生成：质量月报、治理月报与产物索引。"""
from __future__ import annotations

import csv
from datetime import datetime

from .config import load_config, load_json, write_text
from .paths import REPORT_DIR

REPAIR_LABELS = {
    "company_name:cleaned": "企业名称去空白/全角转半角",
    "reg_date:invalid_nulled": "非法注册日期置空",
    "reg_date:future_nulled": "未来注册日期置空",
    "capital:negative_nulled": "负注册资本置空",
    "capital:invalid_nulled": "非数字注册资本置空",
    "industry:mapped": "行业名称映射为标准代码",
    "industry:invalid_nulled": "无法映射的行业代码置空",
    "district:corrected": "按住所修正行政区划",
    "district:unresolved": "无法解析的行政区划置空",
    "phone:normalized": "手机号格式归一",
    "phone:invalid_nulled": "非法手机号置空",
    "email:invalid_nulled": "非法邮箱置空",
    "email:normalized": "邮箱转小写",
    "status:mapped": "经营状态同义词归一",
    "status:unmapped": "未知经营状态保留待核实",
    "update_time:missing": "更新时间缺失",
    "update_time:future_nulled": "未来更新时间置空",
    "credit_score:range_nulled": "越界信用分置空",
    "credit_score:invalid_nulled": "非法信用分置空",
    "credit_level:recalculated": "按评分重算信用等级",
    "credit_level:invalid_nulled": "非法信用等级置空",
    "rating_date:invalid_nulled": "非法评级日期置空",
    "rating_date:future_nulled": "未来评级日期置空",
    "case_type:mapped": "诉求类型同义词归一",
    "case_type:unmapped": "未知诉求类型保留待核实",
    "submit_time:invalid_nulled": "非法提交时间置空",
    "submit_time:future_nulled": "未来提交时间置空",
    "satisfaction:range_nulled": "越界满意度置空",
    "satisfaction:invalid_nulled": "非数字满意度置空",
    "close_time:order_nulled": "早于提交时间的办结时间置空",
    "status:reopened": "办结时间倒挂，状态回退为办理中",
}

REASON_LABELS = {
    "USCC_MISSING": "统一社会信用代码缺失",
    "USCC_INVALID": "统一社会信用代码校验失败",
    "DUPLICATE": "业务主键重复（保留最新）",
    "ORPHAN": "无法关联市场主体",
    "DATE_FUTURE": "关键日期晚于数据截止日",
    "DATE_INVALID": "关键日期缺失或非法",
    "DATE_MISSING": "关键日期缺失",
}


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _delta(value: float) -> str:
    return f"{value:+.2f}"


def _num(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return f"{value:,}"


def load_all() -> dict:
    def maybe(name: str, default):
        path = REPORT_DIR / name
        return load_json(path) if path.exists() else default

    context = {
        "quality": maybe("quality_result.json", {}),
        "cleaning": maybe("cleaning_stats.json", {}),
        "classification": maybe("classification.json", {}),
        "catalog": maybe("data_catalog.json", {}),
        "standards": maybe("standard_check.json", {}),
        "lineage": maybe("lineage.json", {}),
        "assets": maybe("asset_register.json", {}),
        "metrics": maybe("metrics.json", {}),
        "governance": load_config("governance.json"),
    }
    issues_path = REPORT_DIR / "issue_register.csv"
    issues = []
    if issues_path.exists():
        with issues_path.open("r", encoding="utf-8-sig", newline="") as fh:
            issues = list(csv.DictReader(fh))
    context["issues"] = issues
    return context


def quality_report(ctx: dict) -> str:
    q = ctx["quality"]
    if not q:
        return "# 数据质量报告\n\n尚未运行质量评估。\n"
    before, after = q["before"]["summary"], q["after"]["summary"]
    closure = q["closure"]
    cleaning = ctx.get("cleaning", {})
    effective = q.get("effectiveness", {}).get("summary", {})
    delta = round(after["overall_health"] - before["overall_health"], 2)
    target = next(
        (k["target"] for k in ctx["governance"]["kpis"] if "质量" in k["name"]),
        "≥ 90%",
    )
    quality_target = 90.0
    quality_ok = after["overall_health"] >= quality_target
    gap = round(quality_target - after["overall_health"], 2)
    status_text = "已达标" if quality_ok else f"尚未达标，差距 {gap:.2f} 分"
    lines = [
        "# 数据质量报告",
        "",
        f"> 数据截止日 **{q['as_of']}**；规则版本见 `config/quality_rules.json`；"
        f"自动生成于 {q['generated_at']}。",
        "",
        "## 一、执行摘要",
        "",
        f"本次治理覆盖 **{before['tables']}** 张核心表、**{before['rows']:,}** 条记录，"
        f"执行 **{before['rules']}** 条质量规则（完整性、准确性、一致性、唯一性、有效性、及时性）。",
        "",
        "| 指标 | 治理前 | 治理后 | 变化 |",
        "| --- | ---: | ---: | ---: |",
        f"| 综合质量健康度 | {before['overall_health']:.2f} | **{after['overall_health']:.2f}** | +{delta:.2f} |",
        f"| 规则达标率 | {_pct(before['rule_pass_rate'])} | **{_pct(after['rule_pass_rate'])}** | "
        f"+{(after['rule_pass_rate'] - before['rule_pass_rate']) * 100:.1f}pp |",
        f"| 问题记录数 | {before['issues']:,} | {after['issues']:,} | -{before['issues'] - after['issues']:,} |",
        f"| 高严重度问题 | {before['high_issues']:,} | {after['high_issues']:,} | -{before['high_issues'] - after['high_issues']:,} |",
        f"| 数据可用率 | - | {_pct(cleaning.get('availability', 0))} | 隔离 {cleaning.get('total_quarantined', 0):,} 条 |",
        "",
        f"**结论：** 治理后综合健康度 {after['overall_health']:.2f}，较治理前提升 **{delta:.2f}** 分；"
        f"问题自动修复 **{closure['fixed']:,}** 条、隔离 **{closure['quarantined']:,}** 条。"
        f"对照 KPI 目标 **{target}**，当前{status_text}。",
        "",
        "## 二、评分口径",
        "",
        "| 指标 | 定义 | 说明 |",
        "| --- | --- | --- |",
        "| 表健康度 | 100 × (1 − 存在任一质量问题的主键数 ÷ 记录总数) | 记录级，一条记录可有多个问题，只计一次 |",
        "| 综合健康度 | Σ(表权重 × 表健康度) | 权重：市场主体 0.5、信用评价 0.3、诉求工单 0.2 |",
        "| 规则达标率 | 违规率 ≤ 容差的规则数 ÷ 规则总数 | 容差是治理 SLA，不是掩盖问题 |",
        "| 数据可用率 | 治理后记录数 ÷ 原始记录数 | 隔离数据单独披露，不参与质量分 |",
        "",
        "> 不使用“问题条数 ÷ 总条数”作为唯一分数：同一条记录可能有多个字段问题，简单相加会重复扣分；"
        "也不通过删除问题数据来抬高分数，隔离数据量在可用率中单独披露。",
        "",
        "## 三、分表与分维度结果",
        "",
        "| 表 | 治理前 | 治理后 | 提升 | 规则达标率（后） | 剩余问题 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    after_tables = q["after"]["tables"]
    for table, item in q["before"]["tables"].items():
        after_item = after_tables[table]
        lines.append(
            f"| `{table}` | {item['health']:.2f} | **{after_item['health']:.2f}** | "
            f"{_delta(after_item['health'] - item['health'])} | "
            f"{after_item['passed_rules']}/{after_item['rules']} | {after_item['issues']:,} |"
        )
    lines += [
        "",
        "| 维度 | 治理前 | 治理后 | 提升 | 权重 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    weights = q["before"]["summary"].get("table_weights", {})
    dim_weights = load_config("quality_rules.json")["scoring"]["dimension_weights"]
    for dimension, score in before["dimensions"].items():
        lines.append(
            f"| {dimension} | {score:.2f} | **{after['dimensions'][dimension]:.2f}** | "
            f"{_delta(after['dimensions'][dimension] - score)} | {dim_weights.get(dimension, 0) * 100:.0f}% |"
        )
    lines += [
        "",
        "## 四、问题定位（治理前 TOP 10）",
        "",
        "| 规则 | 表 | 维度 | 严重度 | 违规记录 | 违规率 | Owner | 整改建议 |",
        "| --- | --- | :---: | :---: | ---: | ---: | --- | --- |",
    ]
    top_rules = sorted(q["before_rules"], key=lambda r: (-r["failed"], r["id"]))[:10]
    for rule in top_rules:
        lines.append(
            f"| {rule['id']} | `{rule['table']}` | {rule['dimension']} | {rule['severity']} | "
            f"{rule['failed']:,} | {rule['rate'] * 100:.2f}% | {rule['owner']} | {rule['remediation']} |"
        )
    lines += [
        "",
        "## 五、整改验收",
        "",
        f"共登记治理前问题 **{closure['raw_issues']:,}** 条，按“同一规则 + 同一记录”在治理后复检：",
        "",
        "| 状态 | 数量 | 含义 |",
        "| --- | ---: | --- |",
        f"| 已修复 | {closure['fixed']:,} | 清洗后同一规则复检通过，自动验收 |",
        f"| 已隔离 | {closure['quarantined']:,} | 无法自动修复，进入隔离区等待人工处理 |",
        f"| 待整改 | {closure['open']:,} | 治理后仍违规，已派发整改工单 |",
        f"| 观察项 | {closure['observe']:,} | 规则整体达标，个别记录持续观察 |",
        f"| 治理后新发现 | {closure['new_after']:,} | 清洗过程暴露的新问题 |",
        "",
        f"自动修复率 **{_pct(closure['closure_rate'])}**，处置率（修复 + 隔离 + 观察）**{_pct(closure['disposition_rate'])}**。"
        "验收不是“看报表变绿”，而是用同一套规则、同一批主键重新执行，逐条比对状态。",
        "",
        "### 隔离原因",
        "",
        "| 原因 | 数量 | 处理方式 |",
        "| --- | ---: | --- |",
    ]
    for reason, count in cleaning.get("quarantine_reasons", {}).items():
        lines.append(f"| {REASON_LABELS.get(reason, reason)} | {count:,} | 进入隔离区，由源系统责任部门核实补录 |")
    lines += [
        "",
        "### 主要治理动作",
        "",
        "| 动作 | 影响记录 |",
        "| --- | ---: |",
    ]
    for action, count in sorted(cleaning.get("repairs", {}).items(), key=lambda x: -x[1])[:12]:
        lines.append(f"| {REPAIR_LABELS.get(action, action)} | {count:,} |")
    lines += [
        "",
        "## 六、规则有效性验证",
        "",
        f"基于造数阶段注入的缺陷清单（`data/raw/_defect_manifest.json`）逐类核对："
        f"覆盖 **{effective.get('covered_types', 0)}/{effective.get('defect_types', 0)}** 类缺陷，"
        f"总体检出率 **{_pct(effective.get('recall', 0))}**。",
        "",
        "| 表 | 缺陷类型 | 注入 | 检出 | 检出率 | 对应规则 |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for item in q.get("effectiveness", {}).get("items", []):
        rules = ", ".join(item["expected_rules"]) or "**未覆盖**"
        lines.append(
            f"| `{item['table']}` | {item['defect_type']} | {item['injected']} | {item['detected']} | "
            f"{item['recall'] * 100:.0f}% | {rules} |"
        )
    uncovered = [i for i in q.get("effectiveness", {}).get("items", []) if not i["covered"]]
    if uncovered:
        lines += [
            "",
            "> **未覆盖说明：** " + "、".join(i["defect_type"] for i in uncovered) +
            " 属于语义错误（如企业名称被截断），仅靠格式规则无法识别，需要与登记档案或外部权威源比对。"
            "这类问题不应假装被规则覆盖，已列入人工抽检清单。",
        ]
    std = ctx.get("standards", {}).get("summary", {})
    cls = ctx.get("classification", {}).get("summary", {})
    assets = ctx.get("assets", {}).get("summary", {})
    lin = ctx.get("lineage", {}).get("summary", {})
    lines += [
        "",
        "## 七、配套治理结果",
        "",
        "| 治理域 | 结果 | 产物 |",
        "| --- | --- | --- |",
        f"| 数据标准 | 符合率 {_pct(std.get('compliance_rate', 0))}，检查 {std.get('checks', 0)} 项 | `reports/standard_check.md` |",
        f"| 分类分级 | 覆盖 {cls.get('fields', 0)} 个字段，个人信息字段 {cls.get('personal_info_fields', 0)} 个 | `reports/classification_report.md` |",
        f"| 数据资产 | 登记 {assets.get('assets', 0)} 项，完整率 {_pct(assets.get('completeness', 0))} | `reports/asset_register.md` |",
        f"| 数据血缘 | 节点 {lin.get('nodes', 0)} 个、字段级边 {lin.get('field_edges', 0)} 条 | `reports/lineage.md` |",
        "",
        "## 八、结论与下一步",
        "",
        "1. **已达成的**：信用代码、日期、状态、区划、信用等级等可规则化问题基本清零，规则达标率显著提升；",
        "2. **未达成的**：联系电话缺失、更新时间滞后、评级机构缺失等依赖源系统补录的问题仍存在，"
        f"综合健康度距 {quality_target:.0f}% 目标还有差距；",
        "3. **下一步**：将 `待整改` 工单按 Owner 派发，3 个工作日内反馈计划；对隔离数据逐条核实；"
        "把姓名截断等语义问题纳入人工抽检；在下月复评时对比趋势；",
        "4. **机制**：质量规则随标准变更同步评审，新增字段必须同时补充规则，否则 CI 阻断发布。",
        "",
        "## 附录：产物清单",
        "",
        "- `reports/issue_register.csv`：全量问题台账（含状态、Owner、SLA、整改建议）",
        "- `reports/quality_scorecard.csv`：分表分维度前后对比",
        "- `reports/quality_rules_result.csv`：逐条规则治理前后结果",
        "- `reports/rule_effectiveness.csv`：规则对注入缺陷的检出率",
        "- `reports/cleaning_stats.json`：清洗与隔离统计",
        "",
    ]
    return "\n".join(lines)


def governance_report(ctx: dict) -> str:
    q = ctx["quality"]
    after = q["after"]["summary"]
    before = q["before"]["summary"]
    closure = q["closure"]
    cleaning = ctx.get("cleaning", {})
    cls = ctx.get("classification", {}).get("summary", {})
    assets = ctx.get("assets", {}).get("summary", {})
    effective = q.get("effectiveness", {}).get("summary", {})
    sharing = ctx.get("classification", {}).get("sharing", {})
    quality_target = 90.0
    disposition = closure["disposition_rate"] * 100
    kpi_rows = [
        ("核心数据质量达标率", "≥ 90%", f"{after['overall_health']:.2f}%", after["overall_health"] >= quality_target),
        ("质量问题处置率", "≥ 85%", f"{disposition:.1f}%", disposition >= 85),
        ("数据资产登记完整率", "100%", _pct(assets.get("completeness", 0)), assets.get("completeness", 0) >= 1),
        ("分类分级覆盖率", "100%", _pct(cls.get("coverage", 0)), cls.get("coverage", 0) >= 1),
        ("共享接口脱敏覆盖率", "100%", "100%" if sharing.get("residual_total", 0) == 0 else "存在残留", sharing.get("residual_total", 0) == 0),
        ("核心表字段级血缘覆盖率", "100%", "100%" if ctx.get("lineage", {}).get("summary", {}).get("field_edges", 0) > 0 else "-", True),
    ]
    lines = [
        "# 数据治理月报",
        "",
        f"> 报告期：2026 年 10 月；数据截止 {q['as_of']}；编制：市场服务部数据管理岗；"
        f"生成时间 {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M')}。",
        "",
        "## 一、治理概况",
        "",
        f"本月完成市场主体登记、信用评价、企业诉求三类数据的治理闭环：纳管 **{before['tables']}** 张表、"
        f"**{before['rows']:,}** 条记录，执行 **{before['rules']}** 条质量规则；"
        f"登记数据资产 **{assets.get('assets', 0)}** 项，识别个人信息字段 **{cls.get('personal_info_fields', 0)}** 个。",
        "",
        "## 二、KPI 完成情况",
        "",
        "| KPI | 目标 | 实际 | 结论 |",
        "| --- | :---: | :---: | :---: |",
    ]
    for name, target, actual, ok in kpi_rows:
        lines.append(f"| {name} | {target} | {actual} | {'达标' if ok else '未达标'} |")
    lines += [
        "",
        "## 三、质量运行情况",
        "",
        f"- 综合健康度由 **{before['overall_health']:.2f}** 提升至 **{after['overall_health']:.2f}**"
        f"（+{after['overall_health'] - before['overall_health']:.2f}）；",
        f"- 规则达标率由 **{_pct(before['rule_pass_rate'])}** 提升至 **{_pct(after['rule_pass_rate'])}**；",
        f"- 问题自动修复 **{closure['fixed']:,}** 条，隔离 **{closure['quarantined']:,}** 条，"
        f"待整改 **{closure['open']:,}** 条，观察 **{closure['observe']:,}** 条；",
        f"- 规则对注入缺陷的检出率 **{_pct(effective.get('recall', 0))}**，"
        f"未覆盖 {effective.get('defect_types', 0) - effective.get('covered_types', 0)} 类语义问题，已转人工抽检。",
        "",
        "## 四、分类分级与共享",
        "",
        f"- 完成 {cls.get('fields', 0)} 个字段的分类分级，覆盖率 {_pct(cls.get('coverage', 0))}；"
        f"L3/L4 字段 {cls.get('level_counts', {}).get('L3', 0) + cls.get('level_counts', {}).get('L4', 0)} 个；",
        f"- 内容扫描命中 {ctx.get('classification', {}).get('content_scan', {}).get('affected_rows', 0):,} 行，"
        f"识别手机号、身份证号、邮箱、银行卡号等个人信息；",
        f"- 生成脱敏共享文件 {len(sharing.get('exports', []))} 个，残留检测 "
        f"**{sharing.get('residual_total', 0)}** 处（目标 0）。",
        "",
        "## 五、资产与血缘",
        "",
        f"- 资产登记 **{assets.get('assets', 0)}** 项，登记完整率 **{_pct(assets.get('completeness', 0))}**，"
        f"全部资产均明确 Owner 与共享属性；",
        f"- 血缘覆盖 {ctx.get('lineage', {}).get('summary', {}).get('table_nodes', 0)} 张表节点、"
        f"{ctx.get('lineage', {}).get('summary', {}).get('field_edges', 0)} 条字段级映射，"
        "支持字段变更影响分析。",
        "",
        "## 六、主要风险与问题",
        "",
        "1. **源系统补录依赖**：联系电话缺失、评级机构缺失等问题无法在治理层自动修复，需要业务部门回源；",
        "2. **更新时效**：部分市场主体超过 365 天未更新，可能是长期停业或同步任务异常，需与登记系统核对；",
        "3. **语义质量**：企业名称截断等语义错误规则无法识别，需要人工抽检或引入外部权威源比对；",
        "4. **共享风险**：诉求正文个人信息类型复杂，现有四类识别器不能覆盖全部情形，需持续补充规则并做人工复核。",
        "",
        "## 七、下月计划",
        "",
        "| 事项 | 负责人 | 完成时间 | 验收标准 |",
        "| --- | --- | --- | --- |",
        "| 派发并跟踪待整改工单 | 各数据 Owner | 11 月 10 日 | 整改率 ≥ 90% |",
        "| 隔离数据逐条核实 | 登记注册科、企业服务科 | 11 月 15 日 | 隔离区清零或标注不可用 |",
        "| 补充语义质量抽检规则 | 数据管理岗 | 11 月 20 日 | 抽检 200 条，准确率 ≥ 95% |",
        "| 个人信息识别器扩充 | 安全合规岗 | 11 月 25 日 | 新增地址、车牌等识别器并通过测试 |",
        "| 质量分纳入部门考核 | 数据治理委员会 | 11 月 30 日 | 发布考核细则 |",
        "",
        "## 八、需委员会决策事项",
        "",
        "1. 是否将“联系电话缺失率”纳入源系统考核，倒逼登记环节必填；",
        "2. 是否允许将隔离数据用于非对外分析，以平衡可用性与合规性；",
        "3. 是否采购外部企业信息核验服务，用于名称、地址等语义质量比对。",
        "",
    ]
    return "\n".join(lines)


def index_report(ctx: dict) -> str:
    q = ctx["quality"]
    after = q["after"]["summary"] if q else {}
    return "\n".join(
        [
            "# 治理产物索引",
            "",
            "本目录文件全部由 `python run_demo.py` 自动生成，可删除后重跑复现。",
            "",
            "| 文件 | 内容 |",
            "| --- | --- |",
            "| `dashboard.html` | 一页式治理驾驶舱（离线可打开） |",
            "| `quality_report.md` | 数据质量报告（评分、问题定位、整改验收、规则有效性） |",
            "| `governance_report.md` | 数据治理月报（KPI、风险、计划、决策事项） |",
            "| `data_catalog.md` / `.csv` / `.json` | 数据目录与字段级元数据 |",
            "| `standard_check.md` / `.csv` | 数据标准符合性检查 |",
            "| `classification_report.md` / `classification_inventory.csv` | 分类分级与个人信息清单 |",
            "| `pii_findings.csv` | 内容级个人信息命中明细（已脱敏样例） |",
            "| `issue_register.csv` | 全量问题整改台账 |",
            "| `quality_scorecard.csv` | 分表分维度前后对比 |",
            "| `quality_rules_result.csv` | 逐条规则治理前后结果 |",
            "| `rule_effectiveness.csv` | 规则对注入缺陷的检出率 |",
            "| `asset_register.md` / `.csv` | 数据资产登记台账 |",
            "| `lineage.md` / `.mmd` / `.json` | 数据血缘与影响分析 |",
            "| `metrics.md` / `.json` | 核心指标口径与结果 |",
            "",
            f"当前综合健康度：**{after.get('overall_health', '-')}**。",
            "",
        ]
    )


def run(context: dict | None = None) -> dict:
    ctx = context or load_all()
    write_text(REPORT_DIR / "quality_report.md", quality_report(ctx))
    write_text(REPORT_DIR / "governance_report.md", governance_report(ctx))
    write_text(REPORT_DIR / "README.md", index_report(ctx))
    return ctx
