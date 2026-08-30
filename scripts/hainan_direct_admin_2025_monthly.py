"""海南省直辖县级行政区划2025年官方统计月报汇总来源。"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = (
    ROOT
    / "raw"
    / "province_fiscal"
    / "2025"
    / "official"
    / "hainan_2025_dec_monthly_direct_admin_excerpt.txt"
)
SOURCE_URL = (
    "https://stats.hainan.gov.cn/tjj/tjsu/jdsj/2025/202601/"
    "P020260224596167970030.pdf"
)


HAINAN_DIRECT_ADMIN_2025_MONTHLY_SOURCE = {
    "year": 2025,
    "city_name": "海南省直辖县级行政区划",
    "city_id": "CN-469000",
    "source_doc_id": "SRC-A2-HAINAN-2025-DEC-MONTHLY-469000-CORE",
    "url": SOURCE_URL,
    "attachment_url": SOURCE_URL,
    "path": RAW_PATH,
    "text_path": RAW_PATH,
    "text_is_curated": True,
    "document_title": "海南省2025年12月份统计月报（15个省直辖县级行政单元汇总）",
    "publisher": "海南省统计局",
    "publisher_level": "省级统计机构",
    "publication_date": "2026-02-24",
    "source_grade": "A2",
    "source_format": "txt",
    "data_status": "execution",
    "data_status_label": "2025年1—12月官方统计月报值",
    "document_type": "省级统计月报分市县表逐行加总摘录",
    "title_source": "official_pdf_table_excerpt",
    "page_number": "第36—37、48—49页（PDF印刷页）",
    "page_count": "50",
    "raw_unit": "亿元",
    "raw_units": {
        "gdp_current_100m": "亿元",
        "general_public_revenue_100m": "亿元",
        "general_public_expenditure_100m": "亿元",
        "gov_fund_revenue_100m": "亿元",
    },
    "patterns": {
        "gdp_current_100m": r"GDP=([0-9.]+)亿元",
        "general_public_revenue_100m": r"地方一般公共预算收入=([0-9.]+)亿元",
        "general_public_expenditure_100m": r"地方一般公共预算支出=([0-9.]+)亿元",
        "gov_fund_revenue_100m": r"政府性基金收入=([0-9.]+)亿元",
    },
    "note": (
        "A2海南省统计局2025年12月份统计月报；第36、48、49表逐行列示15个省直辖县级行政单元。"
        "本配置将五指山、文昌、琼海、万宁、定安、屯昌、澄迈、临高、东方、乐东、琼中、保亭、"
        "陵水、白沙、昌江15行同年度原始值分别加总并换算为亿元，生成CN-469000汇总值；不含海口、"
        "三亚、儋州（含洋浦）和三沙。第37表没有这15行的合计增速，GDP实际增速不做简单平均或现价"
        "加权，保持缺失。2025年政府性基金收入同步来自第48表。"
    ),
}
