"""海南省直辖县级行政区划官方年鉴汇总来源。"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_BASE = ROOT / "raw" / "province_fiscal" / "hainan_yearbook" / "2024"
YEARBOOK_URL = "https://stats.hainan.gov.cn/tjj/tjsu/ndsj/2024/202412/P020250116308974141111.pdf"

_PUBLICATION_DATES = {
    2018: "2025-01-16",
    2019: "2025-01-16",
    2020: "2025-01-16",
    2021: "2025-01-16",
    2022: "2025-01-16",
    2023: "2025-01-16",
}
_GDP_BY_YEAR = {
    2018: "2181.88",
    2019: "2340.15",
    2020: "2404.16",
    2021: "2774.85",
    2022: "2963.66",
    2023: "3217.66",
}


def _source(year: int) -> dict[str, object]:
    patterns: dict[str, str] = {"gdp_current_100m": r"GDP=([0-9.]+)"}
    if year == 2023:
        patterns.update(
            {
                "general_public_revenue_100m": r"收入=([0-9.]+)",
                "general_public_expenditure_100m": r"支出=([0-9.]+)",
            }
        )
    return {
        "year": year,
        "city_name": "海南省直辖县级行政区划",
        "city_id": "CN-469000",
        "source_doc_id": f"SRC-A2-HAINAN-YEARBOOK-2024-469000-CORE-{year}",
        "url": YEARBOOK_URL,
        "attachment_url": YEARBOOK_URL,
        "path": RAW_BASE / "hainan_2024_yearbook.pdf",
        "text_path": RAW_BASE / f"hainan_2024_469000_{year}_excerpt.txt",
        "document_title": f"海南统计年鉴2024（{year}年各市县统计表）",
        "publisher": "海南省统计局",
        "publisher_level": "省级统计机构",
        "publication_date": _PUBLICATION_DATES[year],
        "source_grade": "A2",
        "source_format": "pdf",
        "raw_unit": "亿元",
        "data_status": "yearbook",
        "data_status_label": f"{year}年官方统计年鉴值",
        "document_type": "省级统计年鉴官方PDF表（直辖县级行政区划汇总）",
        "title_source": "official_yearbook",
        "page_number": "第42页表3-12" + ("；第114页表7-7、第116页表7-8" if year == 2023 else ""),
        "page_count": "498",
        "patterns": patterns,
        "note": (
            "A2海南省统计局《海南统计年鉴2024》；表3-12‘各市县生产总值’按当年价格、"
            "原始单位万元，列示五指山、文昌、琼海、万宁、定安、屯昌、澄迈、临高、东方、"
            "乐东、琼中、保亭、陵水、白沙、昌江15个直辖县级单元；本批将这15行同年度"
            "逐项加总并换算为亿元，作为CN-469000汇总行。2023年一般公共预算收入/支出分别"
            "来自表7-7和表7-8，原始单位万元，按15个同口径单元逐项加总并换算为亿元。"
            "不含海口、三亚、儋州等地级市，也不把三沙市混入直辖县级行政区划。"
        ),
    }


HAINAN_DIRECT_ADMIN_YEARBOOK_SOURCES = tuple(_source(year) for year in range(2018, 2024))
