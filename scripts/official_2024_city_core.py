"""2024 年济宁、牡丹江和宝鸡官方核心字段升级来源。

本批次只接入能够定位到官方公报原件、正文位置和全市口径的数值：
济宁公报同时提供 GDP、GDP 实际增速及一般公共预算收支；牡丹江公报
升级 GDP 现价总量；宝鸡公报升级 GDP 实际增速。摘录文件只作为解析底稿，
原始 PDF/HTML 由 ``load_city_year_fiscal_sources`` 负责下载、哈希和归档。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw" / "province_fiscal" / "2024" / "official"


OFFICIAL_2024_CITY_CORE_SOURCES = (
    {
        "year": 2024,
        "city_name": "济宁市",
        "city_id": "CN-370800",
        "source_doc_id": "SRC-A2-JINING-CITY-STATISTICAL-BULLETIN-2024",
        "url": "https://www.jining.gov.cn/art/2025/4/3/art_33403_2898214.html?xxgkhide=1",
        "landing_page_url": "https://www.jining.gov.cn/art/2025/4/3/art_33403_2898214.html?xxgkhide=1",
        "attachment_url": "https://www.jining.gov.cn/module/download/downfile.jsp?classid=0&showname=2024%E5%B9%B4%E6%B5%8E%E5%AE%81%E5%B8%82%E5%9B%BD%E6%B0%91%E7%BB%8F%E6%B5%8E%E5%92%8C%E7%A4%BE%E4%BC%9A%E5%8F%91%E5%B1%95%E7%BB%9F%E8%AE%A1%E5%85%AC%E6%8A%A5.pdf&filename=d9404370a6774bb9a88816603a903b1b.pdf",
        "path": RAW_DIR / "jining_2024_statistical_bulletin.pdf",
        "text_path": RAW_DIR / "jining_2024_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2024年济宁市国民经济和社会发展统计公报",
        "publisher": "济宁市统计局、国家统计局济宁调查队",
        "publisher_level": "市级统计机构官方统计公报",
        "publication_date": "2025-03-31",
        "source_grade": "A2",
        "source_format": "pdf",
        "data_status": "preliminary",
        "data_status_label": "2024年官方统计公报数",
        "document_type": "官方统计公报经济财政指标",
        "page_number": "PDF第1、11—12页",
        "page_count": "16",
        "raw_unit": "亿元",
        "raw_units": {
            "gdp_current_100m": "亿元",
            "gdp_real_growth_pct": "%",
            "general_public_revenue_100m": "亿元",
            "general_public_expenditure_100m": "亿元",
        },
        "patterns": {
            "gdp_current_100m": r"城市=济宁市｜年度=2024｜GDP=([0-9.]+)亿元｜GDP增速=[0-9.]+%",
            "gdp_real_growth_pct": r"城市=济宁市｜年度=2024｜GDP=[0-9.]+亿元｜GDP增速=([0-9.]+)%",
            "general_public_revenue_100m": r"城市=济宁市｜年度=2024｜.*?一般公共预算收入=([0-9.]+)亿元",
            "general_public_expenditure_100m": r"城市=济宁市｜年度=2024｜.*?一般公共预算支出=([0-9.]+)亿元",
        },
        "source_locator": "PDF第1页综合段、第11—12页财政金融段；城市=济宁市；年度=2024；行政范围=全市",
        "lineage_locator_type": "pdf_text_statement",
        "lineage_extraction_method": "curated-official-pdf-city-core-parser",
        "lineage_normalization_rule": "官方统计公报原始单位为亿元/百分比；数值直接读取，保留两位小数；GDP增速按不变价格计算；行政范围为全市。",
        "lineage_selection_reason": "A2市级统计机构与国家统计局调查队联合发布的官方公报，正文同时明确年度、单位及全市行政范围；用于升级原 D/B2 暂存值。",
        "note": "济宁市统计局、国家统计局济宁调查队官方统计公报；第1页披露全市生产总值5867.5亿元、按不变价格增长5.8%，第11—12页披露全市一般公共预算收入496.3亿元、支出800.2亿元。公报数据为初步统计数。",
    },
    {
        "year": 2024,
        "city_name": "牡丹江市",
        "city_id": "CN-231000",
        "source_doc_id": "SRC-A2-MUDANJIANG-CITY-STATISTICAL-BULLETIN-2024-GDP",
        "url": "https://www.mdj.gov.cn/mdjsrmzf/c100093/202504/1002755/files/2024%E5%B9%B4%E7%89%A1%E4%B8%B9%E6%B1%9F%E5%B8%82%E5%9B%BD%E6%B0%91%E7%BB%8F%E6%B5%8E%E5%92%8C%E7%A4%BE%E4%BC%9A%E5%8F%91%E5%B1%95%E7%BB%9F%E8%AE%A1%E5%85%AC%E6%8A%A5.pdf",
        "landing_page_url": "https://www.mdj.gov.cn/mdjsrmzf/c100093/202504/1002755.shtml",
        "attachment_url": "https://www.mdj.gov.cn/mdjsrmzf/c100093/202504/1002755/files/2024%E5%B9%B4%E7%89%A1%E4%B8%B9%E6%B1%9F%E5%B8%82%E5%9B%BD%E6%B0%91%E7%BB%8F%E6%B5%8E%E5%92%8C%E7%A4%BE%E4%BC%9A%E5%8F%91%E5%B1%95%E7%BB%9F%E8%AE%A1%E5%85%AC%E6%8A%A5.pdf",
        "path": RAW_DIR / "mudanjiang_2024_statistical_bulletin.pdf",
        "text_path": RAW_DIR / "mudanjiang_2024_statistical_bulletin_core_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2024年牡丹江市国民经济和社会发展统计公报",
        "publisher": "牡丹江市统计局",
        "publisher_level": "市级统计机构官方统计公报",
        "publication_date": "2025-04-16",
        "source_grade": "A2",
        "source_format": "pdf",
        "data_status": "preliminary",
        "data_status_label": "2024年官方统计公报数",
        "document_type": "官方统计公报 GDP 指标",
        "page_number": "PDF第2页综合段",
        "page_count": "11",
        "raw_unit": "亿元",
        "raw_units": {"gdp_current_100m": "亿元"},
        "patterns": {
            "gdp_current_100m": r"城市=牡丹江市｜年度=2024｜GDP=([0-9.]+)亿元｜GDP增速=[0-9.]+%",
        },
        "source_locator": "PDF第2页综合段；城市=牡丹江市；年度=2024；行政范围=全市",
        "lineage_locator_type": "pdf_text_statement",
        "lineage_extraction_method": "curated-official-pdf-city-core-parser",
        "lineage_normalization_rule": "官方统计公报原始单位为亿元；数值直接读取，保留两位小数；行政范围为全市。",
        "lineage_selection_reason": "A2市级统计机构官方公报明确披露2024年全市地区生产总值现价总量，用于升级原 D 级暂存值。",
        "note": "牡丹江市统计局官方统计公报；第2页披露2024年全市地区生产总值1051.4亿元、比上年增长3.8%，GDP总量接入本批，增速和财政收支沿用已有官方字段来源。",
    },
    {
        "year": 2024,
        "city_name": "宝鸡市",
        "city_id": "CN-610300",
        "source_doc_id": "SRC-A2-BAOJI-CITY-STATISTICAL-BULLETIN-2024",
        "url": "https://tjj.baoji.gov.cn/zzzb/tjgb/202505/t20250516_1149356.html",
        "landing_page_url": "https://tjj.baoji.gov.cn/zzzb/tjgb/202505/t20250516_1149356.html",
        "attachment_url": "https://tjj.baoji.gov.cn/zzzb/tjgb/202505/t20250516_1149356.html",
        "path": RAW_DIR / "baoji_2024_statistical_bulletin.html",
        "text_path": RAW_DIR / "baoji_2024_statistical_bulletin_core_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2024年宝鸡市国民经济和社会发展统计公报",
        "publisher": "宝鸡市统计局、国家统计局宝鸡调查队",
        "publisher_level": "市级统计机构官方统计公报",
        "publication_date": "2025-05-16",
        "source_grade": "A2",
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2024年官方统计公报数",
        "document_type": "官方统计公报 GDP 增速指标",
        "page_number": "官方网页综合段",
        "page_count": "1",
        "raw_unit": "%",
        "raw_units": {"gdp_real_growth_pct": "%"},
        "patterns": {
            "gdp_real_growth_pct": r"城市=宝鸡市｜年度=2024｜GDP增速=([0-9.]+)%",
        },
        "source_locator": "官方统计公报综合段；城市=宝鸡市；年度=2024；行政范围=全市",
        "lineage_locator_type": "html_text_statement",
        "lineage_extraction_method": "curated-official-html-city-core-parser",
        "lineage_normalization_rule": "官方统计公报原始单位为%；数值直接读取，保留两位小数；GDP增速按不变价格计算；行政范围为全市。",
        "lineage_selection_reason": "A2市级统计机构与国家统计局调查队联合发布的官方公报明确披露2024年全市GDP实际增速，用于升级原 B2 暂存来源。",
        "note": "宝鸡市统计局、国家统计局宝鸡调查队官方统计公报；综合段明确2024年全市地区生产总值按不变价格比上年增长5.6%，本批只升级增速字段，GDP现价总量及财政字段沿用各自更高等级来源。",
    },
)


__all__ = ["OFFICIAL_2024_CITY_CORE_SOURCES"]
