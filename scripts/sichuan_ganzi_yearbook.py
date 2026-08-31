"""四川省甘孜州官方统计年鉴 2018—2021 年核心经济财政批次。

《甘孜统计年鉴—2022》由甘孜州统计局编印并公开于甘孜州政府文件域。年鉴的
“甘孜州主要经济指标数据”表提供2017—2021年州级 GDP 总量及增速；财政部分
的“甘孜州各县（市）一般公共预算收入/支出总量”表提供同一时期州级全域合计。
这里逐年接入州级合计，不把县市行相加后冒充州级值。
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw" / "province_fiscal" / "sichuan" / "ganzi"
CITY_NAME = "甘孜藏族自治州"
CITY_ID = "CN-513300"


def _pattern(year: int, label: str, unit: str) -> str:
    return (
        rf"城市={re.escape(CITY_NAME)}｜年度={year}｜"
        rf"(?:(?!城市=).)*?{re.escape(label)}=([0-9.,-]+){re.escape(unit)}"
    )


def _source(*, year: int, path_name: str) -> dict:
    fields = (
        "gdp_current_100m",
        "gdp_real_growth_pct",
        "general_public_revenue_100m",
        "general_public_expenditure_100m",
    )
    labels = {
        "gdp_current_100m": ("GDP", "万元"),
        "gdp_real_growth_pct": ("GDP增速", "%"),
        "general_public_revenue_100m": ("一般公共预算收入", "万元"),
        "general_public_expenditure_100m": ("一般公共预算支出", "万元"),
    }
    path = RAW_DIR / path_name
    return {
        "year": year,
        "city_name": CITY_NAME,
        "city_id": CITY_ID,
        "source_doc_id": f"SRC-A2-SICHUAN-GANZI-YEARBOOK-2022-{year}-CORE",
        "url": "https://files.gzz.gov.cn/upload/file/20/zhengwen/fbac560e35af4e1c948edde73cfd9f4c.pdf",
        "path": path,
        "text_path": path,
        "text_is_curated": True,
        "document_title": "甘孜统计年鉴—2022（2017—2021年主要经济指标及财政表）",
        "publisher": "甘孜藏族自治州统计局",
        "publisher_level": "州级统计机构",
        "publication_date": "2023-12-27",
        "source_grade": "A2",
        "source_format": "txt",
        "raw_unit": "万元",
        "raw_units": {field: labels[field][1] for field in fields},
        "data_status": "reported",
        "data_status_label": f"{year}年官方统计年鉴表值",
        "document_type": "州级统计年鉴多年度核心经济财政表",
        "access_status": "官方统计年鉴精确摘录已归档",
        "page_number": "年鉴PDF第549—551、599—600页；主要经济指标及财政表",
        "page_count": "612",
        "patterns": {
            field: _pattern(year, labels[field][0], labels[field][1])
            for field in fields
        },
        "note": (
            "A2甘孜州统计局官方统计年鉴精确摘录；GDP和财政字段均为甘孜州全州合计，"
            "GDP总量来自主要经济指标表，增速为按可比价口径的同比增速，财政收入/支出来自"
            "财政总量表；年鉴原始单位为万元，统一换算为亿元。"
        ),
    }


SICHUAN_GANZI_YEARBOOK_SOURCES = tuple(
    _source(
        year=year,
        path_name=f"ganzi_{year}_yearbook_2022_core_excerpt.txt",
    )
    for year in range(2018, 2022)
)
