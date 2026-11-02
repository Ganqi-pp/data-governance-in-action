# -*- coding: utf-8 -*-
"""治理引擎核心逻辑的单元测试。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dgov.cleanse import PHONE_RE, mask_address, mask_email, mask_name, mask_phone  # noqa: E402
from dgov.classify import classify_column  # noqa: E402
from dgov.config import load_json  # noqa: E402
from dgov.standards import _to_snake  # noqa: E402


class TestMasking(unittest.TestCase):
    def test_phone(self):
        self.assertEqual(mask_phone("13812345678"), "138****5678")

    def test_name(self):
        self.assertEqual(mask_name("张伟"), "张*")

    def test_email(self):
        self.assertEqual(mask_email("zhangwei@example.com"), "z***@example.com")

    def test_address(self):
        self.assertEqual(mask_address("河北省", "保定市"), "河北省保定市***")


class TestClassification(unittest.TestCase):
    def test_personal_sensitive(self):
        for column in ("phone", "id_card", "user_phone"):
            self.assertEqual(classify_column(column)["level"], "L4", column)

    def test_personal_general(self):
        self.assertEqual(classify_column("address")["level"], "L3")
        self.assertEqual(classify_column("email")["level"], "L3")

    def test_business(self):
        self.assertEqual(classify_column("pay_amount")["level"], "L2")

    def test_public(self):
        self.assertEqual(classify_column("order_id")["level"], "L1")


class TestStandards(unittest.TestCase):
    def test_snake_case_conversion(self):
        self.assertEqual(_to_snake("campaignName"), "campaign_name")
        self.assertEqual(_to_snake("startTime"), "start_time")

    def test_phone_pattern(self):
        self.assertTrue(PHONE_RE.match("13812345678"))
        self.assertFalse(PHONE_RE.match("1381234567"))


class TestRuleConfig(unittest.TestCase):
    def test_rules_are_valid(self):
        rules = load_json("quality_rules.json")["rules"]
        ids = [r["id"] for r in rules]
        self.assertEqual(len(ids), len(set(ids)), "规则 ID 不能重复")
        allowed = {"unique", "not_null", "enum", "regex", "expression", "referential", "freshness"}
        for rule in rules:
            self.assertIn(rule["type"], allowed, rule["id"])
            self.assertIn(rule["dataset"], {"order", "user", "product"}, rule["id"])
            self.assertIn(rule["severity"], {"high", "medium", "low"}, rule["id"])
            self.assertIn("owner", rule, rule["id"])


if __name__ == "__main__":
    unittest.main()
