"""图灵数据公开预览截图中的 2025 年城市基金收入精确摘录。

这里只登记无需登录即可查看的公开预览表格单元格。截图中的空白项不转
为零，也不把该付费数据集的未公开下载内容当作已获取来源。
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "raw" / "province_fiscal" / "secondary" / "tuling_fund_preview_2025_excerpt.txt"
LANDING_URL = "https://www.tulingdata.cn/6452/"
ATTACHMENT_URL = "https://www.tulingdata.cn/wp-content/uploads/2026/08/image.avif"


def _source(city_name: str, city_id: str, value: str) -> dict[str, object]:
    return {
        "year": 2025,
        "city_name": city_name,
        "city_id": city_id,
        "source_doc_id": f"SRC-B2-TULING-PREVIEW-FUND-2025-{city_id}",
        "url": LANDING_URL,
        "attachment_url": ATTACHMENT_URL,
        "path": RAW_PATH,
        "text_path": RAW_PATH,
        "text_is_curated": True,
        "document_title": "中国城市-政府性基金收支统计数据集（2000-2025）公开预览表",
        "publisher": "图灵数据（公开预览）",
        "publisher_level": "公开二手数据平台",
        "publication_date": "2026-08-29",
        "source_grade": "B2",
        "source_format": "txt",
        "data_status": "reported",
        "data_status_label": "2025年公开预览精确值",
        "document_type": "公开数据集预览表格逐行摘录",
        "page_number": "公开附件预览截图；按城市代码、年度和金额列定位",
        "source_locator": f"公开预览截图；城市={city_name}；代码={city_id[3:]}; 年度=2025；全市口径",
        "raw_unit": "亿元",
        "patterns": {
            "gov_fund_revenue_100m": (
                rf"城市={re.escape(city_name)}｜代码={city_id[3:]}｜年度=2025｜"
                rf"政府性基金收入=({re.escape(value)})亿元"
            )
        },
        "access_status": "入口页和公开附件预览已归档；未访问受限下载内容",
        "note": (
            "B2公开二手精确表格；仅使用入口页无需登录即可查看的公开预览截图。"
            "截图中空白项保持缺失，不以零值填充；数值单位为亿元，行政范围为城市全市。"
        ),
    }


PUBLIC_PREVIEW_FUND_SOURCES = tuple(
    _source(city, city_id, value)
    for city, city_id, value in (
        ("合肥市", "CN-340100", "396.10"),
        ("蚌埠市", "CN-340300", "65.32"),
        ("淮南市", "CN-340400", "46.42"),
        ("淮北市", "CN-340600", "29.97"),
        ("池州市", "CN-341700", "20.23"),
        ("漳州市", "CN-350600", "210.68"),
        ("兰州市", "CN-620100", "101.33"),
        ("金昌市", "CN-620300", "4.09"),
        ("天水市", "CN-620500", "13.11"),
        ("武威市", "CN-620600", "7.61"),
        ("酒泉市", "CN-620900", "10.03"),
        ("定西市", "CN-621100", "7.88"),
        ("陇南市", "CN-621200", "13.43"),
        ("临夏回族自治州", "CN-622900", "29.11"),
        ("甘南藏族自治州", "CN-623000", "7.39"),
        ("茂名市", "CN-440900", "64.79"),
        ("肇庆市", "CN-441200", "113.14"),
        ("惠州市", "CN-441300", "90.70"),
    )
)
