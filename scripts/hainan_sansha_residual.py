"""海南省三沙市 GDP 官方合计差额计算来源。

海南统计年鉴的市县 GDP 表列出海口、三亚、儋州和 15 个省直辖县级单元，
但不列三沙；同一官方年鉴/公报的全省总量明确包含三沙。这里仅在省级总量
与 18 个已列单元之差显著大于省级总量两位小数带来的舍入区间时，登记为
``calculated``，不把它伪装成三沙市直接披露值。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw"

FORMULA_ID = "F-HN-SANSHA-GDP-RESIDUAL"
INPUT_FIELDS = "hainan_province_gdp_total_100m;hainan_18_city_gdp_sum_100m"
CALC_NOTE = (
    "海南省官方市县 GDP 表未列三沙；目标值=同年度海南省总量−表3-12所列18个市县合计。"
    "省级总量只保留两位小数，理论舍入区间约为±0.005亿元；仅接入绝对残差超过该区间的年度，"
    "结果保留计算值属性，不等同于三沙市直接披露值。"
)


def _spec(
    year: int,
    raw_value: str,
    *,
    path: Path,
    text_path: Path,
    url: str,
    publication_date: str,
    note: str,
    page_number: str | None = None,
    source_format: str | None = None,
) -> dict[str, object]:
    return {
        "city_name": "三沙市",
        "city_id": "CN-460300",
        "year": year,
        "source_doc_id": f"SRC-A2-HN-SANSHA-GDP-RESIDUAL-{year}",
        "url": url,
        "path": path,
        "text_path": text_path,
        "text_is_curated": True,
        "document_title": "海南统计年鉴及海南省统计公报三沙市 GDP 合计差额计算底稿",
        "publisher": "海南省统计局",
        "publisher_level": "province",
        "publication_date": publication_date,
        "source_grade": "A2",
        "source_format": source_format or ("pdf" if path.suffix.lower() == ".pdf" else "png"),
        "document_type": "官方统计年鉴市县表与省级合计差额计算",
        "data_status": "calculated",
        "data_status_label": "官方年鉴合计差额计算值",
        "table_name": "官方统计年鉴市县 GDP 表与省级 GDP 总量差额",
        "page_number": page_number or ("70（印刷页42）" if year <= 2023 else "74（印刷页48）"),
        "patterns": {
            "gdp_current_100m": rf"RESIDUAL_GDP_{year}=({raw_value})亿元",
        },
        "raw_units": {"gdp_current_100m": "亿元"},
        "value_origin": "calculated",
        "calculation_id": f"CAL-CN-460300-{year}-gdp_current_100m",
        "calculation_formula_id": FORMULA_ID,
        "calculation_input_record_ids": (
            f"SRC-HN-GDP-TOTAL-{year};SRC-HN-GDP-18-REGIONS-{year}"
        ),
        "calculation_input_fields": INPUT_FIELDS,
        "calculation_note": CALC_NOTE,
        "note": note,
    }


_YEARBOOK_2024_PATH = RAW_DIR / "province_fiscal" / "hainan_yearbook" / "2024" / "hainan_2024_yearbook.pdf"
_YEARBOOK_2024_TEXT = RAW_DIR / "province_fiscal" / "hainan_yearbook" / "2024" / "hainan_2024_sansha_gdp_residual_excerpt.txt"
_YEARBOOK_2025_PATH = RAW_DIR / "province_fiscal" / "hainan_yearbook" / "2025" / "hainan_2025_3-12_page74.png"
_YEARBOOK_2025_TEXT = RAW_DIR / "province_fiscal" / "hainan_yearbook" / "2025" / "hainan_2025_sansha_gdp_residual_excerpt.txt"
_SANSHA_2025_TEXT = RAW_DIR / "province_fiscal" / "2025" / "official" / "hainan_2025_sansha_gdp_residual_excerpt.txt"


HAINAN_SANSHA_RESIDUAL_SOURCES = (
    _spec(
        2018,
        "0.0884",
        path=_YEARBOOK_2024_PATH,
        text_path=_YEARBOOK_2024_TEXT,
        url="https://stats.hainan.gov.cn/tjj/tjsu/ndsj/2024/202412/P020250116308974141111.pdf",
        publication_date="2025-01-16",
        note="2018 年使用《海南统计年鉴2024》表3-1省级总量与表3-12 18个市县行；残差高于两位小数舍入区间。",
    ),
    _spec(
        2019,
        "3.6116",
        path=_YEARBOOK_2024_PATH,
        text_path=_YEARBOOK_2024_TEXT,
        url="https://stats.hainan.gov.cn/tjj/tjsu/ndsj/2024/202412/P020250116308974141111.pdf",
        publication_date="2025-01-16",
        note="2019 年使用《海南统计年鉴2024》表3-1省级总量与表3-12 18个市县行；残差高于两位小数舍入区间。",
    ),
    _spec(
        2020,
        "3.3646",
        path=_YEARBOOK_2024_PATH,
        text_path=_YEARBOOK_2024_TEXT,
        url="https://stats.hainan.gov.cn/tjj/tjsu/ndsj/2024/202412/P020250116308974141111.pdf",
        publication_date="2025-01-16",
        note="2020 年使用《海南统计年鉴2024》表3-1省级总量与表3-12 18个市县行；残差高于两位小数舍入区间。",
    ),
    _spec(
        2021,
        "2.0001",
        path=_YEARBOOK_2024_PATH,
        text_path=_YEARBOOK_2024_TEXT,
        url="https://stats.hainan.gov.cn/tjj/tjsu/ndsj/2024/202412/P020250116308974141111.pdf",
        publication_date="2025-01-16",
        note="2021 年使用《海南统计年鉴2024》表3-1省级总量与表3-12 18个市县行；残差高于两位小数舍入区间。",
    ),
    _spec(
        2023,
        "0.8998",
        path=_YEARBOOK_2024_PATH,
        text_path=_YEARBOOK_2024_TEXT,
        url="https://stats.hainan.gov.cn/tjj/tjsu/ndsj/2024/202412/P020250116308974141111.pdf",
        publication_date="2025-01-16",
        note="2023 年使用《海南统计年鉴2024》表3-1省级总量与表3-12 18个市县行；2023省级总量为初步核算数。",
    ),
    _spec(
        2024,
        "6.4243",
        path=_YEARBOOK_2025_PATH,
        text_path=_YEARBOOK_2025_TEXT,
        url="https://stats.hainan.gov.cn/tjj/tjsu/ndsj/2025/202606/P020260618358658287664.pdf",
        publication_date="2026-06-18",
        note=(
            "2024 年使用《海南统计年鉴2025》表3-12 18个市县行与海南省2024年统计公报省级总量；"
            "公报入口=https://stats.hainan.gov.cn/tjj/tjgb/fzgb/2023_87039/202503/t20250313_3832017.html。"
        ),
    ),
    _spec(
        2025,
        "7.9303",
        path=_SANSHA_2025_TEXT,
        text_path=_SANSHA_2025_TEXT,
        url="https://stats.hainan.gov.cn/tjj/ywdt/xwfb/202601/t20260123_4015998.html",
        publication_date="2026-04-24",
        page_number="海南省统计局网页；海南省2025年12月份统计月报第36页；海口GDP数据页；三亚、儋州统计公报网页",
        source_format="txt",
        note=(
            "2025 年使用海南省统计局2025年全省GDP官方发布值与2025年12月份统计月报分市县表，"
            "并以海口市统计局、三亚市统计局和儋州市统计局官方年度GDP补齐表3-12未列示的18行；"
            "五项输入均为2025年度现价GDP，残差超过省级总量两位小数的舍入区间。"
        ),
    ),
)


HAINAN_SANSHA_FORMULA_REGISTRY = {
    "formula_id": FORMULA_ID,
    "formula_name": "三沙市 GDP 官方合计差额计算",
    "expression": "海南省 GDP 总量 − 表3-12所列18个市县 GDP 合计",
    "input_fields": INPUT_FIELDS,
    "output_field": "gdp_current_100m",
    "formula_version": "v1.0",
    "unit": "亿元",
    "enabled": True,
}

HAINAN_SANSHA_FORMULA_DEPENDENCY = [
    {
        "formula_id": FORMULA_ID,
        "depends_on_field": field,
        "dependency_type": "input",
        "formula_version": "v1.0",
    }
    for field in INPUT_FIELDS.split(";")
]
