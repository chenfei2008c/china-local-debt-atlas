"""河北省统计年鉴分市 GDP 表中雄安新区的官方合计差额计算来源。

《河北经济年鉴2025》表 3-8 同时列示：保定市（含定州和雄安）、
保定市①（不含定州和雄安）以及定州市。三行来自同一张官方表，
因此用前者减去后两者可得到雄安新区的同口径 GDP。结果明确标记为
``calculated``，不把它伪装成雄安新区直接披露行。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw"

FORMULA_ID = "F-HEBEI-XIONGAN-GDP-RESIDUAL"
INPUT_FIELDS = "hebei_baoding_including_xiongan_gdp_100m;hebei_baoding_excluding_xiongan_gdp_100m;hebei_dingzhou_gdp_100m"
CALC_NOTE = (
    "《河北经济年鉴2025》表3-8为同一张官方分市 GDP 表；表注明确保定市含定州和雄安，"
    "保定市①不含定州和雄安。目标值=保定市−保定市①−定州市，结果为同口径合计差额，"
    "标记为 calculated，不等同于雄安新区直接披露值。"
)


XIONGAN_GDP_SOURCE = {
    "year": 2024,
    "city_name": "雄安新区",
    "city_id": "CN-133100",
    "source_doc_id": "SRC-A1-HEBEI-XIONGAN-GDP-RESIDUAL-2024",
    "url": "https://tjj.hebei.gov.cn/hbstjj/tjnj/2025/zk/indexch.htm",
    "landing_page_url": "https://tjj.hebei.gov.cn/hbstjj/tjnj/2025/zk/indexch.htm",
    "attachment_url": "https://tjj.hebei.gov.cn/hbstjj/tjnj/2025/zk/html/0308.jpg",
    "download_url": "https://tjj.hebei.gov.cn/hbstjj/tjnj/2025/zk/html/0308.jpg",
    "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "hebei_2025_0308.jpg",
    "text_path": RAW_DIR / "province_fiscal" / "2024" / "official" / "hebei_2025_xiongan_gdp_residual_excerpt.txt",
    "document_title": "河北经济年鉴2025表3-8分市地区生产总值（2024年）",
    "publisher": "河北省统计局",
    "publisher_level": "省级统计机构",
    "publication_date": "2025-12-31",
    "source_grade": "A1",
    "source_format": "jpg",
    "raw_unit": "亿元",
    "data_status": "calculated",
    "data_status_label": "2024年官方年鉴同表合计差额计算值",
    "document_type": "官方统计年鉴分市经济表合计差额计算",
    "page_number": "表3-8；在线图片 html/0308.jpg",
    "table_name": "3-8 分市地区生产总值（2024年）",
    "value_origin": "calculated",
    "calculation_id": "CAL-CN-133100-2024-gdp_current_100m",
    "calculation_formula_id": FORMULA_ID,
    "calculation_input_record_ids": "SRC-A1-HEBEI-YEARBOOK-2025-TABLE-0308-BAODING;SRC-A1-HEBEI-YEARBOOK-2025-TABLE-0308-BAODING-EXCLUDING-XIONGAN;SRC-A1-HEBEI-YEARBOOK-2025-TABLE-0308-DINGZHOU",
    "calculation_input_fields": INPUT_FIELDS,
    "calculation_note": CALC_NOTE,
    "patterns": {
        "gdp_current_100m": r"XIONGAN_GDP_2024=(492\.4)亿元",
    },
    "raw_units": {"gdp_current_100m": "亿元"},
    "gdp_current_100m_raw_100m": "492.4",
    "gdp_current_100m_raw_unit": "亿元",
    "gdp_current_100m_evidence_excerpt": "XIONGAN_GDP_2024=492.4亿元",
    "source_locator": "河北经济年鉴2025表3-8；保定市=5265.7、保定市①=4339.4、定州市=433.9（亿元）；表注含/不含雄安口径",
    "lineage_locator_type": "image_table_calculation",
    "lineage_extraction_method": "official-yearbook-image-table-residual-calculation",
    "lineage_selection_reason": "同一官方表逐行核对城市口径后计算雄安新区合计差额；不使用独立县级数据或媒体转述。",
    "note": "河北省统计局官方年鉴在线图片表3-8；保定市含定州和雄安，保定市①不含定州和雄安。492.4亿元=5265.7−4339.4−433.9，结果保留为calculated。",
}

HEBEI_XIONGAN_FORMULA_REGISTRY = {
    "formula_id": FORMULA_ID,
    "formula_name": "雄安新区 GDP 官方年鉴同表合计差额计算",
    "expression": "保定市（含定州和雄安）−保定市①（不含定州和雄安）−定州市",
    "input_fields": INPUT_FIELDS,
    "output_field": "gdp_current_100m",
    "formula_version": "v1.0",
    "unit": "亿元",
    "enabled": True,
}

HEBEI_XIONGAN_FORMULA_DEPENDENCY = [
    {
        "formula_id": FORMULA_ID,
        "depends_on_field": field,
        "dependency_type": "input",
        "formula_version": "v1.0",
    }
    for field in INPUT_FIELDS.split(";")
]

