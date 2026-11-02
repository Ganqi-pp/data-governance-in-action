# -*- coding: utf-8 -*-
"""全局配置与路径。"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
SQL_DIR = ROOT / "sql"
DATA_DIR = ROOT / "data"
REPORT_DIR = ROOT / "reports"
DOCS_DIR = ROOT / "docs"

DB_PATH = DATA_DIR / "governance.db"

SEVERITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}
SEVERITY_LABEL = {"high": "高", "medium": "中", "low": "低"}
LAYER_LABEL = {"ods": "贴源层", "dwd": "明细层", "dws": "汇总层"}


def load_json(name: str) -> dict:
    with open(CONFIG_DIR / name, "r", encoding="utf-8") as fh:
        return json.load(fh)
