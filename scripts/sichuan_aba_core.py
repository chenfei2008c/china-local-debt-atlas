"""四川省阿坝州 2018—2021 年核心经济财政公报来源。

四份来源均为阿坝州统计局/阿坝州人民政府公开的年度统计公报，明确给出
全州口径的现价 GDP、按可比价格计算的 GDP 实际增速、一般公共预算收入和支出。
公报中的部分数据为初步统计数，因此保留 preliminary 状态，不把公报数伪装成最终决算。
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw" / "province_fiscal" / "sichuan" / "aba"
CITY_NAME = "阿坝藏族羌族自治州"
CITY_ID = "CN-513200"


def _pattern(year: int, label: str, unit: str) -> str:
    return (
        rf"城市={re.escape(CITY_NAME)}｜年度={year}｜"
        rf"(?:(?!城市=).)*?{re.escape(label)}=([0-9.,-]+){re.escape(unit)}"
    )


def _source(
    *,
    year: int,
    url: str,
    publication_date: str,
    path_name: str,
    note: str,
) -> dict:
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
        "source_doc_id": f"SRC-A2-SICHUAN-ABA-{year}-CORE",
        "url": url,
        "path": path,
        "text_path": path,
        "text_is_curated": True,
        "document_title": f"阿坝藏族羌族自治州{year}年国民经济和社会发展统计公报",
        "publisher": "阿坝藏族羌族自治州人民政府、阿坝州统计局",
        "publisher_level": "州级政府/统计机构",
        "publication_date": publication_date,
        "source_grade": "A2",
        "source_format": "txt",
        "raw_unit": "亿元",
        "raw_units": {field: labels[field][1] for field in fields},
        "data_status": "preliminary",
        "data_status_label": f"{year}年统计公报数（初步统计）",
        "document_type": "州级统计公报核心经济财政指标",
        "access_status": "官方网页精确摘录已归档",
        "page_number": "官方网页正文：综合部分、财政金融部分",
        "page_count": "1",
        "patterns": {
            field: _pattern(year, labels[field][0], labels[field][1])
            for field in fields
        },
        "note": note,
    }


SICHUAN_ABA_CORE_SOURCES = (
    _source(
        year=2018,
        url="https://abazhou.gov.cn/abazhou/c109400/201903/25d704553e8648d0bcb58f54bb7e6b24.shtml",
        publication_date="2019-03-20",
        path_name="aba_2018_statistical_bulletin_core_excerpt.txt",
        note=(
            "A2阿坝州统计局官方统计公报；全州地区生产总值306.67亿元，按可比价计算增长4.7%；"
            "地方公共财政预算收入24.66亿元，一般公共预算支出291.69亿元。GDP绝对数为当年价格，"
            "增长速度按可比价格，财政数为全州口径；公报注明部分数据为初步统计数。"
        ),
    ),
    _source(
        year=2019,
        url="https://www.abazhou.gov.cn/abazhou/c109400/202004/b21d07c441ee40f6a934684fddea8ff2.shtml",
        publication_date="2020-04-23",
        path_name="aba_2019_statistical_bulletin_core_excerpt.txt",
        note=(
            "A2阿坝州统计局官方统计公报；全州地区生产总值390.08亿元，按可比价计算增长6.1%；"
            "一般公共预算收入26.40亿元，支出305.88亿元。公报说明GDP增长速度按可比价格计算，"
            "财政数来自州财政局且为全州口径，部分数据为初步统计数。"
        ),
    ),
    _source(
        year=2020,
        url="https://abazhou.gov.cn/abazhou/c109400/202104/db754eb02e09411286efd4a42a860538.shtml",
        publication_date="2021-04-06",
        path_name="aba_2020_statistical_bulletin_core_excerpt.txt",
        note=(
            "A2阿坝州统计局官方统计公报；全州地区生产总值411.75亿元，按可比价格计算增长3.3%；"
            "一般公共预算收入28.73亿元，支出368.38亿元。公报说明GDP增长速度按可比价格计算，"
            "财政数来自州财政局且为全州口径，部分数据为初步统计数。"
        ),
    ),
    _source(
        year=2021,
        url="https://www.abazhou.gov.cn/abazhou/c109400/202204/402af59c81134632aaa7c04c09099d74.shtml",
        publication_date="2022-04-01",
        path_name="aba_2021_statistical_bulletin_core_excerpt.txt",
        note=(
            "A2阿坝州统计局官方统计公报；全州地区生产总值449.63亿元，按可比价格计算增长7.5%；"
            "一般公共预算收入31.85亿元，支出310.16亿元。公报说明GDP增长速度按可比价格计算，"
            "财政数来自州财政局且为全州口径，部分数据为初步统计数。"
        ),
    ),
)
