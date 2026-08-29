"""济源（河南省直辖县级行政区划占位行）官方统计公报来源。"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


HENAN_DIRECT_ADMIN_BULLETIN_SOURCES = (
    {
        "year": 2024,
        "city_name": "省直辖县级行政区划",
        "city_id": "CN-419000",
        "source_doc_id": "SRC-A2-JIYUAN-2024-STATISTICAL-BULLETIN-CORE",
        "url": "https://fgw.jiyuan.gov.cn/14186/17304/20647/t976771.html",
        "attachment_url": "https://fgw.jiyuan.gov.cn/14186/17304/20647/t976771.html",
        "path": ROOT / "raw" / "province_fiscal" / "2024" / "official" / "jiyuan_2024_statistical_bulletin.html",
        "text_path": ROOT / "raw" / "province_fiscal" / "2024" / "official" / "jiyuan_2024_419000_core_excerpt.txt",
        "document_title": "2024年济源国民经济和社会发展统计公报",
        "publisher": "济源产城融合示范区发展改革和统计局",
        "publisher_level": "地市统计机构",
        "publication_date": "2025-04-28",
        "source_grade": "A2",
        "source_format": "html",
        "raw_unit": "亿元",
        "data_status": "bulletin",
        "data_status_label": "2024年官方统计公报值（初步统计）",
        "document_type": "地市官方国民经济和社会发展统计公报",
        "title_source": "official_bulletin",
        "page_number": "网页正文：综合、财政金融",
        "page_count": "1",
        "patterns": {
            "gdp_real_growth_pct": r"增速=([0-9.]+)",
            "general_public_revenue_100m": r"收入=([0-9.]+)",
            "general_public_expenditure_100m": r"支出=([0-9.]+)",
        },
        "note": (
            "A2济源产城融合示范区官方统计公报，明确为全市口径；2024年GDP原公报初步核算为"
            "789.56亿元，2025年官方公报依据第五次全国经济普查将2024年GDP修订为780.21亿元，"
            "本批采用较新的官方修订数，并保留2024年官方公报中的财政执行数。GDP增速、一般预算"
            "收入和支出均按官方公报原文提取，不以省级汇总或市本级数代替。"
        ),
    },
    {
        "year": 2025,
        "city_name": "省直辖县级行政区划",
        "city_id": "CN-419000",
        "source_doc_id": "SRC-A2-JIYUAN-2025-STATISTICAL-BULLETIN-CORE",
        "url": "https://fgw.jiyuan.gov.cn/14186/17304/20647/P020260605388230295609.pdf",
        "attachment_url": "https://fgw.jiyuan.gov.cn/14186/17304/20647/P020260605388230295609.pdf",
        "path": ROOT / "raw" / "province_fiscal" / "2025" / "official" / "jiyuan_2025_statistical_bulletin.pdf",
        "text_path": ROOT / "raw" / "province_fiscal" / "2025" / "official" / "jiyuan_2025_419000_core_excerpt.txt",
        "document_title": "2025年济源国民经济和社会发展统计公报",
        "publisher": "济源产城融合示范区发展改革和统计局",
        "publisher_level": "地市统计机构",
        "publication_date": "2026-06-04",
        "source_grade": "A2",
        "source_format": "pdf",
        "raw_unit": "亿元",
        "data_status": "bulletin",
        "data_status_label": "2025年官方统计公报值（初步统计）",
        "document_type": "地市官方国民经济和社会发展统计公报",
        "title_source": "official_bulletin",
        "page_number": "PDF第2页、第10页",
        "page_count": "16",
        "patterns": {
            "gdp_current_100m": r"GDP=([0-9.]+)",
            "gdp_real_growth_pct": r"增速=([0-9.]+)",
            "general_public_revenue_100m": r"收入=([0-9.]+)",
            "general_public_expenditure_100m": r"支出=([0-9.]+)",
        },
        "note": (
            "A2济源产城融合示范区官方统计公报，明确为全市口径；2025年GDP、GDP增速、一般"
            "公共预算收入和支出均来自公报正文。公报注明2025年数据为初步统计数，并另行披露"
            "2024年GDP修订值；本批2025字段保留初步统计状态，不伪装为最终决算。"
        ),
    },
    {
        "year": 2024,
        "city_name": "省直辖县级行政区划",
        "city_id": "CN-419000",
        "source_doc_id": "SRC-A2-JIYUAN-2025-BULLETIN-2024-REVISED-GDP",
        "url": "https://fgw.jiyuan.gov.cn/14186/17304/20647/P020260605388230295609.pdf",
        "attachment_url": "https://fgw.jiyuan.gov.cn/14186/17304/20647/P020260605388230295609.pdf",
        "path": ROOT / "raw" / "province_fiscal" / "2025" / "official" / "jiyuan_2025_statistical_bulletin.pdf",
        "text_path": ROOT / "raw" / "province_fiscal" / "2025" / "official" / "jiyuan_2024_revised_gdp_excerpt.txt",
        "document_title": "2025年济源国民经济和社会发展统计公报（2024年GDP修订披露）",
        "publisher": "济源产城融合示范区发展改革和统计局",
        "publisher_level": "地市统计机构",
        "publication_date": "2026-06-04",
        "source_grade": "A2",
        "source_format": "pdf",
        "raw_unit": "亿元",
        "data_status": "revised",
        "data_status_label": "2024年官方修订值",
        "document_type": "地市官方统计公报中的历史数据修订披露",
        "title_source": "official_bulletin",
        "page_number": "PDF第15页（印刷页第16页）注2",
        "page_count": "16",
        "patterns": {"gdp_current_100m": r"GDP修订=([0-9.]+)"},
        "note": (
            "A2济源产城融合示范区发展改革和统计局2025年官方统计公报注2明确：根据第五次全国"
            "经济普查结果，2024年济源地区生产总值修订为780.21亿元；本字段以该最新官方修订值"
            "替代2024年公报中的初步核算值789.56亿元，避免同一年度保留旧版GDP。"
        ),
    },
)
