"""路径与通用常量。"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
REFERENCE_DIR = DATA_DIR / "reference"
SERVING_DIR = DATA_DIR / "serving"
REPORT_DIR = ROOT / "reports"
DOCS_DIR = ROOT / "docs"
TEMPLATE_DIR = ROOT / "templates"
DB_PATH = DATA_DIR / "warehouse.db"

AS_OF_DEFAULT = "2026-10-31"
SEED_DEFAULT = 20260701

TABLE_TITLES = {
    "market_register": "市场主体登记信息",
    "credit_rating": "市场主体信用评价",
    "complaint_case": "企业诉求工单",
    "ods_market_register": "市场主体登记信息（贴源层）",
    "ods_credit_rating": "市场主体信用评价（贴源层）",
    "ods_complaint_case": "企业诉求工单（贴源层）",
    "dwd_market_register": "市场主体登记信息（明细层）",
    "dwd_credit_rating": "市场主体信用评价（明细层）",
    "dwd_complaint_case": "企业诉求工单（明细层）",
}

LEVEL_NAMES = {"L1": "公开", "L2": "内部", "L3": "敏感", "L4": "核心"}


def rel(path: Path) -> str:
    """返回相对仓库根目录的 POSIX 风格路径，便于写入报告。"""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)
