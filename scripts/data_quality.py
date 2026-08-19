"""字段级来源等级与口径一致性判断。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


ACCEPTED_SOURCE_GRADES = {"A1", "A2", "B1", "B2"}
_MONEY_QUANTUM = Decimal("0.01")


@dataclass(frozen=True)
class FieldAssessment:
    """字段值进入正式层前的状态与标准化结果。"""

    status: str
    normalized_value: Decimal | None
    reason: str = ""


def is_accepted_source_grade(source_grade: Any) -> bool:
    return str(source_grade or "").strip().upper() in ACCEPTED_SOURCE_GRADES


def _as_decimal(value: Any) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


def assess_field_value(
    *,
    value: Any,
    source_grade: Any,
    source_year: int | None,
    metric_year: int,
    source_geo_scope: str | None,
    metric_geo_scope: str,
) -> FieldAssessment:
    """判断字段是否满足高等级、年度和行政范围门槛。

    低等级来源仍可作为 provisional 暂存值，但不得计入高等级完成率；
    年度或行政范围不一致时直接 blocked，避免口径错配进入派生指标。
    """

    normalized = _as_decimal(value)
    if normalized is None:
        return FieldAssessment("missing", None, "源文件未披露可解析数值")
    if source_year is not None and int(source_year) != int(metric_year):
        return FieldAssessment("blocked", normalized.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP), "来源年度与指标年度不一致")
    if source_geo_scope != metric_geo_scope:
        return FieldAssessment("blocked", normalized.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP), "来源行政范围与目标范围不一致")
    if not is_accepted_source_grade(source_grade):
        return FieldAssessment("provisional", normalized.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP), "来源等级为 C/D，不能作为正式值")
    return FieldAssessment("accepted", normalized.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP))


def debt_fact_has_balance_limit_conflict(fact: dict[str, Any], tolerance: Decimal = Decimal("0.20")) -> bool:
    """返回债务事实是否出现余额超过对应限额且未提供例外说明。"""

    pairs = (
        ("general_debt_balance_100m", "general_debt_limit_100m"),
        ("special_debt_balance_100m", "special_debt_limit_100m"),
        ("statutory_debt_balance_100m", "statutory_debt_limit_100m"),
    )
    if fact.get("balance_limit_exception_note"):
        return False
    for balance_key, limit_key in pairs:
        balance = _as_decimal(fact.get(balance_key))
        limit = _as_decimal(fact.get(limit_key))
        if balance is not None and limit is not None and balance > limit + tolerance:
            return True
    return False
