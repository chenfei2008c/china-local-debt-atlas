"""湖北省直管四单元 2025 年官方统计公报批次。"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_BASE = ROOT / "raw" / "province_fiscal" / "hubei_bulletin" / "2025"


HUBEI_DIRECT_ADMIN_2025_BULLETIN_SOURCE = {
    "year": 2025,
    "city_name": "湖北省直辖县级行政区划",
    "city_id": "CN-429000",
    "source_doc_id": "SRC-A2-HUBEI-2025-BULLETINS-429000-CORE",
    "url": "https://tjj.hubei.gov.cn/tjsj/tjgb/ndtjgb/sztjgb/",
    "attachment_url": "https://tjj.hubei.gov.cn/tjsj/tjgb/ndtjgb/sztjgb/202605/P020260508387240145521.pdf",
    "path": RAW_BASE / "xiantao_2025_bulletin.pdf",
    "text_path": RAW_BASE / "hubei_2025_429000_bulletins_excerpt.txt",
    "document_title": "湖北省直管四单元2025年国民经济和社会发展统计公报汇编",
    "publisher": "湖北省统计局及仙桃、潜江、天门、神农架林区统计机构",
    "publisher_level": "省级统计机构及直管单元统计机构",
    "publication_date": "2026-05-08",
    "source_grade": "A2",
    "source_format": "pdf",
    "raw_unit": "亿元",
    "data_status": "preliminary",
    "data_status_label": "2025年统计快报数",
    "document_type": "市级统计公报官方PDF汇编（直管单元汇总）",
    "page_number": "仙桃第1、8页；潜江公报第1、8页；天门第1、7页；神农架第2、8页",
    "patterns": {
        "gdp_current_100m": r"GDP=([0-9.]+)",
        "general_public_revenue_100m": r"收入=([0-9.]+)",
        "general_public_expenditure_100m": r"支出=([0-9.]+)",
    },
    "note": (
        "A2湖北省统计局市州统计公报入口及四个直管单元官方公报；四份公报均明确2025年"
        "GDP现价绝对数、一般公共预算收入/支出及全市行政范围。本批逐项加总仙桃、潜江、"
        "天门、神农架林区四地数值，收入采用地方一般公共预算收入，支出采用一般公共预算"
        "支出；2025年公报属于统计快报/初步核算，保留preliminary状态。公报没有直管四单元"
        "合计GDP实际增速，故不以当前价加权或简单平均方式生成该字段。"
    ),
}
