"""玉树州 2024 年全州财政预算执行报告来源。

来源为玉树州人民政府门户发布、玉树州财政局提交自治州人代会审议的
《玉树藏族自治州2024年财政预算执行情况和2025年财政预算草案的报告》。
报告明确披露全州口径的一般公共预算收入、支出和政府性基金预算收入。
报告同时说明，省财政厅批复决算后具体收支可能调整，因此本来源标记为
``execution``，不冒充最终决算。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
_RAW_DIR = ROOT / "raw" / "province_fiscal" / "2024" / "official"


YUSHU_2024_BUDGET_SOURCE = {
    "year": 2024,
    "city_name": "玉树藏族自治州",
    "city_id": "CN-632700",
    "source_doc_id": "SRC-A2-YUSHU-2024-BUDGET-EXECUTION",
    "url": "https://www.yushuzhou.gov.cn/html/2856/632425.html",
    "landing_page_url": "https://www.yushuzhou.gov.cn/html/2856/632425.html",
    "attachment_url": "https://www.yushuzhou.gov.cn/webaspx/ImageHandler.ashx?portalid=1&filename=/images/2025021712001636311.pdf",
    "path": _RAW_DIR / "yushu_budget_report_2024.pdf",
    "text_path": _RAW_DIR / "yushu_budget_report_2024_excerpt.txt",
    "text_is_curated": True,
    "document_title": "玉树藏族自治州2024年财政预算执行情况和2025年财政预算草案的报告",
    "publisher": "玉树州财政局",
    "publisher_level": "州级财政机构",
    "publication_date": "2025-01-31",
    "source_grade": "A2",
    "source_format": "pdf",
    "data_status": "execution",
    "data_status_label": "2024年全州一般公共预算执行数/政府性基金预算收入执行数",
    "document_type": "州级财政局官方预算执行报告",
    "page_number": "PDF第2—3页；第5页决算调整说明",
    "page_count": "101",
    "access_status": "官方网页及PDF附件已归档",
    "raw_unit": "亿元",
    "patterns": {
        "general_public_revenue_100m": (
            r"全州一般公共预算总收入完成[0-9.]+亿元[，,]其中：地方一般公共预算收入完成([0-9.]+)亿元"
        ),
        "general_public_expenditure_100m": (
            r"全州一般公共预算总支出完成[0-9.]+亿元[，,]其中：一般公共预算支出完成([0-9.]+)亿元"
        ),
        "gov_fund_revenue_100m": (
            r"全州政府性基金预算收入完成[0-9.]+亿元[，,]其中：地方政府性基金预算收入完成([0-9.]+)亿元"
        ),
    },
    "note": (
        "A2玉树州人民政府门户发布、玉树州财政局官方报告，明确为玉树州全州口径。"
        "报告披露2024年地方一般公共预算收入3.74亿元、地方一般公共预算支出163.76亿元、"
        "地方政府性基金预算收入0.25亿元；原始单位为亿元。报告第5页说明全州和州本级"
        "四本预算具体收支待省财政厅批复决算后可能变化，因此标记为execution，不伪装成final。"
        "不使用州本级数，也不使用2025年预算草案数。"
    ),
}

