"""国家统计局国家数据“主要城市年度数据”2024 年 A1 快照适配器。

接口公开返回 36 个主要城市，不能外推到未返回的地级行政单元。适配器保留
完整 342 城市请求响应快照，只把响应中明确有值的城市字段写入标准暂存层。
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping


GDP_PATH = Path("raw/macro_fiscal/nbs_city_gdp_2024.json")
FISCAL_PATH = Path("raw/macro_fiscal/nbs_city_fiscal_2024.json")
GDP_URL = "https://data.stats.gov.cn/dg/website/publicrelease/web/external/stream/esData"
FISCAL_URL = GDP_URL
SOURCE_ID = "SRC-A1-NBS-MAJOR-CITY-ANNUAL-2024"


def _decimal(value: Any) -> Decimal | None:
    text = str(value or "").strip().replace(",", "").replace("，", "")
    if not text or text in {"-", "—", "…", "...", "/"}:
        return None
    try:
        return Decimal(text).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def _read(path: Path) -> tuple[dict[str, Any], str]:
    content = path.read_bytes()
    return json.loads(content.decode("utf-8")), hashlib.sha256(content).hexdigest()


def _records(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in payload.get("data", []):
        code = str(item.get("code") or "")
        if not code:
            continue
        values: dict[str, Any] = {}
        for value in item.get("values", []):
            raw = value.get("value")
            if raw in (None, ""):
                continue
            label = str(value.get("i_showname") or "")
            if "地区生产总值" in label and "当年价格" not in label:
                values["gdp_current_100m"] = _decimal(raw)
            elif "地方一般公共预算收入" in label:
                values["general_public_revenue_100m"] = _decimal(raw)
            elif "地方一般公共预算支出" in label:
                values["general_public_expenditure_100m"] = _decimal(raw)
        if values:
            result[code] = {"name": item.get("name", ""), **values}
    return result


def load_nbs_city_annual_2024(
    root: Path, city_master: list[Mapping[str, Any]]
) -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    """读取国家统计局 2024 年主要城市 A1 响应并匹配城市主表。"""

    gdp_payload, gdp_hash = _read(root / GDP_PATH)
    fiscal_payload, fiscal_hash = _read(root / FISCAL_PATH)
    by_code: dict[str, Mapping[str, Any]] = {}
    for city in city_master:
        admin_code = str(city.get("admin_code_6") or "")
        if admin_code:
            by_code[admin_code + "000000"] = city
    merged = _records(gdp_payload)
    for code, record in _records(fiscal_payload).items():
        merged.setdefault(code, {}).update(record)

    values: dict[tuple[str, str], dict[str, Any]] = {}
    for code, candidate in merged.items():
        city = by_code.get(code)
        if not city or not city.get("city_id"):
            continue
        record: dict[str, Any] = {
            "source_doc_id": SOURCE_ID,
            "source_grade": "A1",
            "source_format": "json",
            "data_status": "execution",
            "data_status_label": "2024年国家统计局国家数据主要城市年度值",
            "source_locator": (
                f"{GDP_PATH}、{FISCAL_PATH}；API响应code={code}；"
                f"城市={candidate.get('name') or city.get('city_name_cn')}；2024YY；行政范围=全市"
            ),
            "table_name": "国家统计局国家数据--主要城市年度数据",
            "page_number": "JSON响应",
        }
        for field in (
            "gdp_current_100m",
            "general_public_revenue_100m",
            "general_public_expenditure_100m",
        ):
            value = candidate.get(field)
            if value is None:
                continue
            record[field] = value
            record[f"{field}_raw_100m"] = value
            record[f"{field}_raw_unit"] = "亿元"
            record[f"{field}_evidence_excerpt"] = f"code={code};value={value}"
        record["_field_sources"] = {
            field: dict(record)
            for field in (
                "gdp_current_100m",
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
            )
            if field in record
        }
        values[(str(city["city_id"]), "2024")] = record

    sources = [
        {
            "source_doc_id": SOURCE_ID,
            "publisher": "国家统计局",
            "publisher_level": "国家统计局公开国家数据接口",
            "document_title": "国家数据--主要城市年度数据（2024年）",
            "title_source": "official_nbs_api",
            "attachment_title": f"{GDP_PATH.name}; {FISCAL_PATH.name}",
            "document_type": "国家数据接口JSON响应",
            "source_url": GDP_URL,
            "landing_page_url": "https://data.stats.gov.cn/",
            "attachment_url": GDP_URL,
            "canonical_url": "https://data.stats.gov.cn/",
            "final_resolved_url": GDP_URL,
            "file_name": f"{GDP_PATH.name}; {FISCAL_PATH.name}",
            "mime_type": "application/json",
            "publication_date": "2025-01-01",
            "publication_date_raw": "2024YY年度数据",
            "period_end": "2024-12-31",
            "downloaded_at": "2026-08-24T00:00:00+08:00",
            "content_hash_sha256": f"gdp={gdp_hash};fiscal={fiscal_hash}",
            "archive_uri": f"archive://national-prefecture-panel/{GDP_PATH}",
            "archive_backend": "internal_object",
            "archive_path": f"{GDP_PATH};{FISCAL_PATH}",
            "source_grade": "A1",
            "accepted_for_final": True,
            "http_status": "200",
            "access_status": "国家统计局公开接口响应已归档",
            "coverage_note": "接口请求342个行政单元，响应中仅36个主要城市有值；未返回城市保持空值。",
        }
    ]
    return values, sources


__all__ = ["load_nbs_city_annual_2024"]
