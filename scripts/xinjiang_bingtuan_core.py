"""新疆生产建设兵团汇总单元的核心经济财政来源。

兵团不是普通地级市，但当前全国主表以 CN-659000 作为兵团整体的特殊占位单元。
本适配器只把兵团统计局/国家统计局兵团调查总队公开公报中明确的兵团整体值映射到
该占位单元；不把单个师市或兵团本级值扩展为全兵团值。
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw" / "province_fiscal"
CITY_NAME = "自治区直辖县级行政区划"
CITY_ID = "CN-659000"


def _pattern(year: int, label: str, unit: str) -> str:
    return (
        rf"城市={re.escape(CITY_NAME)}｜年度={year}｜"
        rf"(?:(?!城市=).)*?{re.escape(label)}=([0-9.,-]+){re.escape(unit)}"
    )


def _source(
    *,
    year: int,
    url: str,
    publication_date: str,
    fields: tuple[str, ...],
    note: str,
    source_grade: str = "A2",
    publisher: str = "新疆生产建设兵团统计局、国家统计局兵团调查总队",
    publisher_level: str = "兵团统计机构/国家统计局调查总队",
) -> dict:
    labels = {
        "gdp_current_100m": ("GDP", "亿元"),
        "gdp_real_growth_pct": ("GDP增速", "%"),
        "general_public_revenue_100m": ("一般公共预算收入", "亿元"),
        "general_public_expenditure_100m": ("一般公共预算支出", "亿元"),
    }
    path = RAW_DIR / str(year) / "official" / f"xinjiang_bingtuan_{year}_core_excerpt.txt"
    return {
        "year": year,
        "city_name": CITY_NAME,
        "city_id": CITY_ID,
        "source_doc_id": f"SRC-A2-XPCC-{year}-CORE",
        "url": url,
        "path": path,
        "text_path": path,
        "text_is_curated": True,
        "document_title": f"新疆生产建设兵团{year}年国民经济和社会发展统计公报",
        "publisher": publisher,
        "publisher_level": publisher_level,
        "publication_date": publication_date,
        "source_grade": source_grade,
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": f"{year}年统计公报数（初步统计/执行口径）",
        "document_type": "兵团统计公报核心经济财政指标",
        "page_number": "官方公报综合及财政金融部分",
        "raw_unit": "亿元",
        "raw_units": {field: labels[field][1] for field in fields},
        "patterns": {
            field: _pattern(year, labels[field][0], labels[field][1])
            for field in fields
        },
        "note": note,
    }


XPCC_CORE_SOURCES = (
    _source(
        year=2018,
        url="https://tjj.xjbt.gov.cn/2019nj/data/gb.htm",
        publication_date="2019-03-22",
        fields=(
            "gdp_current_100m",
            "gdp_real_growth_pct",
            "general_public_revenue_100m",
            "general_public_expenditure_100m",
        ),
        note=(
            "A2兵团统计局、国家统计局兵团调查总队官方统计公报；数据为兵团整体口径，"
            "GDP和财政原始单位为亿元，公报说明数据为初步统计数、最终以统计年鉴为准。"
            "本项目将兵团整体映射到全国主表的 CN-659000 特殊占位单元，不扩展单个师市值。"
        ),
    ),
    _source(
        year=2019,
        url="https://tjj.xjbt.gov.cn/2020nj/data/gb.htm?COLLCC=3635967698",
        publication_date="2020-01-01",
        fields=(
            "gdp_current_100m",
            "gdp_real_growth_pct",
            "general_public_revenue_100m",
            "general_public_expenditure_100m",
        ),
        note=(
            "A2兵团统计局、国家统计局兵团调查总队官方统计公报；页面未在当前抓取结果中"
            "提供可确认的发布日期，暂以年度占位日期保存并保留入口页。数据为兵团整体口径，"
            "GDP和财政原始单位为亿元，不使用公共财政预算总收入替代一般公共预算收入。"
        ),
    ),
    _source(
        year=2020,
        url="https://www.xjbt.gov.cn/c/2021-03-18/8011262.shtml",
        publication_date="2021-03-18",
        fields=(
            "gdp_current_100m",
            "gdp_real_growth_pct",
            "general_public_revenue_100m",
            "general_public_expenditure_100m",
        ),
        note=(
            "A2兵团官方统计公报；公报明确一般公共预算收入为153.28亿元，另列公共财政预算"
            "收入预计完成1357.45亿元，本项目仅录入前者；收入属于公报预计/初步口径，保留"
            "preliminary 状态。兵团整体映射到 CN-659000，不扩展单个师市值。"
        ),
    ),
    _source(
        year=2021,
        url="https://tjj.xjbt.gov.cn/2022nj/data/gb.htm",
        publication_date="2022-01-01",
        fields=("gdp_current_100m", "gdp_real_growth_pct"),
        note=(
            "A2兵团统计局、国家统计局兵团调查总队官方统计公报；补入公报明确的兵团整体"
            "GDP和实际增速。该公报当前正文未检出全兵团一般公共预算收支数，因此财政字段"
            "继续保持为空，不用二手估值替代。发布日期暂以年度占位日期保存。"
        ),
    ),
    _source(
        year=2022,
        url="https://www.xjbt.gov.cn/c/2023-03-27/8271400.shtml",
        publication_date="2023-03-24",
        fields=("gdp_current_100m", "gdp_real_growth_pct"),
        note=(
            "A2兵团官方统计公报；补入公报明确的兵团整体GDP和实际增速。公报当前正文未"
            "检出全兵团一般公共预算收支数，财政字段继续保持为空，不用上半年数、预算数或"
            "单个师市值替代。"
        ),
    ),
    _source(
        year=2023,
        url="https://www.huyangnet.cn/content/2024-02/03/content_1864372.html",
        publication_date="2024-02-03",
        fields=("gdp_current_100m", "gdp_real_growth_pct"),
        source_grade="B2",
        publisher="胡杨网（兵团官方新闻门户）",
        publisher_level="兵团官方新闻门户精确转载",
        note=(
            "B2兵团官方新闻门户精确转载；页面明确引用兵团统计数据，列示2023年兵团"
            "生产总值3696.58亿元、按不变价格计算比上年增长6.9%。当前未取得可定位的"
            "兵团官方统计公报财政收支全文，财政字段不代填；不扩展单个师市值。"
        ),
    ),
)
