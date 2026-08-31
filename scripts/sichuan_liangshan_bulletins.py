"""四川省凉山州 2018—2021 年核心经济财政公报来源。

四份统计公报均明确给出凉山彝族自治州全州口径的现价 GDP、按可比价格
计算的 GDP 实际增速、一般公共预算收入和一般公共预算支出。当前可稳定
访问的版本是公开转载的官方原文，页面逐份标注原发布机构为凉山彝族自治
州统计局，因此按 B2 精确公开转载来源登记，不冒充州政府官网 A2。
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw" / "province_fiscal" / "sichuan" / "liangshan"
CITY_NAME = "凉山彝族自治州"
CITY_ID = "CN-513400"


def _pattern(year: int, label: str, unit: str) -> str:
    return (
        rf"城市={re.escape(CITY_NAME)}｜年度={year}｜"
        rf"(?:(?!城市=).)*?{re.escape(label)}=([0-9.,-]+){re.escape(unit)}"
    )


def _source(*, year: int, url: str, publication_date: str, path_name: str) -> dict:
    fields = (
        "gdp_current_100m",
        "gdp_real_growth_pct",
        "general_public_revenue_100m",
        "general_public_expenditure_100m",
    )
    labels = {
        "gdp_current_100m": ("GDP", "亿元"),
        "gdp_real_growth_pct": ("GDP增速", "%"),
        "general_public_revenue_100m": ("一般公共预算收入", "亿元"),
        "general_public_expenditure_100m": ("一般公共预算支出", "亿元"),
    }
    path = RAW_DIR / path_name
    return {
        "year": year,
        "city_name": CITY_NAME,
        "city_id": CITY_ID,
        "source_doc_id": f"SRC-B2-SICHUAN-LIANGSHAN-BULLETIN-{year}-CORE",
        "url": url,
        "path": path,
        "text_path": path,
        "text_is_curated": True,
        "document_title": f"凉山州统计局{year}年国民经济和社会发展统计公报",
        "publisher": "凉山彝族自治州统计局（官方原文公开转载）",
        "publisher_level": "州级统计机构原始发布／公开转载存档",
        "publication_date": publication_date,
        "source_grade": "B2",
        "source_format": "txt",
        "raw_unit": "亿元",
        "raw_units": {field: labels[field][1] for field in fields},
        "data_status": "preliminary",
        "data_status_label": f"{year}年统计公报数（初步统计）",
        "document_type": "州级统计公报核心经济财政指标（官方原文公开转载）",
        "access_status": "官方原文公开转载精确摘录已归档",
        "page_number": "网页正文：综合部分、财政金融部分",
        "page_count": "1",
        "patterns": {
            field: _pattern(year, labels[field][0], labels[field][1])
            for field in fields
        },
        "note": (
            "B2凉山州统计局官方统计公报公开转载精确摘录；全州地区生产总值和财政收支均为"
            "凉山彝族自治州全州口径，GDP绝对数按当年价格，增长速度按可比价格计算；公报注明"
            "部分数据为初步统计数。公开转载页保留原文标题、原发布机构、发布日期和逐项数值，"
            "因此可用于升级暂存值，但不标记为地方政府官网A2。"
        ),
    }


SICHUAN_LIANGSHAN_BULLETIN_SOURCES = (
    _source(
        year=2018,
        url="https://tjgb.hongheiku.com/9980.html",
        publication_date="2019-05-01",
        path_name="liangshan_2018_statistical_bulletin_core_excerpt.txt",
    ),
    _source(
        year=2019,
        url="https://tjgb.hongheiku.com/9982.html",
        publication_date="2020-06-01",
        path_name="liangshan_2019_statistical_bulletin_core_excerpt.txt",
    ),
    _source(
        year=2020,
        url="https://www.zgcounty.com/wap/news/45090.html",
        publication_date="2021-05-07",
        path_name="liangshan_2020_statistical_bulletin_core_excerpt.txt",
    ),
    _source(
        year=2021,
        url="https://www.neac.gov.cn/seac/c103544/202210/1159327.shtml",
        publication_date="2022-08-30",
        path_name="liangshan_2021_statistical_bulletin_core_excerpt.txt",
    ),
)
