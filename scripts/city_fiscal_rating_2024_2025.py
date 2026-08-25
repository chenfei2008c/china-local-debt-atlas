"""已归档评级报告中的 2024—2025 年城市经济财政精确表格。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw" / "province_fiscal" / "2025" / "secondary"
N = r"[0-9]+(?:\.[0-9]+)?"


def _source(
    *,
    year: int,
    city_name: str,
    city_id: str,
    slug: str,
    url: str,
    document_title: str,
    publisher: str,
    publication_date: str,
    pdf_name: str,
    excerpt_name: str,
    page_number: str,
    fields: dict[str, str],
    note: str,
    source_doc_id: str | None = None,
) -> dict[str, Any]:
    row_prefix = rf"城市={city_name}｜年度={year}｜"
    patterns: dict[str, str] = {}
    for field, label in fields.items():
        patterns[field] = rf"{row_prefix}.*?{label}=({N})(?=｜|城市=|说明:|$)"
    return {
        "year": year,
        "city_name": city_name,
        "city_id": city_id,
        "source_doc_id": source_doc_id or f"SRC-B2-CITY-RATING-{year}-{slug.upper()}",
        "url": url,
        "landing_page_url": url,
        "attachment_url": url,
        "download_url": url,
        "path": RAW / pdf_name,
        "text_path": RAW / excerpt_name,
        "text_is_curated": True,
        "document_title": document_title,
        "publisher": publisher,
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": publication_date,
        "source_grade": "B2",
        "source_format": "pdf",
        "raw_unit": "亿元",
        "raw_units": {"gdp_real_growth_pct": "%"},
        "data_status": "execution",
        "data_status_label": f"{year}年执行数（评级报告精确表格）",
        "document_type": "评级报告城市经济财政指标表",
        "page_number": page_number,
        "page_count": "",
        "patterns": patterns,
        "source_locator": f"{excerpt_name}；{page_number}；城市={city_name}；{year}年全市口径",
        "note": note,
    }


_COMMON = {
    "handan": {
        "city_name": "邯郸市",
        "city_id": "CN-130400",
        "slug": "handan",
        "url": "https://www.chinamoney.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3375478&mode=save&priority=0",
        "document_title": "邯郸城市发展投资集团有限公司主体长期信用评级报告",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2026-07-13",
        "pdf_name": "handan_2025_rating_report.pdf",
        "excerpt_name": "handan_2024_2025_rating_table_excerpt.txt",
        "page_number": "PDF第9页图表1、图表2",
    },
    "luzhou": {
        "city_name": "泸州市",
        "city_id": "CN-510500",
        "slug": "luzhou",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/company/c/new/2026-06-24/185565_20260624_YHTL.pdf",
        "document_title": "泸州市兴泸投资集团有限公司2026年度跟踪评级报告",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2026-06-24",
        "pdf_name": "luzhou_2025_rating_report.pdf",
        "excerpt_name": "luzhou_2024_2025_rating_table_excerpt.txt",
        "page_number": "PDF第10页图表2、图表3",
    },
    "nanping": {
        "city_name": "南平市",
        "city_id": "CN-350700",
        "slug": "nanping",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/corporate/c/new/2026-06-26/152266_20260626_XKKO.pdf",
        "document_title": "南平武夷集团有限公司2026年跟踪评级报告",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2026-06-26",
        "pdf_name": "nanping_2025_rating_report.pdf",
        "excerpt_name": "nanping_2024_2025_rating_table_excerpt.txt",
        "page_number": "PDF第8—9页图表2",
    },
    "ningde": {
        "city_name": "宁德市",
        "city_id": "CN-350900",
        "slug": "ningde",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/company/c/new/2026-03-31/244958_20260331_36ZI.pdf",
        "document_title": "2026年度宁德市国有资产投资经营集团有限公司信用评级报告",
        "publisher": "中诚信国际信用评级有限责任公司",
        "publication_date": "2026-03-31",
        "pdf_name": "ningde_2025_rating_report.pdf",
        "excerpt_name": "ningde_2024_2025_rating_table_excerpt.txt",
        "page_number": "PDF第9页表3",
    },
    "xiamen": {
        "city_name": "厦门市",
        "city_id": "CN-350200",
        "slug": "xiamen",
        "url": "https://www.lhratings.com/reports/B024098-P87735-2026.pdf",
        "document_title": "厦门市2026年地方政府再融资信用报告",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2026-05-07",
        "pdf_name": "xiamen_2025_budget_report.pdf",
        "excerpt_name": "xiamen_2024_2025_rating_table_excerpt.txt",
        "page_number": "PDF第6页基础数据、PDF第9页图表2",
    },
    "zhuhai": {
        "city_name": "珠海市",
        "city_id": "CN-440400",
        "slug": "zhuhai",
        "url": "https://www.chinamoney.org.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3361527&mode=save&priority=0",
        "document_title": "珠海华发综合发展有限公司2026年跟踪评级报告",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2026-06-12",
        "pdf_name": "zhuhai_2025_fiscal_rating.pdf",
        "excerpt_name": "zhuhai_2024_2025_rating_table_excerpt.txt",
        "page_number": "PDF第9页图表2",
    },
    "anqing": {
        "city_name": "安庆市",
        "city_id": "CN-340800",
        "slug": "anqing",
        "url": "https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3359176&mode=save&priority=0",
        "document_title": "桐城经开区建设投资集团有限公司2026年度跟踪评级报告",
        "publisher": "东方金诚国际信用评估有限公司",
        "publication_date": "2026-06-15",
        "pdf_name": "anqing_2025_rating_report.pdf",
        "excerpt_name": "anqing_2024_2025_rating_table_excerpt.txt",
        "page_number": "PDF第20页图表15",
    },
    "foshan": {
        "city_name": "佛山市",
        "city_id": "CN-440600",
        "slug": "foshan",
        "url": "https://www.chinamoney.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3367875&mode=open&priority=0",
        "document_title": "佛山市投资控股集团有限公司2026年度跟踪评级报告",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2026-06-18",
        "pdf_name": "foshan_2025_fiscal_rating.pdf",
        "excerpt_name": "foshan_2024_2025_rating_table_excerpt.txt",
        "page_number": "PDF第10页图表5",
    },
    "xuzhou": {
        "city_name": "徐州市",
        "city_id": "CN-320300",
        "slug": "xuzhou",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/corporate/c/new/2026-06-18/184140_20260618_LON3.pdf",
        "document_title": "徐州高新产业发展投资有限公司2026年跟踪评级报告",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2026-06-18",
        "pdf_name": "xuzhou_2025_finance_rating.pdf",
        "excerpt_name": "xuzhou_2024_2025_rating_table_excerpt.txt",
        "page_number": "PDF第9页图表2、图表3",
    },
    "taizhou": {
        "city_name": "泰州市",
        "city_id": "CN-321200",
        "slug": "taizhou",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/corporate/c/new/2026-06-22/152418_20260622_WNHE.pdf",
        "document_title": "泰州市主要经济财政数据评级报告",
        "publisher": "评级机构公开披露",
        "publication_date": "2026-06-22",
        "pdf_name": "taizhou_2025_finance_rating.pdf",
        "excerpt_name": "taizhou_2024_2025_rating_table_excerpt.txt",
        "page_number": "PDF第9页图表2、PDF第11页图表4",
    },
}


def _build_sources() -> Iterable[dict[str, Any]]:
    rows = {
        "handan": {
            2024: {"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速", "general_public_revenue_100m": "一般公共预算收入", "general_public_expenditure_100m": "一般公共预算支出", "gov_fund_revenue_100m": "政府性基金收入"},
            2025: {"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速"},
        },
        "luzhou": {
            2024: {"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速", "general_public_revenue_100m": "一般公共预算收入", "general_public_expenditure_100m": "一般公共预算支出", "gov_fund_revenue_100m": "政府性基金收入"},
            2025: {"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速"},
        },
        "nanping": {
            2024: {"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速", "general_public_revenue_100m": "一般公共预算收入", "gov_fund_revenue_100m": "政府性基金收入"},
            2025: {"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速", "general_public_revenue_100m": "一般公共预算收入"},
        },
        "ningde": {
            2024: {"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速", "general_public_revenue_100m": "一般公共预算收入", "gov_fund_revenue_100m": "政府性基金收入"},
            2025: {"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速", "general_public_revenue_100m": "一般公共预算收入"},
        },
        "xiamen": {
            2024: {"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速", "general_public_revenue_100m": "一般公共预算收入", "general_public_expenditure_100m": "一般公共预算支出", "gov_fund_revenue_100m": "政府性基金收入"},
            2025: {"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速"},
        },
        "zhuhai": {
            2024: {"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速", "general_public_revenue_100m": "一般公共预算收入", "general_public_expenditure_100m": "一般公共预算支出", "gov_fund_revenue_100m": "政府性基金收入"},
            2025: {"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速", "general_public_revenue_100m": "一般公共预算收入", "general_public_expenditure_100m": "一般公共预算支出"},
        },
        "anqing": {
            2024: {"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速", "general_public_revenue_100m": "一般公共预算收入", "gov_fund_revenue_100m": "政府性基金收入"},
            2025: {"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速", "general_public_revenue_100m": "一般公共预算收入"},
        },
        "foshan": {
            2024: {"general_public_revenue_100m": "一般公共预算收入", "general_public_expenditure_100m": "一般公共预算支出", "gov_fund_revenue_100m": "政府性基金收入"},
        },
        "xuzhou": {
            2024: {"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速", "general_public_revenue_100m": "一般公共预算收入", "general_public_expenditure_100m": "一般公共预算支出", "gov_fund_revenue_100m": "政府性基金收入"},
            2025: {"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速"},
        },
        "taizhou": {
            2024: {"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速", "general_public_revenue_100m": "一般公共预算收入", "general_public_expenditure_100m": "一般公共预算支出", "gov_fund_revenue_100m": "政府性基金收入"},
            2025: {"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速"},
        },
    }
    notes = {
        "handan": "图表1列示GDP及增速，图表2列示三项财政值；2025年财政三项值已由既有B2来源登记，本批仅补入缺失字段。",
        "luzhou": "图表2列示GDP及增速，图表3列示三项财政值；2025年财政三项值已由既有B2来源登记，本批仅补入缺失字段。",
        "nanping": "图表2列示GDP、增速、一般公共预算收入和政府性基金收入；表格未列一般公共预算支出，2025年基金值已由既有来源登记。",
        "ningde": "表3列示GDP、增速、一般公共预算收入和政府性基金收入；表格未列一般公共预算支出，2025年基金值已由既有来源登记。",
        "xiamen": "基础数据表列示2024年财政三项值，图表2列示2024—2025年GDP及增速；2025年基金值已由既有B2来源登记。",
        "zhuhai": "图表2列示珠海市全市GDP、增速、一般公共预算收入、支出和政府性基金收入；2025年基金值已由既有B2来源登记。",
        "anqing": "图表15列示安庆市全市GDP、增速、一般公共预算收入和政府性基金收入，未列一般公共预算支出；2025年基金值已由既有B2来源登记。",
        "foshan": "图表5列示佛山市全市一般公共预算收入、支出和政府性基金收入，未列GDP；2025年三项值已由既有B2来源登记。",
        "xuzhou": "图表2列示徐州市全市GDP及增速，图表3列示财政三项值；2025年财政三项值已由既有B2来源登记。",
        "taizhou": "图表2列示泰州市全市GDP及增速，图表4列示财政三项值；2025年财政三项值已由既有B2来源登记。",
    }
    for slug, years in rows.items():
        base = _COMMON[slug]
        for year, fields in years.items():
            yield _source(year=year, fields=fields, note=notes[slug], **base)

    zhejiang = {
        "hangzhou": ("杭州市", "CN-330100", "23011.00", "5.20", "2693.21"),
        "ningbo": ("宁波市", "CN-330200", "18716.00", "4.90", "1795.23"),
        "wenzhou": ("温州市", "CN-330300", "10213.90", "6.10", "647.03"),
        "jiaxing": ("嘉兴市", "CN-330400", "7851.06", "5.20", "652.44"),
        "huzhou": ("湖州市", "CN-330500", "4452.80", "5.90", "389.50"),
        "shaoxing": ("绍兴市", "CN-330600", "8932.00", "6.50", "603.45"),
        "jinhua": ("金华市", "CN-330700", "7313.47", "6.30", "555.63"),
        "quzhou": ("衢州市", "CN-330800", "2401.63", "5.50", "216.10"),
        "zhoushan": ("舟山市", "CN-330900", "2346.10", "6.60", "217.52"),
        "taizhou": ("台州市", "CN-331000", "7005.87", "6.10", "517.47"),
        "lishui": ("丽水市", "CN-331100", "2301.40", "6.40", "198.05"),
    }
    for slug, (city_name, city_id, gdp, growth, revenue) in zhejiang.items():
        yield _source(
            year=2025,
            city_name=city_name,
            city_id=city_id,
            slug=slug,
            source_doc_id=f"SRC-B2-ZHEJIANG-REGIONAL-FISCAL-2025-{slug.upper()}",
            url="https://static.sse.com.cn/disclosure/bond/announcement/company/c/new/2026-07-30/244363_20260730_57CX.pdf",
            document_title="湖州市产业投资发展集团有限公司2026年度跟踪评级报告",
            publisher="中证鹏元资信评估股份有限公司",
            publication_date="2026-07-30",
            pdf_name="zhejiang_2025_city_fiscal_rating_report.pdf",
            excerpt_name="zhejiang_2025_economic_fiscal_table_excerpt.txt",
            page_number="PDF第7页表2",
            fields={"gdp_current_100m": "GDP", "gdp_real_growth_pct": "GDP增速", "general_public_revenue_100m": "一般公共预算收入"},
            note=f"B2精确表格；表2列示{city_name}2025年全市GDP、GDP增速和一般公共预算收入，政府性基金收入由既有基金批次登记。",
        )


CITY_FISCAL_RATING_2024_2025_SOURCES = tuple(_build_sources())

__all__ = ["CITY_FISCAL_RATING_2024_2025_SOURCES"]
