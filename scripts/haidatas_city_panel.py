"""海数据公开资源中的全国地级市经济财政面板 D 级适配器。

该文件是第三方整理的公开数据资源，不是财政部门原始发布件。适配器只读取
工作簿中的精确单元格，把 2018—2021 年能与本项目城市主表按省份、城市、年份
唯一匹配的字段作为 D 级 provisional 候选，交由主采集器只补原始空值。

人口列虽然标注为“人口(万人)”，但资源页没有证明其为年末常住人口，因此本
适配器刻意不映射该列。地方政府债务余额/限额列也只作为 D 级临时字段，不能
提高高等级定稿率；一般债、专项债分项及城投债务列不反推主表字段。
"""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping
from zipfile import ZipFile
from xml.etree import ElementTree as ET


SNAPSHOT_PATH = Path(
    "raw/province_fiscal/haidatas/national_city_economic_full_2015_2021.xlsx"
)
SOURCE_DOC_ID = "SRC-D-HAIDATAS-NATIONAL-CITY-ECONOMIC-2015-2021"
SOURCE_GRADE = "D"
SOURCE_URL = (
    "https://www.haidatas.com/dataset/7acc6903-a088-4ae0-a17e-fb044be43187/"
    "resource/156220b3-5cb2-4530-abd0-30931b03657c/download/"
    "%E5%85%A8%E5%9B%BD%E5%9C%B0%E7%BA%A7%E5%B8%82%E7%BB%8F%E6%B5%8E%E5%AE%8C%E6%95%B4%E6%95%B0%E6%8D%AE%281%29.xlsx"
)
LANDING_PAGE_URL = "https://www.haidatas.com/dataset/quanguodijishijingjiwanzhengshuju"
DOWNLOADED_AT = "2026-08-26T00:00:00+08:00"

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_FIELD_COLUMNS = {
    "GDP(亿元)": ("gdp_current_100m", "亿元"),
    "GDP增速(%)": ("gdp_real_growth_pct", "%"),
    "一般公共预算收入(亿元)": ("general_public_revenue_100m", "亿元"),
    "一般公共预算支出(亿元)": ("general_public_expenditure_100m", "亿元"),
    "政府性基金收入(亿元)": ("gov_fund_revenue_100m", "亿元"),
    "地方政府债务余额(亿元)": ("statutory_debt_balance_100m", "亿元"),
    "地方政府债务限额(亿元)": ("statutory_debt_limit_100m", "亿元"),
}


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).strip()


def _name_key(value: Any) -> str:
    text = _clean_text(value)
    replacements = (
        ("恩施土家族苗族自治州", "恩施州"),
        ("黔西南布依族苗族自治州", "黔西南州"),
        ("黔东南苗族侗族自治州", "黔东南州"),
        ("黔南布依族苗族自治州", "黔南州"),
        ("延边朝鲜族自治州", "延边州"),
        ("湘西土家族苗族自治州", "湘西州"),
        ("大理白族自治州", "大理州"),
        ("楚雄彝族自治州", "楚雄州"),
        ("红河哈尼族彝族自治州", "红河州"),
        ("文山壮族苗族自治州", "文山州"),
        ("西双版纳傣族自治州", "西双版纳州"),
        ("德宏傣族景颇族自治州", "德宏州"),
        ("迪庆藏族自治州", "迪庆州"),
        ("凉山彝族自治州", "凉山州"),
        ("阿坝藏族羌族自治州", "阿坝州"),
        ("甘南藏族自治州", "甘南州"),
        ("临夏回族自治州", "临夏州"),
        ("海西蒙古族藏族自治州", "海西州"),
        ("海南藏族自治州", "海南州"),
        ("海北藏族自治州", "海北州"),
        ("黄南藏族自治州", "黄南州"),
        ("玉树藏族自治州", "玉树州"),
        ("果洛藏族自治州", "果洛州"),
        ("博尔塔拉蒙古自治州", "博尔塔拉州"),
        ("巴音郭楞蒙古自治州", "巴音郭楞州"),
        ("昌吉回族自治州", "昌吉州"),
        ("伊犁哈萨克自治州", "伊犁州"),
        ("克孜勒苏柯尔克孜自治州", "克孜勒苏州"),
    )
    for source, target in replacements:
        text = text.replace(source, target)
    return re.sub(r"(市|地区|盟|州)$", "", text)


def _decimal(value: Any) -> Decimal | None:
    text = _clean_text(value).replace(",", "").replace("，", "")
    if not text or text in {"—", "-", "–", "…", "...", "/", "--"}:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _column_number(ref: str) -> int:
    result = 0
    for char in re.match(r"[A-Z]+", ref).group(0):
        result = result * 26 + ord(char) - ord("A") + 1
    return result


def _column_label(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _cell_value(cell: ET.Element, shared: list[str]) -> str:
    value_node = cell.find("m:v", _NS)
    value = value_node.text if value_node is not None else ""
    if cell.attrib.get("t") == "s" and value:
        return shared[int(value)]
    if cell.attrib.get("t") == "inlineStr":
        return "".join(item.text or "" for item in cell.findall(".//m:t", _NS))
    return value


def _read_workbook(path: Path) -> tuple[list[dict[int, str]], str]:
    with ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = [
                "".join(text.text or "" for text in item.findall(".//m:t", _NS))
                for item in shared_root.findall("m:si", _NS)
            ]
        sheet_root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        rows: list[dict[int, str]] = []
        for row in sheet_root.findall(".//m:sheetData/m:row", _NS):
            values: dict[int, str] = {0: row.attrib.get("r", "")}
            for cell in row.findall("m:c", _NS):
                ref = cell.attrib.get("r", "")
                column = re.match(r"[A-Z]+", ref)
                if column:
                    values[_column_number(column.group(0))] = _cell_value(cell, shared)
            rows.append(values)
    return rows, hashlib.sha256(path.read_bytes()).hexdigest()


def _source_record(path: Path, content_hash: str) -> dict[str, Any]:
    archive_path = str(SNAPSHOT_PATH)
    return {
        "source_doc_id": SOURCE_DOC_ID,
        "publisher": "海数据（公开数据资源镜像）",
        "publisher_level": "第三方公开数据平台",
        "document_title": "全国地级市经济完整数据（2015—2021）",
        "title_source": "public_dataset_catalog",
        "attachment_title": path.name,
        "document_type": "第三方整理城市经济财政面板 Excel",
        "source_url": SOURCE_URL,
        "landing_page_url": LANDING_PAGE_URL,
        "attachment_url": SOURCE_URL,
        "canonical_url": LANDING_PAGE_URL,
        "final_resolved_url": SOURCE_URL,
        "file_name": path.name,
        "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "publication_date": "2024-11-10",
        "publication_date_raw": "海数据资源页 metadata_modified=2024-11-10",
        "period_end": "2021-12-31",
        "downloaded_at": DOWNLOADED_AT,
        "content_hash_sha256": content_hash,
        "archive_uri": f"archive://national-prefecture-panel/{archive_path}",
        "archive_backend": "internal_object",
        "archive_path": archive_path,
        "page_count": "",
        "source_grade": SOURCE_GRADE,
        "http_status": "200",
        "access_status": "第三方资源可直接下载；非官方原始附件，授权状态未注明",
        "supersedes_doc_id": "",
        "note": (
            "D级 provisional，仅用于降低原始数值空缺，不计入高等级定稿率；"
            "资源页标注数据来源为公开数据，但未提供逐值官方附件链条。人口列未接入，"
            "因为资源页没有证明其为年末常住人口；地方政府债务余额/限额仅按列名接入，"
            "须回到财政部门法定债务表复核。"
        ),
    }


def load_haidatas_city_panel_sources(
    root: Path, city_master: list[Mapping[str, Any]]
) -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    """读取海数据 Excel，返回 2018—2021 年 D 级城市年度候选。"""

    path = root / SNAPSHOT_PATH
    if not path.exists():
        return {}, []
    rows, content_hash = _read_workbook(path)
    if not rows:
        return {}, [_source_record(path, content_hash)]

    # 工作簿首行是列名；按列名定位而不是依赖固定列号，防止上游添加列后错位。
    headers = {
        value: column
        for column, value in rows[0].items()
        if column != 0 and _clean_text(value)
    }
    required = {"省份", "地级市", "年份", *_FIELD_COLUMNS}
    missing = required - set(headers)
    if missing:
        raise ValueError(f"海数据城市面板缺少列：{sorted(missing)}")

    city_by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
    city_by_key_year: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for city in city_master:
        city_id = str(city.get("city_id") or "")
        if not city_id:
            continue
        province_key = _name_key(city.get("province_name"))
        city_key = _name_key(city.get("city_name_cn"))
        metric_year = str(city.get("metric_year") or "")
        key = (
            province_key,
            city_key,
        )
        city_by_key.setdefault(key, city)
        if metric_year:
            city_by_key_year[(province_key, city_key, metric_year)] = city

    values: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows[1:]:
        year = _decimal(row.get(headers["年份"]))
        if year is None or year != year.to_integral_value() or not 2018 <= int(year) <= 2021:
            continue
        year_text = str(int(year))
        province_key = _name_key(row.get(headers["省份"]))
        city_key = _name_key(row.get(headers["地级市"]))
        city = city_by_key_year.get((province_key, city_key, year_text)) or city_by_key.get(
            (province_key, city_key)
        )
        if not city:
            continue
        city_id = str(city["city_id"])
        record = values.setdefault(
            (city_id, year_text),
            {
                "source_doc_id": SOURCE_DOC_ID,
                "source_grade": SOURCE_GRADE,
                "source_format": "xlsx",
                "source_platform": "haidatas",
                "data_status": "provisional",
                "data_status_label": f"{year_text}年第三方公开面板临时值",
                "city_id": city_id,
                "city_name": str(city.get("city_name_cn") or ""),
                "year": year_text,
                "_field_sources": {},
            },
        )
        row_number = str(row.get(0) or "")
        for source_column, (field, raw_unit) in _FIELD_COLUMNS.items():
            raw = _decimal(row.get(headers[source_column]))
            if raw is None:
                continue
            value = _q2(raw)
            record[field] = value
            record[f"{field}_raw_100m"] = raw
            record[f"{field}_raw_unit"] = raw_unit
            cell_range = f"{_column_label(headers[source_column])}{row_number}"
            record[f"{field}_cell_range"] = cell_range
            record[f"{field}_evidence_excerpt"] = (
                f"省份={row.get(headers['省份'])};地级市={row.get(headers['地级市'])};"
                f"年份={year_text};{source_column}={raw}"
            )
            record["_field_sources"][field] = {
                "source_doc_id": SOURCE_DOC_ID,
                "source_grade": SOURCE_GRADE,
                "source_format": "xlsx",
                "source_platform": "haidatas",
                "data_status": "provisional",
                "data_status_label": f"{year_text}年第三方公开面板临时值",
                "source_locator": (
                    f"{SNAPSHOT_PATH}；Sheet=ALL；列={source_column}；"
                    f"省份={row.get(headers['省份'])}；地级市={row.get(headers['地级市'])}；"
                    f"年份={year_text}；行政范围=全市"
                ),
                "table_name": "全国地级市经济完整数据（ALL）",
                "sheet_name": "ALL",
                "row_number": row_number,
                "cell_range": cell_range,
                field: value,
                f"{field}_raw_100m": raw,
                f"{field}_raw_unit": raw_unit,
                f"{field}_evidence_excerpt": record[f"{field}_evidence_excerpt"],
            }

    return values, [_source_record(path, content_hash)]


__all__ = [
    "HAIDATAS_SOURCE_ID",
    "SOURCE_DOC_ID",
    "load_haidatas_city_panel_sources",
]

HAIDATAS_SOURCE_ID = SOURCE_DOC_ID
