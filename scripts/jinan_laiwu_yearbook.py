"""济南统计年鉴2020中的原莱芜市2019年核心经济财政批量来源。"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw" / "province_fiscal" / "2019" / "official"


JINAN_LAIWU_YEARBOOK_SOURCE = {
    "year": 2019,
    "city_name": "莱芜市",
    "city_id": "CN-371200",
    "source_doc_id": "SRC-A2-JINAN-YEARBOOK-2020-LAIWU-2019",
    "url": "https://jntj.jinan.gov.cn/col27523/art/2020/art_27523_4740688.html",
    "attachment_url": "https://jntj.jinan.gov.cn/api-gateway/jpaas-web-server/front/document/download?fileName=605b0cf545ee4542b7211446c37d8302.pdf&fileUrl=n9s7FT%2FT21J6Ntg6aan3xFRjEd2r0oLNnGSGxHskZ7oR59UeOhH52MO2viijJY%2Bjcd80oJukkfX8UuVcbdVMbASKIB6pUMV6xpaAu1nvxKmU8xxUSG6ZdgGADMLgwA6Q",
    "path": RAW_DIR / "jinan_2020_laiwu_yearbook_excerpt.txt",
    "text_path": RAW_DIR / "jinan_2020_laiwu_yearbook_excerpt.txt",
    "text_is_curated": True,
    "document_title": "济南统计年鉴2020",
    "publisher": "济南市统计局",
    "publisher_level": "市级统计机构",
    "publication_date": "2020-11-20",
    "source_grade": "A2",
    "source_format": "txt",
    "raw_unit": "亿元",
    "raw_units": {
        "gdp_current_100m": "亿元",
        "general_public_revenue_100m": "万元",
        "general_public_expenditure_100m": "万元",
    },
    "data_status": "yearbook",
    "data_status_label": "2019年官方统计年鉴值",
    "document_type": "官方统计年鉴分地区经济财政表（原莱芜市全域合计）",
    "page_number": "PDF第129、188、192页（印刷页110、169、173）；表4-13、表8-3、表8-6",
    "patterns": {
        "gdp_current_100m": r"原莱芜市全域GDP=([0-9.]+)亿元",
        "general_public_revenue_100m": r"原莱芜市全域一般公共预算收入=([0-9.]+)万元",
        "general_public_expenditure_100m": r"原莱芜市全域一般公共预算支出=([0-9.]+)万元",
    },
    "note": (
        "A2济南市统计局《济南统计年鉴2020》；表4-13、表8-3、表8-6分别列示"
        "2019年莱芜区和钢城区的GDP、一般公共预算收入和支出。本批按原莱芜市"
        "行政区划调整前全域，将两区同表逐项合计为CN-371200；不将单一区县值"
        "直接代替原地级市值。第129、188、192页均已人工核验，GDP实际增速未列示，"
        "故保持缺失。"
    ),
}


JINAN_LAIWU_YEARBOOK_SOURCES = (JINAN_LAIWU_YEARBOOK_SOURCE,)
