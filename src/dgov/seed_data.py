"""生成可复现的雄安新区市场主体服务模拟数据，并注入可核验的缺陷。

设计原则
--------
1. 种子固定、无第三方依赖，任何人 clone 后都能得到完全一致的数据；
2. 每个缺陷都写入 ``_defect_manifest.json``，质量规则检出后可以计算检出率，
   避免"报告里说发现了问题，但无法证明规则真的有效"；
3. 缺陷覆盖完整性、唯一性、有效性、一致性、及时性五个维度，另含内容级个人信息；
4. 模拟数据全部为虚构，企业名称、信用代码、电话、身份证号均不对应真实主体。
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import string
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

from .paths import AS_OF_DEFAULT, RAW_DIR, REFERENCE_DIR, SEED_DEFAULT

# ---------------------------------------------------------------------------
# 基础字典
# ---------------------------------------------------------------------------
USCC_CHARS = "0123456789ABCDEFGHJKLMNPQRTUWXY"  # GB 32100-2015，去掉 I/O/S/V/Z
USCC_WEIGHTS = [1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28]

SURNAMES = list(
    "王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾肖田董袁"
    "潘于蒋蔡余杜叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦付方白邹孟熊秦"
)
GIVEN_NAMES = [
    "伟", "芳", "娜", "敏", "静", "丽", "强", "磊", "军", "洋", "勇", "艳", "杰",
    "娟", "涛", "明", "超", "秀英", "霞", "平", "刚", "桂英", "建国", "文辉",
    "思远", "雨轩", "子涵", "浩然", "嘉怡", "欣怡", "志强", "海燕", "晓东",
    "雅静", "宇航", "梦琪", "俊杰", "晨曦", "嘉诚", "若彤",
]

BRANDS = [
    "安泰", "华信", "恒达", "鑫源", "嘉禾", "中科", "博远", "润泽", "天成", "兴业",
    "宏图", "智联", "新元", "盛邦", "龙腾", "启明", "汇通", "广厦", "金桥", "众合",
    "德胜", "凯旋", "蓝天", "绿洲", "先锋", "远东", "昌盛", "瑞丰", "同创", "优卓",
    "新程", "国泰", "恒信", "中盛", "华创", "天工", "沃土", "云帆", "春晖", "万象",
]

# code, 名称, 企业名中的简称
INDUSTRIES = [
    ("A01", "农业", "农业"),
    ("C13", "农副食品加工业", "食品"),
    ("C26", "化学原料和化学制品制造业", "化工"),
    ("C35", "专用设备制造业", "装备"),
    ("C39", "计算机、通信和其他电子设备制造业", "电子"),
    ("E47", "房屋建筑业", "建筑"),
    ("E50", "建筑装饰、装修和其他建筑业", "装饰"),
    ("F51", "批发业", "商贸"),
    ("F52", "零售业", "零售"),
    ("G54", "道路运输业", "物流"),
    ("G60", "邮政业", "快递"),
    ("I64", "互联网和相关服务", "互联网"),
    ("I65", "软件和信息技术服务业", "科技"),
    ("J66", "货币金融服务", "金融"),
    ("K70", "房地产业", "地产"),
    ("L72", "商务服务业", "商务"),
    ("M73", "研究和试验发展", "研发"),
    ("M74", "专业技术服务业", "技术服务"),
    ("N77", "生态保护和环境治理业", "环保"),
    ("P82", "教育", "教育"),
    ("Q84", "卫生", "医疗"),
    ("R88", "文化艺术业", "文化"),
]

DIVISIONS = [
    ("130000", "河北省", "省", ""),
    ("133100", "雄安新区", "功能区", "130000"),
    ("130629", "容城县", "县", "133100"),
    ("130632", "安新县", "县", "133100"),
    ("130638", "雄县", "县", "133100"),
]

ROADS = [
    "振兴路", "朝阳街", "建设大街", "文化路", "育才路", "和平街", "新华路",
    "迎宾大道", "科技路", "创业大街", "滨河路", "富民路",
]

STATUSES = [
    ("存续", "正常经营", 0.72),
    ("在业", "正常经营", 0.15),
    ("注销", "已注销", 0.07),
    ("吊销", "吊销未注销", 0.04),
    ("迁出", "迁出本辖区", 0.02),
]

CREDIT_AGENCIES = ["河北征信有限公司", "雄安新区公共信用中心", "中诚信河北分公司", "联合信用河北分公司"]
CASE_TYPES = ["登记注册", "税务办理", "社保缴纳", "政策咨询", "融资服务", "市场监管", "其他"]
CASE_STATUSES = ["待受理", "办理中", "已办结", "已回访"]
HANDLING_DEPTS = ["市场服务部", "税务局", "人社局", "行政审批局", "金融办", "综合执法局"]

CONTENT_TEMPLATES = [
    "反映在办理营业执照变更时窗口排队时间较长，希望优化预约流程。",
    "咨询小微企业社保补贴政策，希望明确申报材料和办理时限。",
    "反映企业周边道路施工影响物流通行，建议协调施工时段。",
    "投诉某商户未明码标价，希望核查处理并反馈结果。",
    "咨询高新技术企业认定条件、申报时间及所需材料。",
    "反映留抵退税申请进度较慢，希望查询当前办理节点。",
    "建议增加企业融资对接活动频次，帮助小微企业获得信贷支持。",
    "反映园区停车位不足，希望协调增加临时停车区域。",
    "咨询医疗器械经营许可变更流程，希望提供线上办理指引。",
    "反映社保增减员线上系统偶发卡顿，建议优化系统稳定性。",
]

PII_SNIPPETS = {
    "PII-MOBILE": [
        "，联系电话13812345678，请工作日联系。",
        "，手机号15900001111，方便时回电。",
        "，可联系18612340000。",
    ],
    "PII-IDCARD": [
        "，经办人身份证号130629199001011234，用于身份核验。",
        "，法定代表人身份证号130632198512120028。",
    ],
    "PII-EMAIL": [
        "，邮箱zhangsan@example.com，请发送材料清单。",
        "，联系邮箱qiye-service@example.org。",
    ],
    "PII-BANKCARD": [
        "，退款账户6222020200001234567，请核对。",
        "，收款账号6217000010001234568。",
    ],
}


# ---------------------------------------------------------------------------
# 统一社会信用代码
# ---------------------------------------------------------------------------
def uscc_check_char(body17: str) -> str:
    total = sum(USCC_CHARS.index(ch) * w for ch, w in zip(body17, USCC_WEIGHTS))
    remainder = total % 31
    return USCC_CHARS[(31 - remainder) % 31]


def is_valid_uscc(code: str) -> bool:
    if not code or len(code) != 18:
        return False
    if any(ch not in USCC_CHARS for ch in code):
        return False
    return uscc_check_char(code[:17]) == code[17]


def make_uscc(rng: random.Random, prefix: str = "91133100") -> str:
    body = prefix + "".join(rng.choice(USCC_CHARS) for _ in range(18 - len(prefix) - 1))
    return body + uscc_check_char(body)


# ---------------------------------------------------------------------------
# 造数工具
# ---------------------------------------------------------------------------
def d(value: date) -> str:
    return value.isoformat()


def random_date(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def weighted_choice(rng: random.Random, items: list[tuple[str, str, float]]) -> str:
    r = rng.random()
    acc = 0.0
    for value, _desc, weight in items:
        acc += weight
        if r <= acc:
            return value
    return items[-1][0]


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------------------
# 参考数据
# ---------------------------------------------------------------------------
def build_reference() -> None:
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(
        REFERENCE_DIR / "administrative_divisions.csv",
        [
            {"code": c, "name": n, "level": lv, "parent_code": p}
            for c, n, lv, p in DIVISIONS
        ],
        ["code", "name", "level", "parent_code"],
    )
    write_csv(
        REFERENCE_DIR / "industry_codes.csv",
        [{"code": c, "name": n, "section": c[0]} for c, n, _ in INDUSTRIES],
        ["code", "name", "section"],
    )
    write_csv(
        REFERENCE_DIR / "market_status_codes.csv",
        [
            {"code": "存续", "name": "存续（在营、开业、在册）"},
            {"code": "在业", "name": "在业"},
            {"code": "注销", "name": "注销"},
            {"code": "吊销", "name": "吊销"},
            {"code": "迁出", "name": "迁出"},
        ],
        ["code", "name"],
    )
    write_csv(
        REFERENCE_DIR / "credit_levels.csv",
        [
            {"code": "A", "name": "信用良好", "score_min": "90", "score_max": "100"},
            {"code": "B", "name": "信用较好", "score_min": "75", "score_max": "89"},
            {"code": "C", "name": "信用一般", "score_min": "60", "score_max": "74"},
            {"code": "D", "name": "信用较差", "score_min": "0", "score_max": "59"},
        ],
        ["code", "name", "score_min", "score_max"],
    )


# ---------------------------------------------------------------------------
# 市场主体登记
# ---------------------------------------------------------------------------
MARKET_FIELDS = [
    "reg_id", "unified_social_credit_code", "company_name", "reg_date",
    "reg_capital_wan", "industry_code", "district_code", "address",
    "legal_person", "contact_phone", "contact_email", "status", "update_time",
]


def build_market_register(rng: random.Random, as_of: date) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    used_names: set[str] = set()
    used_uscc: set[str] = set()
    for i in range(1, 1201):
        district = rng.choices(
            ["133100", "130629", "130632", "130638"], weights=[18, 30, 27, 25]
        )[0]
        div_name = dict((c, n) for c, n, _, _ in DIVISIONS)[district]
        industry_code, _industry_name, short = rng.choice(INDUSTRIES)
        while True:
            name = f"{'雄安' if district == '133100' else div_name[:-1]}{rng.choice(BRANDS)}{short}有限公司"
            if name not in used_names:
                used_names.add(name)
                break
        uscc = make_uscc(rng)
        while uscc in used_uscc:
            uscc = make_uscc(rng)
        used_uscc.add(uscc)
        reg = random_date(rng, date(2005, 1, 1), date(2026, 9, 30))
        capital = round(min(50000, max(1.0, rng.lognormvariate(4.4, 1.15))), 2)
        road = rng.choice(ROADS)
        number = rng.randint(1, 588)
        if district == "133100":
            address = f"河北省雄安新区启动区{road}{number}号"
        else:
            address = f"河北省雄安新区{div_name}{road}{number}号"
        update = max(reg, as_of - timedelta(days=rng.randint(0, 330)))
        rows.append(
            {
                "reg_id": f"REG2026{i:06d}",
                "unified_social_credit_code": uscc,
                "company_name": name,
                "reg_date": d(reg),
                "reg_capital_wan": f"{capital:.2f}",
                "industry_code": industry_code,
                "district_code": district,
                "address": address,
                "legal_person": rng.choice(SURNAMES) + rng.choice(GIVEN_NAMES),
                "contact_phone": "1" + rng.choice("356789") + "".join(str(rng.randint(0, 9)) for _ in range(9)),
                "contact_email": f"qy{i:04d}@{rng.choice(['example.com', 'example.cn', 'mail.example.com'])}",
                "status": weighted_choice(rng, STATUSES),
                "update_time": d(update),
            }
        )

    manifest: list[dict] = []
    used: set[int] = set()

    def pick(count: int) -> list[int]:
        pool = [i for i in range(len(rows)) if i not in used]
        chosen = rng.sample(pool, count)
        used.update(chosen)
        return chosen

    def record(defect_type: str, field: str, keys: list[str], rules: list[str]) -> None:
        manifest.append(
            {"type": defect_type, "field": field, "keys": keys, "expected_rules": rules}
        )

    # 1. 信用代码校验位错误 / 缺失
    idxs = pick(40)
    for i in idxs:
        code = rows[i]["unified_social_credit_code"]
        for candidate in USCC_CHARS:
            broken = code[:17] + candidate
            if not is_valid_uscc(broken):
                rows[i]["unified_social_credit_code"] = broken
                break
    record("USCC_INVALID", "unified_social_credit_code", [rows[i]["reg_id"] for i in idxs], ["DQ-REG-003"])

    idxs = pick(6)
    for i in idxs:
        rows[i]["unified_social_credit_code"] = ""
    record("USCC_MISSING", "unified_social_credit_code", [rows[i]["reg_id"] for i in idxs], ["DQ-REG-001"])

    # 2. 企业名称空白 / 截断（截断为语义错误，当前规则不覆盖）
    idxs = pick(45)
    for i in idxs:
        rows[i]["company_name"] = rng.choice(["  ", "\u3000", " "]) + rows[i]["company_name"]
    record("NAME_WHITESPACE", "company_name", [rows[i]["reg_id"] for i in idxs], ["DQ-REG-004"])

    idxs = pick(12)
    for i in idxs:
        rows[i]["company_name"] = rows[i]["company_name"][:-1]
    record("NAME_TRUNCATED", "company_name", [rows[i]["reg_id"] for i in idxs], [])

    # 3. 联系电话格式 / 缺失
    idxs = pick(70)
    for i in idxs:
        phone = rows[i]["contact_phone"]
        style = rng.choice(["hyphen", "space", "plus86", "fullwidth"])
        if style == "hyphen":
            rows[i]["contact_phone"] = f"{phone[:3]}-{phone[3:7]}-{phone[7:]}"
        elif style == "space":
            rows[i]["contact_phone"] = f"{phone[:3]} {phone[3:7]} {phone[7:]}"
        elif style == "plus86":
            rows[i]["contact_phone"] = f"+86{phone}"
        else:
            rows[i]["contact_phone"] = phone.translate(
                str.maketrans("0123456789", "０１２３４５６７８９")
            )
    record("PHONE_FORMAT", "contact_phone", [rows[i]["reg_id"] for i in idxs], ["DQ-REG-010"])

    idxs = pick(65)
    for i in idxs:
        rows[i]["contact_phone"] = ""
    record("PHONE_MISSING", "contact_phone", [rows[i]["reg_id"] for i in idxs], ["DQ-REG-009"])

    # 4. 邮箱
    idxs = pick(25)
    for i in idxs:
        rows[i]["contact_email"] = rng.choice(["abc@", "abc@qq", "a b@qq.com", "abc.qq.com"])
    record("EMAIL_INVALID", "contact_email", [rows[i]["reg_id"] for i in idxs], ["DQ-REG-011"])

    # 5. 日期
    idxs = pick(12)
    for i in idxs:
        rows[i]["reg_date"] = f"2027-{rng.randint(1, 9):02d}-{rng.randint(1, 28):02d}"
    record("DATE_FUTURE", "reg_date", [rows[i]["reg_id"] for i in idxs], ["DQ-REG-007"])

    idxs = pick(8)
    for i in idxs:
        rows[i]["reg_date"] = rng.choice(["2024/13/40", "2024-02-30", "2024.05.12"])
    record("DATE_INVALID", "reg_date", [rows[i]["reg_id"] for i in idxs], ["DQ-REG-006"])

    # 6. 注册资本
    idxs = pick(6)
    for i in idxs:
        rows[i]["reg_capital_wan"] = "-100.00"
    record("CAPITAL_NEGATIVE", "reg_capital_wan", [rows[i]["reg_id"] for i in idxs], ["DQ-REG-008"])

    # 7. 行业代码：名称代替代码（可映射） / 非法代码（不可映射）
    idxs = pick(32)
    for i in idxs:
        if rng.random() < 0.75:
            rows[i]["industry_code"] = rng.choice(INDUSTRIES)[1]
        else:
            rows[i]["industry_code"] = "Z999"
    record("INDUSTRY_NONSTANDARD", "industry_code", [rows[i]["reg_id"] for i in idxs], ["DQ-REG-012"])

    # 8. 区划代码与地址不一致
    idxs = pick(28)
    for i in idxs:
        other = rng.choice([c for c, _, _, _ in DIVISIONS if c not in ("130000", rows[i]["district_code"])])
        rows[i]["district_code"] = other
    record("DISTRICT_MISMATCH", "district_code", [rows[i]["reg_id"] for i in idxs], ["DQ-REG-014"])

    # 9. 经营状态非标准
    idxs = pick(40)
    synonyms = ["正常", "在营", "开业", "经营中", "存续经营"]
    for pos, i in enumerate(idxs):
        rows[i]["status"] = synonyms[pos % len(synonyms)] if pos < 30 else "状态待核实"
    record("STATUS_NONSTANDARD", "status", [rows[i]["reg_id"] for i in idxs], ["DQ-REG-015"])

    # 10. 更新时间陈旧 / 缺失（只挑注册日期足够早的记录，避免制造“更新早于注册”的假缺陷）
    def old_enough(index: int) -> bool:
        try:
            return date.fromisoformat(rows[index]["reg_date"]) <= as_of - timedelta(days=400)
        except ValueError:
            return False

    pool = [i for i in range(len(rows)) if i not in used and old_enough(i)]
    idxs = rng.sample(pool, 50)
    used.update(idxs)
    for i in idxs:
        rows[i]["update_time"] = d(as_of - timedelta(days=rng.randint(400, 700)))
    record("UPDATE_STALE", "update_time", [rows[i]["reg_id"] for i in idxs], ["DQ-REG-017"])

    idxs = pick(8)
    for i in idxs:
        rows[i]["update_time"] = ""
    record("UPDATE_MISSING", "update_time", [rows[i]["reg_id"] for i in idxs], ["DQ-REG-016"])

    # 11. 法定代表人、地址缺失
    idxs = pick(20)
    for i in idxs:
        rows[i]["legal_person"] = ""
    record("LEGAL_PERSON_MISSING", "legal_person", [rows[i]["reg_id"] for i in idxs], ["DQ-REG-013"])

    idxs = pick(12)
    for i in idxs:
        rows[i]["address"] = ""
    record("ADDRESS_MISSING", "address", [rows[i]["reg_id"] for i in idxs], ["DQ-REG-018"])

    # 12. 重复登记：复制干净记录，更新日期更晚，因此清洗后保留副本
    clean_pool = [i for i in range(len(rows)) if i not in used]
    dup_indices = rng.sample(clean_pool, 40)
    dup_keys: list[str] = []
    for n, i in enumerate(dup_indices, start=1):
        original = rows[i]
        copy = dict(original)
        copy["reg_id"] = f"REG2026DUP{n:04d}"
        copy["update_time"] = d(as_of - timedelta(days=rng.randint(1, 60)))
        rows.append(copy)
        dup_keys.extend([original["reg_id"], copy["reg_id"]])
    record("DUPLICATE_REG", "unified_social_credit_code", dup_keys, ["DQ-REG-002"])

    return rows, manifest


# ---------------------------------------------------------------------------
# 信用评价
# ---------------------------------------------------------------------------
CREDIT_FIELDS = [
    "rating_id", "unified_social_credit_code", "credit_score", "credit_level",
    "rating_date", "rating_agency", "update_time",
]


def build_credit_rating(
    rng: random.Random, as_of: date, market_rows: list[dict]
) -> tuple[list[dict], list[dict]]:
    valid_uscc = [r["unified_social_credit_code"] for r in market_rows if is_valid_uscc(r["unified_social_credit_code"])]
    sampled = rng.sample(valid_uscc, 950)
    rows: list[dict] = []
    for i, uscc in enumerate(sampled, start=1):
        score = rng.randint(55, 100)
        level = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D"
        rating_date = random_date(rng, date(2025, 11, 1), date(2026, 9, 30))
        update = min(as_of, rating_date + timedelta(days=rng.randint(0, 45)))
        rows.append(
            {
                "rating_id": f"CR2026{i:06d}",
                "unified_social_credit_code": uscc,
                "credit_score": str(score),
                "credit_level": level,
                "rating_date": d(rating_date),
                "rating_agency": rng.choice(CREDIT_AGENCIES),
                "update_time": d(update),
            }
        )

    manifest: list[dict] = []
    used: set[int] = set()

    def pick(count: int) -> list[int]:
        pool = [i for i in range(len(rows)) if i not in used]
        chosen = rng.sample(pool, count)
        used.update(chosen)
        return chosen

    def record(defect_type: str, field: str, keys: list[str], rules: list[str]) -> None:
        manifest.append({"type": defect_type, "field": field, "keys": keys, "expected_rules": rules})

    # 关联主体不存在（有效校验位但不在登记库）
    idxs = pick(30)
    existing = set(valid_uscc)
    for i in idxs:
        while True:
            ghost = make_uscc(rng)
            if ghost not in existing:
                break
        rows[i]["unified_social_credit_code"] = ghost
    record("CREDIT_ORPHAN", "unified_social_credit_code", [rows[i]["rating_id"] for i in idxs], ["DQ-CRE-002"])

    # 信用等级非标准
    idxs = pick(22)
    bad_levels = ["aa", "AAAA", "优秀", "A "]
    for pos, i in enumerate(idxs):
        rows[i]["credit_level"] = bad_levels[pos % len(bad_levels)]
    record("CREDIT_LEVEL_INVALID", "credit_level", [rows[i]["rating_id"] for i in idxs], ["DQ-CRE-004"])

    # 分数越界
    idxs = pick(8)
    for pos, i in enumerate(idxs):
        rows[i]["credit_score"] = "105" if pos % 2 == 0 else "-5"
    record("CREDIT_SCORE_RANGE", "credit_score", [rows[i]["rating_id"] for i in idxs], ["DQ-CRE-003"])

    # 评级日期未来
    idxs = pick(6)
    for i in idxs:
        rows[i]["rating_date"] = f"2027-{rng.randint(1, 6):02d}-01"
    record("RATING_DATE_FUTURE", "rating_date", [rows[i]["rating_id"] for i in idxs], ["DQ-CRE-005"])

    # 评级机构缺失
    idxs = pick(18)
    for i in idxs:
        rows[i]["rating_agency"] = ""
    record("AGENCY_MISSING", "rating_agency", [rows[i]["rating_id"] for i in idxs], ["DQ-CRE-006"])

    # 更新时间陈旧
    idxs = pick(25)
    for i in idxs:
        rows[i]["update_time"] = d(as_of - timedelta(days=rng.randint(400, 800)))
    record("UPDATE_STALE", "update_time", [rows[i]["rating_id"] for i in idxs], ["DQ-CRE-007"])

    # 等级与分数不一致（可自动重算）
    idxs = pick(15)
    for i in idxs:
        rows[i]["credit_level"] = "A"
        rows[i]["credit_score"] = str(rng.randint(50, 65))
    record("LEVEL_SCORE_MISMATCH", "credit_level", [rows[i]["rating_id"] for i in idxs], ["DQ-CRE-008"])

    return rows, manifest


# ---------------------------------------------------------------------------
# 企业诉求工单
# ---------------------------------------------------------------------------
CASE_FIELDS = [
    "case_id", "unified_social_credit_code", "case_type", "submit_time", "content",
    "handling_dept", "status", "satisfaction", "close_time",
]


def build_complaint_case(
    rng: random.Random, as_of: date, market_rows: list[dict]
) -> tuple[list[dict], list[dict], list[dict]]:
    valid_uscc = [r["unified_social_credit_code"] for r in market_rows if is_valid_uscc(r["unified_social_credit_code"])]
    rows: list[dict] = []
    for i in range(1, 1501):
        submit = random_date(rng, date(2025, 1, 1), date(2026, 9, 30))
        status = rng.choices(CASE_STATUSES, weights=[8, 17, 65, 10])[0]
        close = ""
        satisfaction = ""
        if status in ("已办结", "已回访"):
            close = d(min(as_of, submit + timedelta(days=rng.randint(1, 30))))
            satisfaction = str(rng.choices([1, 2, 3, 4, 5], weights=[2, 3, 8, 30, 57])[0])
        rows.append(
            {
                "case_id": f"TS2026{i:06d}",
                "unified_social_credit_code": rng.choice(valid_uscc),
                "case_type": rng.choice(CASE_TYPES),
                "submit_time": d(submit),
                "content": rng.choice(CONTENT_TEMPLATES),
                "handling_dept": rng.choice(HANDLING_DEPTS),
                "status": status,
                "satisfaction": satisfaction,
                "close_time": close,
            }
        )

    manifest: list[dict] = []
    pii_manifest: list[dict] = []
    used: set[int] = set()

    def pick(count: int) -> list[int]:
        pool = [i for i in range(len(rows)) if i not in used]
        chosen = rng.sample(pool, count)
        used.update(chosen)
        return chosen

    def record(defect_type: str, field: str, keys: list[str], rules: list[str]) -> None:
        manifest.append({"type": defect_type, "field": field, "keys": keys, "expected_rules": rules})

    # 关联主体不存在
    idxs = pick(35)
    for i in idxs:
        rows[i]["unified_social_credit_code"] = "91133100" + "".join(
            rng.choice(USCC_CHARS) for _ in range(9)
        ) + "0"
    record("CASE_ORPHAN", "unified_social_credit_code", [rows[i]["case_id"] for i in idxs], ["DQ-CASE-002"])

    # 满意度非法
    idxs = pick(28)
    for pos, i in enumerate(idxs):
        rows[i]["satisfaction"] = ["0", "6", "满意", ""][pos % 4]
    record("SATISFACTION_INVALID", "satisfaction", [rows[i]["case_id"] for i in idxs], ["DQ-CASE-005"])

    # 办结时间早于提交时间
    idxs = pick(12)
    for i in idxs:
        submit = date.fromisoformat(rows[i]["submit_time"])
        rows[i]["close_time"] = d(submit - timedelta(days=rng.randint(1, 5)))
        rows[i]["status"] = "已办结"
    record("CLOSE_BEFORE_SUBMIT", "close_time", [rows[i]["case_id"] for i in idxs], ["DQ-CASE-006"])

    # 状态非标准
    idxs = pick(25)
    synonyms = ["处理中", "已完成", "待处理", "已回复"]
    for pos, i in enumerate(idxs):
        rows[i]["status"] = synonyms[pos % len(synonyms)] if pos < 20 else "挂起"
    record("CASE_STATUS_NONSTANDARD", "status", [rows[i]["case_id"] for i in idxs], ["DQ-CASE-004"])

    # 工单类型非标准
    idxs = pick(20)
    for pos, i in enumerate(idxs):
        rows[i]["case_type"] = ["其他问题", "咨询", "投诉建议"][pos % 3]
    record("CASE_TYPE_NONSTANDARD", "case_type", [rows[i]["case_id"] for i in idxs], ["DQ-CASE-003"])

    # 内容缺失
    idxs = pick(12)
    for i in idxs:
        rows[i]["content"] = ""
    record("CONTENT_MISSING", "content", [rows[i]["case_id"] for i in idxs], ["DQ-CASE-001"])

    # 提交时间未来
    idxs = pick(8)
    for i in idxs:
        rows[i]["submit_time"] = "2027-03-15"
    record("SUBMIT_DATE_FUTURE", "submit_time", [rows[i]["case_id"] for i in idxs], ["DQ-CASE-007"])

    # 已办结但缺失办结时间
    idxs = pick(10)
    for i in idxs:
        rows[i]["status"] = "已办结"
        rows[i]["close_time"] = ""
        rows[i]["satisfaction"] = ""
    record("CLOSE_TIME_MISSING", "close_time", [rows[i]["case_id"] for i in idxs], ["DQ-CASE-008"])

    # 内容中的个人信息（用于分类分级内容扫描，不参与质量分）
    idxs = pick(150)
    detectors = ["PII-MOBILE", "PII-IDCARD", "PII-EMAIL", "PII-BANKCARD"]
    for pos, i in enumerate(idxs):
        detector = detectors[pos % len(detectors)] if pos < 100 else rng.choice(detectors)
        rows[i]["content"] = rows[i]["content"].rstrip("。") + rng.choice(PII_SNIPPETS[detector])
        pii_manifest.append(
            {"type": detector, "table": "complaint_case", "field": "content", "key": rows[i]["case_id"]}
        )

    return rows, manifest, pii_manifest


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def generate(as_of_text: str = AS_OF_DEFAULT, seed: int = SEED_DEFAULT) -> dict:
    as_of = date.fromisoformat(as_of_text)
    rng = random.Random(seed)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    build_reference()

    market_rows, market_manifest = build_market_register(rng, as_of)
    rng2 = random.Random(seed + 1)
    credit_rows, credit_manifest = build_credit_rating(rng2, as_of, market_rows)
    rng3 = random.Random(seed + 2)
    case_rows, case_manifest, pii_manifest = build_complaint_case(rng3, as_of, market_rows)

    write_csv(RAW_DIR / "market_register.csv", market_rows, MARKET_FIELDS)
    write_csv(RAW_DIR / "credit_rating.csv", credit_rows, CREDIT_FIELDS)
    write_csv(RAW_DIR / "complaint_case.csv", case_rows, CASE_FIELDS)

    manifest = {
        "seed": seed,
        "as_of": as_of_text,
        "note": "模拟数据，全部为虚构内容；缺陷为脚本按固定种子注入，可用于评估规则检出率。",
        "tables": {
            "market_register": {"rows": len(market_rows), "defects": market_manifest},
            "credit_rating": {"rows": len(credit_rows), "defects": credit_manifest},
            "complaint_case": {"rows": len(case_rows), "defects": case_manifest},
        },
        "pii": {
            "table": "complaint_case",
            "field": "content",
            "injected": len(pii_manifest),
            "items": pii_manifest,
        },
    }
    (RAW_DIR / "_defect_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    (RAW_DIR / "README.md").write_text(
        "# 模拟原始数据说明\n\n"
        "本目录数据由 `python run_demo.py seed` 按固定随机种子生成，**全部为虚构内容**，"
        "不对应任何真实企业或个人。\n\n"
        "| 文件 | 内容 | 行数 |\n| --- | --- | ---: |\n"
        f"| `market_register.csv` | 市场主体登记信息 | {len(market_rows)} |\n"
        f"| `credit_rating.csv` | 市场主体信用评价 | {len(credit_rows)} |\n"
        f"| `complaint_case.csv` | 企业诉求工单（12345） | {len(case_rows)} |\n"
        f"| `_defect_manifest.json` | 注入缺陷清单（用于计算规则检出率） | - |\n\n"
        "缺陷类型、影响行号与对应规则见 `_defect_manifest.json`；质量报告中的"
        "“规则有效性验证”即基于该清单计算。\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="生成雄安新区市场主体服务模拟数据")
    parser.add_argument("--as-of", default=AS_OF_DEFAULT)
    parser.add_argument("--seed", type=int, default=SEED_DEFAULT)
    args = parser.parse_args()
    manifest = generate(args.as_of, args.seed)
    total = sum(t["rows"] for t in manifest["tables"].values())
    print(f"[seed] 已生成 {total} 行模拟数据 -> {RAW_DIR}")


if __name__ == "__main__":
    main()
