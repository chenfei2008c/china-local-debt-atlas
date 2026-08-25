"""大公国际公开评级报告中的城市经济财政精确表格（B2）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw" / "province_fiscal" / "2025" / "secondary"
N = r"[0-9]+(?:\.[0-9]+)?"


def _source(
    *, year: int, city_name: str, city_id: str, slug: str, url: str,
    pdf_name: str, excerpt_name: str, fields: dict[str, str], page_number: str
) -> dict[str, Any]:
    prefix = rf"城市={city_name}｜年度={year}｜"
    return {
        "year": year,
        "city_name": city_name,
        "city_id": city_id,
        "source_doc_id": f"SRC-B2-DAGONG-CITY-{year}-{slug.upper()}",
        "url": url,
        "landing_page_url": url,
        "attachment_url": url,
        "download_url": url,
        "path": RAW / pdf_name,
        "text_path": RAW / excerpt_name,
        "text_is_curated": True,
        "document_title": f"大公国际{city_name}2026年度跟踪评级报告",
        "publisher": "大公国际资信评估有限公司",
        "publisher_level": "公开评级报告B2精确表格来源",
        "publication_date": "2026-06-01",
        "source_grade": "B2",
        "source_format": "pdf",
        "raw_unit": "亿元",
        "raw_units": {"gdp_real_growth_pct": "%", "resident_population_10k": "万人"},
        "data_status": "execution",
        "data_status_label": f"{year}年执行数（评级报告精确表格）",
        "document_type": "评级报告城市经济财政指标表",
        "page_number": page_number,
        "page_count": "",
        "patterns": {
            field: rf"{prefix}.*?{label}=({N})(?=｜|城市=|说明:|$)"
            for field, label in fields.items()
        },
        "source_locator": f"{excerpt_name}；{page_number}；城市={city_name}；{year}年全市口径",
        "note": "大公国际公开报告表2逐项列示，年度、单位和行政范围明确；2025年按执行数登记。",
    }


def _build_sources() -> Iterable[dict[str, Any]]:
    common = {
        "zibo": {
            "city_name": "淄博市", "city_id": "CN-370300", "slug": "zibo",
            "url": "https://www.dagongcredit.com/dggj/content_file/ratingNotice/regularTracking/2026/6/272fb2976ff940b1963a4ca8da1fd7b3.pdf",
            "pdf_name": "zibo_2025_dagong_rating_report.pdf",
            "excerpt_name": "zibo_2024_2025_dagong_rating_table_excerpt.txt",
        },
        "jinan": {
            "city_name": "济南市", "city_id": "CN-370100", "slug": "jinan",
            "url": "https://www.dagongcredit.com/dggj/content_file/ratingNotice/regularTracking/2026/6/e836b97fd4c34ab5aa12e0262b99c16d.pdf",
            "pdf_name": "jinan_2025_dagong_rating_report.pdf",
            "excerpt_name": "jinan_2024_2025_dagong_rating_table_excerpt.txt",
        },
        "zhumadian": {
            "city_name": "驻马店市", "city_id": "CN-411700", "slug": "zhumadian",
            "url": "https://www.dagongcredit.com/dggj/content_file/ratingNotice/regularTracking/2026/6/ca04b21378cb424488ba092b7ddd92e3.pdf",
            "pdf_name": "zhumadian_2025_dagong_rating_report.pdf",
            "excerpt_name": "zhumadian_2024_2025_dagong_rating_table_excerpt.txt",
        },
    }
    rows = {
        "zibo": {
            2024: {"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速", "general_public_revenue_100m": "一般公共预算收入", "general_public_expenditure_100m": "一般公共预算支出", "gov_fund_revenue_100m": "政府性基金收入"},
            2025: {"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速", "resident_population_10k": "年末常住人口"},
        },
        "jinan": {
            2024: {"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速", "general_public_revenue_100m": "一般公共预算收入", "general_public_expenditure_100m": "一般公共预算支出", "gov_fund_revenue_100m": "政府性基金收入"},
            2025: {"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速", "resident_population_10k": "年末常住人口"},
        },
        "zhumadian": {
            2024: {"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速", "general_public_revenue_100m": "一般公共预算收入", "general_public_expenditure_100m": "一般公共预算支出", "gov_fund_revenue_100m": "政府性基金收入"},
            2025: {"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速", "general_public_revenue_100m": "一般公共预算收入", "general_public_expenditure_100m": "一般公共预算支出", "gov_fund_revenue_100m": "政府性基金收入"},
        },
    }
    for slug, years in rows.items():
        for year, fields in years.items():
            yield _source(year=year, fields=fields, page_number="PDF第9页表2", **common[slug])


DAGONG_CITY_FISCAL_SOURCES = tuple(_build_sources())

__all__ = ["DAGONG_CITY_FISCAL_SOURCES"]
