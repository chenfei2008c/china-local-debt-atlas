"""批量来源登记、等级过滤和核心面板覆盖率工具。

本模块只处理来源与字段覆盖的标准化，不负责下载文件，也不直接选择数值。
它把“省级批量来源”和“城市年度来源”统一为同一份登记结构，供采集器、
缺口报告和后续批次调度复用。
"""

from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable, Mapping


SOURCE_GRADE_RANK = {"D": 0, "C": 1, "B2": 2, "B1": 3, "A2": 4, "A1": 5}
ACCEPTED_SOURCE_GRADES = {"A1", "A2", "B1", "B2"}
CORE_RAW_FIELDS = (
    "gdp_current_100m",
    "gdp_real_growth_pct",
    "resident_population_10k",
    "general_public_revenue_100m",
    "general_public_expenditure_100m",
    "gov_fund_revenue_100m",
    "statutory_debt_limit_100m",
    "statutory_debt_balance_100m",
)
TARGET_START_YEAR = 2018
TARGET_END_YEAR = 2025

BATCH_REGISTRY_FIELDS = (
    "source_doc_id",
    "publisher",
    "source_grade",
    "accepted_for_final",
    "document_type",
    "source_url",
    "attachment_url",
    "file_name",
    "mime_type",
    "publication_date",
    "coverage_scope",
    "covered_city_count",
    "covered_year_count",
    "covered_core_value_count",
    "covered_cities",
    "covered_years",
    "covered_fields",
    "coverage_status",
    "note",
)

CORE_COVERAGE_FIELDS = (
    "field_name",
    "target_year_start",
    "target_year_end",
    "target_rows",
    "numeric_non_null_rows",
    "numeric_missing_rows",
    "high_grade_rows",
    "high_grade_missing_rows",
    "provisional_rows",
    "unattributed_rows",
    "numeric_coverage_pct",
    "high_grade_coverage_pct",
)

_RECORD_ID = re.compile(r"^MACRO-(CN-\d+)-(\d{4})-")


def _as_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _as_year(value: Any) -> str:
    text = _as_text(value)
    if not text:
        return ""
    try:
        return str(int(text))
    except ValueError as exc:
        raise ValueError(f"年度必须是整数：{value!r}") from exc


def _field_set(value: Any) -> list[str]:
    if isinstance(value, str):
        values = re.split(r"[;,，、\s]+", value)
    else:
        values = list(value or [])
    return sorted({str(item).strip() for item in values if str(item).strip() in CORE_RAW_FIELDS})


def _is_non_null(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _is_selected(value: Any) -> bool:
    return _as_text(value).lower() in {"true", "1", "yes", "是"}


def _parse_record_id(value: Any) -> tuple[str, str] | None:
    match = _RECORD_ID.match(_as_text(value))
    return None if match is None else (match.group(1), match.group(2))


def _pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "0.00"
    value = (Decimal(numerator) / Decimal(denominator) * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return format(value, "f")


def normalize_batch_source(source: Mapping[str, Any]) -> dict[str, str]:
    """把一个来源配置规范化为可写入批次登记表的记录。"""

    source_doc_id = _as_text(source.get("source_doc_id"))
    if not source_doc_id:
        raise ValueError("批量来源必须包含 source_doc_id")

    source_grade = _as_text(source.get("source_grade")).upper()
    if source_grade and source_grade not in SOURCE_GRADE_RANK:
        raise ValueError(f"未知来源等级：{source_grade}")

    normalized_fields = ";".join(_field_set(source.get("fields")))
    return {
        "source_doc_id": source_doc_id,
        "publisher": _as_text(source.get("publisher")),
        "year": _as_year(source.get("year")),
        "source_grade": source_grade,
        "accepted_for_final": str(source_grade in ACCEPTED_SOURCE_GRADES).lower(),
        "document_type": _as_text(source.get("document_type")),
        "source_url": _as_text(source.get("source_url") or source.get("url")),
        "attachment_url": _as_text(source.get("attachment_url")),
        "file_name": _as_text(source.get("file_name") or source.get("path")),
        "mime_type": _as_text(source.get("mime_type") or source.get("format")),
        "publication_date": _as_text(source.get("publication_date")),
        "coverage_scope": _as_text(source.get("coverage_scope")) or "unclassified",
        "covered_city_count": "0",
        "covered_year_count": "0",
        "covered_core_value_count": "0",
        "covered_cities": "",
        "covered_years": _as_year(source.get("year")),
        "fields": normalized_fields,
        "covered_fields": normalized_fields,
        "coverage_status": "registered_only",
        "note": _as_text(source.get("note")),
    }


def build_batch_source_registry(
    source_rows: Iterable[Mapping[str, Any]],
    lineage_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, str]]:
    """从来源表和字段血缘汇总每份来源实际覆盖的城市、年份和字段。"""

    selected_by_source: dict[str, list[tuple[str, str, str]]] = {}
    for lineage in lineage_rows:
        if not _is_selected(lineage.get("selected_flag")):
            continue
        field = _as_text(lineage.get("target_field"))
        if field not in CORE_RAW_FIELDS or not _is_non_null(lineage.get("normalized_value")):
            continue
        parsed = _parse_record_id(lineage.get("target_record_id"))
        source_doc_id = _as_text(lineage.get("source_doc_id"))
        if parsed is None or not source_doc_id:
            continue
        city_id, year = parsed
        selected_by_source.setdefault(source_doc_id, []).append((city_id, year, field))

    output: list[dict[str, str]] = []
    for source in source_rows:
        row = normalize_batch_source(source)
        covered = selected_by_source.get(row["source_doc_id"], [])
        cities = sorted({item[0] for item in covered})
        years = sorted({item[1] for item in covered}, key=int)
        fields = sorted({item[2] for item in covered})
        if len(cities) > 1:
            row["coverage_scope"] = "multicity_batch"
        elif cities:
            row["coverage_scope"] = "city_year"
        row["covered_city_count"] = str(len(cities))
        row["covered_year_count"] = str(len(years))
        row["covered_core_value_count"] = str(len(covered))
        row["covered_cities"] = ";".join(cities)
        row["covered_years"] = ";".join(years)
        row["covered_fields"] = ";".join(fields)
        if not covered:
            row["coverage_status"] = "registered_no_selected_value"
        elif row["accepted_for_final"] == "true":
            row["coverage_status"] = "accepted"
        else:
            row["coverage_status"] = "provisional_only"
        output.append(row)
    return output


def build_core_coverage_report(
    macro_rows: Iterable[Mapping[str, Any]],
    lineage_rows: Iterable[Mapping[str, Any]],
    source_rows: Iterable[Mapping[str, Any]],
    *,
    start_year: int = TARGET_START_YEAR,
    end_year: int = TARGET_END_YEAR,
) -> list[dict[str, str]]:
    """同时计算数值覆盖率、高等级定稿率和暂存值数量。"""

    targets = [
        row
        for row in macro_rows
        if start_year <= int(_as_text(row.get("metric_year"))) <= end_year
    ]
    source_grades = {
        _as_text(row.get("source_doc_id")): _as_text(row.get("source_grade")).upper()
        for row in source_rows
        if _as_text(row.get("source_doc_id"))
    }
    accepted_by_key: set[tuple[str, str]] = set()
    provisional_by_key: set[tuple[str, str]] = set()
    attributed_by_key: set[tuple[str, str]] = set()
    for lineage in lineage_rows:
        if not _is_selected(lineage.get("selected_flag")):
            continue
        parsed = _parse_record_id(lineage.get("target_record_id"))
        field = _as_text(lineage.get("target_field"))
        if parsed is None or field not in CORE_RAW_FIELDS or not _is_non_null(lineage.get("normalized_value")):
            continue
        key = (lineage["target_record_id"], field)
        grade = source_grades.get(_as_text(lineage.get("source_doc_id")), "")
        attributed_by_key.add(key)
        if grade in ACCEPTED_SOURCE_GRADES:
            accepted_by_key.add(key)
        else:
            provisional_by_key.add(key)

    output: list[dict[str, str]] = []
    for field in CORE_RAW_FIELDS:
        non_null = 0
        high_grade = 0
        provisional = 0
        unattributed = 0
        for row in targets:
            value = row.get(field)
            if not _is_non_null(value):
                continue
            non_null += 1
            record_id = f"MACRO-{row['city_id']}-{row['metric_year']}-PREFECTURE"
            key = (record_id, field)
            if key in accepted_by_key:
                high_grade += 1
            elif key in provisional_by_key:
                provisional += 1
            else:
                unattributed += 1
        total = len(targets)
        output.append(
            {
                "field_name": field,
                "target_year_start": str(start_year),
                "target_year_end": str(end_year),
                "target_rows": str(total),
                "numeric_non_null_rows": str(non_null),
                "numeric_missing_rows": str(total - non_null),
                "high_grade_rows": str(high_grade),
                "high_grade_missing_rows": str(total - high_grade),
                "provisional_rows": str(provisional),
                "unattributed_rows": str(unattributed),
                "numeric_coverage_pct": _pct(non_null, total),
                "high_grade_coverage_pct": _pct(high_grade, total),
            }
        )
    return output
