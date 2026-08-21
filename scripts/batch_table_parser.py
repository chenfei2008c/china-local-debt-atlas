"""省级分地区表和城市财政表的统一行解析器。"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
from typing import Any, Iterable, Mapping

try:
    from scripts.batch_source_registry import CORE_RAW_FIELDS, SOURCE_GRADE_RANK
except ModuleNotFoundError:  # 允许直接运行 scripts 下的模块
    from batch_source_registry import CORE_RAW_FIELDS, SOURCE_GRADE_RANK


UNIT_FACTORS = {
    "亿元": Decimal("1"),
    "万元": Decimal("0.0001"),
    "元": Decimal("0.00000001"),
    "万人": Decimal("1"),
    "人": Decimal("0.0001"),
    "%": Decimal("1"),
    "百分比": Decimal("1"),
}


def normalize_city_label(value: Any) -> str:
    """统一处理中英文空格、标点和常见的表格分隔符。"""

    text = "" if value is None else str(value)
    text = re.sub(r"[\s\u3000]+", "", text)
    return text.strip("|｜:：\t")


def _row_parts(row: Any, value_index: int) -> tuple[str, Any]:
    if isinstance(row, Mapping):
        city_label = row.get("city_name") or row.get("行政区") or row.get("地区") or row.get("city")
        if "values" in row:
            values = row["values"]
            return str(city_label or ""), list(values)[value_index]
        if value_index == 0:
            return str(city_label or ""), row.get("value")
        return str(city_label or ""), None
    parts = list(row)
    if not parts:
        return "", None
    if value_index < 0 or value_index >= len(parts):
        return str(parts[0]), None
    return str(parts[0]), parts[value_index]


def _row_excerpt(row: Any) -> str:
    if isinstance(row, Mapping):
        values = row.get("values")
        return " ".join(str(item) for item in ([row.get("city_name")] + list(values or [])))
    return " ".join(str(item) for item in row)


def _parse_number(value: Any) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("，", "")
    text = text.replace("％", "%").rstrip("%")
    if text in {"", "-", "—", "–", "...", "…"}:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def parse_city_value_rows(
    rows: Iterable[Any],
    *,
    city_aliases: Mapping[str, str],
    field_name: str,
    value_index: int,
    raw_unit: str,
    metric_year: int,
    source_doc_id: str,
    source_grade: str,
    geo_scope: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """将提取后的表格行转为标准事实和拒绝记录。

    ``rows`` 可以来自 HTML/Excel 解析器的列表行，也可以是带 ``city_name`` 与
    ``values`` 的映射。解析器只接受 2018—2025 年和核心原始字段；城市本级、
    区县及省级合计行不会被写入事实结果。
    """

    if field_name not in CORE_RAW_FIELDS:
        raise ValueError(f"非核心原始字段：{field_name}")
    if not 2018 <= int(metric_year) <= 2025:
        raise ValueError(f"年度超出本轮范围：{metric_year}")
    if not source_doc_id:
        raise ValueError("source_doc_id 不能为空")
    grade = str(source_grade or "").strip().upper()
    if grade not in SOURCE_GRADE_RANK:
        raise ValueError(f"未知来源等级：{source_grade}")
    unit = str(raw_unit or "").strip()
    if unit not in UNIT_FACTORS:
        raise ValueError(f"不支持的原始单位：{raw_unit}")

    aliases = {normalize_city_label(key): value for key, value in city_aliases.items()}
    facts: list[dict[str, Any]] = []
    rejects: list[dict[str, Any]] = []

    for row_number, row in enumerate(rows, start=1):
        city_label, raw_value = _row_parts(row, value_index)
        normalized_label = normalize_city_label(city_label)
        city_id = aliases.get(normalized_label, "")
        reject_base = {
            "row_number": str(row_number),
            "city_label": city_label,
            "city_id": city_id,
            "field_name": field_name,
            "metric_year": str(metric_year),
            "raw_value": "" if raw_value is None else str(raw_value),
            "source_doc_id": source_doc_id,
        }
        if not city_id:
            rejects.append({**reject_base, "reason_code": "unmatched_city", "reason": "城市名称未匹配到行政区划映射"})
            continue
        if geo_scope != "prefecture_whole":
            rejects.append({**reject_base, "reason_code": "scope_mismatch", "reason": "来源不是地级行政单元全域口径"})
            continue
        number = _parse_number(raw_value)
        if number is None:
            rejects.append({**reject_base, "reason_code": "invalid_numeric", "reason": "数值为空、破折号或无法解析"})
            continue
        normalized_value = number * UNIT_FACTORS[unit]
        facts.append(
            {
                "city_id": city_id,
                "metric_year": str(metric_year),
                "field_name": field_name,
                "raw_value": str(raw_value).strip(),
                "raw_unit": unit,
                "normalized_value": normalized_value,
                "source_doc_id": source_doc_id,
                "source_grade": grade,
                "geo_scope": geo_scope,
                "source_locator": f"row:{row_number}",
                "evidence_excerpt": _row_excerpt(row),
                "value_origin": "disclosed",
            }
        )
    return facts, rejects
