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


# 《海南统计年鉴2025》为扫描版 PDF。本批只归档与 2024 年汇总值直接相关的三张
# 清晰表页 PNG，保留官方原始 PDF 入口；摘录中的数值均由表格 15 行逐项加总，
# 并经过 OCR 与人工视觉复核，避免把 325MB 整本扫描附件提交进 Git 仓库。
RAW_2025_BASE = ROOT / "raw" / "province_fiscal" / "hainan_yearbook" / "2025"
YEARBOOK_2025_URL = (
    "https://stats.hainan.gov.cn/tjj/tjsu/ndsj/2025/202606/"
    "P020260618358658287664.pdf"
)


def _scan_source(
    *,
    field: str,
    source_doc_id: str,
    page_number: str,
    image_name: str,
    excerpt_name: str,
    value_pattern: str,
    label: str,
) -> dict[str, object]:
    return {
        "year": 2024,
        "city_name": "海南省直辖县级行政区划",
        "city_id": "CN-469000",
        "source_doc_id": source_doc_id,
        "url": YEARBOOK_2025_URL,
        "attachment_url": YEARBOOK_2025_URL,
        "path": RAW_2025_BASE / image_name,
        "text_path": RAW_2025_BASE / excerpt_name,
        "document_title": f"海南统计年鉴2025（2024年各市县{label}表）",
        "publisher": "海南省统计局",
        "publisher_level": "省级统计机构",
        "publication_date": "2026-06-18",
        "source_grade": "A2",
        "source_format": "png",
        "raw_unit": "亿元",
        "data_status": "yearbook",
        "data_status_label": "2024年官方统计年鉴值",
        "document_type": "省级统计年鉴官方扫描表页证据（直辖县级行政区划汇总）",
        "title_source": "official_yearbook",
        "page_number": page_number,
        "page_count": "544",
        "patterns": {field: value_pattern},
        "note": (
            "A2海南省统计局《海南统计年鉴2025》官方扫描PDF；本地归档对应表页PNG，"
            f"原始PDF入口保留在 attachment_url；表格{page_number}列示同口径15个直辖县级单元。"
            f"{label}值按15行原始单位万元逐项加总并换算为亿元，摘录值已由OCR与人工视觉复核。"
            "本批不含海口、三亚、儋州等地级市，也不含三沙市；不使用图表目测估值。"
        ),
    }


HAINAN_DIRECT_ADMIN_YEARBOOK_2025_SOURCES = (
    _scan_source(
        field="gdp_current_100m",
        source_doc_id="SRC-A2-HAINAN-YEARBOOK-2025-469000-GDP-2024",
        page_number="第74页（印刷页第48页）表3-12",
        image_name="hainan_2025_3-12_page74.png",
        excerpt_name="hainan_2025_469000_2024_gdp_excerpt.txt",
        value_pattern=r"GDP=([0-9.]+)",
        label="生产总值",
    ),
    _scan_source(
        field="general_public_revenue_100m",
        source_doc_id="SRC-A2-HAINAN-YEARBOOK-2025-469000-REVENUE-2024",
        page_number="第150页（印刷页第124页）表7-7",
        image_name="hainan_2025_7-7_page150.png",
        excerpt_name="hainan_2025_469000_2024_revenue_excerpt.txt",
        value_pattern=r"收入=([0-9.]+)",
        label="地方一般公共预算收入",
    ),
    _scan_source(
        field="general_public_expenditure_100m",
        source_doc_id="SRC-A2-HAINAN-YEARBOOK-2025-469000-EXPENDITURE-2024",
        page_number="第152页（印刷页第126页）表7-8",
        image_name="hainan_2025_7-8_page152.png",
        excerpt_name="hainan_2025_469000_2024_expenditure_excerpt.txt",
        value_pattern=r"支出=([0-9.]+)",
        label="地方一般公共预算支出",
    ),
)


# 《海南统计年鉴2023》表7-7、表7-8分别列示2022年各市县地方一般公共预算
# 收入和支出。本批只归档两张官方表页PNG，15个直辖县级单元按同一年度、同一
# 行口径逐项加总，不把海口、三亚、儋州或三沙市混入汇总行。
RAW_2023_BASE = ROOT / "raw" / "province_fiscal" / "hainan_yearbook" / "2023"
YEARBOOK_2023_URL = (
    "https://stats.hainan.gov.cn/tjj/tjsu/ndsj/2023/202311/"
    "P020240603544257625279.pdf"
)


def _historical_scan_source(
    *,
    data_year: int,
    yearbook_year: int,
    yearbook_url: str,
    raw_base: Path,
    publication_date: str,
    page_count: str,
    field: str,
    source_doc_id: str,
    page_number: str,
    image_name: str,
    excerpt_name: str,
    value_pattern: str,
    label: str,
) -> dict[str, object]:
    return {
        "year": data_year,
        "city_name": "海南省直辖县级行政区划",
        "city_id": "CN-469000",
        "source_doc_id": source_doc_id,
        "url": yearbook_url,
        "attachment_url": yearbook_url,
        "path": raw_base / image_name,
        "text_path": raw_base / excerpt_name,
        "document_title": f"海南统计年鉴{yearbook_year}（{data_year}年各市县{label}表）",
        "publisher": "海南省统计局",
        "publisher_level": "省级统计机构",
        "publication_date": publication_date,
        "source_grade": "A2",
        "source_format": "png",
        "raw_unit": "亿元",
        "data_status": "yearbook",
        "data_status_label": f"{data_year}年官方统计年鉴值",
        "document_type": "省级统计年鉴官方扫描表页证据（直辖县级行政区划汇总）",
        "title_source": "official_yearbook",
        "page_number": page_number,
        "page_count": page_count,
        "patterns": {field: value_pattern},
        "note": (
            f"A2海南省统计局《海南统计年鉴{yearbook_year}》官方PDF表页；"
            f"{label}表{page_number}列示15个直辖县级单元。"
            "本批按15行原始单位万元逐项加总并换算为亿元，摘录值已由OCR与人工视觉复核；"
            "不含海口、三亚、儋州等地级市，也不含三沙市。"
        ),
    }


HAINAN_DIRECT_ADMIN_YEARBOOK_2023_SOURCES = (
    _historical_scan_source(
        data_year=2022,
        yearbook_year=2023,
        yearbook_url=YEARBOOK_2023_URL,
        raw_base=RAW_2023_BASE,
        publication_date="2023-11-23",
        page_count="536",
        field="general_public_revenue_100m",
        source_doc_id="SRC-A2-HAINAN-YEARBOOK-2023-469000-REVENUE-2022",
        page_number="第126页（PDF第154页）表7-7",
        image_name="hainan_2023_7-7_page154.png",
        excerpt_name="hainan_2023_469000_2022_revenue_excerpt.txt",
        value_pattern=r"收入=([0-9.]+)",
        label="地方一般公共预算收入",
    ),
    _historical_scan_source(
        data_year=2022,
        yearbook_year=2023,
        yearbook_url=YEARBOOK_2023_URL,
        raw_base=RAW_2023_BASE,
        publication_date="2023-11-23",
        page_count="536",
        field="general_public_expenditure_100m",
        source_doc_id="SRC-A2-HAINAN-YEARBOOK-2023-469000-EXPENDITURE-2022",
        page_number="第128页（PDF第156页）表7-8",
        image_name="hainan_2023_7-8_page156.png",
        excerpt_name="hainan_2023_469000_2022_expenditure_excerpt.txt",
        value_pattern=r"支出=([0-9.]+)",
        label="地方一般公共预算支出",
    ),
)


# 海南统计局官方年鉴压缩包中的财政章节分别给出上一年度各市县地方一般公共预算
# 收入和支出。2019、2020、2021、2022 年鉴对应 2018、2019、2020、2021 年数据；本地只归档
# 表7-7和表7-8的清晰表页PNG，官方压缩包入口作为附件来源保留。
RAW_2019_BASE = ROOT / "raw" / "province_fiscal" / "hainan_yearbook" / "2019"
RAW_2020_BASE = ROOT / "raw" / "province_fiscal" / "hainan_yearbook" / "2020"
RAW_2021_BASE = ROOT / "raw" / "province_fiscal" / "hainan_yearbook" / "2021"
RAW_2022_BASE = ROOT / "raw" / "province_fiscal" / "hainan_yearbook" / "2022"
YEARBOOK_2019_URL = (
    "https://stats.hainan.gov.cn/tjj/tjsu/ndsj/2019_77838/201909/"
    "P020240306633278360675.zip"
)
YEARBOOK_2020_URL = (
    "https://stats.hainan.gov.cn/tjj/tjsu/ndsj/2020/202010/"
    "P020240306635447560382.zip"
)
YEARBOOK_2021_URL = (
    "https://stats.hainan.gov.cn/tjj/tjsu/ndsj/2021/202110/"
    "P020260202629383416266.zip"
)
YEARBOOK_2022_URL = (
    "https://stats.hainan.gov.cn/tjj/tjsu/ndsj/2021_84481/202211/"
    "P020231116624247052503.zip"
)


HAINAN_DIRECT_ADMIN_YEARBOOK_2019_2021_SOURCES = (
    _historical_scan_source(
        data_year=2018,
        yearbook_year=2019,
        yearbook_url=YEARBOOK_2019_URL,
        raw_base=RAW_2019_BASE,
        publication_date="2019-09-13",
        page_count="20",
        field="general_public_revenue_100m",
        source_doc_id="SRC-A2-HAINAN-YEARBOOK-2019-469000-REVENUE-2018",
        page_number="第154页（PDF第10页）表7-7",
        image_name="hainan_2019_7-7_page10.png",
        excerpt_name="hainan_2019_469000_2018_revenue_excerpt.txt",
        value_pattern=r"收入=([0-9.]+)",
        label="地方一般公共预算收入",
    ),
    _historical_scan_source(
        data_year=2018,
        yearbook_year=2019,
        yearbook_url=YEARBOOK_2019_URL,
        raw_base=RAW_2019_BASE,
        publication_date="2019-09-13",
        page_count="20",
        field="general_public_expenditure_100m",
        source_doc_id="SRC-A2-HAINAN-YEARBOOK-2019-469000-EXPENDITURE-2018",
        page_number="第156页（PDF第12页）表7-8",
        image_name="hainan_2019_7-8_page12.png",
        excerpt_name="hainan_2019_469000_2018_expenditure_excerpt.txt",
        value_pattern=r"支出=([0-9.]+)",
        label="地方一般公共预算支出",
    ),
    _historical_scan_source(
        data_year=2019,
        yearbook_year=2020,
        yearbook_url=YEARBOOK_2020_URL,
        raw_base=RAW_2020_BASE,
        publication_date="2020-10-13",
        page_count="20",
        field="general_public_revenue_100m",
        source_doc_id="SRC-A2-HAINAN-YEARBOOK-2020-469000-REVENUE-2019",
        page_number="第154页（PDF第10页）表7-7",
        image_name="hainan_2020_7-7_page10.png",
        excerpt_name="hainan_2020_469000_2019_revenue_excerpt.txt",
        value_pattern=r"收入=([0-9.]+)",
        label="地方一般公共预算收入",
    ),
    _historical_scan_source(
        data_year=2019,
        yearbook_year=2020,
        yearbook_url=YEARBOOK_2020_URL,
        raw_base=RAW_2020_BASE,
        publication_date="2020-10-13",
        page_count="20",
        field="general_public_expenditure_100m",
        source_doc_id="SRC-A2-HAINAN-YEARBOOK-2020-469000-EXPENDITURE-2019",
        page_number="第156页（PDF第12页）表7-8",
        image_name="hainan_2020_7-8_page12.png",
        excerpt_name="hainan_2020_469000_2019_expenditure_excerpt.txt",
        value_pattern=r"支出=([0-9.]+)",
        label="地方一般公共预算支出",
    ),
    _historical_scan_source(
        data_year=2020,
        yearbook_year=2021,
        yearbook_url=YEARBOOK_2021_URL,
        raw_base=RAW_2021_BASE,
        publication_date="2021-10-27",
        page_count="20",
        field="general_public_revenue_100m",
        source_doc_id="SRC-A2-HAINAN-YEARBOOK-2021-469000-REVENUE-2020",
        page_number="第136页（PDF第10页）表7-7",
        image_name="hainan_2021_7-7_page10.png",
        excerpt_name="hainan_2021_469000_2020_revenue_excerpt.txt",
        value_pattern=r"收入=([0-9.]+)",
        label="地方一般公共预算收入",
    ),
    _historical_scan_source(
        data_year=2020,
        yearbook_year=2021,
        yearbook_url=YEARBOOK_2021_URL,
        raw_base=RAW_2021_BASE,
        publication_date="2021-10-27",
        page_count="20",
        field="general_public_expenditure_100m",
        source_doc_id="SRC-A2-HAINAN-YEARBOOK-2021-469000-EXPENDITURE-2020",
        page_number="第138页（PDF第12页）表7-8",
        image_name="hainan_2021_7-8_page12.png",
        excerpt_name="hainan_2021_469000_2020_expenditure_excerpt.txt",
        value_pattern=r"支出=([0-9.]+)",
        label="地方一般公共预算支出",
    ),
    _historical_scan_source(
        data_year=2021,
        yearbook_year=2022,
        yearbook_url=YEARBOOK_2022_URL,
        raw_base=RAW_2022_BASE,
        publication_date="2022-11-17",
        page_count="20",
        field="general_public_revenue_100m",
        source_doc_id="SRC-A2-HAINAN-YEARBOOK-2022-469000-REVENUE-2021",
        page_number="第126页（PDF第10页）表7-7",
        image_name="hainan_2022_7-7_page10.png",
        excerpt_name="hainan_2022_469000_2021_revenue_excerpt.txt",
        value_pattern=r"收入=([0-9.]+)",
        label="地方一般公共预算收入",
    ),
    _historical_scan_source(
        data_year=2021,
        yearbook_year=2022,
        yearbook_url=YEARBOOK_2022_URL,
        raw_base=RAW_2022_BASE,
        publication_date="2022-11-17",
        page_count="20",
        field="general_public_expenditure_100m",
        source_doc_id="SRC-A2-HAINAN-YEARBOOK-2022-469000-EXPENDITURE-2021",
        page_number="第128页（PDF第12页）表7-8",
        image_name="hainan_2022_7-8_page12.png",
        excerpt_name="hainan_2022_469000_2021_expenditure_excerpt.txt",
        value_pattern=r"支出=([0-9.]+)",
        label="地方一般公共预算支出",
    ),
)
