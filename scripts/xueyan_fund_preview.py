"""学研数据网公开预览图片中的城市政府性基金收入精确摘录。

只使用入口页和无需登录即可查看的公开预览证据，不访问付费下载链接；
预览中没有明确数值的城市年度保持缺失。
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "raw" / "province_fiscal" / "secondary" / "xueyan_fund_preview_excerpt.txt"
LANDING_URL = "https://www.xueyandata.com/2331/"
IMAGE_URL = "https://www.xueyandata.com/wp-content/uploads/2025/08/微信图片_20250824095044_319_89.png"


def _source(city_name: str, city_id: str, year: int, value: str) -> dict[str, object]:
    return {
        "year": year,
        "city_name": city_name,
        "city_id": city_id,
        "source_doc_id": f"SRC-B2-XUEYAN-PREVIEW-FUND-{year}-{city_id}",
        "url": LANDING_URL,
        "attachment_url": IMAGE_URL,
        "path": RAW_PATH,
        "text_path": RAW_PATH,
        "text_is_curated": True,
        "document_title": "地级市政府性基金收入合计 2002~2024 公开预览表",
        "publisher": "学研数据网（公开预览）",
        "publisher_level": "公开二手数据平台",
        "publication_date": "2025-08-24",
        "source_grade": "B2",
        "source_format": "txt",
        "data_status": "reported",
        "data_status_label": "公开预览精确值",
        "document_type": "公开数据集预览表格逐行摘录",
        "page_number": "入口页公开预览图片；按城市代码、年度和金额列定位",
        "source_locator": f"入口页公开预览图片；城市={city_name}；代码={city_id[3:]}; 年度={year}；全市口径",
        "raw_unit": "亿元",
        "patterns": {
            "gov_fund_revenue_100m": (
                rf"城市={re.escape(city_name)}｜代码={city_id[3:]}｜年度={year}｜"
                rf"政府性基金收入=({re.escape(value)})亿元"
            )
        },
        "access_status": "入口页和公开预览图片已归档；未访问受限下载内容",
        "note": (
            "B2公开二手精确表格；仅使用无需登录即可查看的公开预览图片。"
            "不绕过付费下载，不对预览未列示年度插值；数值单位为亿元，行政范围为地级市全市。"
        ),
    }


PUBLIC_PREVIEW_FUND_SOURCES = tuple(
    _source(city, city_id, year, value)
    for city, city_id, year, value in (
        ("七台河市", "CN-230900", 2022, "5.18"),
        ("七台河市", "CN-230900", 2023, "3.22"),
        ("七台河市", "CN-230900", 2024, "2.27"),
        ("三亚市", "CN-460200", 2022, "70.96"),
        ("三亚市", "CN-460200", 2023, "153.30"),
        ("三亚市", "CN-460200", 2024, "119.30"),
    )
)
