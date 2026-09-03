"""海南省统计年鉴三沙市一般预算收支的官方合计差额计算来源。

2019—2022 年《海南统计年鉴》的表 7-7、表 7-8同时列出“地市小计”和
18 个市县行。18 个已列行包括海口、三亚、儋州及 15 个省直辖县级单元，
不单列三沙；三沙为该表中唯一缺列的地级行政单元。因此本模块只在同一张
官方表内用“地市小计−18 行合计”计算三沙值，并明确标注为 calculated，
不把计算值伪装成三沙市直接披露值。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw"

FORMULA_ID = "F-HN-SANSHA-FISCAL-RESIDUAL"
INPUT_FIELDS = "hainan_all_regions_fiscal_subtotal_10000yuan;hainan_18_city_fiscal_sum_10000yuan"
CALC_NOTE = (
    "海南省官方统计年鉴表7-7/7-8同时列出‘地市小计’与18个已列市县行，"
    "但不单列三沙；目标值=同一表地市小计−18个已列行合计。"
    "三沙是该表唯一未列地级行政单元，结果保留官方表内差额的计算属性，"
    "不等同于三沙市直接披露值。原始单位为万元，主表换算为亿元并保留两位小数。"
)


def _spec(
    *,
    data_year: int,
    yearbook_year: int,
    field: str,
    field_label: str,
    raw_value: str,
    image_name: str,
    excerpt_name: str,
    page_number: str,
    url: str,
    publication_date: str,
) -> dict[str, object]:
    field_token = "REVENUE" if field.endswith("revenue_100m") else "EXPENDITURE"
    return {
        "city_name": "三沙市",
        "city_id": "CN-460300",
        "year": data_year,
        "source_doc_id": (
            f"SRC-A2-HAINAN-YEARBOOK-{yearbook_year}-SANSHA-"
            f"{field_token}-{data_year}"
        ),
        "url": url,
        "attachment_url": url,
        "path": RAW_DIR / "province_fiscal" / "hainan_yearbook" / str(yearbook_year) / image_name,
        "text_path": RAW_DIR / "province_fiscal" / "hainan_yearbook" / str(yearbook_year) / excerpt_name,
        "text_is_curated": True,
        "document_title": f"海南统计年鉴{yearbook_year}表7-{'7' if field.endswith('revenue_100m') else '8'}三沙市财政差额计算底稿",
        "publisher": "海南省统计局",
        "publisher_level": "省级统计机构",
        "publication_date": publication_date,
        "source_grade": "A2",
        "source_format": "png",
        "data_status": "calculated",
        "data_status_label": f"{data_year}年官方年鉴地市小计差额计算值",
        "document_type": "省级统计年鉴官方扫描表及同表合计差额计算",
        "table_name": f"表7-{'7' if field.endswith('revenue_100m') else '8'} 各市县地方一般公共预算{field_label}",
        "page_number": page_number,
        "patterns": {field: rf"RESIDUAL_{field.upper()}_{data_year}=({raw_value})万元"},
        "raw_units": {field: "万元"},
        "value_origin": "calculated",
        "calculation_id": f"CAL-CN-460300-{data_year}-{field}",
        "calculation_formula_id": FORMULA_ID,
        "calculation_input_record_ids": (
            f"SRC-HN-FISCAL-SUBTOTAL-{data_year};SRC-HN-FISCAL-18-REGIONS-{data_year}"
        ),
        "calculation_input_fields": INPUT_FIELDS,
        "calculation_note": CALC_NOTE,
        "lineage_locator_type": "page_table",
        "lineage_extraction_method": "official-yearbook-image-table-residual-calculation",
        "lineage_normalization_rule": "万元÷10000→亿元；Decimal计算后四舍五入至0.01亿元",
        "lineage_selection_reason": (
            "同一官方表格存在地市小计和18个已列市县行；18行覆盖海口、三亚、"
            "儋州及15个省直辖县级单元，三沙为唯一未列地级行政单元。"
        ),
        "note": (
            f"{data_year}年数据来自海南统计年鉴{yearbook_year}；地市小计−18行合计"
            f"={raw_value}万元。计算依据、表内合计及行口径详见同目录官方扫描表和摘录。"
        ),
    }


YEARBOOKS = {
    2019: {
        "url": "https://stats.hainan.gov.cn/tjj/tjsu/ndsj/2019_77838/201909/P020240306633278360675.zip",
        "publication_date": "2019-09-13",
        "page_revenue": "第154页（PDF第10页）表7-7",
        "page_expenditure": "第156页（PDF第12页）表7-8",
    },
    2020: {
        "url": "https://stats.hainan.gov.cn/tjj/tjsu/ndsj/2020/202010/P020240306635447560382.zip",
        "publication_date": "2020-10-13",
        "page_revenue": "第154页（PDF第10页）表7-7",
        "page_expenditure": "第156页（PDF第12页）表7-8",
    },
    2021: {
        "url": "https://stats.hainan.gov.cn/tjj/tjsu/ndsj/2021/202110/P020260202629383416266.zip",
        "publication_date": "2021-10-27",
        "page_revenue": "第136页（PDF第10页）表7-7",
        "page_expenditure": "第138页（PDF第12页）表7-8",
    },
    2022: {
        "url": "https://stats.hainan.gov.cn/tjj/tjsu/ndsj/2021_84481/202211/P020231116624247052503.zip",
        "publication_date": "2022-11-17",
        "page_revenue": "第126页（PDF第10页）表7-7",
        "page_expenditure": "第128页（PDF第12页）表7-8",
    },
}


_RESIDUALS = {
    (2019, 2018, "revenue"): "9958",
    (2019, 2018, "expenditure"): "241667",
    (2020, 2019, "revenue"): "4748",
    (2020, 2019, "expenditure"): "215839",
    (2021, 2020, "revenue"): "6171",
    (2021, 2020, "expenditure"): "222348",
    (2022, 2021, "revenue"): "8932",
    (2022, 2021, "expenditure"): "190961",
}


HAINAN_SANSHA_FISCAL_RESIDUAL_SOURCES = tuple(
    _spec(
        data_year=data_year,
        yearbook_year=yearbook_year,
        field=(
            "general_public_revenue_100m"
            if fiscal_field == "revenue"
            else "general_public_expenditure_100m"
        ),
        field_label=("收入" if fiscal_field == "revenue" else "支出"),
        raw_value=raw_value,
        image_name=(
            f"hainan_{yearbook_year}_7-7_page10.png"
            if fiscal_field == "revenue"
            else f"hainan_{yearbook_year}_7-8_page12.png"
        ),
        excerpt_name=(
            f"hainan_{yearbook_year}_sansha_{data_year}_revenue_residual_excerpt.txt"
            if fiscal_field == "revenue"
            else f"hainan_{yearbook_year}_sansha_{data_year}_expenditure_residual_excerpt.txt"
        ),
        page_number=(
            YEARBOOKS[yearbook_year]["page_revenue"]
            if fiscal_field == "revenue"
            else YEARBOOKS[yearbook_year]["page_expenditure"]
        ),
        url=YEARBOOKS[yearbook_year]["url"],
        publication_date=YEARBOOKS[yearbook_year]["publication_date"],
    )
    for (yearbook_year, data_year, fiscal_field), raw_value in _RESIDUALS.items()
)


HAINAN_SANSHA_FISCAL_FORMULA_REGISTRY = {
    "formula_id": FORMULA_ID,
    "formula_name": "三沙市一般预算收支官方年鉴合计差额计算",
    "expression": "官方年鉴地市小计 − 同表18个已列市县合计",
    "input_fields": INPUT_FIELDS,
    "output_field": "general_public_revenue_100m;general_public_expenditure_100m",
    "formula_version": "v1.0",
    "unit": "亿元",
    "enabled": True,
}

HAINAN_SANSHA_FISCAL_FORMULA_DEPENDENCY = [
    {
        "formula_id": FORMULA_ID,
        "depends_on_field": field,
        "dependency_type": "input",
        "formula_version": "v1.0",
    }
    for field in INPUT_FIELDS.split(";")
]
