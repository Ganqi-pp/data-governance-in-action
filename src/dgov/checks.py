"""数据校验与脱敏的纯函数，供造数、清洗、质量规则和分类分级共用。"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Iterable

USCC_CHARS = "0123456789ABCDEFGHJKLMNPQRTUWXY"  # GB 32100-2015，去掉 I/O/S/V/Z
USCC_WEIGHTS = [1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28]

PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def uscc_check_char(body17: str) -> str:
    total = sum(USCC_CHARS.index(ch) * w for ch, w in zip(body17, USCC_WEIGHTS))
    return USCC_CHARS[(31 - total % 31) % 31]


def is_valid_uscc(code: str) -> bool:
    code = (code or "").strip().upper()
    if len(code) != 18 or any(ch not in USCC_CHARS for ch in code):
        return False
    return uscc_check_char(code[:17]) == code[17]


def normalize_phone(value: str) -> str | None:
    """去分隔符、+86/0086 前缀，全角转半角；不合法返回 None。"""
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", str(value)).strip()
    text = re.sub(r"[\s\-()（）]", "", text)
    if text.startswith("+86"):
        text = text[3:]
    elif text.startswith("0086"):
        text = text[4:]
    elif text.startswith("86") and len(text) == 13:
        text = text[2:]
    return text if PHONE_RE.match(text) else None


def is_valid_email(value: str) -> bool:
    return bool(value) and bool(EMAIL_RE.match(value.strip()))


def parse_date(value: str | None) -> date | None:
    """兼容 YYYY-MM-DD、YYYY/MM/DD、YYYY.MM.DD、YYYYMMDD 与带时间的形式。"""
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", str(value)).strip()
    if not text:
        return None
    text = text.split(" ")[0].split("T")[0]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.date()
        except ValueError:
            continue
    return None


def parse_datetime(value: str | None) -> str | None:
    """归一为 YYYY-MM-DD HH:MM:SS；只有日期时补 00:00:00。"""
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", str(value)).strip()
    if not text:
        return None
    normalized = text.replace("/", "-").replace(".", "-").replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y%m%d"):
        try:
            parsed = datetime.strptime(normalized, fmt)
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


def clean_text(value: str | None) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    return f"{digits[:3]}****{digits[-4:]}" if len(digits) >= 7 else "***"


def mask_name(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    return value[0] + "*" * max(1, len(value) - 1)


def mask_email(value: str) -> str:
    value = (value or "").strip()
    if "@" not in value:
        return "***"
    local, domain = value.split("@", 1)
    return f"{local[:1]}***@{domain}"


def mask_idcard(value: str) -> str:
    value = (value or "").strip()
    if len(value) < 8:
        return "***"
    return value[:3] + "*" * 11 + value[-4:]


def mask_bankcard(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    return "*" * max(0, len(digits) - 4) + digits[-4:] if len(digits) > 4 else "***"


def mask_address(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    match = re.match(r"^(.*?(?:县|区|新区))", value)
    if match:
        return match.group(1) + "***"
    return value[:6] + "***"


def mask_content(value: str, patterns: Iterable[tuple[str, str]]) -> str:
    """按 (regex, masking_name) 依次替换正文中的个人信息。"""
    text = value or ""
    for pattern, masking in patterns:
        def replace(match: re.Match, masking: str = masking) -> str:
            raw = match.group(0)
            if masking == "phone_mask":
                return mask_phone(raw)
            if masking == "idcard_mask":
                return mask_idcard(raw)
            if masking == "email_mask":
                return mask_email(raw)
            if masking == "bankcard_mask":
                return mask_bankcard(raw)
            return "***"
        text = re.sub(pattern, replace, text)
    return text


def ratio(numerator: float, denominator: float, digits: int = 2) -> float:
    if not denominator:
        return 0.0
    return round(numerator / denominator, digits)
