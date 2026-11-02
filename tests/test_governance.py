"""单元 + 集成测试。

运行：python -m unittest discover -s tests -v
集成测试依赖 reports/ 下的运行产物；CI 会先执行 python run_demo.py。
"""
from __future__ import annotations

import csv
import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dgov.checks import (  # noqa: E402
    is_valid_email,
    is_valid_uscc,
    mask_address,
    mask_bankcard,
    mask_email,
    mask_idcard,
    mask_name,
    mask_phone,
    normalize_phone,
    parse_date,
    parse_datetime,
    uscc_check_char,
)
from dgov.classify import field_rule  # noqa: E402
from dgov.config import load_config  # noqa: E402
from dgov.paths import DATA_DIR, RAW_DIR, REPORT_DIR  # noqa: E402

REPORTS = REPORT_DIR


class TestChecks(unittest.TestCase):
    def test_uscc_checksum(self):
        body = "91133100" + "ABCDEFGHJ"
        code = body + uscc_check_char(body)
        self.assertTrue(is_valid_uscc(code))
        broken = code[:17] + ("0" if code[17] != "0" else "1")
        self.assertFalse(is_valid_uscc(broken))
        self.assertFalse(is_valid_uscc(""))
        self.assertFalse(is_valid_uscc("91133100ABCDEFGH"))  # 17 位

    def test_phone_normalize(self):
        self.assertEqual(normalize_phone("138-1234-5678"), "13812345678")
        self.assertEqual(normalize_phone("+86 138 1234 5678"), "13812345678")
        self.assertEqual(normalize_phone("１３８１２３４５６７８"), "13812345678")
        self.assertIsNone(normalize_phone("12345"))
        self.assertIsNone(normalize_phone("23812345678"))
        self.assertIsNone(normalize_phone(""))

    def test_email(self):
        self.assertTrue(is_valid_email("a@example.com"))
        self.assertFalse(is_valid_email("a@"))
        self.assertFalse(is_valid_email("a b@example.com"))

    def test_dates(self):
        self.assertEqual(parse_date("2024-05-12"), date(2024, 5, 12))
        self.assertEqual(parse_date("2024/05/12"), date(2024, 5, 12))
        self.assertEqual(parse_date("2024.05.12"), date(2024, 5, 12))
        self.assertEqual(parse_date("20240512"), date(2024, 5, 12))
        self.assertIsNone(parse_date("2024-02-30"))
        self.assertIsNone(parse_date("2024/13/40"))
        self.assertEqual(parse_datetime("2024-05-12"), "2024-05-12 00:00:00")
        self.assertEqual(parse_datetime("2024/05/12 08:30"), "2024-05-12 08:30:00")

    def test_masks(self):
        self.assertEqual(mask_phone("13812345678"), "138****5678")
        self.assertEqual(mask_name("张三"), "张*")
        self.assertEqual(mask_email("zhangsan@example.com"), "z***@example.com")
        self.assertEqual(mask_idcard("130629199001011234"), "130***********1234")
        self.assertEqual(mask_bankcard("6222020200001234567"), "***************4567")
        self.assertIn("***", mask_address("河北省雄安新区容城县振兴路12号"))


class TestConfig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.standards = load_config("standards.json")
        cls.rules = load_config("quality_rules.json")
        cls.classification = load_config("classification_rules.json")
        cls.assets = load_config("assets.json")
        cls.transformations = load_config("transformations.json")
        cls.lineage = load_config("lineage.json")

    def test_rule_ids_unique_and_fields_exist(self):
        ids = [rule["id"] for rule in self.rules["rules"]]
        self.assertEqual(len(ids), len(set(ids)), "规则编号必须唯一")
        for rule in self.rules["rules"]:
            self.assertIn(rule["table"], self.standards["tables"], rule["id"])
            if rule.get("field"):
                self.assertIn(rule["field"], self.standards["tables"][rule["table"]]["fields"], rule["id"])
            self.assertIn(rule["dimension"], {"完整性", "准确性", "一致性", "唯一性", "有效性", "及时性"})
            self.assertIn(rule["severity"], {"高", "中", "低"})
            self.assertGreaterEqual(rule["tolerance"], 0)
            self.assertIn("remediation", rule)

    def test_classification_covers_all_fields(self):
        standard_fields = {
            (table, field)
            for table, table_std in self.standards["tables"].items()
            for field in table_std["fields"]
        }
        classified = {(rule["table"], rule["field"]) for rule in self.classification["field_rules"]}
        self.assertEqual(standard_fields - classified, set())
        for rule in self.classification["field_rules"]:
            self.assertIn(rule["level"], {"L1", "L2", "L3", "L4"})
            if rule["personal_info"]:
                self.assertTrue(rule.get("masking"), f"个人信息字段缺少脱敏策略：{rule}")

    def test_field_rule_defaults(self):
        self.assertEqual(field_rule("market_register", "contact_phone")["level"], "L3")
        self.assertTrue(field_rule("complaint_case", "content")["personal_info"])
        self.assertEqual(field_rule("ods_market_register", "contact_phone")["level"], "L3")

    def test_transformations_cover_dwd(self):
        for table, spec in self.transformations["tables"].items():
            targets = {field["target"] for field in spec["fields"]}
            standard = set(self.standards["tables"][table]["fields"]) | {"dq_flags"}
            self.assertEqual(standard - targets, set(), f"{table} 存在未映射字段")

    def test_assets_nodes_and_required_fields(self):
        node_ids = {node["id"] for node in self.lineage["nodes"]}
        asset_ids = [asset["id"] for asset in self.assets["assets"]]
        self.assertEqual(len(asset_ids), len(set(asset_ids)))
        for asset in self.assets["assets"]:
            if asset.get("node_id"):
                self.assertIn(asset["node_id"], node_ids)
            for key in ("name", "type", "domain", "owner", "steward", "level", "sharing", "update_frequency", "description"):
                self.assertTrue(asset.get(key), f"{asset['id']} 缺少 {key}")


class TestGeneratedData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest_path = RAW_DIR / "_defect_manifest.json"

    @unittest.skipUnless((RAW_DIR / "market_register.csv").exists(), "需要先生成模拟数据")
    def test_manifest_and_data(self):
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["as_of"], "2026-10-31")
        self.assertEqual(manifest["tables"]["market_register"]["rows"], 1240)
        self.assertGreater(len(manifest["tables"]["market_register"]["defects"]), 10)
        with (RAW_DIR / "market_register.csv").open(encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 1240)
        self.assertGreaterEqual(sum(1 for r in rows if not r["contact_phone"]), 50)


class TestReports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.quality_path = REPORTS / "quality_result.json"
        cls.quality = json.loads(cls.quality_path.read_text(encoding="utf-8")) if cls.quality_path.exists() else None

    @unittest.skipUnless((REPORTS / "quality_result.json").exists(), "需要先运行 python run_demo.py")
    def test_quality_improves(self):
        before = self.quality["before"]["summary"]["overall_health"]
        after = self.quality["after"]["summary"]["overall_health"]
        self.assertGreater(after, before + 8)
        self.assertGreaterEqual(after, 85)
        self.assertGreaterEqual(self.quality["effectiveness"]["summary"]["recall"], 0.9)
        self.assertGreater(self.quality["closure"]["fixed"], 0)
        self.assertGreater(self.quality["closure"]["open"], 0, "治理后应保留待整改，证明不是删库刷分")

    @unittest.skipUnless((REPORTS / "classification.json").exists(), "需要先运行 python run_demo.py")
    def test_pii_and_sharing(self):
        classification = json.loads((REPORTS / "classification.json").read_text(encoding="utf-8"))
        self.assertEqual(classification["summary"]["coverage"], 1.0)
        self.assertEqual(classification["sharing"]["residual_total"], 0)
        self.assertGreater(classification["content_scan"]["affected_rows"], 0)
        for det_id in ("PII-MOBILE", "PII-IDCARD", "PII-EMAIL", "PII-BANKCARD"):
            self.assertEqual(classification["content_scan"]["by_detector"][det_id]["recall"], 1.0)

    @unittest.skipUnless((REPORTS / "asset_register.json").exists(), "需要先运行 python run_demo.py")
    def test_assets_complete(self):
        assets = json.loads((REPORTS / "asset_register.json").read_text(encoding="utf-8"))
        self.assertEqual(assets["summary"]["assets"], 15)
        self.assertEqual(assets["summary"]["completeness"], 1.0)
        self.assertEqual(assets["summary"]["with_owner"], 15)

    @unittest.skipUnless((REPORTS / "issue_register.csv").exists(), "需要先运行 python run_demo.py")
    def test_issue_register(self):
        with (REPORTS / "issue_register.csv").open(encoding="utf-8-sig") as fh:
            issues = list(csv.DictReader(fh))
        self.assertGreater(len(issues), 500)
        for issue in issues[:100]:
            self.assertIn(issue["status"], {"已修复", "已隔离", "待整改", "观察项"})
            self.assertTrue(issue["due_date"])

    @unittest.skipUnless((REPORTS / "lineage.json").exists(), "需要先运行 python run_demo.py")
    def test_lineage(self):
        lineage = json.loads((REPORTS / "lineage.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(lineage["summary"]["field_edges"], 29)
        node_ids = {node["id"] for node in lineage["nodes"]}
        for edge in lineage["edges"]:
            self.assertIn(edge["from"], node_ids)
            self.assertIn(edge["to"], node_ids)


if __name__ == "__main__":
    unittest.main()
