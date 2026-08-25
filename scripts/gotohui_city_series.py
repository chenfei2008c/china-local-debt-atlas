"""聚汇数据公开历史序列适配器。

聚汇页面公开展示按城市、年度排列的精确序列，并在页面元数据中标注
原始来源机构和单位。本适配器只读取标题与城市完全匹配的总量序列；
不接入预算数、本级数、分项数、辖区数、预测值或页面空白。

该入口是 B2 二手公开来源：原始来源机构保留在字段血缘中，聚汇页面
URL、抓取快照哈希和表格行也保留在原始快照中，后续可以用官方原件替换
而不改变标准输入接口。
"""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping


SNAPSHOT_PATH = Path("raw/province_fiscal/gotohui/city_series_snapshot.json")
SOURCE_GRADE = "B2"
TARGET_FIELDS = {
    "gdp": "gdp_current_100m",
    "growth": "gdp_real_growth_pct",
    "population": "resident_population_10k",
    "revenue": "general_public_revenue_100m",
    "expenditure": "general_public_expenditure_100m",
    "fund": "gov_fund_revenue_100m",
    "limit": "statutory_debt_limit_100m",
    "balance": "statutory_debt_balance_100m",
}


def _decimal(value: Any) -> Decimal | None:
    text = str(value or "").strip().replace(",", "").replace("，", "")
    if not text or text in {"-", "—", "–", "…", "...", "/", "--"}:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _normalize(raw: Decimal, metric: str, unit: str) -> Decimal:
    if metric in {"revenue", "expenditure", "fund", "limit", "balance"} and unit == "万元":
        return _q2(raw / Decimal("10000"))
    if metric == "population" and unit == "人":
        return _q2(raw / Decimal("10000"))
    return _q2(raw)


def _source_id(series: Mapping[str, Any]) -> str:
    return f"SRC-B2-GOTOHUI-{str(series['metric']).upper()}-{series['series_id']}"


def _source_record(series: Mapping[str, Any], snapshot_hash: str) -> dict[str, Any]:
    source_id = _source_id(series)
    return {
        "source_doc_id": source_id,
        "publisher": "聚汇数据（公开历史序列页）",
        "publisher_level": "公开二手数据平台",
        "document_title": str(series.get("title") or ""),
        "title_source": "public_secondary_exact_series",
        "attachment_title": str(series.get("title") or ""),
        "document_type": "公开城市年度历史序列表格",
        "source_url": str(series.get("url") or ""),
        "landing_page_url": str(series.get("url") or ""),
        "attachment_url": str(series.get("url") or ""),
        "canonical_url": str(series.get("url") or ""),
        "final_resolved_url": str(series.get("url") or ""),
        "file_name": SNAPSHOT_PATH.name,
        "mime_type": "application/json",
        "publication_date": "",
        "publication_date_raw": str(series.get("data_range") or ""),
        "period_end": "2025-12-31",
        "downloaded_at": "2026-08-25T00:00:00+08:00",
        "content_hash_sha256": str(series.get("content_hash_sha256") or snapshot_hash),
        "archive_uri": f"archive://national-prefecture-panel/{SNAPSHOT_PATH}",
        "archive_path": str(SNAPSHOT_PATH),
        "source_grade": SOURCE_GRADE,
        "http_status": "200",
        "access_status": "公开页面表格已归档；原始来源与平台来源分层记录",
        "note": (
            "B2公开二手精确序列；页面标题与城市总量指标完全匹配，"
            f"页面标注原始来源为{series.get('source') or '未标注'}，"
            "不接入预算数、本级数、分项数、辖区数和空白年份。"
        ),
    }


def load_gotohui_city_series_sources(
    root: Path, city_master: list[Mapping[str, Any]]
) -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    """读取已归档的公开序列并转换为标准城市年度输入。"""

    path = root / SNAPSHOT_PATH
    if not path.exists():
        return {}, []
    content = path.read_bytes()
    payload = json.loads(content.decode("utf-8"))
    snapshot_hash = hashlib.sha256(content).hexdigest()
    city_by_id = {str(c.get("city_id")): c for c in city_master if c.get("city_id")}
    values: dict[tuple[str, str], dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    seen_sources: set[str] = set()

    for series in payload.get("series", []):
        metric = str(series.get("metric") or "")
        field = TARGET_FIELDS.get(metric)
        city_id = str(series.get("city_id") or "")
        city = city_by_id.get(city_id)
        if not field or not city:
            continue
        source_id = _source_id(series)
        if source_id not in seen_sources:
            sources.append(_source_record(series, snapshot_hash))
            seen_sources.add(source_id)
        unit = str(series.get("unit") or "")
        for item in series.get("rows", []):
            year = str(item.get("year") or "")
            if not year.isdigit() or not 2018 <= int(year) <= 2025:
                continue
            raw = _decimal(item.get("value"))
            if raw is None:
                continue
            value = _normalize(raw, metric, unit)
            key = (city_id, year)
            record = values.setdefault(
                key,
                {
                    "source_doc_id": source_id,
                    "source_grade": SOURCE_GRADE,
                    "source_format": "html",
                    "source_platform": "gotohui",
                    "data_status": "reported",
                    "data_status_label": f"{year}年公开历史序列（页面标注来源：{series.get('source') or '未标注'}）",
                    "city_id": city_id,
                    "city_name": str(city.get("city_name_cn") or series.get("city_name") or ""),
                    "year": year,
                    "_field_sources": {},
                },
            )
            source_locator = (
                f"{SNAPSHOT_PATH}；series_id={series.get('series_id')};"
                f"URL={series.get('url')};表格行={year}年；城市={series.get('city_name')};"
                f"指标={series.get('title')}；页面标注原始来源={series.get('source') or '未标注'}"
            )
            field_source = {
                "source_doc_id": source_id,
                "source_grade": SOURCE_GRADE,
                "source_format": "html",
                "source_platform": "gotohui",
                "data_status": "reported",
                "data_status_label": record["data_status_label"],
                "source_locator": source_locator,
                "table_name": "聚汇数据公开城市年度历史序列表",
                "page_number": "HTML表格",
                f"{field}_raw_100m": raw,
                f"{field}_raw_unit": unit,
                f"{field}_evidence_excerpt": f"{series.get('title')} | {year} | {item.get('value')} {unit}",
            }
            record[field] = value
            record[f"{field}_raw_100m"] = raw
            record[f"{field}_raw_unit"] = unit
            record[f"{field}_evidence_excerpt"] = field_source[f"{field}_evidence_excerpt"]
            record["_field_sources"][field] = field_source
            existing_ids = [x for x in str(record.get("source_doc_id") or "").split(";") if x]
            if source_id not in existing_ids:
                existing_ids.append(source_id)
            record["source_doc_id"] = ";".join(existing_ids)
    return values, sources


__all__ = ["load_gotohui_city_series_sources"]
