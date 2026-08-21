"""2024 年省级地级行政区经济财政精确表适配器。"""

from __future__ import annotations

from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "raw/province_fiscal/2024/secondary/yunnan_2024_city_fiscal_rating_report.pdf"
TEXT = ROOT / "raw/province_fiscal/2024/secondary/yunnan_2024_city_fiscal_rating_report_excerpt.txt"
URL = "https://static.sse.com.cn/disclosure/bond/announcement/corporate/c/new/2025-06-30/152929_20250630_WUHS.pdf"
N = r"[0-9][0-9,]*(?:\.[0-9]+)?"


def _source(city_name: str, city_id: str) -> dict[str, Any]:
    compact = city_name.replace(" ", "")
    return {
        "year": 2024,
        "city_name": city_name,
        "city_id": city_id,
        "source_doc_id": f"SRC-B2-YUNNAN-REGIONAL-FISCAL-2024-{city_id.split('-')[-1]}",
        "url": URL,
        "path": PDF,
        "text_path": TEXT,
        "text_is_curated": True,
        "document_title": "2024年云南省部分地级行政区经济财政指标情况",
        "publisher": "中证鹏元资信评估股份有限公司（上海证券交易所公开披露）",
        "publisher_level": "评级机构公开披露精确表格",
        "publication_date": "2025-06-30",
        "source_grade": "B2",
        "source_format": "pdf",
        "data_status": "execution",
        "data_status_label": "2024年执行数",
        "document_type": "评级报告地级行政区经济财政指标表",
        "page_number": "PDF第9页表2",
        "raw_unit": "亿元",
        "raw_units": {"gdp_real_growth_pct": "%"},
        "patterns": {
            "gdp_current_100m": rf"{compact}｜({N})｜[-0-9.]+%｜{N}｜({N})｜({N})",
            "gdp_real_growth_pct": rf"{compact}｜{N}｜([-0-9.]+)%｜{N}｜{N}｜{N}",
            "general_public_revenue_100m": rf"{compact}｜{N}｜[-0-9.]+%｜{N}｜({N})｜{N}",
            "gov_fund_revenue_100m": rf"{compact}｜{N}｜[-0-9.]+%｜{N}｜{N}｜({N})",
        },
        "source_locator": f"PDF第9页表2；城市={city_name}；2024年全市/全州执行数",
        "note": "B2精确表格；取云南省部分地级行政区表中全市/全州列，GDP增速为不变价增速；不使用人均GDP或图表估读值。",
    }


REGIONAL_FISCAL_2024_SOURCES = tuple(
    _source(city_name, city_id)
    for city_name, city_id in (
        ("昆明市", "CN-530100"),
        ("曲靖市", "CN-530300"),
        ("红河哈尼族彝族自治州", "CN-532500"),
        ("玉溪市", "CN-530400"),
        ("大理白族自治州", "CN-532900"),
        ("昭通市", "CN-530600"),
        ("普洱市", "CN-530800"),
        ("临沧市", "CN-530900"),
        ("西双版纳傣族自治州", "CN-532800"),
        ("丽江市", "CN-530700"),
    )
)


__all__ = ["REGIONAL_FISCAL_2024_SOURCES"]
