"""Masking and stable anonymization helpers for sensitive patient fields."""

from __future__ import annotations

import hashlib
import hmac
import os
import re

_COMPOUND_SURNAMES = (
    "欧阳",
    "太史",
    "端木",
    "上官",
    "司马",
    "东方",
    "独孤",
    "南宫",
    "万俟",
    "闻人",
    "夏侯",
    "诸葛",
    "尉迟",
    "公羊",
    "赫连",
    "澹台",
    "皇甫",
    "宗政",
    "濮阳",
    "公冶",
    "太叔",
    "申屠",
    "公孙",
    "慕容",
    "仲孙",
    "钟离",
    "长孙",
    "宇文",
    "司徒",
    "鲜于",
    "司空",
    "闾丘",
    "子车",
    "亓官",
    "司寇",
    "巫马",
    "公西",
    "颛孙",
    "壤驷",
    "公良",
    "漆雕",
    "乐正",
    "宰父",
    "谷梁",
    "拓跋",
    "夹谷",
    "轩辕",
    "令狐",
    "段干",
    "百里",
    "呼延",
    "东郭",
    "南门",
    "羊舌",
    "微生",
    "公户",
    "公玉",
    "公仪",
    "梁丘",
    "公仲",
    "公上",
    "公门",
    "公山",
    "公坚",
    "左丘",
    "公伯",
    "西门",
    "公祖",
    "第五",
    "公乘",
    "贯丘",
    "公皙",
    "南荣",
    "东里",
    "东宫",
    "仲长",
    "子书",
    "子桑",
    "即墨",
    "达奚",
    "褚师",
)


def mask_name(name) -> str:
    if name is None:
        return ""
    value = str(name).strip()
    if not value:
        return ""
    for surname in _COMPOUND_SURNAMES:
        if value.startswith(surname) and len(value) > len(surname):
            return surname + "*" * (len(value) - len(surname))
    if len(value) == 1:
        return "*"
    return value[0] + "*" * (len(value) - 1)


def mask_phone(phone) -> str:
    if phone is None:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) != 11:
        return "***"
    return f"{digits[:3]}****{digits[-4:]}"


def mask_id_card(id_card) -> str:
    if id_card is None:
        return ""
    value = str(id_card).strip()
    if len(value) < 8:
        return "***"
    return f"{value[:3]}{'*' * (len(value) - 7)}{value[-4:]}"


def hmac_sha256(value: str, secret: str | None = None) -> str:
    secret_value = secret if secret is not None else os.getenv("HMAC_SECRET", "")
    if not secret_value:
        raise ValueError("HMAC_SECRET is required for stable patient identifier hashing.")
    payload = "" if value is None else str(value)
    digest = hmac.new(secret_value.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"hmac_sha256:{digest}"


def hash_id_card(id_card) -> str:
    if id_card is None or str(id_card).strip() == "":
        return ""
    return hmac_sha256(str(id_card).strip())
