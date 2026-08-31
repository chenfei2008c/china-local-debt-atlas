"""湖北、海南直管单元合计 GDP 实际增速的可审计计算来源。

湖北和海南的官方年鉴/统计月报分别给出了组成单元的现价 GDP 及不变价同比
指数（或增速），但没有给出直管单元合计行。这里使用上年组成单元 GDP 作为
权重，计算合计实际增速。结果明确标记为 ``calculated``，不冒充官方合计行。
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, getcontext
from pathlib import Path
import re


getcontext().prec = 40

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw" / "province_fiscal"
TWO_DECIMALS = Decimal("0.01")
ONE_HUNDRED = Decimal("100")

DIRECT_ADMIN_GDP_GROWTH_FORMULA_ID = "F-DIRECT-ADMIN-GDP-GROWTH-WEIGHTED"
DIRECT_ADMIN_GDP_GROWTH_INPUT_FIELDS = (
    "previous_year_component_gdp_100m;component_gdp_real_growth_pct"
)
DIRECT_ADMIN_GDP_GROWTH_FORMULA_REGISTRY = {
    "formula_id": DIRECT_ADMIN_GDP_GROWTH_FORMULA_ID,
    "formula_name": "直管单元 GDP 实际增速（上年 GDP 权重）",
    "expression": (
        "Σ(上年组成单元GDP×(1+组成单元实际增速/100))"
        "/Σ上年组成单元GDP×100−100"
    ),
    "input_fields": DIRECT_ADMIN_GDP_GROWTH_INPUT_FIELDS,
    "output_field": "gdp_real_growth_pct",
    "formula_version": "v1.0",
    "unit": "%",
    "enabled": True,
}
DIRECT_ADMIN_GDP_GROWTH_FORMULA_DEPENDENCY = [
    {
        "formula_id": DIRECT_ADMIN_GDP_GROWTH_FORMULA_ID,
        "depends_on_field": field,
        "dependency_type": "input",
        "formula_version": "v1.0",
    }
    for field in DIRECT_ADMIN_GDP_GROWTH_INPUT_FIELDS.split(";")
]


def calculate_weighted_growth(
    previous_year_component_gdp: list[Decimal],
    component_growth_pct: list[Decimal],
) -> Decimal:
    """按上年组成单元 GDP 权重计算合计实际增速，并四舍五入到两位。"""

    if len(previous_year_component_gdp) != len(component_growth_pct):
        raise ValueError("组成单元 GDP 与增速数量不一致")
    if not previous_year_component_gdp:
        raise ValueError("至少需要一个组成单元")
    total = sum(previous_year_component_gdp, Decimal("0"))
    if total <= 0:
        raise ValueError("上年组成单元 GDP 合计必须大于零")
    current_price_equivalent = sum(
        gdp * (ONE_HUNDRED + growth) / ONE_HUNDRED
        for gdp, growth in zip(previous_year_component_gdp, component_growth_pct)
    )
    growth = current_price_equivalent / total * ONE_HUNDRED - ONE_HUNDRED
    return growth.quantize(TWO_DECIMALS, rounding=ROUND_HALF_UP)


def _spec(
    *,
    city_id: str,
    city_name: str,
    province: str,
    year: int,
    value: str,
    url: str,
    path: Path,
    publication_date: str,
    page_number: str,
    input_record_ids: str,
    input_note: str,
) -> dict[str, object]:
    return {
        "year": year,
        "city_name": city_name,
        "city_id": city_id,
        "source_doc_id": f"SRC-A2-CALC-{city_id}-{year}-GDP-GROWTH",
        "url": url,
        "attachment_url": url,
        "path": path,
        "text_path": path,
        "text_is_curated": True,
        "document_title": f"{province}{year}年直管单元 GDP 实际增速计算底稿",
        "publisher": f"{province}统计机构（官方输入表）",
        "publisher_level": "省级统计机构",
        "publication_date": publication_date,
        "source_grade": "A2",
        "source_format": "txt",
        "raw_unit": "%",
        "raw_units": {"gdp_real_growth_pct": "%"},
        "data_status": "calculated",
        "data_status_label": f"{year}年官方组成单元加权计算值",
        "document_type": "官方统计年鉴/统计月报输入表计算底稿",
        "title_source": "official_table_calculation",
        "access_status": "官方输入表与计算底稿已归档",
        "page_number": page_number,
        "page_count": "",
        "table_name": "组成单元 GDP 现价表与不变价指数/增速表",
        "patterns": {
            "gdp_real_growth_pct": (
                rf"CALC_{city_id}_{year}=({re.escape(value)})%"
            ),
        },
        "note": (
            f"A2{province}官方年鉴/统计月报逐行给出组成单元上年现价GDP和按不变价计算的同比指数/增速；"
            "本值使用上年组成单元GDP作权重，计算直管单元合计实际增速，绝不使用简单平均或当年现价权重。"
            "结果是可复核的calculated值，不是官方直接披露的合计行；输入记录、字段和公式版本均已登记。"
            + input_note
        ),
        "value_origin": "calculated",
        "calculation_id": f"CAL-{city_id}-{year}-gdp_real_growth_pct",
        "calculation_formula_id": DIRECT_ADMIN_GDP_GROWTH_FORMULA_ID,
        "calculation_input_record_ids": input_record_ids,
        "calculation_input_fields": DIRECT_ADMIN_GDP_GROWTH_INPUT_FIELDS,
        "calculation_note": (
            "公式：Σ(上年组成单元GDP×(1+组成单元实际增速/100))/"
            "Σ上年组成单元GDP×100−100；GDP和增速均按官方表格逐行输入，"
            "输出保留两位小数，value_origin=calculated。"
        ),
    }


HUBEI_GDP_GROWTH = {
    2018: "8.29",
    2019: "7.75",
    2020: "-4.80",
    2021: "10.00",
    2022: "2.31",
    2023: "5.65",
    2024: "5.72",
    2025: "6.55",
}
HAINAN_GDP_GROWTH = {
    2018: "4.59",
    2019: "4.40",
    2020: "2.25",
    2021: "8.76",
    2022: "1.48",
    2023: "7.75",
    2024: "3.51",
    2025: "2.80",
}

HUBEI_URLS = {
    2018: "https://tjj.hubei.gov.cn/tjsj/sjkscx/tjnj/qstjnj/201912/P020240903632511602780.rar",
    2019: "https://tjj.hubei.gov.cn/tjsj/sjkscx/tjnj/qstjnj/202010/P020240903631788119195.rar",
    2020: "https://tjj.hubei.gov.cn/tjsj/sjkscx/tjnj/qstjnj/202110/P020240903631312749096.rar",
    2021: "https://tjj.hubei.gov.cn/tjsj/sjkscx/tjnj/qstjnj/202211/P020240903630403969067.rar",
    2022: "https://tjj.hubei.gov.cn/tjsj/sjkscx/tjnj/qstjnj/202402/P020240815365664897419.rar",
    2023: "https://tjj.hubei.gov.cn/tjsj/sjkscx/tjnj/qstjnj/202501/P020250114330164457869.zip",
    2024: "https://tjj.hubei.gov.cn/tjsj/sjkscx/tjnj/qstjnj/202601/P020260114553839802144.zip",
    2025: "https://tjj.hubei.gov.cn/tjsj/tjgb/ndtjgb/sztjgb/",
}
HUBEI_INPUT_IDS = {
    year: (
        f"SRC-A2-HUBEI-YEARBOOK-{year + 1}-429000-CORE;"
        f"SRC-A2-HUBEI-DIRECT-ADMIN-GDP-INDEX-{year}"
    )
    for year in range(2018, 2025)
}
HUBEI_INPUT_IDS[2025] = "SRC-A2-HUBEI-2025-BULLETINS-429000-CORE;SRC-A2-HUBEI-DIRECT-ADMIN-GDP-2024"
HUBEI_YEARBOOK_TEXT = RAW_DIR / "hubei_yearbook" / "direct_admin_growth_calculation_excerpt.txt"
HUBEI_2025_TEXT = HUBEI_YEARBOOK_TEXT

DIRECT_ADMIN_GDP_GROWTH_SOURCES: list[dict[str, object]] = []
for year, value in HUBEI_GDP_GROWTH.items():
    DIRECT_ADMIN_GDP_GROWTH_SOURCES.append(
        _spec(
            city_id="CN-429000",
            city_name="湖北省直辖县级行政区划",
            province="湖北省",
            year=year,
            value=value,
            url=HUBEI_URLS[year],
            path=HUBEI_2025_TEXT if year == 2025 else HUBEI_YEARBOOK_TEXT,
            publication_date="2026-05-08" if year == 2025 else f"{year + 1}-12-31",
            page_number="四地官方公报 GDP 行；年鉴表0115、0116（2018—2024）",
            input_record_ids=HUBEI_INPUT_IDS[year],
            input_note=(
                "湖北四个直管单元为仙桃、潜江、天门、神农架林区；"
                "2018年权重使用2017年官方现价GDP：718.66、671.86、528.25、25.51亿元。"
                if year == 2018
                else "湖北年鉴表0116表头为‘上年=100’，2025年使用四份官方公报逐行实际增速。"
            ),
        )
    )

HAINAN_YEARBOOK_URL = "https://stats.hainan.gov.cn/tjj/tjsu/ndsj/2024/202412/P020250116308974141111.pdf"
HAINAN_2024_MONTHLY_URL = "https://stats.hainan.gov.cn/tjj/tjsu/jdsj/2024/202501/P020250127360656758872.pdf"
HAINAN_2025_MONTHLY_URL = "https://stats.hainan.gov.cn/tjj/tjsu/jdsj/2025/202601/P020260224596167970030.pdf"
HAINAN_INPUT_IDS = {
    year: (
        f"SRC-A2-HAINAN-YEARBOOK-2024-469000-CORE-{year};"
        f"SRC-A2-HAINAN-DIRECT-ADMIN-GDP-INDEX-{year}"
    )
    for year in range(2018, 2024)
}
HAINAN_INPUT_IDS[2024] = "SRC-A2-HAINAN-YEARBOOK-2024-469000-CORE-2023;SRC-A2-HAINAN-2024-DEC-MONTHLY-DIRECT-ADMIN"
HAINAN_INPUT_IDS[2025] = "SRC-A2-HAINAN-YEARBOOK-2025-469000-GDP-2024;SRC-A2-HAINAN-2025-DEC-MONTHLY-469000-CORE"
HAINAN_TEXT = RAW_DIR / "hainan_yearbook" / "direct_admin_growth_calculation_excerpt.txt"
for year, value in HAINAN_GDP_GROWTH.items():
    DIRECT_ADMIN_GDP_GROWTH_SOURCES.append(
        _spec(
            city_id="CN-469000",
            city_name="海南省直辖县级行政区划",
            province="海南省",
            year=year,
            value=value,
            url=(
                HAINAN_2024_MONTHLY_URL
                if year == 2024
                else HAINAN_2025_MONTHLY_URL
                if year == 2025
                else HAINAN_YEARBOOK_URL
            ),
            path=HAINAN_TEXT,
            publication_date="2026-02-24" if year == 2025 else "2025-01-16",
            page_number="年鉴表3-12、3-13；2024/2025年12月统计月报分市县表",
            input_record_ids=HAINAN_INPUT_IDS[year],
            input_note=(
                "海南15个省直辖县级单元为五指山、文昌、琼海、万宁、定安、屯昌、澄迈、临高、"
                "东方、乐东、琼中、保亭、陵水、白沙、昌江；表3-12按当年价格，表3-13按可比价格。"
            ),
        )
    )
