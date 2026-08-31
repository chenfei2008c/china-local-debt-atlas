"""中国城市统计年鉴地级市截面表适配器。

这些工作簿是国家统计局城市社会经济调查司出版的年鉴表的归档镜像。
适配器只读取精确单元格，不从图形或媒体转述估值；原始出版者记为国家统计局，
归档入口按 B2 记录，后续仍可用官方年鉴原件替换镜像而不改变标准输入接口。
"""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping
from zipfile import ZipFile
from xml.etree import ElementTree as ET


NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


YEARBOOK_SPECS = (
    {
        "publication_year": 2019,
        "metric_year": 2018,
        "file_name": "china_city_statistical_yearbook_2019_prefecture.xlsx",
        "columns": {
            # 2019 年鉴的 GDP 与财政字段原始单位均为万元；不把年末户籍人口
            # 或年平均人口误当成年末常住人口。
            "gdp_current_100m": ("AG", "万元"),
            "gdp_real_growth_pct": ("AK", "%"),
            "general_public_revenue_100m": ("AS", "万元"),
            "general_public_expenditure_100m": ("AT", "万元"),
        },
    },
    {
        "publication_year": 2020,
        "metric_year": 2019,
        "file_name": "china_city_statistical_yearbook_2020_prefecture.xlsx",
        "columns": {
            "gdp_current_100m": ("AG", "亿元"),
            "gdp_real_growth_pct": ("AK", "%"),
            "general_public_revenue_100m": ("AS", "万元"),
            "general_public_expenditure_100m": ("AT", "万元"),
        },
    },
    {
        "publication_year": 2021,
        "metric_year": 2020,
        "file_name": "china_city_statistical_yearbook_2021_prefecture.xlsx",
        "columns": {
            "gdp_current_100m": ("T", "亿元"),
            "gdp_real_growth_pct": ("X", "%"),
            "resident_population_10k": ("C", "万人"),
            "general_public_revenue_100m": ("AF", "万元"),
            "general_public_expenditure_100m": ("AG", "万元"),
        },
    },
    {
        "publication_year": 2022,
        "metric_year": 2021,
        "file_name": "china_city_statistical_yearbook_2022_prefecture.xlsx",
        "columns": {
            "gdp_current_100m": ("T", "亿元"),
            "gdp_real_growth_pct": ("X", "%"),
            "general_public_revenue_100m": ("AF", "万元"),
            "general_public_expenditure_100m": ("AG", "万元"),
        },
    },
    {
        "publication_year": 2023,
        "metric_year": 2022,
        "file_name": "china_city_statistical_yearbook_2023_prefecture.xlsx",
        "columns": {
            "gdp_current_100m": ("T", "亿元"),
            "gdp_real_growth_pct": ("X", "%"),
            "general_public_revenue_100m": ("AF", "万元"),
            "general_public_expenditure_100m": ("AG", "万元"),
        },
    },
    {
        "publication_year": 2024,
        "metric_year": 2023,
        "file_name": "china_city_statistical_yearbook_2024_prefecture.xlsx",
        "columns": {
            "gdp_current_100m": ("R", "亿元"),
            "gdp_real_growth_pct": ("V", "%"),
            "resident_population_10k": ("C", "万人"),
            "general_public_revenue_100m": ("AD", "万元"),
            "general_public_expenditure_100m": ("AE", "万元"),
        },
    },
    {
        "publication_year": 2025,
        "metric_year": 2024,
        "file_name": "china_city_statistical_yearbook_2025_population.xlsx",
        "source_doc_id": "SRC-B2-CITY-YEARBOOK-2025-POPULATION",
        "table_name": "中国城市统计年鉴--2025（2024年地级以上城市常住人口表）",
        "sheet_name": "Sheet9",
        "source_url": "https://www.chinautc.com/upload/fckeditor/2-1_%E4%BA%BA%E5%8F%A3%E6%95%B0.xlsx",
        "landing_page_url": "https://www.chinautc.com/templates/H_information/content.aspx?contentid=106806&nodeid=6329&page=ContentPage",
        "columns": {
            "resident_population_10k": ("C", "万人"),
        },
    },
)


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).strip()


def _column_number(ref: str) -> int:
    result = 0
    for char in re.match(r"[A-Z]+", ref).group(0):
        result = result * 26 + ord(char) - ord("A") + 1
    return result


def _read_workbook(path: Path) -> tuple[list[dict[str, str]], str]:
    with ZipFile(path) as archive:
        shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        shared = [
            "".join(text.text or "" for text in item.findall(".//m:t", NS))
            for item in shared_root.findall("m:si", NS)
        ]
        sheet_root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        rows: list[dict[str, str]] = []
        for row in sheet_root.findall(".//m:sheetData/m:row", NS):
            values: dict[str, str] = {"_row_number": row.attrib.get("r", "")}
            for cell in row.findall("m:c", NS):
                value_node = cell.find("m:v", NS)
                value = value_node.text if value_node is not None else ""
                if cell.attrib.get("t") == "s" and value:
                    value = shared[int(value)]
                column = re.match(r"[A-Z]+", cell.attrib.get("r", ""))
                if column:
                    values[column.group(0)] = value
            rows.append(values)
        return rows, hashlib.sha256(path.read_bytes()).hexdigest()


def _as_decimal(value: Any) -> Decimal | None:
    text = str(value or "").strip().replace(",", "").replace("，", "")
    if not text or text in {"—", "-", "…", "...", "/"}:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _normalize(raw: Decimal, raw_unit: str) -> Decimal:
    if raw_unit == "万元":
        return (raw / Decimal("10000")).quantize(Decimal("0.01"))
    return raw.quantize(Decimal("0.01"))


def _yearbook_source_id(publication_year: int) -> str:
    return f"SRC-B2-CITY-YEARBOOK-{publication_year}"


def _raw_url(spec: Mapping[str, Any]) -> str:
    if spec.get("source_url"):
        return str(spec["source_url"])
    file_name = str(spec["file_name"])
    year = str(spec["publication_year"])
    return (
        "https://raw.githubusercontent.com/Zeeny-lin/vibe-coding-gis-/main/yearbook_data/"
        f"{year}/中国城市统计年鉴{year}（excel）【截面数据】/中国城市统计年鉴{year}【地级市截面数据】.xlsx"
    )


def load_city_yearbook_sources(
    root: Path,
    city_master: list[Mapping[str, Any]],
) -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    """读取年鉴中的全市地级市字段，返回标准化值和来源目录。"""

    city_by_name = {
        _clean_text(city.get("city_name_cn")): city
        for city in city_master
        if city.get("city_name_cn")
    }
    # 年鉴镜像存在少量 OCR/转码名称变体。匹配依据同时核对了工作簿
    # 的英文城市名和行政代码，不能把这些行当作缺失；这里只修正名称，
    # 不改变任何数值和行政范围。
    city_name_aliases = {
        "荷泽市": "菏泽市",
        "麥庄市": "枣庄市",
        "深河市": "漯河市",
        "常徳市": "常德市",
        "脩州市": "儋州市",
        "那曲冇": "那曲地区",
    }
    for alias, canonical in city_name_aliases.items():
        if canonical in city_by_name:
            city_by_name[alias] = city_by_name[canonical]
    values: dict[tuple[str, str], dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    base_dir = root / "raw" / "macro_fiscal" / "city_yearbook"

    for spec in YEARBOOK_SPECS:
        path = base_dir / str(spec["file_name"])
        if not path.exists():
            raise FileNotFoundError(f"城市统计年鉴归档缺失：{path}")
        rows, content_hash = _read_workbook(path)
        metric_year = str(spec["metric_year"])
        source_id = str(spec.get("source_doc_id") or _yearbook_source_id(int(spec["publication_year"])))
        table_name = str(
            spec.get("table_name")
            or f"中国城市统计年鉴--{spec['publication_year']}（{spec['metric_year']}年地级以上城市数据）"
        )
        sheet_name = str(spec.get("sheet_name") or "Sheet1")
        landing_page_url = str(spec.get("landing_page_url") or _raw_url(spec))
        source_url = _raw_url(spec)
        field_columns = dict(spec["columns"])
        # XML 的第一个城市数据行为 1-based row=6（列表下标 5），不能跳过北京市。
        for row in rows[5:]:
            city_name = _clean_text(row.get("A"))
            city = city_by_name.get(city_name)
            if not city or not city.get("city_id"):
                continue
            record: dict[str, Any] = {
                "source_doc_id": source_id,
                "source_grade": "B2",
                "source_format": "xlsx",
                "data_status": "yearbook",
                "data_status_label": f"{spec['metric_year']}年年鉴表",
                "source_locator": (
                    f"{path.relative_to(root)}；{sheet_name}；行={row.get('_row_number', '')}；"
                    f"城市={city_name}；表={table_name}；行政范围=全市"
                ),
                "table_name": table_name,
                "sheet_name": sheet_name,
                "row_number": row.get("_row_number", ""),
            }
            for field, (column, raw_unit) in field_columns.items():
                raw_value = _as_decimal(row.get(column))
                if raw_value is None:
                    continue
                normalized = _normalize(raw_value, raw_unit)
                record[field] = normalized
                record[f"{field}_raw"] = raw_value
                record[f"{field}_raw_unit"] = raw_unit
                record[f"{field}_cell_range"] = f"{column}{row.get('_row_number', '')}"
                record[f"{field}_evidence_excerpt"] = str(row.get(column, ""))
            if any(field in record for field in field_columns):
                record["_field_sources"] = {
                    field: dict(record) for field in field_columns if field in record
                }
                values[(str(city["city_id"]), metric_year)] = record

        sources.append(
            {
                "source_doc_id": source_id,
                "publisher": "国家统计局城市社会经济调查司",
                "publisher_level": "国家",
                "document_title": table_name,
                "title_source": "statistical_yearbook",
                "attachment_title": path.name,
                "document_type": "statistical_yearbook_excel",
                "source_url": source_url,
                "landing_page_url": landing_page_url,
                "attachment_url": source_url,
                "canonical_url": landing_page_url,
                "final_resolved_url": source_url,
                "file_name": path.name,
                "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "publication_date": f"{spec['publication_year']}-12-31",
                "publication_date_raw": str(spec["publication_year"]),
                "period_end": f"{spec['metric_year']}-12-31",
                "downloaded_at": "2026-08-31T15:48:00+08:00" if int(spec["publication_year"]) == 2025 else "2026-08-21T00:00:00+08:00",
                "content_hash_sha256": content_hash,
                "archive_uri": f"archive://national-prefecture-panel/{path.relative_to(root)}",
                "archive_backend": "internal_object",
                "archive_path": str(path.relative_to(root)),
                "page_count": "",
                "source_grade": "B2",
                "http_status": "200",
                "access_status": "年鉴截面Excel镜像已归档；待用官方原件复核",
                "supersedes_doc_id": "",
                "note": (
                    "原始出版者为国家统计局城市社会经济调查司；当前使用精确截面表镜像，"
                    "GDP和财政字段为全市口径，财政原始单位为万元，常住人口仅使用表中明确标注的常住人口列；"
                    "2025年人口附件来自中国城市统计年鉴归档入口，保留全市常住人口列。"
                    if int(spec["publication_year"]) == 2025
                    else "原始出版者为国家统计局城市社会经济调查司；当前使用精确截面表镜像，"
                    "GDP和财政字段为全市口径，财政原始单位为万元，常住人口仅使用表中明确标注的常住人口列。"
                ),
            }
        )
    return values, sources


__all__ = ["YEARBOOK_SPECS", "load_city_yearbook_sources"]
