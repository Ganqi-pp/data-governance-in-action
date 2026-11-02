# -*- coding: utf-8 -*-
"""数据分类分级：按字段名规则映射敏感级别与脱敏策略。"""
from __future__ import annotations

import re

from .config import load_json

_RULES_CACHE: list[dict] | None = None


def _rules() -> list[dict]:
    global _RULES_CACHE
    if _RULES_CACHE is None:
        _RULES_CACHE = load_json("classification_rules.json")["rules"]
    return _RULES_CACHE


def level_info(level: str) -> dict:
    return load_json("classification_rules.json")["levels"][level]


def classify_column(column: str) -> dict:
    for rule in _rules():
        if re.search(rule["match"], column, flags=re.IGNORECASE):
            info = level_info(rule["level"])
            return {
                "level": rule["level"],
                "level_name": info["name"],
                "category": rule["category"],
                "mask": rule["mask"],
                "control": info["control"],
            }
    return {"level": "L1", "level_name": "公开", "category": "公开数据", "mask": "无需脱敏", "control": "无额外管控"}


def classify_tables(tables: list[dict]) -> dict:
    """为每张表补充最高密级与敏感字段清单。"""
    summary: dict[str, int] = {"L1": 0, "L2": 0, "L3": 0, "L4": 0}
    for table in tables:
        top = "L1"
        sensitive = []
        for col in table["columns"]:
            info = classify_column(col["name"])
            col.update(info)
            summary[info["level"]] += 1
            if info["level"] in ("L3", "L4"):
                sensitive.append(col["name"])
            if info["level"] > top:
                top = info["level"]
        table["level"] = top
        table["level_name"] = level_info(top)["name"]
        table["sensitive_columns"] = sensitive
    return summary


def masked_examples() -> list[dict]:
    """给出典型敏感字段的脱敏前后对照。"""
    return [
        {"field": "手机号", "before": "13812345678", "after": "138****5678", "rule": "保留前 3 位与后 4 位"},
        {"field": "身份证号", "before": "130681199001011234", "after": "130681********1234", "rule": "保留前 6 位与后 4 位"},
        {"field": "收货地址", "before": "河北省保定市建设大街 88 号 3 单元 502", "after": "河北省保定市***", "rule": "仅保留省/市"},
        {"field": "用户姓名", "before": "张伟", "after": "张*", "rule": "保留姓氏"},
        {"field": "邮箱", "before": "zhangwei@example.com", "after": "z***@example.com", "rule": "保留首字母与域名"},
    ]
