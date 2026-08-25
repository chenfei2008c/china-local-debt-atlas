"""财政部地方政府债券信息公开平台城市年度接口适配器。

平台年度接口只对部分副省级/计划单列市提供城市级序列。本适配器读取已归档
的 JSON 快照，不在运行时依赖网络；只接入接口返回的精确年度值，缺失年份保持空值。
指标代码：0101 债务限额、0601 债务余额、1101 一般预算收入、1103 政府性
基金收入、1104 一般预算支出、1201 GDP。接口没有 GDP 增速和常住人口，绝不推算。
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


SOURCE_GRADE = "A1"
API_ROOT = "https://www.governbond.org.cn:4443/api/loadBondData.action"

CITY_SPECS = {
    "2102": {"city_id": "CN-210200", "city_name": "大连市"},
    "3302": {"city_id": "CN-330200", "city_name": "宁波市"},
    "3502": {"city_id": "CN-350200", "city_name": "厦门市"},
    "3702": {"city_id": "CN-370200", "city_name": "青岛市"},
    "4403": {"city_id": "CN-440300", "city_name": "深圳市"},
}

INDICATOR_FIELDS = {
    "0101": "statutory_debt_limit_100m",
    "0601": "statutory_debt_balance_100m",
    "1101": "general_public_revenue_100m",
    "1103": "gov_fund_revenue_100m",
    "1104": "general_public_expenditure_100m",
    "1201": "gdp_current_100m",
}
INDICATOR_FILES = {"0101": "01", "0601": "06", "1101": "1101", "1103": "1103", "1104": "1104", "1201": "1201"}
DATA_FIELDS = set(INDICATOR_FIELDS.values())


def _decimal(value: Any) -> Decimal | None:
    if value is None or str(value).strip() in {"", "null", "None"}:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _source_id(city_code: str) -> str:
    return f"SRC-A1-CELMA-CITY-ANNUAL-{city_code}"


def load_celma_city_annual_sources(root: Path) -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    values: dict[tuple[str, str], dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    for city_code, spec in CITY_SPECS.items():
        source_id = _source_id(city_code)
        file_paths = [root / "raw" / "province_fiscal" / "celma" / f"{city_code}_{INDICATOR_FILES[indicator]}.json" for indicator in INDICATOR_FIELDS]
        records_by_field: dict[str, list[dict[str, Any]]] = {}
        for indicator, field in INDICATOR_FIELDS.items():
            path = root / "raw" / "province_fiscal" / "celma" / f"{city_code}_{INDICATOR_FILES[indicator]}.json"
            if not path.exists():
                raise FileNotFoundError(f"财政部平台城市接口快照缺失：{path}")
            payload = json.loads(path.read_text(encoding="utf-8"))
            if str(payload.get("code")) != "0":
                raise ValueError(f"财政部平台城市接口返回异常：{path}")
            records_by_field[field] = list(payload.get("data") or [])
        years: set[str] = set()
        for field, records in records_by_field.items():
            for item in records:
                year = str(item.get("SET_YEAR") or "")
                if not year.isdigit() or not 2018 <= int(year) <= 2025:
                    continue
                value = _decimal(item.get("AMOUNT"))
                if value is None:
                    continue
                years.add(year)
                row = values.setdefault(
                    (spec["city_id"], year),
                    {
                        "source_doc_id": source_id,
                        "source_grade": SOURCE_GRADE,
                        "source_format": "json",
                        "data_status": "reported",
                        "data_status_label": f"{year}年财政部地方政府债券信息公开平台年度接口值",
                        "city_id": spec["city_id"],
                        "city_name": spec["city_name"],
                        "year": year,
                        "_field_sources": {},
                    },
                )
                row[field] = value
                field_source = {
                    "source_doc_id": source_id,
                    "source_grade": SOURCE_GRADE,
                    "source_format": "json",
                    "data_status": "reported",
                    "data_status_label": f"{year}年财政部地方政府债券信息公开平台年度接口值",
                    "source_locator": f"{path.relative_to(root)}；接口参数=dataType=NDZB&adCode={city_code}&zb={indicator}；城市={spec['city_name']}；年份={year}；ZB_ID={indicator}",
                    "table_name": f"财政部平台{year}年度城市指标{indicator}",
                    "page_number": "JSON记录",
                    f"{field}_raw_100m": value,
                    f"{field}_raw_unit": "亿元",
                    f"{field}_evidence_excerpt": json.dumps(item, ensure_ascii=False, separators=(",", ":")),
                }
                row["_field_sources"][field] = field_source
                row[f"{field}_raw_100m"] = value
                row[f"{field}_raw_unit"] = "亿元"
                row[f"{field}_evidence_excerpt"] = field_source[f"{field}_evidence_excerpt"]
        hashes = ";".join(
            f"{path.name}:{hashlib.sha256(path.read_bytes()).hexdigest()}"
            for path in file_paths
        )
        sources.append(
            {
                "source_doc_id": source_id,
                "publisher": "财政部政府债务研究和评估中心",
                "publisher_level": "中央",
                "document_title": f"中国地方政府债券信息公开平台——{spec['city_name']}年度指标接口",
                "title_source": "official_api",
                "attachment_title": ";".join(path.name for path in file_paths),
                "document_type": "地方政府债券信息公开平台城市年度指标JSON快照",
                "source_url": f"{API_ROOT}?dataType=NDZB&adCode={city_code}&zb=01",
                "landing_page_url": "https://www.celma.org.cn/ndsj/index.jhtml",
                "attachment_url": API_ROOT,
                "canonical_url": API_ROOT,
                "final_resolved_url": API_ROOT,
                "file_name": ";".join(path.name for path in file_paths),
                "mime_type": "application/json",
                "publication_date": "2026-08-24",
                "publication_date_raw": "年度接口实时快照（抓取日2026-08-24）",
                "period_end": "2025-12-31",
                "downloaded_at": "2026-08-24T00:00:00+08:00",
                "content_hash_sha256": hashes,
                "archive_uri": f"archive://national-prefecture-panel/raw/province_fiscal/celma/{city_code}_*.json",
                "archive_backend": "internal_object",
                "archive_path": "raw/province_fiscal/celma/",
                "page_count": "",
                "source_grade": SOURCE_GRADE,
                "http_status": "200",
                "access_status": "财政部平台公开接口快照已归档",
                "supersedes_doc_id": "",
                "note": "只接入平台返回的城市年度精确值；该平台接口未提供GDP实际增速和年末常住人口，因此两字段不推算；原始单位为亿元。",
            }
        )
    return values, sources


__all__ = ["load_celma_city_annual_sources"]
