"""《海南统计年鉴·2022》中的青海省各市（州）2018—2019年财政批次。

海南州统计局编印的官方年鉴第222—223印刷页（PDF第234—235页）交叉披露青海省各市州
地方一般公共预算收入和一般公共预算支出。这里接入六个地级行政单元的全域值；西宁和海东
已有更高优先级或其他批次时由主表字段等级规则处理。
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
YEARBOOK_URL = (
    "https://www.hainanzhou.gov.cn/upload/main/infopublicity/publicinformation/file/2023/12/17/202312172146284831.pdf"
)
RAW_DIR = ROOT / "raw/province_fiscal/2022/official"

TARGET_CITIES = {
    "海北藏族自治州": "CN-632200",
    "黄南藏族自治州": "CN-632300",
    "海南藏族自治州": "CN-632500",
    "果洛藏族自治州": "CN-632600",
    "玉树藏族自治州": "CN-632700",
    "海西蒙古族藏族自治州": "CN-632800",
}

FISCAL_VALUES = {
    2018: {
        "海北藏族自治州": ("4.44", "79.30"),
        "黄南藏族自治州": ("3.16", "86.04"),
        "海南藏族自治州": ("10.45", "107.42"),
        "果洛藏族自治州": ("2.31", "77.78"),
        "玉树藏族自治州": ("2.10", "100.96"),
        "海西蒙古族藏族自治州": ("54.48", "138.18"),
    },
    2019: {
        "海北藏族自治州": ("3.75", "82.98"),
        "黄南藏族自治州": ("3.48", "109.03"),
        "海南藏族自治州": ("10.17", "116.51"),
        "果洛藏族自治州": ("1.89", "93.81"),
        "玉树藏族自治州": ("1.98", "153.45"),
        "海西蒙古族藏族自治州": ("49.52", "163.58"),
    },
}

QINGHAI_2018_2019_SOURCE_IDS = {
    "SRC-A2-HAINAN-YEARBOOK-2022-QINGHAI-2018-FISCAL",
    "SRC-A2-HAINAN-YEARBOOK-2022-QINGHAI-2019-FISCAL",
}


def _pattern(city_name: str, year: int, label: str) -> str:
    return (
        rf"城市={re.escape(city_name)}｜年度={year}｜"
        rf"(?:(?!城市=).)*?{re.escape(label)}=([0-9.,-]+)亿元"
    )


def _config(year: int, city_name: str, city_id: str) -> dict:
    path = RAW_DIR / f"qinghai_hainan_yearbook_{year}_fiscal_excerpt.txt"
    source_id = f"SRC-A2-HAINAN-YEARBOOK-2022-QINGHAI-{year}-FISCAL"
    return {
        "year": year,
        "city_name": city_name,
        "city_id": city_id,
        "source_doc_id": source_id,
        "url": YEARBOOK_URL,
        "path": path,
        "text_path": path,
        "text_is_curated": True,
        "document_title": "海南统计年鉴·2022：青海省各市（州）地方一般公共预算收入和一般公共预算支出",
        "publisher": "海南藏族自治州统计局",
        "publisher_level": "州级统计机构",
        "publication_date": "2023-11-01",
        "source_grade": "A2",
        "source_format": "txt",
        "raw_unit": "亿元",
        "raw_units": {
            "general_public_revenue_100m": "亿元",
            "general_public_expenditure_100m": "亿元",
        },
        "data_status": "reported",
        "data_status_label": f"{year}年官方统计年鉴表值",
        "document_type": "州级统计年鉴跨省市州财政表",
        "page_number": "PDF第234—235页（印刷页222—223）",
        "title_source": "official_pdf_title_page",
        "access_status": "官方PDF精确摘录已归档",
        "table_name": "青海省各市（州）地方一般公共预算收入、一般公共预算支出",
        "patterns": {
            "general_public_revenue_100m": _pattern(city_name, year, "一般公共预算收入"),
            "general_public_expenditure_100m": _pattern(city_name, year, "一般公共预算支出"),
        },
        "note": (
            "A2海南藏族自治州统计局编印《海南统计年鉴·2022》官方PDF跨表；"
            f"第{year}年值来自青海省各市（州）表，单位亿元，行政范围为市州全域，"
            "不使用市本级或区县值。"
        ),
    }


QINGHAI_2018_2019_FISCAL_SOURCES = tuple(
    _config(year, city_name, city_id)
    for year in (2018, 2019)
    for city_name, city_id in TARGET_CITIES.items()
)
