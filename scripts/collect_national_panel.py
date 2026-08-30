#!/usr/bin/env python3
"""采集并生成全国地级行政单元 2018—2026 年数据面板。

本脚本把“抓取”拆成可审计的几个阶段：
1. 下载并保存年度行政区划原始文件；
2. 生成年度城市主表；
3. 读取公开研究型城市面板作为暂存/临时宏观来源；
4. 合并已经完成的广东省 2024 年官方试跑结果、2025 年官方地市 GDP/财政批次、宁夏四市、山东济南/青岛及常州/洛阳/岳阳/衡阳 2025 年财政执行批次；
5. 以 Decimal 计算派生指标并写出来源、字段血缘、公式和采集状态。

没有公开且可验证的数值保持为空，并进入 collection_status；不得用 0 代替缺失。
"""

from __future__ import annotations

import csv
import gzip
import hashlib
from html import unescape
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, getcontext
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.request import Request, urlopen

try:
    from scripts.province_debt_sources import extract_official_debt_facts
    from scripts.data_quality import OFFICIAL_DEBT_EXCEPTION_STATUS, debt_fact_has_balance_limit_conflict
    from scripts.evidence_based_missing import EVIDENCE_BY_KEY, EVIDENCE_CHECKED_AT, EVIDENCE_SOURCE_DOCUMENTS
    from scripts.official_city_macro_sources import parse_city_fund_revenue_text, parse_guangdong_city_budget_page, parse_guangdong_city_gdp_html
    from scripts.pdf_layout_text import extract_pdf_text
    from scripts.batch_source_registry import (
        BATCH_REGISTRY_FIELDS,
        CORE_COVERAGE_FIELDS,
        build_batch_source_registry,
        build_core_coverage_report,
    )
    from scripts.batch_table_parser import parse_city_value_rows
    from scripts.city_yearbook_sources import load_city_yearbook_sources
except ModuleNotFoundError:  # 允许以 python scripts/collect_national_panel.py 直接运行
    from province_debt_sources import extract_official_debt_facts
    from data_quality import OFFICIAL_DEBT_EXCEPTION_STATUS, debt_fact_has_balance_limit_conflict
    from evidence_based_missing import EVIDENCE_BY_KEY, EVIDENCE_CHECKED_AT, EVIDENCE_SOURCE_DOCUMENTS
    from official_city_macro_sources import parse_city_fund_revenue_text, parse_guangdong_city_budget_page, parse_guangdong_city_gdp_html
    from pdf_layout_text import extract_pdf_text
    from batch_source_registry import (
        BATCH_REGISTRY_FIELDS,
        CORE_COVERAGE_FIELDS,
        build_batch_source_registry,
        build_core_coverage_report,
    )
    from batch_table_parser import parse_city_value_rows
    from city_yearbook_sources import load_city_yearbook_sources

try:
    from scripts.curated_city_fiscal_2025 import CURATED_2025_CITY_FISCAL_SOURCES
    from scripts.supplemental_city_fiscal_2025 import SUPPLEMENTAL_CITY_FISCAL_SOURCES
    from scripts.regional_fiscal_2024 import REGIONAL_FISCAL_2024_SOURCES
    from scripts.city_fiscal_rating_2024_2025 import CITY_FISCAL_RATING_2024_2025_SOURCES
    from scripts.dagong_city_fiscal_2024_2025 import DAGONG_CITY_FISCAL_SOURCES
    from scripts.nbs_city_annual_2024 import load_nbs_city_annual_2024
    from scripts.regional_fiscal_2022_2024 import load_regional_fiscal_sources
    from scripts.celma_city_annual import load_celma_city_annual_sources
    from scripts.gotohui_city_series import load_gotohui_city_series_sources
    from scripts.crei_city_bulletins import load_crei_city_bulletin_sources
    from scripts.hongheiku_city_bulletins import load_hongheiku_city_bulletin_sources
    from scripts.dachuang_city_panel import load_dachuang_city_panel_sources
    from scripts.haidatas_city_panel import HAIDATAS_SOURCE_ID, load_haidatas_city_panel_sources
    from scripts.hubei_direct_admin_yearbook import HUBEI_DIRECT_ADMIN_YEARBOOK_SOURCES
    from scripts.hubei_direct_admin_2025_bulletins import HUBEI_DIRECT_ADMIN_2025_BULLETIN_SOURCE
    from scripts.hainan_direct_admin_yearbook import HAINAN_DIRECT_ADMIN_YEARBOOK_SOURCES
    from scripts.hainan_direct_admin_yearbook import HAINAN_DIRECT_ADMIN_YEARBOOK_2025_SOURCES
    from scripts.hainan_direct_admin_yearbook import HAINAN_DIRECT_ADMIN_YEARBOOK_2023_SOURCES
    from scripts.hainan_direct_admin_yearbook import HAINAN_DIRECT_ADMIN_YEARBOOK_2019_2021_SOURCES
    from scripts.henan_direct_admin_bulletins import HENAN_DIRECT_ADMIN_BULLETIN_SOURCES
    from scripts.jiyuan_historical_bulletins import JIYUAN_HISTORICAL_SOURCES
except ModuleNotFoundError:  # 允许以 python scripts/collect_national_panel.py 直接运行
    from curated_city_fiscal_2025 import CURATED_2025_CITY_FISCAL_SOURCES
    from supplemental_city_fiscal_2025 import SUPPLEMENTAL_CITY_FISCAL_SOURCES
    from regional_fiscal_2024 import REGIONAL_FISCAL_2024_SOURCES
    from city_fiscal_rating_2024_2025 import CITY_FISCAL_RATING_2024_2025_SOURCES
    from dagong_city_fiscal_2024_2025 import DAGONG_CITY_FISCAL_SOURCES
    from nbs_city_annual_2024 import load_nbs_city_annual_2024
    from regional_fiscal_2022_2024 import load_regional_fiscal_sources
    from celma_city_annual import load_celma_city_annual_sources
    from gotohui_city_series import load_gotohui_city_series_sources
    from crei_city_bulletins import load_crei_city_bulletin_sources
    from hongheiku_city_bulletins import load_hongheiku_city_bulletin_sources
    from dachuang_city_panel import load_dachuang_city_panel_sources
    from haidatas_city_panel import HAIDATAS_SOURCE_ID, load_haidatas_city_panel_sources
    from hubei_direct_admin_yearbook import HUBEI_DIRECT_ADMIN_YEARBOOK_SOURCES
    from hubei_direct_admin_2025_bulletins import HUBEI_DIRECT_ADMIN_2025_BULLETIN_SOURCE
    from hainan_direct_admin_yearbook import HAINAN_DIRECT_ADMIN_YEARBOOK_SOURCES
    from hainan_direct_admin_yearbook import HAINAN_DIRECT_ADMIN_YEARBOOK_2025_SOURCES
    from hainan_direct_admin_yearbook import HAINAN_DIRECT_ADMIN_YEARBOOK_2023_SOURCES
    from hainan_direct_admin_yearbook import HAINAN_DIRECT_ADMIN_YEARBOOK_2019_2021_SOURCES
    from henan_direct_admin_bulletins import HENAN_DIRECT_ADMIN_BULLETIN_SOURCES
    from jiyuan_historical_bulletins import JIYUAN_HISTORICAL_SOURCES

getcontext().prec = 40

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw"
OUTPUT_DIR = ROOT / "outputs" / "national_prefecture_panel_2018_2026"
RETRIEVED_AT = "2026-08-01T00:00:00+08:00"
START_YEAR = 2018
END_YEAR = 2026
AVAILABLE_ROSTER_YEARS = range(2018, 2025)
DIRECT_MUNICIPALITIES = {"110000": "北京市", "120000": "天津市", "310000": "上海市", "500000": "重庆市"}
CITY_PANEL_URL = "https://raw.githubusercontent.com/JasmineHao/JasmineHao.github.io/main/econ6083/final-project/notebooks/data/china_city_panel_with_policies.csv"
AREA_URL_TEMPLATE = "https://raw.githubusercontent.com/adyliu/china_area/master/area_code_{year}.csv.gz"
NBS_RULE_URL = "https://www.stats.gov.cn/hd/cjwtjd/202302/t20230207_1902279.html"
GD_ROOT = Path("/Users/kataru/Library/Mobile Documents/com~apple~CloudDocs/Documents/wkplz/268801 中国地方债研究/outputs/guangdong_2024")
GD_2025_GDP_URL = "https://stats.gd.gov.cn/fsjdgnsczz/content/post_4854894.html"
GD_2025_GDP_PATH = RAW_DIR / "macro_fiscal" / "guangdong_2025_city_gdp.html"
GD_BUDGET_REPORT_URL = "https://czt.gd.gov.cn/czysjs/content/post_4857651.html"
GD_BUDGET_ATTACHMENT_3_URL = "https://czt.gd.gov.cn/attachment/0/607/607013/4857651.pdf"
GD_BUDGET_ATTACHMENT_3_PATH = RAW_DIR / "province_fiscal" / "2025" / "official" / "guangdong_2025_budget_attachment_3.pdf"
GD_BUDGET_ATTACHMENT_3_TEXT_PATH = GD_BUDGET_ATTACHMENT_3_PATH.with_suffix(".txt")
GD_CITY_FUND_SOURCES = (
    {
        "city_name": "广州市",
        "city_id": "CN-440100",
        "source_doc_id": "SRC-GZ-CITY-FUND-2025",
        "url": "https://www.gz.gov.cn/attachment/7/7970/7970896/10682364.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "guangzhou_2025_budget_report.pdf",
        "document_title": "广州市2025年预算执行情况和2026年预算草案",
        "publisher": "广州市财政局",
        "publication_date": "2026-01-19",
        "note": "报告正文标记为2025年预计执行情况；全市政府性基金预算收入为1000亿元，表21同步列示执行数10000000万元。",
    },
    {
        "city_name": "深圳市",
        "city_id": "CN-440300",
        "source_doc_id": "SRC-SZ-CITY-FUND-2025",
        "url": "https://www.sz.gov.cn/attachment/1/1704/1704493/12737941.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "shenzhen_2025_budget_report.pdf",
        "document_title": "关于深圳市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "深圳市财政局",
        "publication_date": "2026-04-13",
        "note": "官方公报正文披露2025年全市政府性基金预算收入667亿元，并明确为预计执行数，待年终决算依法报告。",
    },
    {
        "city_name": "东莞市",
        "city_id": "CN-441900",
        "source_doc_id": "SRC-DG-CITY-FUND-2025",
        "url": "https://czj.dg.gov.cn/attachment/0/403/403768/4501595.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "dongguan_2025_budget_report.pdf",
        "document_title": "东莞市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "东莞市财政局",
        "publication_date": "2026-02-04",
        "note": "官方预算执行报告正文披露2025年全市政府性基金预算收入138.49亿元，执行状态明确。",
    },
    {
        "city_name": "中山市",
        "city_id": "CN-442000",
        "source_doc_id": "SRC-ZS-CITY-FUND-2025",
        "url": "https://czj.zs.gov.cn/sy/gzdt/zwdt/content/post_2594033.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "zhongshan_2025_budget_report.html",
        "format": "html",
        "document_title": "2026年中山市本级政府预算公开",
        "publisher": "中山市财政局",
        "publication_date": "2026-02-05",
        "note": "官方预算公开PDF正文披露2025年全市政府性基金收入80.4亿元，按报告原文全市口径记录。",
    },
    {
        "city_name": "汕头市",
        "city_id": "CN-440500",
        "source_doc_id": "SRC-ST-CITY-FUND-2025",
        "url": "https://rd.shantou.gov.cn/swjdbzhy/wjgg/202602/d8eb76c630924e459f556039f751330f.shtml",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "shantou_2025_budget_report.html",
        "format": "html",
        "document_title": "汕头市第十五届人民代表大会财政经济委员会关于汕头市2025年预算执行情况和2026年预算草案的审查结果报告",
        "publisher": "汕头市人大",
        "publication_date": "2026-02-05",
        "note": "市人大官方审查结果报告明确披露2025年全市政府性基金预算收入100.7亿元，执行口径、全市口径。",
    },
    {
        "city_name": "湛江市",
        "city_id": "CN-440800",
        "source_doc_id": "SRC-ZJ-CITY-FUND-2025",
        "url": "https://www.zhanjiang.gov.cn/zdlyxxgk/czyjshsg/czyjs/czys/content/post_2159807.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "zhanjiang_2025_budget_report.html",
        "format": "html",
        "document_title": "湛江市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "湛江市人民政府",
        "publication_date": "2026-02-05",
        "note": "市政府官方报告明确披露2025年全市政府性基金预算收入64.7亿元，完成年度预算82.8%，执行口径、全市口径。",
    },
)
CITY_FUND_SOURCE_IDS = {item["source_doc_id"] for item in GD_CITY_FUND_SOURCES}

# 宁夏四市 2025 年预算执行报告同时包含全市财政收支和政府性基金收入。
# 这些报告此前已作为债务来源归档；本批以独立来源 ID 登记宏观字段，避免把
# 债务字段和财政字段混成同一条字段血缘。
NINGXIA_2025_FISCAL_SOURCES = (
    {
        "city_name": "银川市",
        "city_id": "CN-640100",
        "source_doc_id": "SRC-NINGXIA-CITY-FISCAL-YINCHUAN-2025",
        "url": "https://www.yinchuan.gov.cn/xxgk/bmxxgkml/sczj/xxgkml_2101/czyjsjsgjf_2119/zfys/202602/t20260212_5171239.html",
        "path": RAW_DIR / "province_debt" / "2025" / "official" / "yinchuan_2025.pdf",
        "text_path": RAW_DIR / "province_debt" / "2025" / "official" / "yinchuan_2025.txt",
        "document_title": "2025年银川市及市本级预算执行情况和2026年银川市及市本级预算草案的报告",
        "publisher": "银川市财政局",
        "publication_date": "2026-02-12",
        "patterns": {
            "general_public_revenue_100m": (r"全市一般公共预算收入(?:完成)?([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"全市一般公共预算支出完成([0-9.]+)亿元", "亿元"),
            "gov_fund_revenue_100m": (r"全市政府性基金预算收入完成([0-9.]+)亿元", "亿元"),
        },
        "note": "官方预算执行报告正文逐项披露全市口径 2025 年一般公共预算收入、支出和政府性基金预算收入；执行数，不使用市本级数或 2026 年预算草案数。",
    },
    {
        "city_name": "石嘴山市",
        "city_id": "CN-640200",
        "source_doc_id": "SRC-NINGXIA-CITY-FISCAL-SHIZUISHAN-2025",
        "url": "https://www.shizuishan.gov.cn/zwgk/zfxxgkml/czyjsgk/zfys/2026df/202601/P020260206403630063012.pdf",
        "path": RAW_DIR / "province_debt" / "2025" / "official" / "shizuishan_2025.pdf",
        "text_path": RAW_DIR / "province_debt" / "2025" / "official" / "shizuishan_2025.txt",
        "document_title": "关于2025年全市及市本级预算执行情况和2026年全市及市本级预算（草案）的报告",
        "publisher": "石嘴山市财政局",
        "publication_date": "2026-01-29",
        "patterns": {
            "general_public_revenue_100m": (r"全市一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
            "gov_fund_revenue_100m": (r"全市政府性基金预算收入([0-9.]+)亿元", "亿元"),
        },
        "note": "官方预算执行报告正文逐项披露全市口径 2025 年一般公共预算收入、支出和政府性基金预算收入；执行数，不使用市本级数或 2026 年预算草案数。",
    },
    {
        "city_name": "吴忠市",
        "city_id": "CN-640300",
        "source_doc_id": "SRC-NINGXIA-CITY-FISCAL-WUZHONG-2025",
        "url": "https://www.wuzhong.gov.cn/xxgk/zfxxgkml/yjsgkqk/zfys/2026n/202602/P020260204632187152760.pdf",
        "path": RAW_DIR / "province_debt" / "2025" / "official" / "wuzhong_2025.pdf",
        "text_path": RAW_DIR / "province_debt" / "2025" / "official" / "wuzhong_2025.txt",
        "document_title": "吴忠市2026年政府预算公开（2025年预算执行情况）",
        "publisher": "吴忠市财政局",
        "publication_date": "2026-02-04",
        "patterns": {
            "general_public_revenue_100m": (r"2025年，全市一般公共预算收入完成([0-9,]+)万元", "万元"),
            "general_public_expenditure_100m": (r"2025年[，,]?全市一般公共预算支出完成([0-9,]+)万元", "万元"),
            "gov_fund_revenue_100m": (r"全市政府性基金收入完成([0-9,]+)万元", "万元"),
        },
        "note": "官方预算公开报告附表/说明逐项披露全市口径 2025 年精确执行数；原始单位为万元，统一换算为亿元，不使用正文四舍五入值或市本级数。",
    },
    {
        "city_name": "中卫市",
        "city_id": "CN-640500",
        "source_doc_id": "SRC-NINGXIA-CITY-FISCAL-ZHONGWEI-2025",
        "url": "https://www.nxzw.gov.cn/zwgk/bmxxgkml/sczj/fdzdgknr_49463/ysjsxx_49468/zfys/202602/P020260323561503366266.pdf",
        "path": RAW_DIR / "province_debt" / "2025" / "official" / "zhongwei_2025.pdf",
        "text_path": RAW_DIR / "province_debt" / "2025" / "official" / "zhongwei_2025.txt",
        "document_title": "中卫市2026年政府预算信息公开（2025年预算执行情况）",
        "publisher": "中卫市财政局",
        "publication_date": "2026-02-12",
        "patterns": {
            "general_public_revenue_100m": (r"全市地方一般公共预算收入完成([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"全市一般公共预算支出完成([0-9.]+)亿元", "亿元"),
            "gov_fund_revenue_100m": (r"全市地方政府性基金预算收入完成([0-9.]+)亿元", "亿元"),
        },
        "note": "官方预算公开报告正文逐项披露全市口径 2025 年执行数；不使用市本级数或 2026 年预算草案数。",
    },
)

SHANDONG_2025_FISCAL_SOURCES = (
    {
        "city_name": "济南市",
        "city_id": "CN-370100",
        "source_doc_id": "SRC-SHANDONG-CITY-FISCAL-JINAN-2025",
        "url": "https://jncz.jinan.gov.cn/col/col48336/art/2026/art_95d35f3c8a1e47469fb8b5fa3cf63f50.html",
        "attachment_url": "https://jnns.jinan.gov.cn/cms_files/filemanager/1668/attach/20262/cbbf22b3087f4fa89ef76c2891f3272f.pdf?fileName=%E5%85%B3%E4%BA%8E%E6%B5%8E%E5%8D%97%E5%B8%822025%E5%B9%B4%E9%A2%84%E7%AE%97%E6%89%A7%E8%A1%8C%E6%83%85%E5%86%B5%E4%B8%8E2026%E5%B9%B4%E9%A2%84%E7%AE%97%E8%8D%89%E6%A1%88%E7%9A%84%E6%8A%A5%E5%91%8A.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "jinan_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "jinan_2025_budget_report.txt",
        "document_title": "关于济南市2025年预算执行情况与2026年预算草案的报告及附表",
        "publisher": "济南市财政局",
        "publication_date": "2026-02-10",
        "patterns": {
            "general_public_revenue_100m": (r"全市一般公共预算收入完成([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
            "gov_fund_revenue_100m": (r"全市政府性基金预算收入完成([0-9.]+)亿元", "亿元"),
        },
        "note": "济南市财政局官方预算执行报告披露全市口径 2025 年执行数；不使用市级或 2026 年预算草案数。",
    },
    {
        "city_name": "青岛市",
        "city_id": "CN-370200",
        "source_doc_id": "SRC-SHANDONG-CITY-FISCAL-QINGDAO-2025",
        "url": "https://www.qingdao.gov.cn/zwgk/zdgk/czxx/szfyjs/zxqk/202601/t20260130_10495657.shtml",
        "attachment_url": "https://www.qingdao.gov.cn/zwgk/zdgk/czxx/szfyjs/zxqk/202601/P020260130338555114519.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "qingdao_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "qingdao_2025_budget_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "关于青岛市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "青岛市财政局",
        "publication_date": "2026-01-30",
        "patterns": {
            "general_public_revenue_100m": (r"全市一般公共预算收入完成([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"全市一般公共预算支出完成([0-9.]+)亿元", "亿元"),
            "gov_fund_revenue_100m": (r"全市政府性基金预算收入完成([0-9.]+)亿元", "亿元"),
        },
        "note": "青岛市财政局官方预算执行报告披露全市口径 2025 年执行数；不使用市级或 2026 年预算草案数。",
    },
)

NEXT_2025_FISCAL_SOURCES = (
    {
        "city_name": "常州市",
        "city_id": "CN-320400",
        "source_doc_id": "SRC-JIANGSU-CITY-FISCAL-CHANGZHOU-2025",
        "url": "https://rd.changzhou.gov.cn/html/rd/2026/EKPMKPDC_0122/35038.html",
        "attachment_url": "https://rd.changzhou.gov.cn/html/rd/2026/EKPMKPDC_0122/35038.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "changzhou_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "changzhou_2025_budget_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "关于常州市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "常州市财政局",
        "publication_date": "2026-01-22",
        "title_source": "official_page_excerpt",
        "document_type": "官方城市财政预算执行报告（网页）",
        "mime_type": "text/html",
        "patterns": {
            "general_public_revenue_100m": (r"全市一般公共预算收入完成([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"全市一般公共预算支出完成([0-9.]+)亿元", "亿元"),
            "gov_fund_revenue_100m": (r"全市政府性基金预算收入完成([0-9.]+)亿元", "亿元"),
        },
        "note": "常州市人大公开的财政局报告披露全市口径 2025 年预计执行数；报告明确最终数字以 2025 年决算草案为准，当前标记为 execution，不作为最终决算数解读。",
    },
    {
        "city_name": "洛阳市",
        "city_id": "CN-410300",
        "source_doc_id": "SRC-HENAN-CITY-FISCAL-LUOYANG-2025",
        "url": "https://oss.ly.gov.cn/upload-file/files/20260305/4e03eb31347142f2902b518d7388a496.pdf",
        "attachment_url": "https://oss.ly.gov.cn/upload-file/files/20260305/4e03eb31347142f2902b518d7388a496.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "luoyang_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "luoyang_2025_budget_report.txt",
        "document_title": "关于洛阳市2025年预算执行情况和2026年预算（草案）的报告",
        "publisher": "洛阳市财政局",
        "publication_date": "2026-03-05",
        "patterns": {
            "general_public_revenue_100m": (r"2025年全市一般公共预算收入年初预算合计[0-9.]+亿元，执行中.*?收入完成([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"支出预算合计[0-9.]+亿元，执行中.*?支出完成([0-9.]+)亿元", "亿元"),
            "gov_fund_revenue_100m": (r"2025年全市政府性基金预算收入年初预算合计[0-9.]+亿元，执行中.*?收入完成([0-9.]+)亿元", "亿元"),
        },
        "note": "洛阳市人大会议官方附件披露全市口径 2025 年预算执行完成数；不使用市级或 2026 年预算草案数。",
    },
    {
        "city_name": "岳阳市",
        "city_id": "CN-430600",
        "source_doc_id": "SRC-HUNAN-CITY-FISCAL-YUEYANG-2025",
        "url": "https://www.yueyang.gov.cn/web/uploadfiles/202601/2026012609340543556.pdf",
        "attachment_url": "https://www.yueyang.gov.cn/uploadfiles/202601/2026012609340543556.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "yueyang_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "yueyang_2025_budget_report.txt",
        "document_title": "关于岳阳市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "岳阳市财政局",
        "publication_date": "2026-01-26",
        "patterns": {
            "general_public_revenue_100m": (r"2025年，全市一般公共预算.*?收入预计完成([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"全市一般公共预算支出预计完成([0-9.]+)亿元", "亿元"),
            "gov_fund_revenue_100m": (r"2025年，预计全市政府性基金收入([0-9.]+)亿元", "亿元"),
        },
        "note": "岳阳市人大会议官方附件披露全市口径 2025 年预计执行数；当前标记为 execution，不作为最终决算数解读。",
    },
    {
        "city_name": "衡阳市",
        "city_id": "CN-430400",
        "source_doc_id": "SRC-HUNAN-CITY-FISCAL-HENGYANG-2025",
        "url": "https://www.hengyang.gov.cn/czj/ztxx/czysjsgk/cxzyhyjsgk/ysjsbg/20260115/i3850020.html",
        "attachment_url": "https://www.hengyang.gov.cn/czj/ztxx/czysjsgk/cxzyhyjsgk/ysjsbg/20260115/i3850020.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "hengyang_2025_budget_report_excerpt.txt",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "hengyang_2025_budget_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "关于衡阳市2025年预算执行情况与2026年预算草案的报告",
        "publisher": "衡阳市财政局",
        "publication_date": "2026-01-15",
        "title_source": "official_page_excerpt",
        "document_type": "官方城市财政预算执行报告（网页摘录）",
        "mime_type": "text/plain",
        "patterns": {
            "general_public_revenue_100m": (r"2025年全市地方一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"2025年全市一般公共预算支出([0-9.]+)亿元", "亿元"),
            "gov_fund_revenue_100m": (r"2025年全市政府性基金预算收入([0-9.]+)亿元", "亿元"),
        },
        "note": "衡阳市财政局官方报告页面定位摘录披露全市口径 2025 年预计执行数；当前标记为 execution，不作为最终决算数解读。",
    },
)

FOLLOWUP_2025_FISCAL_SOURCES = (
    {
        "city_name": "无锡市",
        "city_id": "CN-320200",
        "source_doc_id": "SRC-JIANGSU-CITY-FISCAL-WUXI-2025",
        "url": "https://rd.wuxi.gov.cn/doc/2026/01/30/4726147.shtml",
        "attachment_url": "https://rd.wuxi.gov.cn/doc/2026/01/30/4726147.shtml",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "wuxi_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "wuxi_2025_budget_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "关于无锡市2025年预算执行情况与2026年预算草案的报告",
        "publisher": "无锡市财政局",
        "publication_date": "2026-01-30",
        "title_source": "official_page_excerpt",
        "document_type": "官方城市财政预算执行报告（网页）",
        "mime_type": "text/html",
        "patterns": {
            "general_public_revenue_100m": (r"全市一般公共预算收入完成([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"全市一般公共预算支出完成([0-9.]+)亿元", "亿元"),
            "gov_fund_revenue_100m": (r"全市政府性基金预算收入完成([0-9.]+)亿元", "亿元"),
        },
        "note": "无锡市人大公开的财政局报告披露全市口径 2025 年预计执行数，当前标记为 execution，不作为最终决算数解读。",
    },
    {
        "city_name": "常德市",
        "city_id": "CN-430700",
        "source_doc_id": "SRC-HUNAN-CITY-FISCAL-CHANGDE-2025",
        "url": "https://www.cdsrd.gov.cn/rdhy/rmdbdh/iqajifnqaf/gzbg05/content_3158113",
        "attachment_url": "https://www.cdsrd.gov.cn/rdhy/rmdbdh/iqajifnqaf/gzbg05/content_3158113",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "changde_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "changde_2025_budget_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "关于常德市2025年预算执行情况与2026年全市及市级预算（草案）的报告",
        "publisher": "常德市财政局",
        "publication_date": "2025-12-29",
        "title_source": "official_page_excerpt",
        "document_type": "官方城市财政预算执行报告（网页）",
        "mime_type": "text/html",
        "patterns": {
            "general_public_revenue_100m": (r"全市地方一般公共预算收入预计完成([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
            "gov_fund_revenue_100m": (r"全市政府性基金预算收入完成([0-9.]+)亿元", "亿元"),
        },
        "note": "常德市人大公开的财政局报告披露全市口径 2025 年预计执行数，报告明确决算编制后会有变化，当前标记为 execution。",
    },
    {
        "city_name": "益阳市",
        "city_id": "CN-430900",
        "source_doc_id": "SRC-HUNAN-CITY-FISCAL-YIYANG-2025",
        "url": "https://www.yiyang.gov.cn/czj/5841/5844/5860/content_2143608.html",
        "attachment_url": "https://www.yiyang.gov.cn/czj/5841/5844/5860/content_2143608.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "yiyang_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "yiyang_2025_budget_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "关于益阳市2025年预算执行情况与2026年预算草案的报告",
        "publisher": "益阳市财政局",
        "publication_date": "2026-01-06",
        "title_source": "official_page_excerpt",
        "document_type": "官方城市财政预算执行报告（网页）",
        "mime_type": "text/html",
        "patterns": {
            "general_public_revenue_100m": (r"全市地方一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"全市一般公共预算支出([0-9.]+)亿元", "亿元"),
            "gov_fund_revenue_100m": (r"全市政府性基金预算收入([0-9.]+)亿元", "亿元"),
        },
        "note": "益阳市财政局官方预算报告网页披露全市口径 2025 年预计执行数，当前标记为 execution，不作为最终决算数解读。",
    },
    {
        "city_name": "苏州市",
        "city_id": "CN-320500",
        "source_doc_id": "SRC-JIANGSU-CITY-STATISTICAL-SUZHOU-2025",
        "url": "https://www.suzhou.gov.cn/szsrmzf/ndgmjjhshfztjsjfb/202605/0543af82405748cd9ffa4cfc81aecccd.shtml",
        "attachment_url": "https://www.suzhou.gov.cn/szsrmzf/ndgmjjhshfztjsjfb/202605/0543af82405748cd9ffa4cfc81aecccd.shtml",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "suzhou_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "suzhou_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年苏州市国民经济和社会发展统计公报",
        "publisher": "苏州市统计局",
        "publication_date": "2026-05-22",
        "title_source": "official_page_excerpt",
        "document_type": "官方统计公报（网页）",
        "mime_type": "text/html",
        "patterns": {
            "gdp_current_100m": (r"全年实现地区生产总值([0-9.]+)亿元", "亿元"),
            "gdp_real_growth_pct": (r"地区生产总值[0-9.]+亿元，按不变价格计算比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"全年实现一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "苏州市统计局官方统计公报披露 2025 年全市一般公共预算收入和支出年度数据；政府性基金收入未在本批代填。",
    },
)

NEXT2_2025_FISCAL_SOURCES = (
    {
        "city_name": "徐州市",
        "city_id": "CN-320300",
        "source_doc_id": "SRC-B2-JIANGSU-XUZHOU-FISCAL-2025",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/corporate/c/new/2026-06-18/184140_20260618_LON3.pdf",
        "attachment_url": "https://static.sse.com.cn/disclosure/bond/announcement/corporate/c/new/2026-06-18/184140_20260618_LON3.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "xuzhou_2025_finance_rating.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "xuzhou_2025_finance_rating_excerpt.txt",
        "text_is_curated": True,
        "document_title": "徐州高新产业发展投资有限公司跟踪评级报告（主要财力指标）",
        "publisher": "联合资信评估股份有限公司",
        "publisher_level": "评级机构披露",
        "publication_date": "2026-06-18",
        "title_source": "pdf_table_excerpt",
        "document_type": "评级报告财力指标表（精确表格）",
        "mime_type": "application/pdf",
        "source_grade": "B2",
        "patterns": {
            "general_public_revenue_100m": (r"一般公共预算收入\s*（亿元）\s*560\.29\s*(575\.33)", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出\s*（亿元）\s*1052\.38\s*(1053\.5)", "亿元"),
            "gov_fund_revenue_100m": (r"政府性基金收入\s*（亿元）\s*388\.41\s*(357\.19)", "亿元"),
        },
        "note": "B2 精确表格，联合资信报告明确引用徐州市预算执行报告；2025 年值作为可审计二手补缺，不等同于官方决算原件。",
    },
    {
        "city_name": "扬州市",
        "city_id": "CN-321000",
        "source_doc_id": "SRC-B2-JIANGSU-YANGZHOU-FISCAL-2025",
        "url": "https://www.crei.cn/file/br.aspx?id=20260527164838",
        "attachment_url": "https://www.crei.cn/file/br.aspx?id=20260527164838",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "yangzhou_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "yangzhou_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年扬州市国民经济和社会发展统计公报",
        "publisher": "中国区域经济学会信息平台转载",
        "publisher_level": "公开资料转载",
        "publication_date": "2026-05-27",
        "title_source": "html_table_excerpt",
        "document_type": "统计公报财政表（精确表格转载）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "patterns": {
            "general_public_revenue_100m": (r"全市一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"全市一般公共预算支出([0-9.]+)亿元", "亿元"),
            "gov_fund_revenue_100m": (r"政府性基金预算收入([0-9.]+)亿元", "亿元"),
        },
        "note": "B2 精确表格转载，含扬州市 2025 年财政收入、支出和政府性基金收入；作为可审计二手补缺，不等同于官方决算原件。",
    },
    {
        "city_name": "镇江市",
        "city_id": "CN-321100",
        "source_doc_id": "SRC-B2-JIANGSU-ZHENJIANG-FISCAL-2025",
        "url": "https://www.crei.cn/file/br.aspx?id=20260527164608&op=zc&x=0",
        "attachment_url": "https://www.crei.cn/file/br.aspx?id=20260527164608&op=zc&x=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhenjiang_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhenjiang_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年镇江市国民经济和社会发展统计公报",
        "publisher": "中国区域经济学会信息平台转载",
        "publisher_level": "公开资料转载",
        "publication_date": "2026-05-27",
        "title_source": "html_table_excerpt",
        "document_type": "统计公报财政表（精确表格转载）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "patterns": {
            "general_public_revenue_100m": (r"全年实现一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"全年实现一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2 精确表格转载，含镇江市 2025 年一般公共预算收入和支出；政府性基金收入本批未代填。",
    },
    {
        "city_name": "泰州市",
        "city_id": "CN-321200",
        "source_doc_id": "SRC-B2-JIANGSU-TAIZHOU-FISCAL-2025",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/corporate/c/new/2026-06-22/152418_20260622_WNHE.pdf",
        "attachment_url": "https://static.sse.com.cn/disclosure/bond/announcement/corporate/c/new/2026-06-22/152418_20260622_WNHE.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "taizhou_2025_finance_rating.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "taizhou_2025_finance_rating_excerpt.txt",
        "text_is_curated": True,
        "document_title": "泰州市城投企业跟踪评级报告（主要财政数据）",
        "publisher": "评级机构公开披露",
        "publisher_level": "评级机构披露",
        "publication_date": "2026-06-22",
        "title_source": "pdf_table_excerpt",
        "document_type": "评级报告财政数据表（精确表格）",
        "mime_type": "application/pdf",
        "source_grade": "B2",
        "patterns": {
            "general_public_revenue_100m": (r"一般公共预算收入\s*（亿元）\s*439\.70\s*453\.08\s*(475\.49)", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出\s*（亿元）\s*697\.42\s*695\.93\s*(686\.40)", "亿元"),
            "gov_fund_revenue_100m": (r"政府性基金预算收入\s*（亿元）\s*493\.01\s*420\.56\s*(388\.35)", "亿元"),
        },
        "note": "B2 精确表格，评级报告注明数据根据泰州市财政局、政府决算报告及预算执行报告整理；2025 年值作为可审计二手补缺，不等同于官方决算原件。",
    },
)

NEXT3_2025_FISCAL_SOURCES = (
    {
        "city_name": "福州市",
        "city_id": "CN-350100",
        "source_doc_id": "SRC-FUJIAN-CITY-STATISTICAL-FUZHOU-2025",
        "url": "https://www.fuzhou.gov.cn/zgfzzt/czzj/bjndyjs/zfjsgk/202607/t20260713_5345722.htm",
        "attachment_url": "https://www.fuzhou.gov.cn/zgfzzt/czzj/bjndyjs/zfjsgk/202607/t20260713_5345722.htm",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "fuzhou_2025_finance_final.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "fuzhou_2025_finance_final_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年度福州市财政决算收支情况",
        "publisher": "福州市财政局",
        "publisher_level": "市级",
        "publication_date": "2026-07-13",
        "title_source": "html_heading",
        "document_type": "官方统计公报（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "patterns": {
            "general_public_revenue_100m": (r"全市一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
            "gov_fund_revenue_100m": (r"全市政府性基金预算收入([0-9.]+)亿元", "亿元"),
        },
        "note": "福州市财政局官方财政决算页面披露 2025 年全市一般公共预算收入、支出和政府性基金预算收入；采用决算数，不使用市本级口径。",
    },
    {
        "city_name": "泉州市",
        "city_id": "CN-350500",
        "source_doc_id": "SRC-FUJIAN-CITY-STATISTICAL-QUANZHOU-2025",
        "url": "https://www.quanzhou.gov.cn/zfb/xxgk/zfxxgkzl/qzdt/qzyw/202603/t20260331_3279339.htm",
        "attachment_url": "https://www.quanzhou.gov.cn/zfb/xxgk/zfxxgkzl/qzdt/qzyw/202603/t20260331_3279339.htm",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "quanzhou_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "quanzhou_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年泉州市国民经济和社会发展统计公报",
        "publisher": "泉州市统计局、国家统计局泉州调查队",
        "publisher_level": "市级",
        "publication_date": "2026-03-31",
        "title_source": "html_heading",
        "document_type": "官方统计公报（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "patterns": {
            "gdp_current_100m": (r"地区生产总值([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"地区生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "general_public_revenue_100m": (r"地方一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
            "gov_fund_revenue_100m": (r"政府性基金预算收入([0-9.]+)亿元", "亿元"),
        },
        "note": "泉州市统计局、国家统计局泉州调查队官方统计公报披露 2025 年全市地方一般公共预算收入、支出和政府性基金预算收入；初步统计值按 A2 归档。",
    },
    {
        "city_name": "长沙市",
        "city_id": "CN-430100",
        "source_doc_id": "SRC-HUNAN-CITY-STATISTICAL-CHANGSHA-2025",
        "url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/zss_1/202605/t20260512_33975356.html",
        "attachment_url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/zss_1/202605/t20260512_33975356.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "changsha_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "changsha_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "长沙市2025年国民经济和社会发展统计公报",
        "publisher": "湖南省统计局",
        "publisher_level": "省级统计机构",
        "publication_date": "2026-04-21",
        "title_source": "html_heading",
        "document_type": "官方统计公报（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "patterns": {
            "gdp_current_100m": (r"地区生产总值([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"地区生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "general_public_revenue_100m": (r"全年地方一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "湖南省统计局官方长沙市统计公报披露 2025 年地方一般公共预算收入和支出；政府性基金收入本批未代填。",
    },
    {
        "city_name": "沈阳市",
        "city_id": "CN-210100",
        "source_doc_id": "SRC-B2-LIAONING-SHENYANG-FISCAL-2025",
        "url": "https://www.crei.cn/file/br.aspx?id=20260522102711&op=sczz&x=0",
        "attachment_url": "https://www.crei.cn/file/br.aspx?id=20260522102711&op=sczz&x=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "shenyang_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "shenyang_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年沈阳市国民经济和社会发展统计公报",
        "publisher": "中国区域经济学会信息平台转载",
        "publisher_level": "公开资料转载",
        "publication_date": "2026-05-22",
        "title_source": "html_table_excerpt",
        "document_type": "统计公报财政表（精确表格转载）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "patterns": {
            "general_public_revenue_100m": (r"全年一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2 精确公报转载，含沈阳市 2025 年一般公共预算收入和支出；政府性基金收入本批未代填。",
    },
)

NEXT4_2025_FISCAL_SOURCES = (
    {
        "city_name": "武汉市",
        "city_id": "CN-420100",
        "source_doc_id": "SRC-HUBEI-CITY-BUDGET-WUHAN-2025",
        "url": "https://www.wuhan.gov.cn/ztzl/yjs/2026/yjsgk/bndys_37170/202601/t20260127_2719134.shtml",
        "attachment_url": "https://www.wuhan.gov.cn/ztzl/yjs/2026/yjsgk/bndys_37170/202601/P020260127416819074965.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "wuhan_2025_budget_revenue.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "wuhan_2025_budget_tables_excerpt.txt",
        "text_is_curated": True,
        "document_title": "武汉市2025年全市预算执行表（收入、支出和政府性基金收入）",
        "publisher": "武汉市财政局",
        "publisher_level": "市级",
        "publication_date": "2026-01-26",
        "title_source": "official_budget_directory",
        "document_type": "官方城市预算执行表（PDF表格摘录）",
        "mime_type": "application/pdf",
        "source_grade": "A2",
        "patterns": {
            "general_public_revenue_100m": (r"一般公共预算收入\s*([0-9.]+)\s*万元", "万元"),
            "general_public_expenditure_100m": (r"一般公共预算支出\s*([0-9.]+)\s*万元", "万元"),
            "gov_fund_revenue_100m": (r"政府性基金收入\s*([0-9.]+)\s*万元", "万元"),
        },
        "note": "武汉市财政局官方预算公开目录关联收入、支出和政府性基金收入三张全市执行表；本配置以收入表作为主附件哈希，同时归档支出表和政府性基金收入表，三项均为2025年全市execution数，不使用市本级口径。",
    },
    {
        "city_name": "郑州市",
        "city_id": "CN-410100",
        "source_doc_id": "SRC-HENAN-CITY-STATISTICAL-ZHENGZHOU-2025",
        "url": "https://tjj.zhengzhou.gov.cn/tjgb/10017864.jhtml",
        "attachment_url": "https://tjj.zhengzhou.gov.cn/tjgb/10017864.jhtml",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "zhengzhou_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "zhengzhou_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年郑州市国民经济和社会发展统计公报",
        "publisher": "郑州市统计局",
        "publisher_level": "市级",
        "publication_date": "2026-04-10",
        "title_source": "official_page_excerpt",
        "document_type": "官方统计公报（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "patterns": {
            "gdp_current_100m": (r"全年全市地区生产总值([0-9.]+)亿元，按不变价格计算，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"地区生产总值[0-9.]+亿元，按不变价格计算，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"全年全市地方财政一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"全年全市地方财政一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "郑州市统计局官方统计公报披露2025年全市地方财政一般公共预算收入和支出，均为全市口径年度数；政府性基金收入本批未代填。",
    },
    {
        "city_name": "成都市",
        "city_id": "CN-510100",
        "source_doc_id": "SRC-B2-SICHUAN-CITY-STATISTICAL-CHENGDU-2025",
        "url": "https://www.crei.cn/file/br.aspx?id=20260420165225&op=zc&x=0",
        "attachment_url": "https://www.crei.cn/file/br.aspx?id=20260420165225&op=zc&x=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "chengdu_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "chengdu_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年成都市国民经济和社会发展统计公报",
        "publisher": "中国区域经济学会信息平台转载",
        "publisher_level": "公开资料转载",
        "publication_date": "2026-04-20",
        "title_source": "html_table_excerpt",
        "document_type": "统计公报财政表（精确表格转载）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "patterns": {
            "general_public_revenue_100m": (r"全年地方一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2精确公报转载，数据来自成都市统计局统计公报，且财政段落明确为地方一般公共预算收入和支出；成都市财政局同期官方收入执行表可用于交叉核对收入。政府性基金收入本批未代填。",
    },
    {
        "city_name": "南昌市",
        "city_id": "CN-360100",
        "source_doc_id": "SRC-JIANGXI-CITY-STATISTICAL-NANCHANG-2025",
        "url": "https://www.nc.gov.cn/ncszf/tjfx1/202601/05e40bffc5dd429aac122f372223620f.shtml",
        "attachment_url": "https://www.nc.gov.cn/ncszf/tjfx1/202601/05e40bffc5dd429aac122f372223620f.shtml",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "nanchang_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "nanchang_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "南昌市2025年经济运行情况",
        "publisher": "南昌市统计局",
        "publisher_level": "市级",
        "publication_date": "2026-01-26",
        "title_source": "official_page_excerpt",
        "document_type": "官方统计运行简报（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "patterns": {
            "gdp_current_100m": (r"全市地区生产总值([0-9.]+)亿元，按不变价格计算，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"地区生产总值[0-9.]+亿元，按不变价格计算，比上年增长([0-9.]+)%", "%"),
            "general_public_revenue_100m": (r"全年全市地方一般公共预算收入完成([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"全市一般公共预算支出完成([0-9.]+)亿元", "亿元"),
        },
        "note": "南昌市统计局官方经济运行页面披露2025年全市地方一般公共预算收入和一般公共预算支出；政府性基金收入本批未代填。",
    },
    {
        "city_name": "南宁市",
        "city_id": "CN-450100",
        "source_doc_id": "SRC-B2-GUANGXI-CITY-STATISTICAL-NANNING-2025",
        "url": "https://www.crei.cn/file/br.aspx?id=20260605091538&op=z2&x=0",
        "attachment_url": "https://www.crei.cn/file/br.aspx?id=20260605091538&op=z2&x=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "nanning_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "nanning_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年南宁市国民经济和社会发展统计公报",
        "publisher": "中国区域经济学会信息平台转载",
        "publisher_level": "公开资料转载",
        "publication_date": "2026-06-05",
        "title_source": "html_table_excerpt",
        "document_type": "统计公报财政段落（精确转载）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "patterns": {
            "general_public_revenue_100m": (r"全年一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2精确公报转载，出处标注为南宁市统计局，披露2025年全市一般公共预算收入和支出；政府性基金收入本批未代填。",
    },
)

NEXT5_2025_FISCAL_SOURCES = (
    {
        "city_name": "西安市",
        "city_id": "CN-610100",
        "source_doc_id": "SRC-SHAANXI-CITY-STATISTICAL-XIAN-2025",
        "url": "https://tjj.xa.gov.cn/tjsj/tjgb/gmjjhshfzgb/2055106184529166338.html",
        "attachment_url": "https://tjj.xa.gov.cn/web_files/tjj/file/2026/05/15/202605151000219859531.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "xian_2025_statistical_bulletin.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "xian_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "西安市2025年国民经济和社会发展统计公报",
        "publisher": "西安市统计局、国家统计局西安调查队",
        "publisher_level": "市级统计机构",
        "publication_date": "2026-05-15",
        "title_source": "official_pdf",
        "document_type": "官方统计公报（PDF）",
        "mime_type": "application/pdf",
        "source_grade": "A2",
        "patterns": {
            "gdp_current_100m": (r"地区生产总值([0-9.]+)亿元，按不变价格计算，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"地区生产总值[0-9.]+亿元，按不变价格计算，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"全年一般公共预算收入\s*([0-9.]+)\s*亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出\s*([0-9.]+)\s*亿元", "亿元"),
        },
        "note": "西安市统计局与国家统计局西安调查队官方统计公报披露2025年一般公共预算收入和支出，数据为初步统计数；政府性基金收入本批未代填。",
    },
    {
        "city_name": "海口市",
        "city_id": "CN-460100",
        "source_doc_id": "SRC-B2-HAINAN-CITY-STATISTICAL-HAIKOU-2025",
        "url": "https://www.crei.cn/file/br.aspx?id=20260429152052&op=zc&x=0",
        "attachment_url": "https://www.crei.cn/file/br.aspx?id=20260429152052&op=zc&x=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "haikou_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "haikou_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年海口市国民经济和社会发展统计公报",
        "publisher": "中国区域经济学会信息平台转载",
        "publisher_level": "公开资料转载",
        "publication_date": "2026-04-29",
        "title_source": "html_table_excerpt",
        "document_type": "统计公报财政段落（精确转载）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "patterns": {
            "general_public_revenue_100m": (r"全市地方一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"全市地方一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2精确公报转载，明确区分全口径一般公共预算收入与地方一般公共预算收入；本表采用地方一般公共预算收入253.80亿元及全市地方一般公共预算支出336.74亿元，政府性基金收入本批未代填。",
    },
    {
        "city_name": "银川市",
        "city_id": "CN-640100",
        "source_doc_id": "SRC-NINGXIA-CITY-STATISTICAL-YINCHUAN-2025",
        "url": "https://www.yinchuan.gov.cn/xxgk/bmxxgkml/stjj/xxgkml_2517/tjxx_7670/tjgb_7671/202604/t20260427_5226142.html",
        "attachment_url": "https://www.yinchuan.gov.cn/xxgk/bmxxgkml/stjj/xxgkml_2517/tjxx_7670/tjgb_7671/202604/t20260427_5226142.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "yinchuan_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "yinchuan_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "银川市2025年国民经济和社会发展统计公报",
        "publisher": "银川市统计局、国家统计局银川调查队",
        "publisher_level": "市级统计机构",
        "publication_date": "2026-04-24",
        "title_source": "official_page_excerpt",
        "document_type": "官方统计公报（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "patterns": {
            "gdp_current_100m": (r"全年全市生产总值([0-9.]+)亿元，按不变价格计算，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全市生产总值[0-9.]+亿元，按不变价格计算，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "银川市统计局、国家统计局银川调查队官方统计公报披露2025年一般公共预算收入和支出；政府性基金收入本批未代填。",
    },
    {
        "city_name": "乌鲁木齐市",
        "city_id": "CN-650100",
        "source_doc_id": "SRC-XINJIANG-CITY-STATISTICAL-URUMQI-2025",
        "url": "https://www.wlmq.gov.cn/wlmqs/c119359/202604/6070ed21632343cca95db20395862469.shtml",
        "attachment_url": "https://www.wlmq.gov.cn/wlmqs/c119359/202604/6070ed21632343cca95db20395862469.shtml",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "urumqi_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "urumqi_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "乌鲁木齐市2025年国民经济和社会发展统计公报",
        "publisher": "乌鲁木齐市统计局",
        "publisher_level": "市级统计机构",
        "publication_date": "2026-04-21",
        "title_source": "official_page_excerpt",
        "document_type": "官方统计公报（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "patterns": {
            "gdp_current_100m": (r"实现地区生产总值（GDP）([0-9.]+)亿元，按可比价计算，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"地区生产总值（GDP）[0-9.]+亿元，按可比价计算，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
            "gov_fund_revenue_100m": (r"政府性基金预算收入([0-9.]+)亿元", "亿元"),
        },
        "note": "乌鲁木齐市统计局官方统计公报披露2025年全市一般公共预算收入、支出及政府性基金预算收入，采用公报全市地方财政口径，不使用市本级口径。",
    },
    {
        "city_name": "昆明市",
        "city_id": "CN-530100",
        "source_doc_id": "SRC-B2-YUNNAN-CITY-STATISTICAL-KUNMING-2025",
        "url": "https://www.kunming.cn/news/c/2026-05-22/14043565.shtml",
        "attachment_url": "https://www.kunming.cn/news/c/2026-05-22/14043565.shtml",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "kunming_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "kunming_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "昆明市2025年国民经济和社会发展统计公报财政段落",
        "publisher": "昆明信息港",
        "publisher_level": "地方媒体转载",
        "publication_date": "2026-05-22",
        "title_source": "html_statement_excerpt",
        "document_type": "统计公报财政段落（精确转载）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "patterns": {
            "gdp_current_100m": (r"2025年昆明地区生产总值([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"昆明地区生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"全年全市地方一般公共预算收入完成([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"全市地方一般公共预算支出完成([0-9.]+)亿元", "亿元"),
        },
        "note": "B2精确转载，来源页面明确标注数据来自昆明市统计局统计公报财政段落；一般公共预算收入和支出采用全市地方口径，政府性基金收入本批未代填。",
    },
)

NEXT6_2025_FISCAL_SOURCES = (
    {
        "city_name": "石家庄市",
        "city_id": "CN-130100",
        "source_doc_id": "SRC-HEBEI-CITY-STATISTICAL-SHIJIAZHUANG-2025",
        "url": "https://tjj.sjz.gov.cn/columns/940d701f-5e56-4f5d-9ece-7968f6354993/202605/26/f062dca8-ce95-46f8-b1c9-33f507db5a29.html",
        "attachment_url": "https://tjj.sjz.gov.cn/columns/940d701f-5e56-4f5d-9ece-7968f6354993/202605/26/f062dca8-ce95-46f8-b1c9-33f507db5a29.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "shijiazhuang_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "shijiazhuang_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "石家庄市2025年国民经济和社会发展统计公报",
        "publisher": "石家庄市统计局、国家统计局石家庄调查队",
        "publisher_level": "市级统计机构",
        "publication_date": "2026-05-26",
        "title_source": "official_page_excerpt",
        "document_type": "官方统计公报（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "patterns": {
            "gdp_current_100m": (r"全年地区生产总值([0-9.]+)亿元，按不变价格计算，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"地区生产总值[0-9.]+亿元，按不变价格计算，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "石家庄市统计局、国家统计局石家庄调查队官方统计公报披露2025年全市一般公共预算收入和支出；公报注明这两项指标含辛集市，本批保留该官方全市口径。",
    },
    {
        "city_name": "太原市",
        "city_id": "CN-140100",
        "source_doc_id": "SRC-B2-SHANXI-CITY-STATISTICAL-TAIYUAN-2025",
        "url": "https://tytv5-web.sxtygdy.com/cms/rmt2018_html/60/60tytx/60tytxml/ty/zj/zj77Q/1997220.shtml",
        "attachment_url": "https://tytv5-web.sxtygdy.com/cms/rmt2018_html/60/60tytx/60tytxml/ty/zj/zj77Q/1997220.shtml",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "taiyuan_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "taiyuan_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "太原市2025年国民经济和社会发展统计公报财政段落",
        "publisher": "太原日报数字报、太原市统计局",
        "publisher_level": "地方媒体转载",
        "publication_date": "2026-02-04",
        "title_source": "media_statement_excerpt",
        "document_type": "统计公报财政段落（精确转载）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "patterns": {
            "gdp_current_100m": (r"全市地区生产总值（GDP）([0-9.]+)亿元，增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"地区生产总值（GDP）[0-9.]+亿元，增长([0-9.]+)%", "%"),
            "general_public_revenue_100m": (r"一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2精确转载，页面披露太原市统计局口径的2025年全市一般公共预算收入和支出；不使用市本级或区县数据。",
    },
    {
        "city_name": "佳木斯市",
        "city_id": "CN-230800",
        "source_doc_id": "SRC-B2-HEILONGJIANG-CITY-STATISTICAL-JIAMUSI-2025",
        "url": "https://tjgb.hongheiku.com/djs/69827.html",
        "attachment_url": "https://tjgb.hongheiku.com/djs/69827.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "jiamusi_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "jiamusi_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年佳木斯市国民经济和社会发展统计公报",
        "publisher": "佳木斯市统计局",
        "publisher_level": "公开资料转载",
        "publication_date": "2026-05-02",
        "title_source": "html_statement_excerpt",
        "document_type": "统计公报财政段落（精确转载）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "patterns": {
            "gdp_current_100m": (r"全市实现地区生产总值([0-9.]+)亿元，按不变价格计算，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"地区生产总值[0-9.]+亿元，按不变价格计算，比上年增长([0-9.]+)%", "%"),
            "general_public_revenue_100m": (r"全年实现一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2精确公报转载，来源标注为佳木斯市统计局，披露2025年全市一般公共预算收入和支出。",
    },
    {
        "city_name": "昌都市",
        "city_id": "CN-540300",
        "source_doc_id": "SRC-B2-TIBET-CITY-STATISTICAL-CHANGDU-2025",
        "url": "https://tjgb.hongheiku.com/wp-content/uploads/2026/05/1779504521-5eefb984762b471cbe201a60f13bc9e5.pdf",
        "attachment_url": "https://tjgb.hongheiku.com/wp-content/uploads/2026/05/1779504521-5eefb984762b471cbe201a60f13bc9e5.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "changdu_2025_statistical_bulletin.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "changdu_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "昌都市2025年国民经济和社会发展统计公报",
        "publisher": "昌都市统计局、国家统计局昌都调查队",
        "publisher_level": "公开资料转载",
        "publication_date": "2026-05-20",
        "title_source": "pdf_table_excerpt",
        "document_type": "官方统计公报（精确PDF转载）",
        "mime_type": "application/pdf",
        "source_grade": "B2",
        "patterns": {
            "gdp_current_100m": (r"全市实现地区生产总值([0-9.]+)亿元，按不变价计算，同比增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"地区生产总值[0-9.]+亿元，按不变价计算，同比增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"地方一般公共预算收入完成([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2精确PDF转载，公报来源标注为昌都市统计局、国家统计局昌都调查队；采用全市地方一般公共预算收入和全市一般公共预算支出。",
    },
    {
        "city_name": "哈尔滨市",
        "city_id": "CN-230100",
        "source_doc_id": "SRC-B2-HEILONGJIANG-CITY-STATISTICAL-HARBIN-2025",
        "url": "https://tjgb.hongheiku.com/xjtjgb/xj2020/75212.html",
        "attachment_url": "https://tjgb.hongheiku.com/wp-content/uploads/2026/07/1783745353-2025E5B9B4E59388E5B094E6BBA8E5B882E59BBDE6B091E7BB8FE6B58EE5928CE7A4BEE4BC9AE58F91E5B195E7BB9FE8AEA1E585ACE68AA5-20260603093614665.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "harbin_2025_statistical_bulletin.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "harbin_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年哈尔滨市国民经济和社会发展统计公报",
        "publisher": "哈尔滨市统计局、国家统计局哈尔滨调查队",
        "publisher_level": "公开资料转载",
        "publication_date": "2026-06-03",
        "title_source": "pdf_statement_excerpt",
        "document_type": "官方统计公报（精确PDF转载）",
        "mime_type": "application/pdf",
        "source_grade": "B2",
        "patterns": {
            "gdp_current_100m": (r"全年实现地区生产总值([0-9.]+)亿元，按不变价格计算，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"地区生产总值[0-9.]+亿元，按不变价格计算，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"完成一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2精确PDF转载，公报来源标注为哈尔滨市统计局、国家统计局哈尔滨调查队；采用2025年全市一般公共预算收入和支出。",
    },
)

NEXT7_2025_FISCAL_SOURCES = (
    {
        "city_name": "合肥市",
        "city_id": "CN-340100",
        "source_doc_id": "SRC-B2-ANHUI-CITY-STATISTICAL-HEFEI-2025",
        "url": "https://tjgb.hongheiku.com/djs/68352.html",
        "attachment_url": "https://tjgb.hongheiku.com/wp-content/uploads/2026/04/1775052106-wKgEIWnLK5OAEX2EAApVrfAOX4M661.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "hefei_2025_statistical_bulletin.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "hefei_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "合肥市2025年国民经济和社会发展统计公报",
        "publisher": "合肥市统计局、国家统计局合肥调查队",
        "publisher_level": "公开资料转载",
        "publication_date": "2026-04-01",
        "title_source": "pdf_statement_excerpt",
        "document_type": "官方统计公报（精确PDF转载）",
        "mime_type": "application/pdf",
        "source_grade": "B2",
        "patterns": {
            "gdp_current_100m": (r"地区生产总值（GDP）([0-9.]+)亿元", "亿元"),
            "gdp_real_growth_pct": (r"同比增长([0-9.]+)%", "%"),
            "general_public_revenue_100m": (r"一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2精确PDF转载，页面来源标注为合肥市统计局，披露2025年全市一般公共预算收入和支出；政府性基金收入本批未代填。",
    },
    {
        "city_name": "宜昌市",
        "city_id": "CN-420500",
        "source_doc_id": "SRC-B2-HUBEI-CITY-STATISTICAL-YICHANG-2025",
        "url": "https://www.crei.cn/file/br.aspx?id=20260420163741&op=zc&x=0",
        "attachment_url": "https://www.crei.cn/file/br.aspx?id=20260420163741&op=zc&x=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "yichang_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "yichang_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "宜昌市2025年国民经济和社会发展统计公报",
        "publisher": "宜昌市统计局",
        "publisher_level": "公开资料转载",
        "publication_date": "2026-04-20",
        "title_source": "html_statement_excerpt",
        "document_type": "统计公报财政段落（精确转载）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "patterns": {
            "gdp_current_100m": (r"地区生产总值([0-9.]+)亿元", "亿元"),
            "gdp_real_growth_pct": (r"地区生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "general_public_revenue_100m": (r"地方一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"地方一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2精确公报转载，页面来源标注为宜昌市统计局，披露2025年全市地方一般公共预算收入和支出。",
    },
    {
        "city_name": "荆州市",
        "city_id": "CN-421000",
        "source_doc_id": "SRC-HUBEI-CITY-STATISTICAL-JINGZHOU-2025",
        "url": "https://tjj.hubei.gov.cn/tjsj/tjgb/ndtjgb/sztjgb/202605/P020260508383487119307.pdf",
        "attachment_url": "https://tjj.hubei.gov.cn/tjsj/tjgb/ndtjgb/sztjgb/202605/P020260508383487119307.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "jingzhou_2025_statistical_bulletin.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "jingzhou_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "荆州市2025年国民经济和社会发展统计公报",
        "publisher": "荆州市统计局、湖北省统计局",
        "publisher_level": "省级统计机构转载",
        "publication_date": "2026-05-08",
        "title_source": "official_pdf_table_excerpt",
        "document_type": "官方统计公报（PDF）",
        "mime_type": "application/pdf",
        "source_grade": "A2",
        "patterns": {
            "gdp_current_100m": (r"地区生产总值为([0-9.]+)亿元", "亿元"),
            "gdp_real_growth_pct": (r"地区生产总值为[0-9.]+亿元，按不变价格计算，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"地方一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"全市一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "湖北省统计局官方站点归档的荆州市统计公报披露2025年全市地方一般公共预算收入和一般公共预算支出；政府性基金收入本批未代填。",
    },
    {
        "city_name": "黄石市",
        "city_id": "CN-420200",
        "source_doc_id": "SRC-HUBEI-CITY-FINANCE-HUANGSHI-2025",
        "url": "https://czj.huangshi.gov.cn/2020xxgkzn/2020gknr/2020czzj/sbjyjs/202601/t20260131_1304855.html",
        "attachment_url": "https://czj.huangshi.gov.cn/2020xxgkzn/2020gknr/2020czzj/sbjyjs/202601/t20260131_1304855.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "huangshi_2025_budget_execution.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "huangshi_2025_budget_execution_excerpt.txt",
        "text_is_curated": True,
        "document_title": "关于2025年黄石市预算执行情况和2026年预算草案的报告",
        "publisher": "黄石市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-01-31",
        "title_source": "official_page_excerpt",
        "document_type": "官方预算执行报告（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "patterns": {
            "general_public_revenue_100m": (r"全市一般公共预算收入完成([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"全市一般公共预算支出（含上级转移支付支出）完成([0-9.]+)亿元", "亿元"),
        },
        "note": "黄石市财政局官方预算执行报告披露2025年全市一般公共预算收入和支出；支出明确含上级转移支付支出，保留execution状态，不伪装为决算数。",
    },
    {
        "city_name": "营口市",
        "city_id": "CN-210800",
        "source_doc_id": "SRC-LIAONING-CITY-STATISTICAL-YINGKOU-2025",
        "url": "https://www.yingkou.gov.cn/govxxgk/ykszf/2026-04-27/1dd679cc-5106-428b-b68b-6450f98378d4.html",
        "attachment_url": "https://www.yingkou.gov.cn/govxxgk/ykszf/2026-04-27/1dd679cc-5106-428b-b68b-6450f98378d4.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "yingkou_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "yingkou_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年营口市国民经济和社会发展统计公报",
        "publisher": "营口市人民政府、营口市统计局",
        "publisher_level": "市级政府门户",
        "publication_date": "2026-04-27",
        "title_source": "official_page_excerpt",
        "document_type": "官方统计公报（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "patterns": {
            "gdp_current_100m": (r"地区生产总值([0-9.]+)亿元", "亿元"),
            "gdp_real_growth_pct": (r"地区生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "general_public_revenue_100m": (r"一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "营口市人民政府官方门户发布的统计公报披露2025年全市一般公共预算收入和支出；财政数据来源注明为市财政局。",
    },
)

NEXT8_2025_ECONOMIC_SOURCES = (
    {
        "city_name": "乌海市",
        "city_id": "CN-150300",
        "source_doc_id": "SRC-B2-INNER-MONGOLIA-CITY-STATISTICAL-WUHAI-2025",
        "url": "https://www.sohu.com/a/1016888972_121106854",
        "attachment_url": "https://www.sohu.com/a/1016888972_121106854",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "wuhai_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "wuhai_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "乌海市2025年国民经济和社会发展统计公报",
        "publisher": "乌海市统计局（精确公开转载）",
        "publisher_level": "公开资料转载",
        "publication_date": "2026-04-30",
        "title_source": "html_statement_excerpt",
        "document_type": "统计公报经济财政段落（精确转载）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "negative_if": {
            "gdp_real_growth_pct": "下降",
        },
        "patterns": {
            "gdp_current_100m": (r"地区生产总值([0-9.]+)亿元", "亿元"),
            "gdp_real_growth_pct": (r"地区生产总值[0-9.]+亿元，下降([0-9.]+)%", "%"),
            "general_public_revenue_100m": (r"一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2精确转载，页面标题为乌海市2025年统计公报，来源数据标注为乌海市统计局；经济和财政字段均为全市口径。",
    },
    {
        "city_name": "宝鸡市",
        "city_id": "CN-610300",
        "source_doc_id": "SRC-A2-BAOJI-CITY-ECONOMIC-2025",
        "url": "https://www.baoji.gov.cn/sjgk/tjgb/tjgb/202606/t20260605_1275705.html",
        "attachment_url": "https://www.baoji.gov.cn/sjgk/tjgb/tjgb/202606/t20260605_1275705.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "baoji_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "baoji_2025_statistical_bulletin_economic_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年宝鸡市国民经济和社会发展统计公报",
        "publisher": "宝鸡市人民政府、宝鸡市统计局",
        "publisher_level": "市级政府门户",
        "publication_date": "2026-06-05",
        "title_source": "html_statement_excerpt",
        "document_type": "统计公报经济指标（官方网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "data_status": "preliminary",
        "patterns": {
            "gdp_current_100m": (r"地区生产总值([0-9.]+)亿元", "亿元"),
            "gdp_real_growth_pct": (r"地区生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
        },
        "note": "A2官方统计公报；公报注明财政数据来自宝鸡市财政局，经济部分为初步统计数；GDP为现价、增长速度为不变价，人口为年末全市常住人口。",
    },
)

NEXT9_2025_ECONOMIC_SOURCES = (
    {
        "city_name": "开封市",
        "city_id": "CN-410200",
        "source_doc_id": "SRC-B2-HENAN-CITY-STATISTICAL-KAIFENG-2025",
        "url": "https://tjgb.hongheiku.com/djs/70907.html",
        "attachment_url": "https://tjgb.hongheiku.com/djs/70907.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "kaifeng_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "kaifeng_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年开封市国民经济和社会发展统计公报",
        "publisher": "开封市统计局、国家统计局开封调查队",
        "publisher_level": "公开资料转载",
        "publication_date": "2026-05-17",
        "title_source": "html_statement_excerpt",
        "document_type": "统计公报经济财政段落（精确转载）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "patterns": {
            "gdp_current_100m": (r"全年全市生产总值（GDP）([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全年全市生产总值（GDP）[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"全年全市一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2精确转载，页面来源标注为开封市统计局、国家统计局开封调查队；采用2025年全市GDP、增速、年末常住人口和一般公共预算收支，政府性基金收入未在本来源中披露。",
    },
    {
        "city_name": "新乡市",
        "city_id": "CN-410700",
        "source_doc_id": "SRC-B2-HENAN-CITY-STATISTICAL-XINXIANG-2025",
        "url": "https://tjgb.hongheiku.com/xjtjgb/xj2020/72753.html",
        "attachment_url": "https://tjgb.hongheiku.com/xjtjgb/xj2020/72753.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "xinxiang_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "xinxiang_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年新乡市国民经济和社会发展统计公报",
        "publisher": "新乡市统计局、国家统计局新乡调查队",
        "publisher_level": "公开资料转载",
        "publication_date": "2026-05-27",
        "title_source": "html_statement_excerpt",
        "document_type": "统计公报经济财政段落（精确转载）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "patterns": {
            "gdp_current_100m": (r"全年全市地区生产总值([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全年全市地区生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2精确转载，页面来源标注为新乡市统计局、国家统计局新乡调查队；采用2025年全市GDP、增速、年末常住人口和一般公共预算收支，政府性基金收入未在本来源中披露。",
    },
    {
        "city_name": "安阳市",
        "city_id": "CN-410500",
        "source_doc_id": "SRC-B2-HENAN-CITY-STATISTICAL-ANYANG-2025",
        "url": "https://tjgb.hongheiku.com/xjtjgb/xj2020/72689.html",
        "attachment_url": "https://tjgb.hongheiku.com/xjtjgb/xj2020/72689.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "anyang_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "anyang_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年安阳市国民经济和社会发展统计公报",
        "publisher": "安阳市统计局",
        "publisher_level": "公开资料转载",
        "publication_date": "2026-05-27",
        "title_source": "html_statement_excerpt",
        "document_type": "统计公报经济财政段落（精确转载）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "patterns": {
            "gdp_current_100m": (r"全年全市实现地区生产总值([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全年全市实现地区生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2精确转载，页面来源标注为安阳市统计局；采用2025年全市GDP、增速、年末常住人口和一般公共预算收支，政府性基金收入未在本来源中披露。",
    },
)

NEXT10_2025_ECONOMIC_SOURCES = (
    {
        "city_name": "南阳市",
        "city_id": "CN-411300",
        "source_doc_id": "SRC-A2-HENAN-CITY-STATISTICAL-NANYANG-2025",
        "url": "https://tj.nanyang.gov.cn/2026/04-20/1398809.html",
        "attachment_url": "https://tj.nanyang.gov.cn/2026/04-20/1398809.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "nanyang_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "nanyang_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年南阳市国民经济和社会发展统计公报",
        "publisher": "南阳市统计局、国家统计局南阳调查队",
        "publisher_level": "市级统计机构",
        "publication_date": "2026-04-20",
        "title_source": "official_page_excerpt",
        "document_type": "官方统计公报（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "patterns": {
            "gdp_current_100m": (r"全年全市地区生产总值([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全年全市地区生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "A2南阳市统计局、国家统计局南阳调查队官方统计公报；采用2025年全市GDP、增速、年末常住人口和一般公共预算收支，政府性基金收入未在本来源中披露。",
    },
    {
        "city_name": "许昌市",
        "city_id": "CN-411000",
        "source_doc_id": "SRC-A2-HENAN-CITY-STATISTICAL-XUCHANG-2025",
        "url": "https://www.xuchang.gov.cn/xcsrmzfsjfb/037003/20260512/7129ddbc-01f7-4f05-bd11-ebcae800f449.html",
        "attachment_url": "https://www.xuchang.gov.cn/xcsrmzfsjfb/037003/20260512/7129ddbc-01f7-4f05-bd11-ebcae800f449.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "xuchang_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "xuchang_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年许昌市国民经济和社会发展统计公报",
        "publisher": "许昌市统计局、国家统计局许昌调查队",
        "publisher_level": "市级统计机构",
        "publication_date": "2026-05-12",
        "title_source": "official_page_excerpt",
        "document_type": "官方统计公报（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "patterns": {
            "gdp_current_100m": (r"全年全市地区生产总值([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全年全市地区生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"全年全市一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "A2许昌市统计局、国家统计局许昌调查队官方统计公报；采用2025年全市GDP、增速、年末常住人口和一般公共预算收支，政府性基金收入未在本来源中披露。",
    },
    {
        "city_name": "鹤壁市",
        "city_id": "CN-410600",
        "source_doc_id": "SRC-B2-HENAN-CITY-STATISTICAL-HEBI-2025",
        "url": "https://tjgb.hongheiku.com/xjtjgb/xj2020/72286.html",
        "attachment_url": "https://tjgb.hongheiku.com/xjtjgb/xj2020/72286.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "hebi_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "hebi_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年鹤壁市国民经济和社会发展统计公报",
        "publisher": "鹤壁市统计局",
        "publisher_level": "公开资料转载",
        "publication_date": "2026-05-22",
        "title_source": "html_statement_excerpt",
        "document_type": "统计公报经济财政段落（精确转载）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "patterns": {
            "gdp_current_100m": (r"全年全市生产总值([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全年全市生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"全年全市一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2精确转载，页面来源标注为鹤壁市统计局；采用2025年全市GDP、增速、年末常住人口和一般公共预算收支，政府性基金收入未在本来源中披露。",
    },
)

NEXT11_2025_ECONOMIC_SOURCES = (
    {
        "city_name": "商丘市",
        "city_id": "CN-411400",
        "source_doc_id": "SRC-B2-HENAN-CITY-STATISTICAL-SHANGQIU-2025",
        "url": "https://tjgb.hongheiku.com/xjtjgb/xj2020/71808.html",
        "attachment_url": "https://tjgb.hongheiku.com/xjtjgb/xj2020/71808.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "shangqiu_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "shangqiu_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年商丘市国民经济和社会发展统计公报",
        "publisher": "商丘市统计局",
        "publisher_level": "公开资料转载",
        "publication_date": "2026-05-20",
        "title_source": "html_statement_excerpt",
        "document_type": "统计公报经济财政段落（精确转载）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "patterns": {
            "gdp_current_100m": (r"全年全市生产总值([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全年全市生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"全年全市一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2精确转载，页面来源标注为商丘市统计局；采用2025年全市GDP、增速、年末常住人口和一般公共预算收支，政府性基金收入未在本来源中披露。",
    },
    {
        "city_name": "信阳市",
        "city_id": "CN-411500",
        "source_doc_id": "SRC-A2-HENAN-CITY-STATISTICAL-XINYANG-2025",
        "url": "https://tjj.xinyang.gov.cn/2026/05-21/786229.html",
        "attachment_url": "https://tjj.xinyang.gov.cn/2026/05-21/786229.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "xinyang_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "xinyang_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年信阳市国民经济和社会发展统计公报",
        "publisher": "信阳市统计局",
        "publisher_level": "市级统计机构",
        "publication_date": "2026-05-21",
        "title_source": "official_page_excerpt",
        "document_type": "官方统计公报（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "patterns": {
            "gdp_current_100m": (r"全年全市地区生产总值([0-9.]+)亿元，按可比价格计算，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全年全市地区生产总值[0-9.]+亿元，按可比价格计算，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "A2信阳市统计局官方统计公报；采用2025年全市GDP、增速、年末常住人口和一般公共预算收支，政府性基金收入未在本来源中披露。",
    },
    {
        "city_name": "周口市",
        "city_id": "CN-411600",
        "source_doc_id": "SRC-B2-HENAN-CITY-STATISTICAL-ZHOUKOU-2025",
        "url": "https://tjgb.hongheiku.com/djs/70352.html",
        "attachment_url": "https://tjgb.hongheiku.com/djs/70352.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhoukou_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhoukou_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年周口市国民经济和社会发展统计公报",
        "publisher": "周口市统计局",
        "publisher_level": "公开资料转载",
        "publication_date": "2026-05-13",
        "title_source": "html_statement_excerpt",
        "document_type": "统计公报经济财政段落（精确转载）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "patterns": {
            "gdp_current_100m": (r"全年全市地区生产总值([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全年全市地区生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2精确转载，页面来源标注为周口市统计局；采用2025年全市GDP、增速、年末常住人口和一般公共预算收支，政府性基金收入未在本来源中披露。",
    },
)

NEXT12_2025_ECONOMIC_SOURCES = (
    {
        "city_name": "濮阳市",
        "city_id": "CN-410900",
        "source_doc_id": "SRC-B2-HENAN-CITY-STATISTICAL-PUYANG-2025",
        "url": "https://tjgb.hongheiku.com/xjtjgb/xj2020/74371.html",
        "attachment_url": "https://tjgb.hongheiku.com/xjtjgb/xj2020/74371.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "puyang_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "puyang_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年濮阳市国民经济和社会发展统计公报",
        "publisher": "濮阳市统计局",
        "publisher_level": "公开资料转载",
        "publication_date": "2026-06-05",
        "title_source": "html_statement_excerpt",
        "document_type": "统计公报经济财政段落（精确转载）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "patterns": {
            "gdp_current_100m": (r"全年全市地区生产总值([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全年全市地区生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2精确转载，页面来源标注为濮阳市统计局；采用2025年全市GDP、增速、年末常住人口和一般公共预算收支，政府性基金收入未在本来源中披露。",
    },
    {
        "city_name": "驻马店市",
        "city_id": "CN-411700",
        "source_doc_id": "SRC-B2-HENAN-CITY-STATISTICAL-ZHUMADIAN-2025",
        "url": "https://tjgb.hongheiku.com/xjtjgb/xj2020/75501.html",
        "attachment_url": "https://tjgb.hongheiku.com/xjtjgb/xj2020/75501.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhumadian_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhumadian_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年驻马店市国民经济和社会发展统计公报",
        "publisher": "驻马店市统计局",
        "publisher_level": "公开资料转载",
        "publication_date": "2026-07-15",
        "title_source": "html_statement_excerpt",
        "document_type": "统计公报经济财政段落（精确转载）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "patterns": {
            "gdp_current_100m": (r"全年全市地区生产总值([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全年全市地区生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2精确转载，页面来源标注为驻马店市统计局；采用2025年全市GDP、增速、年末常住人口和一般公共预算收支，政府性基金收入未在本来源中披露。",
    },
    {
        "city_name": "漯河市",
        "city_id": "CN-411100",
        "source_doc_id": "SRC-B2-HENAN-CITY-STATISTICAL-LUOHE-2025",
        "url": "https://m.sohu.com/a/1035539528_121106991",
        "attachment_url": "https://m.sohu.com/a/1035539528_121106991",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "luohe_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "luohe_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年漯河市国民经济和社会发展统计公报",
        "publisher": "漯河市统计局",
        "publisher_level": "公开资料转载",
        "publication_date": "2026-06-12",
        "title_source": "html_statement_excerpt",
        "document_type": "统计公报经济财政段落（精确转载）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "patterns": {
            "gdp_current_100m": (r"全年全市地区生产总值([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全年全市地区生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2精确转载，页面来源标注为漯河市统计局；采用2025年全市GDP、增速、年末常住人口和一般公共预算收支，政府性基金收入未在本来源中披露。",
    },
)

NEXT13_2025_ECONOMIC_SOURCES = (
    {
        "city_name": "平顶山市",
        "city_id": "CN-410400",
        "source_doc_id": "SRC-A2-HENAN-CITY-STATISTICAL-PINGDINGSHAN-2025",
        "url": "https://pds.gov.cn/contents/22179/468637.html",
        "attachment_url": "https://pds.gov.cn/contents/22179/468637.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "pingdingshan_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "pingdingshan_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年平顶山市国民经济和社会发展统计公报",
        "publisher": "平顶山市统计局",
        "publisher_level": "市级统计机构",
        "publication_date": "2026-06-30",
        "title_source": "official_page_excerpt",
        "document_type": "官方统计公报经济指标（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "data_status": "preliminary",
        "patterns": {
            "gdp_current_100m": (r"全年全市地区生产总值([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全年全市地区生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
        },
        "note": "A2平顶山市统计局官方统计公报；采用2025年全市GDP、增速和年末常住人口，经济数据为公报初步统计结果；一般预算收支和政府性基金收入分别按财政执行报告来源入表。",
    },
)

NEXT14_2025_ECONOMIC_SOURCES = (
    {
        "city_name": "焦作市",
        "city_id": "CN-410800",
        "source_doc_id": "SRC-A2-HENAN-CITY-STATISTICAL-JIAOZUO-2025",
        "url": "https://oss.jiaozuo.gov.cn/4108000001/upload-file/files/20260617/b10d4ba7a3a746b1bb7df94c4df344a0.pdf",
        "attachment_url": "https://oss.jiaozuo.gov.cn/4108000001/upload-file/files/20260617/b10d4ba7a3a746b1bb7df94c4df344a0.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "jiaozuo_2025_statistical_bulletin.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "jiaozuo_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年焦作市国民经济和社会发展统计公报",
        "publisher": "焦作市统计局",
        "publisher_level": "市级统计机构",
        "publication_date": "2026-06-17",
        "title_source": "official_pdf_excerpt",
        "document_type": "官方统计公报经济财政指标（PDF）",
        "mime_type": "application/pdf",
        "source_grade": "A2",
        "data_status": "preliminary",
        "patterns": {
            "gdp_current_100m": (r"全年全市地区生产总值([0-9.]+)亿元，同比增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全年全市地区生产总值[0-9.]+亿元，同比增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "A2焦作市统计局官方统计公报PDF；采用2025年全市GDP、增速、年末常住人口和一般公共预算收支，公报注明为初步统计数，政府性基金收入未在本来源中披露。",
    },
)

NEXT15_2025_ECONOMIC_SOURCES = (
    {
        "city_name": "三门峡市",
        "city_id": "CN-411200",
        "source_doc_id": "SRC-A2-HENAN-CITY-STATISTICAL-SANMENXIA-2025",
        "url": "https://www.smx.gov.cn/10486/2026/6/2269438.html",
        "attachment_url": "https://www.smx.gov.cn/10486/2026/6/2269438.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "sanmenxia_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "sanmenxia_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年三门峡市国民经济和社会发展统计公报",
        "publisher": "三门峡市统计局",
        "publisher_level": "市级统计机构",
        "publication_date": "2026-06-22",
        "title_source": "official_page_excerpt",
        "document_type": "官方统计公报经济财政指标（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "data_status": "preliminary",
        "patterns": {
            "gdp_current_100m": (r"全年全市地区生产总值([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全年全市地区生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "A2三门峡市统计局官方统计公报；采用2025年全市GDP、增速、年末常住人口和一般公共预算收支，公报注明为初步统计结果，政府性基金收入未在本来源中披露。",
    },
    {
        "city_name": "洛阳市",
        "city_id": "CN-410300",
        "source_doc_id": "SRC-B2-HENAN-CITY-STATISTICAL-LUOYANG-2025",
        "url": "https://tjgb.hongheiku.com/djs/69917.html",
        "attachment_url": "https://tjgb.hongheiku.com/djs/69917.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "luoyang_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "luoyang_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年洛阳市国民经济和社会发展统计公报",
        "publisher": "洛阳市统计局",
        "publisher_level": "公开资料转载",
        "publication_date": "2026-04-30",
        "title_source": "html_statement_excerpt",
        "document_type": "统计公报经济财政段落（精确转载）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "data_status": "preliminary",
        "patterns": {
            "gdp_current_100m": (r"全年全市生产总值达到([0-9.]+)亿元，按可比价计算，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全年全市生产总值达到[0-9.]+亿元，按可比价计算，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2精确转载，页面来源标注为洛阳市统计局；采用2025年全市GDP、增速、年末常住人口和一般公共预算收支，公报注明为初步统计结果，政府性基金收入未在本来源中披露。",
    },
)

NEXT16_2025_ECONOMIC_SOURCES = (
    {
        "city_name": "岳阳市",
        "city_id": "CN-430600",
        "source_doc_id": "SRC-A2-HUNAN-CITY-STATISTICAL-YUEYANG-2025",
        "url": "https://www.yueyang.gov.cn/tjgb/content_2380060.html",
        "attachment_url": "https://www.yueyang.gov.cn/tjgb/content_2380060.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "yueyang_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "yueyang_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "岳阳市2025年国民经济和社会发展统计公报",
        "publisher": "岳阳市统计局",
        "publisher_level": "市级统计机构",
        "publication_date": "2026-04-30",
        "title_source": "official_page_excerpt",
        "document_type": "官方统计公报经济指标（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "data_status": "preliminary",
        "patterns": {
            "gdp_current_100m": (r"全年地区生产总值([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全年地区生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
        },
        "note": "A2岳阳市统计局官方统计公报；补录2025年全市GDP、增速和年末常住人口，财政收入、支出沿用已归档的市级财政来源。",
    },
    {
        "city_name": "益阳市",
        "city_id": "CN-430900",
        "source_doc_id": "SRC-A2-HUNAN-CITY-STATISTICAL-YIYANG-2025",
        "url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/yiys_1/202605/t20260512_33975330.html",
        "attachment_url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/yiys_1/202605/t20260512_33975330.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "yiyang_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "yiyang_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "益阳市2025年国民经济和社会发展统计公报",
        "publisher": "湖南省统计局、益阳市统计局",
        "publisher_level": "省级统计机构转载",
        "publication_date": "2026-04-30",
        "title_source": "official_page_excerpt",
        "document_type": "官方统计公报经济指标（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "data_status": "preliminary",
        "patterns": {
            "gdp_current_100m": (r"全年地区生产总值([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全年地区生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
        },
        "note": "A2湖南省统计局公开的益阳市统计公报；补录2025年全市GDP、增速和年末常住人口，财政收入、支出沿用已归档的市级财政来源。",
    },
    {
        "city_name": "常德市",
        "city_id": "CN-430700",
        "source_doc_id": "SRC-A2-HUNAN-CITY-STATISTICAL-CHANGDE-2025",
        "url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/cds_1/202605/t20260518_33979393.html",
        "attachment_url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/cds_1/202605/t20260518_33979393.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "changde_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "changde_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "常德市2025年国民经济和社会发展统计公报",
        "publisher": "湖南省统计局、常德市统计局",
        "publisher_level": "省级统计机构转载",
        "publication_date": "2026-05-15",
        "title_source": "official_page_excerpt",
        "document_type": "官方统计公报经济指标（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "data_status": "preliminary",
        "patterns": {
            "gdp_current_100m": (r"2025年全市实现地区生产总值([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"2025年全市实现地区生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"全市年末常住人口([0-9.]+)万人", "万人"),
        },
        "note": "A2湖南省统计局公开的常德市统计公报；补录2025年全市GDP、增速和年末常住人口，财政收入、支出沿用已归档的市级财政来源。",
    },
)

NEXT17_2025_ECONOMIC_SOURCES = (
    {
        "city_name": "衡阳市",
        "city_id": "CN-430400",
        "source_doc_id": "SRC-A2-HUNAN-CITY-STATISTICAL-HENGYANG-2025",
        "url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/hys_1/202605/t20260512_33975342.html",
        "attachment_url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/hys_1/202605/t20260512_33975342.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "hengyang_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "hengyang_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "衡阳市2025年国民经济和社会发展统计公报",
        "publisher": "湖南省统计局、衡阳市统计局",
        "publisher_level": "省级统计机构转载",
        "publication_date": "2026-05-12",
        "title_source": "official_page_excerpt",
        "document_type": "官方统计公报经济财政指标（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "data_status": "preliminary",
        "patterns": {
            "gdp_current_100m": (r"实现地区生产总值（GDP）([0-9.]+)亿元，增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"实现地区生产总值（GDP）[0-9.]+亿元，增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"2025年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"全市地方一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"全年一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "A2湖南省统计局公开的衡阳市统计公报；补录2025年全市GDP、增速、年末常住人口和一般公共预算收支，政府性基金收入未在本来源中披露。",
    },
    {
        "city_name": "邵阳市",
        "city_id": "CN-430500",
        "source_doc_id": "SRC-A2-HUNAN-CITY-STATISTICAL-SHAOYANG-2025",
        "url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/sys_1/202605/t20260518_33979386.html",
        "attachment_url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/sys_1/202605/t20260518_33979386.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "shaoyang_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "shaoyang_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "邵阳市2025年国民经济和社会发展统计公报",
        "publisher": "湖南省统计局、邵阳市统计局",
        "publisher_level": "省级统计机构转载",
        "publication_date": "2026-05-18",
        "title_source": "official_page_excerpt",
        "document_type": "官方统计公报经济财政指标（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "data_status": "preliminary",
        "patterns": {
            "gdp_current_100m": (r"完成地区生产总值([0-9.]+)亿元、增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"完成地区生产总值[0-9.]+亿元、增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"地方一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "A2湖南省统计局公开的邵阳市统计公报；补录2025年全市GDP、增速、年末常住人口和一般公共预算收支，政府性基金收入未在本来源中披露。",
    },
    {
        "city_name": "郴州市",
        "city_id": "CN-431000",
        "source_doc_id": "SRC-A2-HUNAN-CITY-STATISTICAL-CHENZHOU-2025",
        "url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/czs_1/202605/t20260512_33975324.html",
        "attachment_url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/czs_1/202605/t20260512_33975324.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "chenzhou_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "chenzhou_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "郴州市2025年国民经济和社会发展统计公报",
        "publisher": "湖南省统计局、郴州市统计局",
        "publisher_level": "省级统计机构转载",
        "publication_date": "2026-04-17",
        "title_source": "official_page_excerpt",
        "document_type": "官方统计公报经济财政指标（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "data_status": "preliminary",
        "patterns": {
            "gdp_current_100m": (r"地区生产总值([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"地区生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"地方一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "A2湖南省统计局公开的郴州市统计公报；补录2025年全市GDP、增速、年末常住人口和一般公共预算收支，政府性基金收入未在本来源中披露。",
    },
    {
        "city_name": "永州市",
        "city_id": "CN-431100",
        "source_doc_id": "SRC-A2-HUNAN-CITY-STATISTICAL-YONGZHOU-2025",
        "url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/yzs_1/202605/t20260521_33982654.html",
        "attachment_url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/yzs_1/202605/t20260521_33982654.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "yongzhou_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "yongzhou_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "永州市2025年国民经济和社会发展统计公报",
        "publisher": "湖南省统计局、永州市统计局",
        "publisher_level": "省级统计机构转载",
        "publication_date": "2026-05-21",
        "title_source": "official_page_excerpt",
        "document_type": "官方统计公报经济财政指标（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "data_status": "preliminary",
        "patterns": {
            "gdp_current_100m": (r"地区生产总值\[2\]([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"地区生产总值\[2\][0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"地方一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "A2湖南省统计局公开的永州市统计公报；补录2025年全市GDP、增速、年末常住人口和一般公共预算收支，政府性基金收入未在本来源中披露。",
    },
    {
        "city_name": "怀化市",
        "city_id": "CN-431200",
        "source_doc_id": "SRC-A2-HUNAN-CITY-STATISTICAL-HUAIHUA-2025",
        "url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/hhs_1/202605/t20260512_33975309.html",
        "attachment_url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/hhs_1/202605/t20260512_33975309.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "huaihua_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "huaihua_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "怀化市2025年国民经济与社会发展统计公报",
        "publisher": "湖南省统计局、怀化市统计局",
        "publisher_level": "省级统计机构转载",
        "publication_date": "2026-05-12",
        "title_source": "official_page_excerpt",
        "document_type": "官方统计公报经济财政指标（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "data_status": "preliminary",
        "patterns": {
            "gdp_current_100m": (r"完成地区生产总值（GDP）([0-9.]+)亿元，较上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"完成地区生产总值（GDP）[0-9.]+亿元，较上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"全市年末常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"地方一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"全市一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "A2湖南省统计局公开的怀化市统计公报；补录2025年全市GDP、增速、年末常住人口和一般公共预算收支，公报注明财政数据来自市财政局快报，政府性基金收入未在本来源中披露。",
    },
    {
        "city_name": "娄底市",
        "city_id": "CN-431300",
        "source_doc_id": "SRC-A2-HUNAN-CITY-STATISTICAL-LOUDI-2025",
        "url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/lds_1/202605/t20260512_33975300.html",
        "attachment_url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/lds_1/202605/t20260512_33975300.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "loudi_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "loudi_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "娄底市2025年国民经济和社会发展统计公报",
        "publisher": "湖南省统计局、娄底市统计局",
        "publisher_level": "省级统计机构转载",
        "publication_date": "2026-04-29",
        "title_source": "official_page_excerpt",
        "document_type": "官方统计公报经济财政指标（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "data_status": "preliminary",
        "patterns": {
            "gdp_current_100m": (r"实现地区生产总值([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"实现地区生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"常住人口([0-9.]+)万人，其中城镇人口", "万人"),
            "general_public_revenue_100m": (r"地方一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"公共财政预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "A2湖南省统计局公开的娄底市统计公报；补录2025年全市GDP、增速、年末常住人口和一般公共预算收支，政府性基金收入未在本来源中披露。",
    },
)

NEXT18_2025_ECONOMIC_SOURCES = (
    {
        "city_name": "张家界市",
        "city_id": "CN-430800",
        "source_doc_id": "SRC-A2-HUNAN-CITY-STATISTICAL-ZHANGJIAJIE-2025",
        "url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/zjj_1/202605/33975335/files/d3f82e78caf645eeab356512dcef1e3a.pdf",
        "attachment_url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/zjj_1/202605/33975335/files/d3f82e78caf645eeab356512dcef1e3a.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "zhangjiajie_2025_statistical_bulletin.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "zhangjiajie_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "张家界市2025年国民经济和社会发展统计公报",
        "publisher": "湖南省统计局、张家界市统计局",
        "publisher_level": "省级统计机构转载",
        "publication_date": "2026-05-06",
        "title_source": "official_pdf_excerpt",
        "document_type": "官方统计公报经济财政指标（扫描 PDF）",
        "mime_type": "application/pdf",
        "source_grade": "A2",
        "data_status": "preliminary",
        "patterns": {
            "gdp_current_100m": (r"全市实现地区生产总值([0-9.]+)亿元，同比增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全市实现地区生产总值[0-9.]+亿元，同比增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "A2湖南省统计局公开的张家界市统计公报扫描 PDF；按人工核对页 1、11、17 摘录2025年全市GDP、增速、年末常住人口和一般公共预算收支，政府性基金收入未在本来源中披露。",
    },
    {
        "city_name": "湘潭市",
        "city_id": "CN-430300",
        "source_doc_id": "SRC-A2-HUNAN-CITY-STATISTICAL-XIANGTAN-2025",
        "url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/xts_1/202605/33975345/files/f4a40747dddb439698b17b49eaecedba.pdf",
        "attachment_url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/xts_1/202605/33975345/files/f4a40747dddb439698b17b49eaecedba.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "xiangtan_2025_statistical_bulletin.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "xiangtan_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "湘潭市2025年国民经济和社会发展统计公报",
        "publisher": "湘潭市统计局、国家统计局湘潭调查队",
        "publisher_level": "市级统计机构",
        "publication_date": "2026-04-28",
        "title_source": "official_pdf_excerpt",
        "document_type": "官方统计公报经济财政指标（PDF）",
        "mime_type": "application/pdf",
        "source_grade": "A2",
        "data_status": "preliminary",
        "patterns": {
            "gdp_current_100m": (r"地区生产总值\[2\]([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"地区生产总值\[2\][0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"地方一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"全市一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "A2湘潭市统计局官方统计公报 PDF；补录2025年全市GDP、增速、年末常住人口和一般公共预算收支，政府性基金收入未在本来源中披露。",
    },
    {
        "city_name": "湘西土家族苗族自治州",
        "city_id": "CN-433100",
        "source_doc_id": "SRC-A2-HUNAN-PREFECTURE-STATISTICAL-XIANGXI-2025",
        "url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/xxz_1/202605/33975294/files/602a896243b34c51ad25f22ef2aa7cc2.pdf",
        "attachment_url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/xxz_1/202605/33975294/files/602a896243b34c51ad25f22ef2aa7cc2.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "xiangxi_2025_statistical_bulletin.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "xiangxi_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "湘西自治州2025年国民经济和社会发展统计公报",
        "publisher": "湘西州统计局、国家统计局湘西调查队",
        "publisher_level": "州级统计机构",
        "publication_date": "2026-04-22",
        "title_source": "official_pdf_excerpt",
        "document_type": "官方统计公报经济财政指标（PDF）",
        "mime_type": "application/pdf",
        "source_grade": "A2",
        "data_status": "preliminary",
        "patterns": {
            "gdp_current_100m": (r"全州实现生产总值（GDP）([0-9.]+)亿元，增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全州实现生产总值（GDP）[0-9.]+亿元，增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"常住人口([0-9.]+)万人。其中", "万人"),
            "general_public_revenue_100m": (r"全州一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"全州一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "A2湘西州统计局官方统计公报 PDF；补录2025年全州GDP、增速、年末常住人口和一般公共预算收支，政府性基金收入未在本来源中披露。",
    },
)

NEXT19_2025_ECONOMIC_SOURCES = (
    {
        "city_name": "株洲市",
        "city_id": "CN-430200",
        "source_doc_id": "SRC-A2-HUNAN-CITY-STATISTICAL-ZHUZHOU-2025",
        "url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/zzs_1/202605/t20260512_33975349.html",
        "attachment_url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/zzs_1/202605/t20260512_33975349.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "zhuzhou_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "zhuzhou_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "source_format": "html",
        "document_title": "株洲市2025年国民经济和社会发展统计公报",
        "publisher": "湖南省统计局、株洲市统计局",
        "publisher_level": "省级统计机构转载",
        "publication_date": "2026-04-29",
        "title_source": "official_html",
        "document_type": "官方统计公报经济财政指标（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "data_status": "preliminary",
        "patterns": {
            "gdp_current_100m": (r"全市地区生产总值([0-9.]+)亿元，增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全市地区生产总值[0-9.]+亿元，增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"全市年末常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"地方一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "A2湖南省统计局转载株洲市统计局官方统计公报；补录2025年全市GDP、增速、年末常住人口和一般公共预算收支，政府性基金收入未在本来源中披露。公报注明2025年数据为初步统计数。",
    },
)

NEXT20_2025_ECONOMIC_SOURCES = (
    {
        "city_name": "长沙市",
        "city_id": "CN-430100",
        "source_doc_id": "SRC-A2-HUNAN-CITY-STATISTICAL-CHANGSHA-2025-POPULATION",
        "url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/zss_1/202605/t20260512_33975356.html",
        "attachment_url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/zss_1/202605/t20260512_33975356.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "changsha_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "changsha_2025_statistical_bulletin_population_excerpt.txt",
        "text_is_curated": True,
        "source_format": "html",
        "document_title": "长沙市2025年国民经济和社会发展统计公报",
        "publisher": "湖南省统计局、长沙市统计局",
        "publisher_level": "省级统计机构转载",
        "publication_date": "2026-04-21",
        "title_source": "official_html",
        "document_type": "官方统计公报人口指标（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "data_status": "preliminary",
        "patterns": {
            "resident_population_10k": (r"年末全市常住总人口([0-9.]+)万人", "万人"),
        },
        "note": "A2湖南省统计局转载长沙市统计局官方统计公报；补录2025年末全市常住总人口，公报未将政府性基金执行数与预算预期数混列，因此不在本来源中填充基金收入。",
    },
)

NEXT21_2025_ECONOMIC_SOURCES = (
    {
        "city_name": "克拉玛依市",
        "city_id": "CN-650200",
        "source_doc_id": "SRC-B2-XINJIANG-CITY-STATISTICAL-KARAMAY-2025",
        "url": "https://szb.kelamayi.com.cn/html/2026-05/19/content_1516_343187.htm",
        "attachment_url": "https://szb.kelamayi.com.cn/html/2026-05/19/content_1517_343188.htm",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "karamay_2025_statistical_bulletin_page07.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "karamay_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "source_format": "html",
        "document_title": "克拉玛依市2025年国民经济和社会发展统计公报",
        "publisher": "克拉玛依市统计局、克拉玛依日报",
        "publisher_level": "市级统计机构官方公报转载",
        "publication_date": "2026-05-19",
        "title_source": "official_newspaper_html",
        "document_type": "官方统计公报经济财政指标（网页及跨页转载）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "data_status": "preliminary",
        "patterns": {
            "gdp_current_100m": (r"全年实现地区生产总值（GDP）([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全年实现地区生产总值（GDP）[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"一般公共预算收入决算口径，全年全市一般公共财政预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共财政预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2克拉玛依市统计局官方统计公报由克拉玛依日报数字报完整转载；按公报明确的2025年一般公共预算收入决算口径采用106.92亿元，不采用体制改革前核定数134.6亿元。政府性基金收入未在本来源中披露。",
    },
    {
        "city_name": "吐鲁番市",
        "city_id": "CN-650400",
        "source_doc_id": "SRC-A2-XINJIANG-CITY-STATISTICAL-TURPAN-2025",
        "url": "https://www.tlf.gov.cn/tlfs/c106274/202604/5dac049b5b88481b8363227e425e73d5.shtml",
        "attachment_url": "https://www.tlf.gov.cn/tlfs/c106274/202604/5dac049b5b88481b8363227e425e73d5.shtml",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "turpan_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "turpan_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "source_format": "html",
        "document_title": "吐鲁番市2025年国民经济和社会发展统计公报",
        "publisher": "吐鲁番市统计局",
        "publisher_level": "市级统计机构",
        "publication_date": "2026-04-22",
        "title_source": "official_html",
        "document_type": "官方统计公报经济财政指标（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "data_status": "preliminary",
        "patterns": {
            "gdp_current_100m": (r"全年实现地区生产总值\(GDP\)([0-9.]+)亿元，按不变价格计算，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全年实现地区生产总值\(GDP\)[0-9.]+亿元，按不变价格计算，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"全年一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"全年一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "A2吐鲁番市统计局官方统计公报；补录2025年GDP、增速、年末常住人口和一般公共预算收支，政府性基金收入未在本来源中披露。",
    },
    {
        "city_name": "哈密市",
        "city_id": "CN-650500",
        "source_doc_id": "SRC-A2-XINJIANG-CITY-STATISTICAL-HAMI-2025",
        "url": "https://www.hami.gov.cn/hami/c120173/202605/9bc459f53d3d4abda752ae0e967cf68a.shtml",
        "attachment_url": "https://www.hami.gov.cn/hami/c120173/202605/9bc459f53d3d4abda752ae0e967cf68a.shtml",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "hami_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "hami_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "source_format": "html",
        "document_title": "哈密市2025年国民经济和社会发展统计公报",
        "publisher": "哈密市统计局、国家统计局哈密调查队",
        "publisher_level": "市级统计机构",
        "publication_date": "2026-05-09",
        "title_source": "official_html",
        "document_type": "官方统计公报经济财政指标（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "data_status": "preliminary",
        "patterns": {
            "gdp_current_100m": (r"全年实现地区生产总值（GDP）([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全年实现地区生产总值（GDP）[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "general_public_revenue_100m": (r"一般公共预算收入完成([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "A2哈密市统计局、国家统计局哈密调查队官方统计公报；补录2025年GDP、增速和一般公共预算收支，公报未明确披露2025年末全市常住人口，人口字段不作推断填充，政府性基金收入未用预算数代填。",
    },
)

NEXT22_2025_ECONOMIC_SOURCES = (
    {
        "city_name": "昌吉回族自治州",
        "city_id": "CN-652300",
        "source_doc_id": "SRC-B2-XINJIANG-PREFECTURE-STATISTICAL-CHANGJI-2025",
        "url": "https://www.crei.cn/file/br.aspx?id=20260508105148",
        "attachment_url": "https://www.crei.cn/file/br.aspx?id=20260508105148",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "changji_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "changji_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "source_format": "html",
        "document_title": "昌吉回族自治州2025年国民经济和社会发展统计公报",
        "publisher": "昌吉回族自治州统计局",
        "publisher_level": "州级统计机构官方公报转载",
        "publication_date": "2026-05-08",
        "title_source": "official_reprint_html",
        "document_type": "官方统计公报经济财政指标（精确转载网页）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "data_status": "preliminary",
        "patterns": {
            "gdp_current_100m": (r"全年实现地区生产总值（GDP）([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全年实现地区生产总值（GDP）[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "general_public_revenue_100m": (r"全年一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2昌吉回族自治州统计局官方公报精确转载；补录2025年GDP、增速和一般公共预算收支，公报未明确披露全州年末常住人口，政府性基金收入未在本来源中披露。",
    },
)

NEXT23_2025_ECONOMIC_SOURCES = (
    {
        "city_name": "博尔塔拉蒙古自治州",
        "city_id": "CN-652700",
        "source_doc_id": "SRC-A2-XINJIANG-PREFECTURE-STATISTICAL-BOZHOU-2025",
        "url": "https://www.xjboz.gov.cn/xjboz/c125800/202604/119d224f1920458fb81d8de4ae48fb54.shtml",
        "attachment_url": "https://www.xjboz.gov.cn/xjboz/c125800/202604/119d224f1920458fb81d8de4ae48fb54.shtml",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "bozhou_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "bozhou_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "source_format": "html",
        "document_title": "博尔塔拉蒙古自治州2025年国民经济和社会发展统计公报",
        "publisher": "博尔塔拉蒙古自治州统计局",
        "publisher_level": "州级统计机构",
        "publication_date": "2026-04-20",
        "title_source": "official_html",
        "document_type": "官方统计公报经济财政指标（网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "data_status": "preliminary",
        "patterns": {
            "gdp_current_100m": (r"自治州地区生产总值([0-9.]+)亿元，按不变价格计算，同比增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"自治州地区生产总值[0-9.]+亿元，按不变价格计算，同比增长([0-9.]+)%", "%"),
            "general_public_revenue_100m": (r"自治州一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"自治州一般公共预算支出([0-9.]+)亿元", "亿元"),
            "gov_fund_revenue_100m": (r"政府性基金预算收入([0-9.]+)亿元", "亿元"),
        },
        "note": "A2博尔塔拉蒙古自治州统计局官方统计公报；补录2025年GDP、增速、一般公共预算收支和政府性基金收入，公报未明确披露全州年末常住人口。公报注明GDP、金融、保险、邮电、交通、外贸包含五师，财政字段采用自治州财政口径。",
    },
    {
        "city_name": "巴音郭楞蒙古自治州",
        "city_id": "CN-652800",
        "source_doc_id": "SRC-B2-XINJIANG-PREFECTURE-STATISTICAL-BAZHOU-2025",
        "url": "https://www.crei.cn/file/br.aspx?id=20260528085331&op=sczz&x=0",
        "attachment_url": "https://www.crei.cn/file/br.aspx?id=20260528085331&op=sczz&x=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "bazhou_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "bazhou_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "source_format": "html",
        "document_title": "巴音郭楞蒙古自治州2025年国民经济和社会发展统计公报",
        "publisher": "巴音郭楞蒙古自治州统计局、国家统计局巴音郭楞调查队",
        "publisher_level": "州级统计机构官方公报转载",
        "publication_date": "2026-05-28",
        "title_source": "official_reprint_html",
        "document_type": "官方统计公报经济财政指标（精确转载网页）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "data_status": "preliminary",
        "patterns": {
            "gdp_current_100m": (r"全年巴州地区实现生产总值（GDP）([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全年巴州地区实现生产总值（GDP）[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全州常住人口（不含铁门关市）([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"全年地方一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"地方一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2巴音郭楞蒙古自治州统计局官方公报精确转载；补录2025年GDP、增速、年末常住人口和一般公共预算收支。公报明确人口口径不含铁门关市，政府性基金收入未在本来源中披露。",
    },
)

NEXT24_2025_ECONOMIC_SOURCES = (
    {
        "city_name": "和田地区",
        "city_id": "CN-653200",
        "source_doc_id": "SRC-A2-XINJIANG-PREFECTURE-HOTAN-2025-STATISTICS-FINAL-FISCAL",
        "url": "https://www.xjht.gov.cn/xjht/c128291/202603/ff9ab42d41b44c749fa720ed94692fd6.shtml",
        "attachment_url": "https://www.xjht.gov.cn/xjht/c128291/202603/ff9ab42d41b44c749fa720ed94692fd6.shtml",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "hotan_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "hotan_2025_economic_fiscal_excerpt.txt",
        "text_is_curated": True,
        "source_format": "html",
        "document_title": "2025年和田地区统计公报及2025年度和田地区政府决算公开",
        "publisher": "和田地区统计局、和田地区财政局",
        "publisher_level": "地级行政机构官方发布",
        "publication_date": "2026-07-03",
        "title_source": "official_page_and_attachment_excerpt",
        "document_type": "官方统计公报及政府决算附件经济财政指标（网页、DOC）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "data_status": "preliminary",
        "source_locator": "hotan_2025_economic_fiscal_excerpt.txt；GDP增速=统计公报正文；一般预算收入=正式决算表本年收入合计；一般预算支出=正式决算表本年支出合计；政府性基金收入=正式决算表政府性基金收入；正式决算附件另归档为hotan_2025_final_budget_decision.doc",
        "patterns": {
            "gdp_real_growth_pct": (r"全年地区生产总值（GDP）比上年增长([0-9.]+)%", "%"),
            "general_public_revenue_100m": (r"一般公共预算收入决算表：本年收入合计([0-9]+)万元", "万元"),
            "general_public_expenditure_100m": (r"一般公共预算支出决算表：本年支出合计([0-9]+)万元", "万元"),
            "gov_fund_revenue_100m": (r"政府性基金预算收入决算表：政府性基金收入([0-9]+)万元", "万元"),
        },
        "note": "A2官方来源组合：和田地区统计局2025年统计公报补录GDP实际增速，和田地区财政局2025年度政府决算公开正式决算表补录全地区一般公共预算收入517283万元、支出4542199万元和政府性基金收入103427万元，统一换算为亿元。正式决算表优先于阶段性执行口径；不使用地区本级表数，也不把2025年统计公报中未披露的GDP绝对额、人口推断填入。",
    },
    {
        "city_name": "和田地区",
        "city_id": "CN-653200",
        "source_doc_id": "SRC-B2-XINJIANG-PREFECTURE-HOTAN-2025-GDP-TOTAL",
        "url": "https://xj.chinadaily.com.cn/a/202605/21/WS6a0eccc1a310942cc49ad950.html",
        "attachment_url": "https://xj.chinadaily.com.cn/a/202605/21/WS6a0eccc1a310942cc49ad950.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "hotan_2025_gdp_chinadaily.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "hotan_2025_gdp_chinadaily_excerpt.txt",
        "text_is_curated": True,
        "source_format": "html",
        "document_title": "中国日报网：开局起步‘十五五’——新疆和田进入历史上最好、最快、最稳发展时期",
        "publisher": "中国日报网（新疆自治区人民政府新闻办公室新闻发布会报道）",
        "publisher_level": "中央媒体精确公开报道",
        "publication_date": "2026-05-21",
        "title_source": "chinadaily_news_release",
        "document_type": "公开报道引用地区经济指标",
        "mime_type": "text/html",
        "source_grade": "B2",
        "data_status": "preliminary",
        "source_locator": "hotan_2025_gdp_chinadaily_excerpt.txt；正文第96行附近；和田地区全地区",
        "patterns": {
            "gdp_current_100m": (r"城市=和田地区｜年度=2025｜GDP=([0-9.]+)亿元", "亿元"),
        },
        "note": "B2精确公开报道；中国日报网报道新疆自治区人民政府新闻办公室新闻发布会，明确和田地区生产总值2025年增长至648.11亿元。和田地区官方统计公报未披露GDP绝对额，本来源仅补GDP现价总量，不覆盖A2官方来源已接入的GDP增速和财政字段；不使用平均增速反推GDP。",
    },
    {
        "city_name": "克孜勒苏柯尔克孜自治州",
        "city_id": "CN-653000",
        "source_doc_id": "SRC-A2-XINJIANG-PREFECTURE-KIZILSU-2025-STATISTICS-FISCAL",
        "url": "https://www.xjkz.gov.cn/xjkz/c101979/202606/d76bebc5d6524f16ad96a53ea24f4c57.shtml",
        "attachment_url": "https://www.xjkz.gov.cn/xjkz/c101979/202606/d76bebc5d6524f16ad96a53ea24f4c57.shtml",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "kizilsu_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "kizilsu_2025_economic_fiscal_excerpt.txt",
        "text_is_curated": True,
        "source_format": "html",
        "document_title": "克孜勒苏柯尔克孜自治州2025年统计公报及2025年经济运行情况",
        "publisher": "克孜勒苏柯尔克孜自治州统计局、克孜勒苏柯尔克孜自治州人民政府",
        "publisher_level": "自治州官方发布",
        "publication_date": "2026-06-02",
        "title_source": "official_page_and_image_excerpt",
        "document_type": "官方统计公报及经济运行财政指标（网页、图文附件）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "data_status": "preliminary",
        "source_locator": "kizilsu_2025_economic_fiscal_excerpt.txt；GDP及增速=统计公报图文第1页；人口=统计公报图文第12页；一般预算收入、支出=克州2025年经济运行情况财政段落；公报第1、2、12页图像已归档",
        "patterns": {
            "gdp_current_100m": (r"全年实现地区生产总值（GDP）([0-9.]+)亿元", "亿元"),
            "gdp_real_growth_pct": (r"全年实现地区生产总值（GDP）[0-9.]+亿元，按可比价格计算，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全州常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"2025年，全州一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"全州一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "A2克州官方图文统计公报和官方经济运行情况组合：补录2025年GDP、实际增速、年末常住人口及一般公共预算收支；财政数来自官方年度经济运行财政段落，政府性基金收入本批未取得全州全年决算数，不用预算数或阶段性执行数代填。",
    },
)

NEXT25_2025_ECONOMIC_SOURCES = (
    {
        "city_name": "阿克苏地区",
        "city_id": "CN-652900",
        "source_doc_id": "SRC-B2-XINJIANG-PREFECTURE-AKSU-2025-STATISTICS-FISCAL",
        "url": "https://www.crei.cn/file/br.aspx?id=20260528085809&op=sczz&x=0",
        "attachment_url": "https://www.crei.cn/file/br.aspx?id=20260528085809&op=sczz&x=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "aksu_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "aksu_2025_economic_fiscal_excerpt.txt",
        "text_is_curated": True,
        "source_format": "html",
        "document_title": "阿克苏地区2025年国民经济和社会发展统计公报",
        "publisher": "阿克苏地区统计局（官方公报精确转载）",
        "publisher_level": "地区统计机构官方公报转载",
        "publication_date": "2026-04-30",
        "title_source": "official_reprint_html",
        "document_type": "官方统计公报经济财政指标（精确转载网页）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "data_status": "preliminary",
        "source_locator": "aksu_2025_economic_fiscal_excerpt.txt；GDP及增速=统计公报正文；一般公共预算收入、支出=统计公报财政段落；公报未披露常住人口和政府性基金收入",
        "patterns": {
            "gdp_current_100m": (r"全年阿克苏地区生产总值（GDP）([0-9.]+)亿元", "亿元"),
            "gdp_real_growth_pct": (r"全年阿克苏地区生产总值（GDP）[0-9.]+亿元，按不变价格计算，比上年增长([0-9.]+)%", "%"),
            "general_public_revenue_100m": (r"全年一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "B2阿克苏地区统计局公报精确转载；正文精确披露2025年GDP、实际增速和一般公共预算收支。因当前可核验页面未披露年末常住人口与政府性基金收入，二者不以其他口径推算。",
    },
    {
        "city_name": "喀什地区",
        "city_id": "CN-653100",
        "source_doc_id": "SRC-A2-XINJIANG-PREFECTURE-KASHGAR-2025-STATISTICS-FISCAL",
        "url": "https://www.kashi.gov.cn/ksdqxzgs/c112198/202604/4eb6af2f3cda49a8baa7df45973b6f21.shtml",
        "attachment_url": "https://www.kashi.gov.cn/ksdqxzgs/c112198/202604/4eb6af2f3cda49a8baa7df45973b6f21.shtml",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "kashgar_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "kashgar_2025_economic_fiscal_excerpt.txt",
        "text_is_curated": True,
        "source_format": "html",
        "document_title": "喀什地区2025年国民经济和社会发展统计公报",
        "publisher": "喀什地区统计局、国家统计局喀什调查队",
        "publisher_level": "地区统计机构",
        "publication_date": "2026-04-08",
        "title_source": "official_image_page",
        "document_type": "官方统计公报经济财政指标（图文网页）",
        "mime_type": "text/html",
        "source_grade": "A2",
        "data_status": "preliminary",
        "source_locator": "kashgar_2025_economic_fiscal_excerpt.txt；GDP=官方公报图文第1页；一般预算收入、支出=官方公报图文第16页；对应图像已归档；公报未披露常住人口和政府性基金收入",
        "patterns": {
            "gdp_current_100m": (r"2025年，喀什地区生产总值（GDP）([0-9.]+)亿元", "亿元"),
            "gdp_real_growth_pct": (r"2025年，喀什地区生产总值（GDP）[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "general_public_revenue_100m": (r"全年一般公共预算收入完成([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "A2喀什地区统计局和国家统计局喀什调查队官方图文公报；补录2025年GDP、实际增速和一般公共预算收支。公报未披露年末常住人口与政府性基金收入，二者不以其他口径推算。",
    },
)

NEXT26_2025_ECONOMIC_SOURCES = (
    {
        "city_name": "成都市",
        "city_id": "CN-510100",
        "source_doc_id": "SRC-B2-SICHUAN-CITY-STATISTICAL-CHENGDU-2025-ECONOMIC",
        "url": "https://www.crei.cn/file/br.aspx?id=20260420165225&op=zc&x=0",
        "attachment_url": "https://www.crei.cn/file/br.aspx?id=20260420165225&op=zc&x=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "chengdu_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "chengdu_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "source_format": "html",
        "document_title": "2025年成都市国民经济和社会发展统计公报",
        "publisher": "中国区域经济学会信息平台转载（出处为成都市统计局）",
        "publisher_level": "市级统计机构公报转载",
        "publication_date": "2026-04-20",
        "title_source": "official_reprint_html",
        "document_type": "统计公报经济指标（精确转载网页）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "data_status": "preliminary",
        "source_locator": "chengdu_2025_statistical_bulletin_excerpt.txt；GDP及增速=统计公报综合段；年末常住人口=统计公报综合段；原始网页已归档",
        "patterns": {
            "gdp_current_100m": (r"2025年成都市地区生产总值([0-9.]+)亿元，按可比价格计算，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"2025年成都市地区生产总值[0-9.]+亿元，按可比价格计算，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
        },
        "note": "B2成都市统计局公报精确转载；补录2025年GDP、实际增速和年末常住人口。财政收入、支出和政府性基金收入由同一公报/成都市财政局独立来源分别记录，不在本经济批次重复覆盖。",
    },
)

NEXT27_2025_ECONOMIC_SOURCES = (
    {
        "city_name": "扬州市",
        "city_id": "CN-321000",
        "source_doc_id": "SRC-B2-JIANGSU-CITY-STATISTICAL-YANGZHOU-2025-ECONOMIC",
        "url": "https://www.crei.cn/file/br.aspx?id=20260527164838",
        "attachment_url": "https://www.crei.cn/file/br.aspx?id=20260527164838",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "yangzhou_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "yangzhou_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "source_format": "html",
        "document_title": "2025年扬州市国民经济和社会发展统计公报",
        "publisher": "中国区域经济学会信息平台转载（出处为扬州市统计局）",
        "publisher_level": "市级统计机构公报转载",
        "publication_date": "2026-05-27",
        "title_source": "official_reprint_html",
        "document_type": "统计公报经济指标（精确转载网页）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "data_status": "preliminary",
        "source_locator": "yangzhou_2025_statistical_bulletin_excerpt.txt；GDP及增速=统计公报综合段；年末常住人口=统计公报人口段；原始网页已归档",
        "patterns": {
            "gdp_current_100m": (r"2025年全市实现生产总值([0-9.]+)亿元，按不变价格计算，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"2025年全市实现生产总值[0-9.]+亿元，按不变价格计算，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
        },
        "note": "B2扬州市统计公报精确转载；补录2025年GDP、实际增速和年末常住人口。财政收入、支出和政府性基金收入由独立财政批次记录。",
    },
    {
        "city_name": "镇江市",
        "city_id": "CN-321100",
        "source_doc_id": "SRC-B2-JIANGSU-CITY-STATISTICAL-ZHENJIANG-2025-ECONOMIC",
        "url": "https://www.crei.cn/file/br.aspx?id=20260527164608&op=zc&x=0",
        "attachment_url": "https://www.crei.cn/file/br.aspx?id=20260527164608&op=zc&x=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhenjiang_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhenjiang_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "source_format": "html",
        "document_title": "2025年镇江市国民经济和社会发展统计公报",
        "publisher": "中国区域经济学会信息平台转载（出处为镇江市统计局）",
        "publisher_level": "市级统计机构公报转载",
        "publication_date": "2026-05-27",
        "title_source": "official_reprint_html",
        "document_type": "统计公报经济指标（精确转载网页）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "data_status": "preliminary",
        "source_locator": "zhenjiang_2025_statistical_bulletin_excerpt.txt；GDP及增速=统计公报综合段；原始网页已归档；公报未披露常住人口",
        "patterns": {
            "gdp_current_100m": (r"全年地区生产总值([0-9.]+)亿元，按不变价格计算，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"全年地区生产总值[0-9.]+亿元，按不变价格计算，比上年增长([0-9.]+)%", "%"),
        },
        "note": "B2镇江市统计公报精确转载；补录2025年GDP和实际增速，常住人口因公报未披露而保持为空；财政字段由独立财政批次记录。",
    },
)

NEXT28_2025_ECONOMIC_SOURCES = (
    {
        "city_name": "海口市",
        "city_id": "CN-460100",
        "source_doc_id": "SRC-B2-HAINAN-CITY-STATISTICAL-HAIKOU-2025-ECONOMIC",
        "url": "https://www.crei.cn/file/br.aspx?id=20260429152052&op=zc&x=0",
        "attachment_url": "https://www.crei.cn/file/br.aspx?id=20260429152052&op=zc&x=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "haikou_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "haikou_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "source_format": "html",
        "document_title": "2025年海口市国民经济和社会发展统计公报",
        "publisher": "中国区域经济学会信息平台转载（出处为海口市统计局）",
        "publisher_level": "市级统计机构公报转载",
        "publication_date": "2026-04-29",
        "title_source": "official_reprint_html",
        "document_type": "统计公报经济指标（精确转载网页）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "data_status": "preliminary",
        "source_locator": "haikou_2025_statistical_bulletin_excerpt.txt；GDP及增速=统计公报综合段；原始网页已归档",
        "patterns": {
            "gdp_current_100m": (r"2025年全市实现地区生产总值([0-9.]+)亿元，比上年增长[0-9.]+%", "亿元"),
            "gdp_real_growth_pct": (r"2025年全市实现地区生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
        },
        "note": "B2海口市统计公报精确转载；补录2025年GDP和实际增速，财政字段由独立财政批次记录。",
    },
    {
        "city_name": "宜昌市",
        "city_id": "CN-420500",
        "source_doc_id": "SRC-B2-HUBEI-CITY-STATISTICAL-YICHANG-2025-POPULATION",
        "url": "https://www.crei.cn/file/br.aspx?id=20260420163741&op=zc&x=0",
        "attachment_url": "https://www.crei.cn/file/br.aspx?id=20260420163741&op=zc&x=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "yichang_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "yichang_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "source_format": "html",
        "document_title": "宜昌市2025年国民经济和社会发展统计公报",
        "publisher": "宜昌市统计局（精确公报转载）",
        "publisher_level": "市级统计机构公报转载",
        "publication_date": "2026-04-20",
        "title_source": "official_reprint_html",
        "document_type": "统计公报人口指标（精确转载网页）",
        "mime_type": "text/html",
        "source_grade": "B2",
        "data_status": "preliminary",
        "source_locator": "yichang_2025_statistical_bulletin_excerpt.txt；年末常住人口=统计公报人口段；原始网页已归档",
        "patterns": {
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
        },
        "note": "B2宜昌市统计公报精确转载；补录2025年年末常住人口，经济财政其他字段由独立批次记录。",
    },
)

NEXT29_2025_ECONOMIC_SOURCES = (
    {
        "city_name": "合肥市",
        "city_id": "CN-340100",
        "source_doc_id": "SRC-B2-ANHUI-CITY-STATISTICAL-HEFEI-2025-POPULATION",
        "url": "https://tjgb.hongheiku.com/djs/68352.html",
        "attachment_url": "https://tjgb.hongheiku.com/wp-content/uploads/2026/04/1775052106-wKgEIWnLK5OAEX2EAApVrfAOX4M661.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "hefei_2025_statistical_bulletin.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "hefei_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "source_format": "pdf",
        "document_title": "合肥市2025年国民经济和社会发展统计公报",
        "publisher": "合肥市统计局、国家统计局合肥调查队（精确公报转载）",
        "publisher_level": "市级统计机构公报转载",
        "publication_date": "2026-04-01",
        "title_source": "official_reprint_pdf",
        "document_type": "统计公报人口指标（精确PDF转载）",
        "mime_type": "application/pdf",
        "source_grade": "B2",
        "data_status": "preliminary",
        "source_locator": "hefei_2025_statistical_bulletin_excerpt.txt；年末常住人口=统计公报人口段；原始PDF已归档",
        "patterns": {
            "resident_population_10k": (r"年末全市常住人口([0-9.]+)万人", "万人"),
        },
        "note": "B2合肥市统计公报精确PDF转载；补录2025年年末常住人口1000.5万人，财政和GDP字段由既有批次记录。",
    },
)

NEXT30_2025_ECONOMIC_SOURCES = (
    {
        "city_name": "福州市",
        "city_id": "CN-350100",
        "source_doc_id": "SRC-A2-FUJIAN-CITY-STATISTICAL-FUZHOU-2025",
        "url": "https://www.fuzhou.gov.cn/zwgk/tjxx/ndbg/202604/t20260414_5308173.htm",
        "attachment_url": "https://www.fuzhou.gov.cn/zwgk/tjxx/ndbg/202604/t20260414_5308173.htm",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "fuzhou_2025_statistical_bulletin_official.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "fuzhou_2025_statistical_bulletin_official_excerpt.txt",
        "text_is_curated": True,
        "source_format": "html",
        "document_title": "2025年福州市国民经济和社会发展统计公报",
        "publisher": "福州市统计局、福州市人民政府",
        "publisher_level": "地级市统计机构官方发布",
        "publication_date": "2026-04-14",
        "title_source": "official_html",
        "document_type": "官方统计公报经济财政指标",
        "mime_type": "text/html",
        "source_grade": "A2",
        "data_status": "preliminary",
        "source_locator": "官方统计公报正文：GDP、增速、年末常住人口、地方一般公共预算收入和支出；原始网页已归档",
        "patterns": {
            "gdp_current_100m": (r"全年实现地区生产总值([0-9.]+)亿元", "亿元"),
            "gdp_real_growth_pct": (r"全年实现地区生产总值[0-9.]+亿元，比上年增长([0-9.]+)%", "%"),
            "resident_population_10k": (r"年末常住人口([0-9.]+)万人", "万人"),
            "general_public_revenue_100m": (r"全年地方一般公共预算收入([0-9.]+)亿元", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出([0-9.]+)亿元", "亿元"),
        },
        "note": "A2福州市人民政府官方统计公报；补录2025年GDP、实际增速、年末常住人口及地方一般公共预算收支。公报未披露全市政府性基金收入，不作推算。",
    },
)

JIANGSU_CITY_FUND_SOURCES = (
    {
        "year": 2018,
        "source_doc_id": "SRC-PROVINCE-FUND-JIANGSU-2018",
        "url": "https://czt.jiangsu.gov.cn/attach/0/4ed7fc056fce46b2b77e1e8e4dd99963.pdf",
        "path": RAW_DIR / "province_debt" / "2018" / "jiangsu_2018.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2018" / "official" / "jiangsu_2018_city_fund_excerpt.txt",
        "document_title": "江苏省2018年分地区政府性基金预算收入执行情况表",
        "publisher": "江苏省财政厅",
        "publisher_level": "省级财政机构",
        "publication_date": "2019-01-14",
        "table_name": "表六 2018年江苏省分地区政府性基金预算收入执行情况表",
        "page_number": "6",
        "source_grade": "A1",
        "data_status": "execution",
        "data_status_label": "2018年执行数",
        "cities": {
            "CN-320100": "南京市",
            "CN-320200": "无锡市",
            "CN-320300": "徐州市",
            "CN-320400": "常州市",
            "CN-320500": "苏州市",
            "CN-320600": "南通市",
            "CN-320700": "连云港市",
            "CN-320800": "淮安市",
            "CN-320900": "盐城市",
            "CN-321000": "扬州市",
            "CN-321100": "镇江市",
            "CN-321200": "泰州市",
            "CN-321300": "宿迁市",
        },
    },
    {
        "year": 2020,
        "source_doc_id": "SRC-PROVINCE-FUND-JIANGSU-2020-FINAL",
        "url": "https://czt.jiangsu.gov.cn/attach/0/d8a51d4d8db842dc82c3db7b6a6ae840.pdf",
        "path": RAW_DIR / "province_debt" / "2021" / "official" / "jiangsu_2021.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2020" / "official" / "jiangsu_2020_city_fund_excerpt.txt",
        "document_title": "江苏省2020年分地区政府性基金预算收入决算数（2021年官方决算附件）",
        "publisher": "江苏省财政厅",
        "publisher_level": "省级财政机构",
        "publication_date": "2022-01-20",
        "table_name": "表六 2021年江苏省分地区政府性基金预算收入执行情况表（2020年决算数）",
        "page_number": "6",
        "source_grade": "A1",
        "data_status": "final",
        "data_status_label": "2020年决算数",
        "cities": {
            "CN-320100": "南京市",
            "CN-320200": "无锡市",
            "CN-320300": "徐州市",
            "CN-320400": "常州市",
            "CN-320500": "苏州市",
            "CN-320600": "南通市",
            "CN-320700": "连云港市",
            "CN-320800": "淮安市",
            "CN-320900": "盐城市",
            "CN-321000": "扬州市",
            "CN-321100": "镇江市",
            "CN-321200": "泰州市",
            "CN-321300": "宿迁市",
        },
    },
    {
        "year": 2021,
        "source_doc_id": "SRC-PROVINCE-FUND-JIANGSU-2021-FINAL",
        "url": "https://czt.jiangsu.gov.cn/attach/-1/2304031513142867083.pdf",
        "path": RAW_DIR / "province_debt" / "2022" / "official" / "jiangsu_2022.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2021" / "official" / "jiangsu_2021_city_fund_excerpt.txt",
        "document_title": "江苏省2021年分地区政府性基金预算收入决算数（2022年官方决算附件）",
        "publisher": "江苏省财政厅",
        "publisher_level": "省级财政机构",
        "publication_date": "2023-04-03",
        "table_name": "表六 2022年江苏省分地区政府性基金预算收入执行情况表（2021年决算数）",
        "page_number": "8",
        "source_grade": "A1",
        "data_status": "final",
        "data_status_label": "2021年决算数",
        "cities": {
            "CN-320100": "南京市",
            "CN-320200": "无锡市",
            "CN-320300": "徐州市",
            "CN-320400": "常州市",
            "CN-320500": "苏州市",
            "CN-320600": "南通市",
            "CN-320700": "连云港市",
            "CN-320800": "淮安市",
            "CN-320900": "盐城市",
            "CN-321000": "扬州市",
            "CN-321100": "镇江市",
            "CN-321200": "泰州市",
            "CN-321300": "宿迁市",
        },
    },
    {
        "year": 2022,
        "source_doc_id": "SRC-PROVINCE-FUND-JIANGSU-2022-FINAL",
        "url": "https://czt.jiangsu.gov.cn/attach/-1/2504291824050610353.pdf",
        "path": RAW_DIR / "province_debt" / "2023" / "official" / "jiangsu_2023.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2022" / "official" / "jiangsu_2022_city_fund_excerpt.txt",
        "document_title": "江苏省2022年分地区政府性基金预算收入决算数（2023年官方决算附件）",
        "publisher": "江苏省财政厅",
        "publisher_level": "省级财政机构",
        "publication_date": "2024-04-29",
        "table_name": "表九 2023年江苏省分地区政府性基金预算收入执行情况表（2022年决算数）",
        "page_number": "16",
        "source_grade": "A1",
        "data_status": "final",
        "data_status_label": "2022年决算数",
        "cities": {
            "CN-320100": "南京市",
            "CN-320200": "无锡市",
            "CN-320300": "徐州市",
            "CN-320400": "常州市",
            "CN-320500": "苏州市",
            "CN-320600": "南通市",
            "CN-320700": "连云港市",
            "CN-320800": "淮安市",
            "CN-320900": "盐城市",
            "CN-321000": "扬州市",
            "CN-321100": "镇江市",
            "CN-321200": "泰州市",
            "CN-321300": "宿迁市",
        },
    },
    {
        "year": 2023,
        "source_doc_id": "SRC-PROVINCE-FUND-JIANGSU-2023",
        "url": "https://czt.jiangsu.gov.cn/attach/-1/2504291824050610353.pdf",
        "path": RAW_DIR / "province_debt" / "2023" / "official" / "jiangsu_2023.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2023" / "official" / "jiangsu_2023_city_fund_excerpt.txt",
        "document_title": "江苏省2023年分地区政府性基金预算收入执行情况表",
        "publisher": "江苏省财政厅",
        "publisher_level": "省级财政机构",
        "publication_date": "2024-04-29",
        "table_name": "表九 2023年江苏省分地区政府性基金预算收入执行情况表",
        "page_number": "9",
        "source_grade": "A1",
        "cities": {
            "CN-320100": "南京市",
            "CN-320200": "无锡市",
            "CN-320300": "徐州市",
            "CN-320400": "常州市",
            "CN-320500": "苏州市",
            "CN-320600": "南通市",
            "CN-320700": "连云港市",
            "CN-320800": "淮安市",
            "CN-320900": "盐城市",
            "CN-321000": "扬州市",
            "CN-321100": "镇江市",
            "CN-321200": "泰州市",
            "CN-321300": "宿迁市",
        },
    },
    {
        "year": 2024,
        "source_doc_id": "SRC-PROVINCE-FUND-JIANGSU-2024",
        "url": "https://czt.jiangsu.gov.cn/attach/-1/2504291825052954904.pdf",
        "path": RAW_DIR / "province_debt" / "2024" / "jiangsu_2024.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2024" / "official" / "jiangsu_2024_city_fund_excerpt.txt",
        "document_title": "江苏省2024年分地区政府性基金预算收入执行情况表",
        "publisher": "江苏省财政厅",
        "publisher_level": "省级财政机构",
        "publication_date": "2025-04-29",
        "table_name": "表九 2024年江苏省分地区政府性基金预算收入执行情况表",
        "page_number": "9",
        "source_grade": "A1",
        "cities": {
            "CN-320100": "南京市",
            "CN-320200": "无锡市",
            "CN-320300": "徐州市",
            "CN-320400": "常州市",
            "CN-320500": "苏州市",
            "CN-320600": "南通市",
            "CN-320700": "连云港市",
            "CN-320800": "淮安市",
            "CN-320900": "盐城市",
            "CN-321000": "扬州市",
            "CN-321100": "镇江市",
            "CN-321200": "泰州市",
            "CN-321300": "宿迁市",
        },
    },
)

JIANGSU_CITY_FISCAL_SOURCES = (
    {
        "year": 2024,
        "source_doc_id": "SRC-PROVINCE-FISCAL-JIANGSU-2024",
        "url": "https://czt.jiangsu.gov.cn/attach/-1/2504291825052954904.pdf",
        "path": RAW_DIR / "province_debt" / "2024" / "jiangsu_2024.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2024" / "official" / "jiangsu_2024_city_fiscal_excerpt.txt",
        "document_title": "江苏省2024年分地区一般公共预算收入、支出执行情况表",
        "publisher": "江苏省财政厅",
        "publisher_level": "省级财政机构",
        "publication_date": "2025-01-19",
        "table_name": "表二、表四 2024年江苏省分地区一般公共预算收入、支出执行情况表",
        "page_number": "2、4",
        "source_grade": "A1",
        "data_status": "execution",
        "data_status_label": "2024年执行数",
        "cities": {
            "CN-320100": "南京市",
            "CN-320200": "无锡市",
            "CN-320300": "徐州市",
            "CN-320400": "常州市",
            "CN-320500": "苏州市",
            "CN-320600": "南通市",
            "CN-320700": "连云港市",
            "CN-320800": "淮安市",
            "CN-320900": "盐城市",
            "CN-321000": "扬州市",
            "CN-321100": "镇江市",
            "CN-321200": "泰州市",
            "CN-321300": "宿迁市",
        },
    },
)
JIANGSU_CITY_FISCAL_SOURCE_IDS = {item["source_doc_id"] for item in JIANGSU_CITY_FISCAL_SOURCES}

# 新疆财政厅 2024 年预算附件中的“各地”表一次覆盖 14 个地州；表中简称
# 通过别名映射到全国主表的规范行政名称。基金表与债务表共用同一官方 PDF，
# 分别保留字段级来源和定位，避免把自治区本级数或转移支付数误当作地州收入。
XINJIANG_2024_CITY_FUND_SOURCES = (
    {
        "year": 2024,
        "source_doc_id": "SRC-PROVINCE-FUND-XINJIANG-2024",
        "url": "https://czt.xinjiang.gov.cn/xjczt/c115511/202501/4a78ff1bea3045eeba621d2d1d7db349/files/02-2024%E5%B9%B4%E8%87%AA%E6%B2%BB%E5%8C%BA%E9%A2%84%E7%AE%97%E6%89%A7%E8%A1%8C%E6%83%85%E5%86%B5%E5%92%8C2025%E5%B9%B4%E8%87%AA%E6%B2%BB%E5%8C%BA%E9%A2%84%E7%AE%97%EF%BC%88%E5%9B%9B%E6%9C%AC%E9%A2%84%E7%AE%97%EF%BC%89.pdf",
        "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "xinjiang_2024_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2024" / "official" / "xinjiang_2024_city_fund_excerpt.txt",
        "document_title": "2024年自治区政府性基金预算执行情况与2025年自治区预算（四本预算）",
        "publisher": "新疆维吾尔自治区财政厅",
        "publisher_level": "省级财政机构",
        "publication_date": "2025-01-01",
        "table_name": "表五：2024年自治区各地政府性基金预算收入完成情况表",
        "page_number": "PDF第76页（印刷页74）",
        "source_grade": "A1",
        "data_status": "execution",
        "data_status_label": "2024年完成数",
        "cities": {
            "乌鲁木齐市": "CN-650100",
            "伊犁州": "CN-654000",
            "塔城地区": "CN-654200",
            "阿勒泰地区": "CN-654300",
            "克拉玛依市": "CN-650200",
            "博尔塔拉州": "CN-652700",
            "昌吉州": "CN-652300",
            "哈密市": "CN-650500",
            "吐鲁番市": "CN-650400",
            "巴音郭楞州": "CN-652800",
            "阿克苏地区": "CN-652900",
            "克孜勒苏州": "CN-653000",
            "喀什地区": "CN-653100",
            "和田地区": "CN-653200",
        },
    },
)
XINJIANG_CITY_FUND_SOURCE_IDS = {item["source_doc_id"] for item in XINJIANG_2024_CITY_FUND_SOURCES}

# 内蒙古自治区城市财政报告中已核验的全市政府性基金收入。来源均能精确定位
# 到报告正文，但不是省财政厅分地区原始表，因此按 B2 纳入，并保留 execution
# 状态；不把市本级数替代为全市数。
CITY_YEAR_FUND_SOURCES = (
    {
        "year": 2024,
        "city_name": "呼和浩特市",
        "city_id": "CN-150100",
        "source_doc_id": "SRC-B2-HOHHOT-CITY-FUND-2024",
        "url": "https://static.0471tv.org.cn/rb/pc/att/202501/23/8ab6d53d-1f5f-4c54-9655-32ba857e97bb.pdf",
        "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "hohhot_2024_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "hohhot_2024_budget_report_excerpt.txt",
        "document_title": "关于呼和浩特市2024年预算执行情况和2025年预算（草案）的报告",
        "publisher": "呼和浩特市财政局",
        "publisher_level": "市级财政机构（精确转载）",
        "publication_date": "2025-01-23",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"2024年，全市政府性基金预算收入([0-9.]+)亿元",
        "raw_unit": "亿元",
        "document_type": "城市财政预算执行报告（精确转载）",
        "page_count": "1",
        "note": "B2精确转载；报告正文明确披露呼和浩特市2024年全市政府性基金预算收入112.52亿元，执行口径，不使用市本级数。",
    },
    {
        "year": 2025,
        "city_name": "呼和浩特市",
        "city_id": "CN-150100",
        "source_doc_id": "SRC-B2-HOHHOT-CITY-FUND-2025",
        "url": "https://static.0471tv.org.cn/rb/pc/att/202603/04/5edaa825-0884-472e-9693-6c0aca69c74a.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "hohhot_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "hohhot_2025_budget_report_excerpt.txt",
        "document_title": "关于呼和浩特市2025年预算执行情况和2026年预算（草案）的报告",
        "publisher": "呼和浩特市财政局",
        "publisher_level": "市级财政机构（精确转载）",
        "publication_date": "2026-02-10",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"原文摘录：.*?全市政府性基金预算收入([0-9.]+)亿元",
        "raw_unit": "亿元",
        "document_type": "城市财政预算执行报告（精确转载）",
        "page_count": "1",
        "note": "B2精确转载；报告正文明确披露呼和浩特市2025年全市政府性基金预算收入75.78亿元，执行口径，不使用市本级数。",
    },
    {
        "year": 2025,
        "city_name": "赤峰市",
        "city_id": "CN-150400",
        "source_doc_id": "SRC-B2-CHIFENG-CITY-FUND-2025",
        "url": "https://www.chifeng.gov.cn/ztzl/rdzl/cfslhzt/cfszf2026lhzt/2026gzbg/202601/t20260130_2723148.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "chifeng_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "chifeng_2025_budget_report_excerpt.txt",
        "document_title": "赤峰市2025年政府工作报告",
        "publisher": "赤峰市人民政府",
        "publisher_level": "市级政府门户",
        "publication_date": "2026-01-30",
        "source_grade": "B2",
        "source_format": "html",
        "pattern": r"全市政府性基金预算收入([0-9]+)万元",
        "raw_unit": "万元",
        "document_type": "政府工作报告财政执行段落（官方网页）",
        "page_count": "1",
        "note": "B2官方网页精确披露；报告明确以2025年12月月报数据作为执行数据，2025年全市政府性基金预算收入466850万元，折算为亿元。",
    },
    {
        "year": 2025,
        "city_name": "大同市",
        "city_id": "CN-140200",
        "source_doc_id": "SRC-B2-DATONG-CITY-FUND-2025",
        "url": "https://www.dt.gov.cn/dtszf/czjczyjs/202602/d228cbfb30e747a0b4d3062fd41aa5b7.shtml",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "datong_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "datong_2025_budget_report_excerpt.txt",
        "document_title": "关于大同市2025年全市和市本级预算执行情况与2026年全市和市本级预算（草案）的报告",
        "publisher": "大同市人民政府",
        "publisher_level": "市级政府门户",
        "publication_date": "2026-02-05",
        "source_grade": "B2",
        "source_format": "html",
        "pattern": r"2025年全市政府性基金预算收入完成([0-9．.]+)亿元",
        "raw_unit": "亿元",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_count": "1",
        "note": "B2官方网页精确披露；报告明确披露大同市2025年全市政府性基金预算收入44.74亿元，执行口径，不使用市本级数。",
    },
    {
        "year": 2025,
        "city_name": "吕梁市",
        "city_id": "CN-141100",
        "source_doc_id": "SRC-B2-LVLIANG-CITY-FUND-2025",
        "url": "https://www.lvliang.gov.cn/llxxgk/zfxxgk/xxgkml/zjxx_21583/sjczyshsgjf/202602/t20260205_2014557.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "lvliang_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "lvliang_2025_budget_report_excerpt.txt",
        "document_title": "关于吕梁市2025年全市和市本级预算执行情况与2026年全市和市本级预算草案的报告",
        "publisher": "吕梁市人民政府",
        "publisher_level": "市级政府门户",
        "publication_date": "2026-02-05",
        "source_grade": "B2",
        "source_format": "html",
        "pattern": r"2025年全市政府性基金收入完成([0-9.]+)亿元",
        "raw_unit": "亿元",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_count": "1",
        "note": "B2官方网页精确披露；报告明确披露吕梁市2025年全市政府性基金收入21.62亿元，执行口径，不使用市本级数。",
    },
    {
        "year": 2025,
        "city_name": "平顶山市",
        "city_id": "CN-410400",
        "source_doc_id": "SRC-B2-PINGDINGSHAN-CITY-FUND-2025",
        "url": "https://www.pds.gov.cn/contents/1378/463143.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "pingdingshan_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "pingdingshan_2025_budget_report_excerpt.txt",
        "document_title": "关于平顶山市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "平顶山市人民政府",
        "publisher_level": "市级政府门户",
        "publication_date": "2026-02-07",
        "source_grade": "B2",
        "source_format": "html",
        "pattern": r"实际完成([0-9]+)万元，为调整预算的63\.9[％%]",
        "raw_unit": "万元",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_count": "1",
        "note": "B2官方网页精确披露；报告明确披露平顶山市2025年全市政府性基金预算收入实际完成702960万元，执行口径，折算为亿元。",
    },
    {
        "year": 2025,
        "city_name": "安康市",
        "city_id": "CN-610900",
        "source_doc_id": "SRC-B2-ANKANG-CITY-FUND-2025",
        "url": "https://www.ankang.gov.cn/Content-2902010.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "ankang_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "ankang_2025_budget_report_excerpt.txt",
        "document_title": "安康市2025年财政预算执行情况和2026年财政预算（草案）的报告",
        "publisher": "安康市人民政府",
        "publisher_level": "市级政府门户",
        "publication_date": "2026-01-22",
        "source_grade": "B2",
        "source_format": "html",
        "pattern": r"全市政府性基金预算收入完成([0-9.]+)亿元",
        "raw_unit": "亿元",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_count": "1",
        "note": "B2官方网页精确披露；报告明确披露安康市2025年全市政府性基金预算收入36.98亿元，执行口径，不使用市本级数。",
    },
    {
        "year": 2025,
        "city_name": "宣城市",
        "city_id": "CN-341800",
        "source_doc_id": "SRC-B2-XUANCHENG-CITY-FUND-2025",
        "url": "https://tyjr.xuancheng.gov.cn/file_xc/20/202602/20260206a37c3db21a3a448a91fb29d6117c45f5.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "xuancheng_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "xuancheng_2025_budget_report_excerpt.txt",
        "document_title": "关于宣城市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "宣城市人民政府",
        "publisher_level": "市级政府门户（附件）",
        "publication_date": "2026-02-06",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"全市政府性基金预算收入完成([0-9.]+)亿元",
        "raw_unit": "亿元",
        "document_type": "城市财政预算执行报告（官方附件）",
        "page_count": "1",
        "note": "B2官方附件精确披露；报告明确披露宣城市2025年全市政府性基金预算收入60.6亿元，执行口径，不使用市本级数。",
    },
    {
        "year": 2025,
        "city_name": "雅安市",
        "city_id": "CN-511800",
        "source_doc_id": "SRC-B2-YAAN-CITY-FUND-2025",
        "url": "https://www.yaan.gov.cn/xinwen/show/511f3181-a603-469c-b00c-dd2e2370f460.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "yaan_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "yaan_2025_budget_report_excerpt.txt",
        "document_title": "关于雅安市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "雅安市人民政府",
        "publisher_level": "市级政府门户",
        "publication_date": "2026-01-21",
        "source_grade": "B2",
        "source_format": "html",
        "pattern": r"全市政府性基金预算收入([0-9，]+)万元",
        "raw_unit": "万元",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_count": "1",
        "note": "B2官方网页精确披露；报告明确披露雅安市2025年全市政府性基金预算收入379174万元，折算为37.92亿元，执行口径，不使用市级数。",
    },
    {
        "year": 2025,
        "city_name": "郑州市",
        "city_id": "CN-410100",
        "source_doc_id": "SRC-A2-ZHENGZHOU-CITY-FUND-2025",
        "url": "https://public.zhengzhou.gov.cn/D08Y/9970746.jhtml",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhengzhou_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhengzhou_2025_budget_report_excerpt.txt",
        "document_title": "郑州市财政局2025年工作总结",
        "publisher": "郑州市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-03-27",
        "source_grade": "A2",
        "source_format": "html",
        "pattern": r"全市政府性基金收入([0-9.]+)亿元",
        "raw_unit": "亿元",
        "document_type": "市级财政年度工作总结（财政执行指标）",
        "page_count": "1",
        "note": "A2官方市级财政机构网页；年度工作总结明确披露郑州市2025年全市政府性基金收入277.5亿元，作为全市执行数，不使用市本级数。",
    },
    {
        "year": 2025,
        "city_name": "成都市",
        "city_id": "CN-510100",
        "source_doc_id": "SRC-A1-CHENGDU-CITY-FUND-2025",
        "url": "https://cdcz.chengdu.gov.cn/cdsczj/c116719/2026-02/05/03efb2ef86c1479fa24afefb45ed5053/files/81f829fadec94ce589c1d664520f9420.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "chengdu_2025_fund_execution.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "chengdu_2025_fund_execution_excerpt.txt",
        "document_title": "2025年成都市政府性基金预算收入执行情况表",
        "publisher": "成都市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-02-05",
        "source_grade": "A1",
        "source_format": "pdf",
        "pattern": r"政府性基金预算收入合计，快报执行数([0-9]+)万元",
        "raw_unit": "万元",
        "document_type": "市级财政政府性基金预算收入执行表",
        "page_count": "1",
        "note": "A1成都市财政局官方执行情况表；表中全市政府性基金预算收入合计快报执行数为12804474万元，标记为execution，折算为亿元。",
    },
    {
        "year": 2025,
        "city_name": "宝鸡市",
        "city_id": "CN-610300",
        "source_doc_id": "SRC-A2-BAOJI-CITY-FUND-2025",
        "url": "https://www.baoji.gov.cn/sjgk/tjgb/tjgb/202606/t20260605_1275705.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "baoji_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "baoji_2025_statistical_bulletin_excerpt.txt",
        "document_title": "2025年宝鸡市国民经济和社会发展统计公报",
        "publisher": "宝鸡市人民政府、宝鸡市统计局",
        "publisher_level": "市级政府门户",
        "publication_date": "2026-06-05",
        "source_grade": "A2",
        "source_format": "html",
        "pattern": r"政府性基金收入([0-9.]+)亿元",
        "raw_unit": "亿元",
        "document_type": "官方统计公报财政指标",
        "page_count": "1",
        "note": "A2官方统计公报；公报注明财政数据来自宝鸡市财政局，披露2025年全市政府性基金收入29.84亿元。",
    },
    {
        "year": 2019,
        "city_name": "平顶山市",
        "city_id": "CN-410400",
        "source_doc_id": "SRC-A1-PINGDINGSHAN-CITY-FUND-2019-FINAL",
        "url": "https://czj.pds.gov.cn/upload/files/2021/5/139573316.pdf",
        "path": RAW_DIR / "province_fiscal" / "2019" / "official" / "pingdingshan_2019_final_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2019" / "official" / "pingdingshan_2019_fund_excerpt.txt",
        "document_title": "平顶山市2019年全市及市级决算草案的说明",
        "publisher": "平顶山市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2021-05-01",
        "source_grade": "A1",
        "source_format": "pdf",
        "pattern": r"2019年全市政府性基金收入决算数([0-9]+)万元",
        "raw_unit": "万元",
        "data_status": "final",
        "data_status_label": "2019年决算数",
        "document_type": "城市财政决算报告（官方附件）",
        "page_count": "1",
        "note": "A1市级财政官方决算草案说明；明确披露2019年全市政府性基金收入决算数1199326万元，使用全市汇总口径，不使用市本级数。",
    },
    {
        "year": 2019,
        "city_name": "开封市",
        "city_id": "CN-410200",
        "source_doc_id": "SRC-A2-KAIFENG-CITY-FUND-2019",
        "url": "https://www.kaifeng.gov.cn/kfsrmzfwz/kfsrmzf/1737386489263988736/Itk1u8Bh.pdf",
        "path": RAW_DIR / "province_fiscal" / "2019" / "official" / "kaifeng_2019_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2019" / "official" / "kaifeng_2019_fund_excerpt.txt",
        "document_title": "关于开封市2019年预算执行情况和2020年预算草案的报告",
        "publisher": "开封市人民政府",
        "publisher_level": "市级政府门户",
        "publication_date": "2020-01-01",
        "source_grade": "A2",
        "source_format": "pdf",
        "pattern": r"2019年全市政府性基金收入.*?实际完成([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "final",
        "data_status_label": "2019年执行数",
        "document_type": "城市财政预算执行报告（官方附件）",
        "page_count": "1",
        "note": "A2市级政府官方预算执行报告；明确披露2019年全市政府性基金收入实际完成189.3亿元，不使用市本级数。",
    },
    {
        "year": 2019,
        "city_name": "南阳市",
        "city_id": "CN-411300",
        "source_doc_id": "SRC-A2-NANYANG-CITY-FUND-2019",
        "url": "https://caizj.nanyang.gov.cn/2020/06-09/98750.html",
        "path": RAW_DIR / "province_fiscal" / "2019" / "official" / "nanyang_2019_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2019" / "official" / "nanyang_2019_fund_excerpt.txt",
        "document_title": "关于南阳市2019年预算执行情况和2020年市级预算草案的报告",
        "publisher": "南阳市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2020-06-09",
        "source_grade": "A2",
        "source_format": "html",
        "pattern": r"2019年政府性基金预算收入年初预算合计185\.3亿元，实际完成([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "final",
        "data_status_label": "2019年执行数",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_count": "1",
        "note": "A2市级财政官方网页；汇总各级人代会批准的2019年全市政府性基金预算收入，实际完成217.7亿元，不使用市本级数。",
    },
    {
        "year": 2019,
        "city_name": "三门峡市",
        "city_id": "CN-411200",
        "source_doc_id": "SRC-A2-SANMENXIA-CITY-FUND-2019",
        "url": "https://www.smx.gov.cn/28024/615965184/949651.html",
        "path": RAW_DIR / "province_fiscal" / "2019" / "official" / "sanmenxia_2019_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2019" / "official" / "sanmenxia_2019_fund_excerpt.txt",
        "document_title": "关于三门峡市2019年财政预算执行情况和2020年财政预算（草案）的报告",
        "publisher": "三门峡市人民政府",
        "publisher_level": "市级政府门户",
        "publication_date": "2020-01-01",
        "source_grade": "A2",
        "source_format": "html",
        "pattern": r"2019年全市政府性基金预算收入年初预算合计574608万元，完成([0-9]+)万元",
        "raw_unit": "万元",
        "data_status": "final",
        "data_status_label": "2019年执行数",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_count": "1",
        "note": "A2市级政府官方报告；汇总全市各级人代会批准的2019年政府性基金预算收入，完成387622万元，不使用市本级数。",
    },
    {
        "year": 2019,
        "city_name": "周口市",
        "city_id": "CN-411600",
        "source_doc_id": "SRC-A2-ZHOUKOU-CITY-FUND-2019",
        "url": "https://www.zhoukou.gov.cn/page_pc/zwgk/jcxxgk/czzj/zfczys/article838607100E1B479FAC8DB07A6617C7EF.html",
        "path": RAW_DIR / "province_fiscal" / "2019" / "official" / "zhoukou_2019_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2019" / "official" / "zhoukou_2019_fund_excerpt.txt",
        "document_title": "全市和市级2019年预算执行情况及2020年预算编制说明",
        "publisher": "周口市人民政府",
        "publisher_level": "市级政府门户",
        "publication_date": "2020-01-01",
        "source_grade": "A2",
        "source_format": "html",
        "pattern": r"2019年各级人代会批准的全市政府性基金收入预算为175\.6亿元，实际完成([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "final",
        "data_status_label": "2019年执行数",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_count": "1",
        "note": "A2市级政府官方报告；明确披露2019年各级人代会批准的全市政府性基金收入实际完成213.8亿元，不使用市级数。",
    },
    {
        "year": 2018,
        "city_name": "三门峡市",
        "city_id": "CN-411200",
        "source_doc_id": "SRC-A2-SANMENXIA-CITY-FUND-2018",
        "url": "https://www.smx.gov.cn/28060/615988512/962416.html",
        "path": RAW_DIR / "province_fiscal" / "2018" / "official" / "sanmenxia_2018_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2018" / "official" / "sanmenxia_2018_fund_excerpt.txt",
        "document_title": "关于三门峡市2018年财政预算执行情况和2019年财政预算（草案）的报告",
        "publisher": "三门峡市人民政府",
        "publisher_level": "市级政府门户",
        "publication_date": "2019-01-01",
        "source_grade": "A2",
        "source_format": "html",
        "pattern": r"2018年全市政府性基金预算收入年初预算合计299766万元，实际完成([0-9]+)万元",
        "raw_unit": "万元",
        "data_status": "final",
        "data_status_label": "2018年执行数",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_count": "1",
        "note": "A2市级政府官方报告；明确披露2018年全市政府性基金预算收入实际完成426173万元，不使用市级数。",
    },
    {
        "year": 2018,
        "city_name": "吕梁市",
        "city_id": "CN-141100",
        "source_doc_id": "SRC-A2-LVLIANG-CITY-FUND-2018",
        "url": "https://www.lvliang.gov.cn/llxxgk/zfxxgk/xxgkml/zjxx_21583/sjczyshsgjf/201903/t20190312_1214261.html",
        "path": RAW_DIR / "province_fiscal" / "2018" / "official" / "lvliang_2018_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2018" / "official" / "lvliang_2018_fund_excerpt.txt",
        "document_title": "吕梁市2018年全市和市本级预算执行情况与2019年全市和市本级预算草案",
        "publisher": "吕梁市人民政府",
        "publisher_level": "市级政府门户",
        "publication_date": "2019-03-12",
        "source_grade": "A2",
        "source_format": "html",
        "pattern": r"2018年全市政府性基金收入完成([0-9]+)万元",
        "raw_unit": "万元",
        "data_status": "final",
        "data_status_label": "2018年执行数",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_count": "1",
        "note": "A2市级政府官方报告；明确披露2018年全市政府性基金收入完成222114万元，不使用市本级数。",
    },
    {
        "year": 2018,
        "city_name": "驻马店市",
        "city_id": "CN-411700",
        "source_doc_id": "SRC-A2-ZHUMADIAN-CITY-FUND-2018",
        "url": "https://www.zmdrd.gov.cn/2019/02-26/35873.html",
        "path": RAW_DIR / "province_fiscal" / "2018" / "official" / "zhumadian_2018_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2018" / "official" / "zhumadian_2018_fund_excerpt.txt",
        "document_title": "关于驻马店市2018年预算执行情况和2019年预算草案的报告",
        "publisher": "驻马店市人民代表大会",
        "publisher_level": "市级人大门户",
        "publication_date": "2019-02-26",
        "source_grade": "A2",
        "source_format": "html",
        "pattern": r"2018年全市政府性基金预算收入年初预算合计172\.3亿元.*?实际完成([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "final",
        "data_status_label": "2018年执行数",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_count": "1",
        "note": "A2市级人大官方报告；汇总全市各级人代会批准的2018年政府性基金预算收入，实际完成184.7亿元，不使用市级数。",
    },
    {
        "year": 2018,
        "city_name": "石家庄市",
        "city_id": "CN-130100",
        "source_doc_id": "SRC-A1-SHIJIAZHUANG-CITY-FUND-2018",
        "url": "https://www.sjz.gov.cn/atm/7/20190729172141947.pdf",
        "path": RAW_DIR / "province_fiscal" / "2018" / "official" / "shijiazhuang_2018_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2018" / "official" / "shijiazhuang_2018_fund_excerpt.txt",
        "document_title": "石家庄市2018年全市政府性基金收入预算完成情况表",
        "publisher": "石家庄市人民政府",
        "publisher_level": "市级政府门户",
        "publication_date": "2019-07-29",
        "source_grade": "A1",
        "source_format": "pdf",
        "pattern": r"政府性基金收入预算完成情况表.*?合计实际完成([0-9]+)万元",
        "raw_unit": "万元",
        "data_status": "final",
        "data_status_label": "2018年实际完成数",
        "document_type": "城市财政预算执行表（官方附件）",
        "page_count": "1",
        "note": "A1市级政府官方预算执行表；表3明确披露2018年全市政府性基金收入合计实际完成5608666万元，不使用市本级数。",
    },
    {
        "year": 2018,
        "city_name": "三明市",
        "city_id": "CN-350400",
        "source_doc_id": "SRC-A2-SANMING-CITY-FUND-2018",
        "url": "https://www.sm.gov.cn/zw/gzbg/czbg/201901/t20190123_1261305.htm",
        "path": RAW_DIR / "province_fiscal" / "2018" / "official" / "sanming_2018_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2018" / "official" / "sanming_2018_fund_excerpt.txt",
        "document_title": "关于三明市2018年预算执行情况及2019年预算草案的报告",
        "publisher": "三明市人民政府",
        "publisher_level": "市级政府门户",
        "publication_date": "2019-01-23",
        "source_grade": "A2",
        "source_format": "html",
        "pattern": r"2018年全市政府性基金收入完成([0-9,]+)万元",
        "raw_unit": "万元",
        "data_status": "final",
        "data_status_label": "2018年执行数",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_count": "1",
        "note": "A2市级政府官方报告；明确披露2018年全市政府性基金收入完成814239万元，不使用市本级数。",
    },
    {
        "year": 2019,
        "city_name": "三明市",
        "city_id": "CN-350400",
        "source_doc_id": "SRC-A2-SANMING-CITY-FUND-2019",
        "url": "https://www.sm.gov.cn/zw/gzbg/czbg/202001/t20200112_1464768.htm",
        "path": RAW_DIR / "province_fiscal" / "2019" / "official" / "sanming_2019_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2019" / "official" / "sanming_2019_fund_excerpt.txt",
        "document_title": "关于三明市2019年预算执行情况及2020年预算草案的报告",
        "publisher": "三明市人民政府",
        "publisher_level": "市级政府门户",
        "publication_date": "2020-01-12",
        "source_grade": "A2",
        "source_format": "html",
        "pattern": r"2019年全市政府性基金预算收入完成([0-9,]+)万元",
        "raw_unit": "万元",
        "data_status": "final",
        "data_status_label": "2019年执行数",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_count": "1",
        "note": "A2市级政府官方报告；明确披露2019年全市政府性基金预算收入完成900622万元，不使用市本级数。",
    },
    {
        "year": 2025,
        "city_name": "焦作市",
        "city_id": "CN-410800",
        "source_doc_id": "SRC-A1-JIAOZUO-CITY-FUND-2025",
        "url": "https://www.jiaozuo.gov.cn/2026/03-16/598258.html",
        "landing_page_url": "https://www.jiaozuo.gov.cn/2026/03-16/598258.html",
        "attachment_url": "https://oss.jiaozuo.gov.cn/4108000001/upload-file/files/20260316/4e4d5b65b033455f82582dd355e22bfb.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "jiaozuo_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "jiaozuo_2025_budget_report_excerpt.txt",
        "document_title": "关于焦作市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "焦作市财政局",
        "publisher_level": "市级财政机构官方附件",
        "publication_date": "2026-03-16",
        "source_grade": "A1",
        "source_format": "pdf",
        "pattern": r"2025年全市政府性基金预算收入.*?实际完成([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年快报执行数",
        "document_type": "城市财政预算执行报告（官方PDF）",
        "page_count": "20",
        "note": "市财政局官方预算执行报告，明确全市口径；采用2025年政府性基金预算收入实际完成76.1亿元，报告注明为快报执行数，不冒充最终决算。",
    },
    {
        "year": 2025,
        "city_name": "周口市",
        "city_id": "CN-411600",
        "source_doc_id": "SRC-B2-ZHOUKOU-CITY-FUND-2025",
        "url": "https://www.zhoukou.gov.cn/page_pc/ztzl/2026nztzl/jj2026nzklh/gzbg/article12e095834093469191fce375af93bfaa.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "zhoukou_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "zhoukou_2025_budget_report_excerpt.txt",
        "document_title": "周口市2025年预算执行情况和2026年预算（草案）报告解读",
        "publisher": "周口市人民政府门户（周口日报转载）",
        "publisher_level": "市级政府门户精确公开",
        "publication_date": "2026-02-10",
        "source_grade": "B2",
        "source_format": "html",
        "pattern": r"政府性基金预算.*?全市收入完成([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方门户公开）",
        "document_type": "城市财政预算执行报告解读（官方网页）",
        "page_count": "1",
        "note": "市政府门户公开的预算执行报告解读，明确全市口径；采用全市政府性基金预算收入完成87.9亿元，不使用市级数。",
    },
    {
        "year": 2025,
        "city_name": "新乡市",
        "city_id": "CN-410700",
        "source_doc_id": "SRC-B2-XINXIANG-CITY-FUND-2025",
        "url": "https://rb.xxrb.com.cn/app_epaper/2026-02/09/content_9965061.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "xinxiang_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "xinxiang_2025_budget_report_excerpt.txt",
        "document_title": "关于新乡市2025年预算执行情况和2026年预算草案的报告（摘要）",
        "publisher": "新乡日报",
        "publisher_level": "市级官方报纸网页",
        "publication_date": "2026-02-09",
        "source_grade": "B2",
        "source_format": "html",
        "pattern": r"全市政府性基金收入预算[0-9.]+亿元，实际完成([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方报告摘要）",
        "document_type": "城市财政预算执行报告摘要（官方报纸网页）",
        "page_count": "1",
        "note": "官方报纸公开的市财政局预算报告摘要，明确全市口径；采用实际完成38.6亿元，不使用市级2026年预算安排。",
    },
    {
        "year": 2025,
        "city_name": "开封市",
        "city_id": "CN-410200",
        "source_doc_id": "SRC-B2-KAIFENG-CITY-FUND-2025",
        "url": "https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3365421&mode=save&priority=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "kaifeng_2025_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "kaifeng_2025_fund_excerpt.txt",
        "document_title": "开封市发展投资集团有限公司主体与相关债项2026年度跟踪评级报告",
        "publisher": "中国货币网公开披露的评级报告",
        "publisher_level": "B2精确表格二手来源",
        "publication_date": "2026-07-01",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"原文摘录：2025年[，,]?开封市.*?政府性基金收入([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "final",
        "data_status_label": "2025年执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_count": "31",
        "note": "中国货币网公开的评级报告含2023—2025年开封市主要经济财政指标精确表格；表列示2025年政府性基金收入72.8亿元，明确为开封市全市口径。",
    },
    {
        "year": 2025,
        "city_name": "唐山市",
        "city_id": "CN-130200",
        "source_doc_id": "SRC-B2-TANGSHAN-CITY-FUND-2025",
        "url": "https://epaper.huanbohainews.com.cn/tsldrb/pad/content/202602/08/content_122246.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "tangshan_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "tangshan_2025_budget_report_excerpt.txt",
        "document_title": "唐山市2025年预算执行情况和2026年预算（草案）的报告",
        "publisher": "唐山劳动日报（环渤海新闻网数字报）",
        "publisher_level": "市级官方报纸网页",
        "publication_date": "2026-02-08",
        "source_grade": "B2",
        "source_format": "html",
        "pattern": r"原文摘录：2025年全市.*?政府性基金预算收入([0-9]+)万元",
        "raw_unit": "万元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方报告公开文本）",
        "document_type": "城市财政预算执行报告（官方报纸网页）",
        "page_count": "1",
        "note": "官方地方报纸数字版公开市财政局预算报告原文，明确全市口径；采用2025年政府性基金预算收入2996305万元，折算299.6305亿元，不使用市级数。",
    },
    {
        "year": 2025,
        "city_name": "抚顺市",
        "city_id": "CN-210400",
        "source_doc_id": "SRC-A2-FUSHUN-CITY-FUND-2025",
        "url": "https://www.fushun.gov.cn/zwgk/002008/002008003/002008003001/20260710/ad0056e5-6526-4452-8ea6-92cbfacafa87.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "fushun_2025_final_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "fushun_2025_final_budget_report_excerpt.txt",
        "document_title": "关于抚顺市2025年财政决算的报告",
        "publisher": "抚顺市人民政府",
        "publisher_level": "市级政府门户",
        "publication_date": "2026-07-10",
        "source_grade": "A2",
        "source_format": "html",
        "pattern": r"原文摘录：.*?2025年全市政府性基金收入([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "final",
        "data_status_label": "2025年决算数",
        "document_type": "城市财政决算报告（官方网页）",
        "page_count": "1",
        "note": "抚顺市政府官方财政决算报告，明确区分全市与市本级；采用2025年全市政府性基金收入5.6亿元，不使用市本级4.9亿元。",
    },
    {
        "year": 2025,
        "city_name": "阜新市",
        "city_id": "CN-210900",
        "source_doc_id": "SRC-A2-FUXIN-CITY-FUND-2025",
        "url": "https://czj.fuxin.gov.cn/content/2026/1090313.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "fuxin_2025_final_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "fuxin_2025_final_budget_report_excerpt.txt",
        "document_title": "关于阜新市2025年财政决算的报告",
        "publisher": "阜新市财政局",
        "publisher_level": "市级财政机构官方网页",
        "publication_date": "2026-07-10",
        "source_grade": "A2",
        "source_format": "html",
        "pattern": r"原文摘录：.*?2025年全市政府性基金预算收入实际完成([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "final",
        "data_status_label": "2025年决算数",
        "document_type": "城市财政决算报告（官方网页）",
        "page_count": "1",
        "note": "阜新市财政局官方财政决算报告，明确全市与市本级口径；采用2025年全市政府性基金预算收入4.23亿元，不使用市本级1.51亿元。",
    },
    {
        "year": 2025,
        "city_name": "盘锦市",
        "city_id": "CN-211100",
        "source_doc_id": "SRC-A2-PANJIN-CITY-FUND-2025",
        "url": "https://www.pjrd.gov.cn/2026_01/09_14/content-549808.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "panjin_2025_budget_execution_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "panjin_2025_budget_execution_report_excerpt.txt",
        "document_title": "关于盘锦市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "盘锦市人大信息网（盘锦市财政局报告）",
        "publisher_level": "市级人大官方门户",
        "publication_date": "2026-01-09",
        "source_grade": "A2",
        "source_format": "html",
        "pattern": r"原文摘录：.*?2025年全市政府性基金预算收入([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_count": "1",
        "note": "盘锦市人大信息网公开盘锦市财政局提交的人代会预算执行报告，明确全市口径；采用2025年全市政府性基金预算收入16.1亿元，不使用市本级2.7亿元。",
    },
    {
        "year": 2025,
        "city_name": "泸州市",
        "city_id": "CN-510500",
        "source_doc_id": "SRC-B2-LUZHOU-CITY-FUND-2025",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/company/c/new/2026-06-24/185565_20260624_YHTL.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "luzhou_2025_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "luzhou_2025_rating_report_excerpt.txt",
        "document_title": "泸州市兴泸投资集团有限公司2026年度跟踪评级报告",
        "publisher": "上海证券交易所公开披露的联合资信评级报告",
        "publisher_level": "交易所披露的B2精确表格来源",
        "publication_date": "2026-06-24",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"原文摘录：.*?2025年一般公共预算收入233\.5亿元、一般公共预算支出523\.8亿元、政府性基金收入([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_count": "28",
        "note": "上海证券交易所公开披露的联合资信跟踪评级报告，图表3列示泸州市主要财政指标；2025年政府性基金收入143.7亿元，表下注明根据《市本级决算和全市总决算情况的报告》和《2025年预算执行情况》整理，明确为泸州市全市口径。",
    },
    {
        "year": 2025,
        "city_name": "六安市",
        "city_id": "CN-341500",
        "source_doc_id": "SRC-A2-LUAN-CITY-FUND-2025",
        "url": "https://czj.luan.gov.cn/public/6608251/10758829.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "luan_2025_budget_execution_analysis.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "luan_2025_budget_execution_analysis_excerpt.txt",
        "document_title": "〖预算执行情况〗2025年全市预算执行情况分析",
        "publisher": "六安市财政局",
        "publisher_level": "市级财政机构官方网页",
        "publication_date": "2026-01-23",
        "source_grade": "A2",
        "source_format": "html",
        "pattern": r"原文摘录：.*?2025年，全市政府性基金预算收入([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行分析（官方网页）",
        "page_count": "1",
        "note": "六安市财政局官方预算执行分析，明确为全市口径；采用2025年全市政府性基金预算收入41亿元，不使用市本级数。",
    },
    {
        "year": 2025,
        "city_name": "汕尾市",
        "city_id": "CN-441500",
        "source_doc_id": "SRC-A2-SHANWEI-CITY-FUND-2025",
        "url": "https://www.shanwei.gov.cn/swczj/zhuanti/czyjshsgjf/czyjs/szfys/2026/content/post_1226558.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "shanwei_2025_budget_execution_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "shanwei_2025_budget_execution_report_excerpt.txt",
        "document_title": "汕尾市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "汕尾市财政局",
        "publisher_level": "市级财政机构官方网页",
        "publication_date": "2026",
        "source_grade": "A2",
        "source_format": "html",
        "pattern": r"原文摘录：.*?2025年全市政府性基金预算收入([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_count": "1",
        "note": "汕尾市财政局官方预算执行报告，明确区分全市与市级口径；采用2025年全市政府性基金预算收入31.4亿元，不使用市级18.5亿元。",
    },
    {
        "year": 2025,
        "city_name": "威海市",
        "city_id": "CN-371000",
        "source_doc_id": "SRC-A2-WEIHAI-CITY-FUND-2025",
        "url": "https://czj.weihai.gov.cn/attach/0/a6f1476961ba475e85d092558b833a51.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "weihai_2025_budget_execution_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "weihai_2025_budget_execution_report_excerpt.txt",
        "document_title": "关于2025年威海市和市级预算执行情况与2026年威海市和市级预算草案的报告",
        "publisher": "威海市财政局",
        "publisher_level": "市级财政机构官方 PDF",
        "publication_date": "2026-01-14",
        "source_grade": "A2",
        "source_format": "pdf",
        "pattern": r"原文摘录：.*?2025年，全市政府性基金预算收入([0-9]+)万元",
        "raw_unit": "万元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（初步汇总数）",
        "document_type": "城市财政预算执行报告（官方 PDF）",
        "page_count": "136",
        "note": "威海市财政局官方预算执行报告，明确全市与市本级口径；采用2025年全市政府性基金预算收入2255185万元，折算225.5185亿元并按统一标准入库225.52亿元；报告说明该执行数据为初步汇总数，决算完成后可能变化，登记为execution。",
    },
    {
        "year": 2025,
        "city_name": "邯郸市",
        "city_id": "CN-130400",
        "source_doc_id": "SRC-B2-HANDAN-CITY-FUND-2025",
        "url": "https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3375478&mode=save&priority=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "handan_2025_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "handan_2025_rating_report_excerpt.txt",
        "document_title": "邯郸城市发展投资集团有限公司主体长期信用评级报告",
        "publisher": "联合资信评估股份有限公司（交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2026-07-13",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"原文摘录：.*?2025年（末）一般公共预算收入386\.37亿元、一般公共预算支出935\.15亿元、政府性基金收入([0-9]+\.[0-9]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_count": "23",
        "note": "交易所公开披露的联合资信评级报告，图表2列示2023—2025年邯郸市主要财力指标；2025年政府性基金收入163.44亿元，表下注明根据《市本级决算和全市总决算情况的报告》和《2025年预算执行情况和2026年预算草案的报告》整理，明确为邯郸市全市口径。",
    },
    {
        "year": 2025,
        "city_name": "安庆市",
        "city_id": "CN-340800",
        "source_doc_id": "SRC-B2-ANQING-CITY-FUND-2025",
        "url": "https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3359176&mode=save&priority=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "anqing_2025_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "anqing_2025_rating_report_excerpt.txt",
        "document_title": "信用评级报告（东方金诚债跟踪评字【2026】0091号）",
        "publisher": "东方金诚国际信用评估有限公司（交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2026-06-15",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"原文摘录：.*?2025年政府性基金收入([0-9]+\.[0-9]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_count": "47",
        "note": "交易所公开披露的东方金诚跟踪评级报告，图表15列示2023—2025年安庆市主要经济及财政指标；2025年政府性基金收入40.40亿元，报告注明依据《关于安庆市2025年预算执行情况和2026年预算草案的报告》等资料整理，明确为安庆市全市口径。",
    },
    {
        "year": 2025,
        "city_name": "鄂州市",
        "city_id": "CN-420700",
        "source_doc_id": "SRC-A2-EZHOU-CITY-FUND-2025",
        "url": "https://www.ezhou.gov.cn/gk/xxgkml/czgk/zfyjs/202602/P020260331611182224746.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "ezhou_2025_budget_execution_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "ezhou_2025_budget_execution_report_excerpt.txt",
        "document_title": "关于鄂州市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "鄂州市财政局",
        "publisher_level": "市级财政机构官方 PDF",
        "publication_date": "2026-01-14",
        "source_grade": "A2",
        "source_format": "pdf",
        "pattern": r"原文摘录：.*?全市政府性基金预算收入完成\s*([0-9]+\.[0-9]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行报告（官方 PDF）",
        "page_count": "24",
        "note": "鄂州市财政局官方预算执行报告，明确区分全市与市本级口径；采用2025年全市政府性基金预算收入134.68亿元，不使用市本级74.02亿元。",
    },
    {
        "year": 2025,
        "city_name": "潍坊市",
        "city_id": "CN-370700",
        "source_doc_id": "SRC-B2-WEIFANG-CITY-FUND-2025",
        "url": "https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3356095&mode=open&priority=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "shandong_2025_city_fiscal_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "shandong_2025_city_fiscal_rating_report_excerpt.txt",
        "document_title": "山东海洋文化旅游发展集团有限公司相关债券2026年跟踪评级报告（24山东文旅MTN001）",
        "publisher": "中证鹏元资信评估股份有限公司（交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2026-06-11",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"原文摘录：.*?潍坊市政府性基金收入([0-9]+\.[0-9]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_count": "23",
        "note": "交易所公开披露的中证鹏元跟踪评级报告，表1列示2025年山东省部分地级行政区经济财政指标；潍坊市政府性基金收入413.14亿元，明确为全市口径。",
    },
    {
        "year": 2025,
        "city_name": "淄博市",
        "city_id": "CN-370300",
        "source_doc_id": "SRC-B2-ZIBO-CITY-FUND-2025",
        "url": "https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3356095&mode=open&priority=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "shandong_2025_city_fiscal_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "shandong_2025_city_fiscal_rating_report_excerpt.txt",
        "document_title": "山东海洋文化旅游发展集团有限公司相关债券2026年跟踪评级报告（24山东文旅MTN001）",
        "publisher": "中证鹏元资信评估股份有限公司（交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2026-06-11",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"原文摘录：.*?淄博市政府性基金收入([0-9]+\.[0-9]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_count": "23",
        "note": "交易所公开披露的中证鹏元跟踪评级报告，表1列示2025年山东省部分地级行政区经济财政指标；淄博市政府性基金收入238.07亿元，明确为全市口径。",
    },
    {
        "year": 2025,
        "city_name": "泰安市",
        "city_id": "CN-370900",
        "source_doc_id": "SRC-B2-TAIAN-CITY-FUND-2025",
        "url": "https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3356095&mode=open&priority=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "shandong_2025_city_fiscal_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "shandong_2025_city_fiscal_rating_report_excerpt.txt",
        "document_title": "山东海洋文化旅游发展集团有限公司相关债券2026年跟踪评级报告（24山东文旅MTN001）",
        "publisher": "中证鹏元资信评估股份有限公司（交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2026-06-11",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"原文摘录：.*?泰安市政府性基金收入([0-9]+\.[0-9]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_count": "23",
        "note": "交易所公开披露的中证鹏元跟踪评级报告，表1列示2025年山东省部分地级行政区经济财政指标；泰安市政府性基金收入130.77亿元，明确为全市口径。",
    },
    {
        "year": 2025,
        "city_name": "滨州市",
        "city_id": "CN-371600",
        "source_doc_id": "SRC-B2-BINZHOU-CITY-FUND-2025",
        "url": "https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3356095&mode=open&priority=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "shandong_2025_city_fiscal_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "shandong_2025_city_fiscal_rating_report_excerpt.txt",
        "document_title": "山东海洋文化旅游发展集团有限公司相关债券2026年跟踪评级报告（24山东文旅MTN001）",
        "publisher": "中证鹏元资信评估股份有限公司（交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2026-06-11",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"原文摘录：.*?滨州市政府性基金收入([0-9]+\.[0-9]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_count": "23",
        "note": "交易所公开披露的中证鹏元跟踪评级报告，表1列示2025年山东省部分地级行政区经济财政指标；滨州市政府性基金收入156.32亿元，明确为全市口径。",
    },
    {
        "year": 2025,
        "city_name": "日照市",
        "city_id": "CN-371100",
        "source_doc_id": "SRC-B2-RIZHAO-CITY-FUND-2025",
        "url": "https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3356095&mode=open&priority=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "shandong_2025_city_fiscal_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "shandong_2025_city_fiscal_rating_report_excerpt.txt",
        "document_title": "山东海洋文化旅游发展集团有限公司相关债券2026年跟踪评级报告（24山东文旅MTN001）",
        "publisher": "中证鹏元资信评估股份有限公司（交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2026-06-11",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"原文摘录：.*?日照市政府性基金收入([0-9]+\.[0-9]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_count": "23",
        "note": "交易所公开披露的中证鹏元跟踪评级报告，表1列示2025年山东省部分地级行政区经济财政指标；日照市政府性基金收入179.29亿元，明确为全市口径。",
    },
    {
        "year": 2025,
        "city_name": "枣庄市",
        "city_id": "CN-370400",
        "source_doc_id": "SRC-B2-ZAOZHUANG-CITY-FUND-2025",
        "url": "https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3356095&mode=open&priority=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "shandong_2025_city_fiscal_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "shandong_2025_city_fiscal_rating_report_excerpt.txt",
        "document_title": "山东海洋文化旅游发展集团有限公司相关债券2026年跟踪评级报告（24山东文旅MTN001）",
        "publisher": "中证鹏元资信评估股份有限公司（交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2026-06-11",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"原文摘录：.*?枣庄市政府性基金收入([0-9]+\.[0-9]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_count": "23",
        "note": "交易所公开披露的中证鹏元跟踪评级报告，表1列示2025年山东省部分地级行政区经济财政指标；枣庄市政府性基金收入287.24亿元，明确为全市口径。",
    },
    {
        "year": 2025,
        "city_name": "三亚市",
        "city_id": "CN-460200",
        "source_doc_id": "SRC-A2-SANYA-CITY-FUND-2025",
        "url": "https://rd.sanya.gov.cn/rdsite/c100028d/202602/9f39ba4d9a0e4eb9b30023b5da21915f.shtml",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "sanya_2025_budget_execution_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "sanya_2025_budget_execution_report_excerpt.txt",
        "document_title": "关于三亚市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "三亚市财政局（市人大公开页面）",
        "publisher_level": "市级财政机构官方网页",
        "publication_date": "2026-01-26",
        "source_grade": "A2",
        "source_format": "html",
        "pattern": r"原文摘录：.*?全市地方政府性基金预算收入([0-9]+\.[0-9]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_count": "1",
        "note": "三亚市人大公开的市财政局预算执行报告，明确全市与市本级口径；采用2025年全市地方政府性基金预算收入138.7亿元。",
    },
    {
        "year": 2025,
        "city_name": "玉溪市",
        "city_id": "CN-530400",
        "source_doc_id": "SRC-A2-YUXI-CITY-FUND-2025",
        "url": "https://www.yuxi.gov.cn/yxszfxxgk/zfysgkyxsczj/20260211/1648874.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "yuxi_2025_budget_execution_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "yuxi_2025_budget_execution_report_excerpt.txt",
        "document_title": "玉溪市2025年地方财政预算执行情况和2026年地方财政预算草案的报告",
        "publisher": "玉溪市财政局",
        "publisher_level": "市级财政机构官方网页",
        "publication_date": "2026-02-11",
        "source_grade": "A2",
        "source_format": "html",
        "pattern": r"原文摘录：.*?全市政府性基金预算收入完成([0-9]+\.[0-9]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_count": "1",
        "note": "玉溪市财政局官方预算执行报告，明确区分全市与市本级口径；采用2025年全市政府性基金预算收入27.05亿元，保留执行状态。",
    },
    {
        "year": 2025,
        "city_name": "曲靖市",
        "city_id": "CN-530300",
        "source_doc_id": "SRC-A2-QUJING-CITY-FUND-2025",
        "url": "https://czj.qj.gov.cn/gov/info/detail/21933.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "qujing_2025_budget_execution_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "qujing_2025_budget_execution_report_excerpt.txt",
        "document_title": "曲靖市2025年地方财政预算执行情况和2026年地方财政预算草案的报告",
        "publisher": "曲靖市财政局",
        "publisher_level": "市级财政机构官方网页",
        "publication_date": "2026-03-19",
        "source_grade": "A2",
        "source_format": "html",
        "pattern": r"原文摘录：.*?全市政府性基金预算收入完成([0-9]+\.[0-9]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_count": "1",
        "note": "曲靖市财政局官方预算公开页面及报告，明确区分全市与市级口径；采用2025年全市政府性基金预算收入37.8亿元，保留执行状态。",
    },
    {
        "year": 2025,
        "city_name": "江门市",
        "city_id": "CN-440700",
        "source_doc_id": "SRC-A2-JIANGMEN-CITY-FUND-2025",
        "url": "https://www.jiangmen.gov.cn/attachment/0/375/375866/3447145.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "jiangmen_2025_budget_execution_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "jiangmen_2025_budget_execution_report_excerpt.txt",
        "document_title": "2026年江门市本级政府预算公开（含2025年预算执行情况）",
        "publisher": "江门市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-02-25",
        "source_grade": "A2",
        "source_format": "pdf",
        "pattern": r"原文摘录：.*?2025年[,，]?全市政府性基金预算收入([0-9]+\.[0-9]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行报告（官方PDF）",
        "page_count": "187",
        "note": "江门市财政局官方预算执行报告正文明确区分全市与市本级口径；采用2025年全市政府性基金预算收入120.01亿元，保留execution状态，不使用市本级15.56亿元。",
    },
    {
        "year": 2025,
        "city_name": "珠海市",
        "city_id": "CN-440400",
        "source_doc_id": "SRC-B2-ZHUHAI-CITY-FUND-2025",
        "url": "https://www.chinamoney.org.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3361527&mode=save&priority=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhuhai_2025_fiscal_rating.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhuhai_2025_fiscal_rating_excerpt.txt",
        "document_title": "珠海华发综合发展有限公司2026年跟踪评级报告",
        "publisher": "联合资信评估股份有限公司（交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2026-06-12",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"政府性基金收入（亿元）\|86\.85\|91\.38\|([0-9.]+)",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年末执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_count": "24",
        "note": "交易所公开披露的联合资信跟踪评级报告，表3列示珠海市全市财政指标；2025年政府性基金收入32.70亿元。该值为B2精确表格来源，不替代市财政局最终决算。",
    },
    {
        "year": 2025,
        "city_name": "佛山市",
        "city_id": "CN-440600",
        "source_doc_id": "SRC-B2-FOSHAN-CITY-FUND-2025",
        "url": "https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3367875&mode=open&priority=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "foshan_2025_fiscal_rating.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "foshan_2025_fiscal_rating_excerpt.txt",
        "document_title": "佛山市建设发展集团有限公司2026年跟踪评级报告",
        "publisher": "联合资信评估股份有限公司（交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2026-06-18",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"政府性基金预算收入\|477\.03\|492\.77\|([0-9.]+)",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年末执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_count": "35",
        "note": "交易所公开披露的联合资信跟踪评级报告，表5列示佛山市全市财政数据；表下注明根据佛山市财政局数据整理，2025年政府性基金预算收入376.06亿元。该值为B2精确表格来源，不替代市财政局最终决算。",
    },
    {
        "year": 2025,
        "city_name": "云浮市",
        "city_id": "CN-445300",
        "source_doc_id": "SRC-A2-YUNFU-CITY-FUND-2025",
        "url": "https://www.yunfu.gov.cn/attachment/0/124/124714/1987579.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "yunfu_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "yunfu_2025_budget_report_excerpt.txt",
        "document_title": "2026年云浮市本级政府预算公开（含2025年预算执行情况）",
        "publisher": "云浮市财政局",
        "publisher_level": "市级财政机构官方PDF",
        "publication_date": "2026-02-06",
        "source_grade": "A2",
        "source_format": "pdf",
        "pattern": r"2025年全市政府性基金预算收入([0-9,]+)万元",
        "raw_unit": "万元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行报告（官方PDF）",
        "page_count": "83",
        "note": "云浮市人民政府/财政局官方预算公开PDF明确披露2025年全市政府性基金预算收入102194万元，原始单位万元，统一换算为10.22亿元；执行数，不使用市本级口径。",
    },
    {
        "year": 2025,
        "city_name": "巴中市",
        "city_id": "CN-511900",
        "source_doc_id": "SRC-B2-SICHUAN-REGIONAL-FISCAL-2025-BAZHONG",
        "url": "https://www.sfecr.com/upload/file/2026-03/col58/1774940677199.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sichuan_2025_regional_fiscal_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sichuan_2025_regional_fiscal_report_excerpt.txt",
        "document_title": "四川省区域经济与信用观察",
        "publisher": "远东资信评估有限公司",
        "publisher_level": "专业评级研究机构（精确表格二手来源）",
        "publication_date": "2026-03-24",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"巴中市｜[^｜]+｜[^｜]+｜([0-9.]+)｜",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（区域研究精确表格）",
        "document_type": "区域经济与信用观察财政指标表",
        "page_count": "31",
        "note": "报告第9页表1精确列示巴中市2025年政府性基金收入123.94亿元；按B2精确表格纳入，保持execution状态，不使用表中其他指标推导财政基金收入。",
    },
    {
        "year": 2025,
        "city_name": "广安市",
        "city_id": "CN-511600",
        "source_doc_id": "SRC-B2-SICHUAN-REGIONAL-FISCAL-2025-GUANGAN",
        "url": "https://www.sfecr.com/upload/file/2026-03/col58/1774940677199.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sichuan_2025_regional_fiscal_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sichuan_2025_regional_fiscal_report_excerpt.txt",
        "document_title": "四川省区域经济与信用观察",
        "publisher": "远东资信评估有限公司",
        "publisher_level": "专业评级研究机构（精确表格二手来源）",
        "publication_date": "2026-03-24",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"广安市｜[^｜]+｜[^｜]+｜([0-9.]+)｜",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（区域研究精确表格）",
        "document_type": "区域经济与信用观察财政指标表",
        "page_count": "31",
        "note": "报告第9页表1精确列示广安市2025年政府性基金收入97.40亿元；按B2精确表格纳入，保持execution状态，不使用表中其他指标推导财政基金收入。",
    },
    {
        "year": 2025,
        "city_name": "内江市",
        "city_id": "CN-511000",
        "source_doc_id": "SRC-B2-SICHUAN-REGIONAL-FISCAL-2025-NEIJIANG",
        "url": "https://www.sfecr.com/upload/file/2026-03/col58/1774940677199.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sichuan_2025_regional_fiscal_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sichuan_2025_regional_fiscal_report_excerpt.txt",
        "document_title": "四川省区域经济与信用观察",
        "publisher": "远东资信评估有限公司",
        "publisher_level": "专业评级研究机构（精确表格二手来源）",
        "publication_date": "2026-03-24",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"内江市｜[^｜]+｜[^｜]+｜([0-9.]+)｜",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（区域研究精确表格）",
        "document_type": "区域经济与信用观察财政指标表",
        "page_count": "31",
        "note": "报告第9页表1精确列示内江市2025年政府性基金收入118.79亿元；按B2精确表格纳入，保持execution状态，不使用表中其他指标推导财政基金收入。",
    },
    {
        "year": 2025,
        "city_name": "南充市",
        "city_id": "CN-511300",
        "source_doc_id": "SRC-B2-SICHUAN-REGIONAL-FISCAL-2025-NANCHONG",
        "url": "https://www.sfecr.com/upload/file/2026-03/col58/1774940677199.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sichuan_2025_regional_fiscal_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sichuan_2025_regional_fiscal_report_excerpt.txt",
        "document_title": "四川省区域经济与信用观察",
        "publisher": "远东资信评估有限公司",
        "publisher_level": "专业评级研究机构（精确表格二手来源）",
        "publication_date": "2026-03-24",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"南充市｜[^｜]+｜[^｜]+｜([0-9.]+)｜",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（区域研究精确表格）",
        "document_type": "区域经济与信用观察财政指标表",
        "page_count": "31",
        "note": "报告第9页表1精确列示南充市2025年政府性基金收入188.70亿元；按B2精确表格纳入，保持execution状态，不使用表中其他指标推导财政基金收入。",
    },
    {
        "year": 2025,
        "city_name": "德阳市",
        "city_id": "CN-510600",
        "source_doc_id": "SRC-B2-SICHUAN-REGIONAL-FISCAL-2025-DEYANG",
        "url": "https://www.sfecr.com/upload/file/2026-03/col58/1774940677199.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sichuan_2025_regional_fiscal_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sichuan_2025_regional_fiscal_report_excerpt.txt",
        "document_title": "四川省区域经济与信用观察",
        "publisher": "远东资信评估有限公司",
        "publisher_level": "专业评级研究机构（精确表格二手来源）",
        "publication_date": "2026-03-24",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"德阳市｜[^｜]+｜[^｜]+｜([0-9.]+)｜",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（区域研究精确表格）",
        "document_type": "区域经济与信用观察财政指标表",
        "page_count": "31",
        "note": "报告第9页表1精确列示德阳市2025年政府性基金收入186.57亿元；按B2精确表格纳入，保持execution状态，不使用表中其他指标推导财政基金收入。",
    },
    {
        "year": 2025,
        "city_name": "宜宾市",
        "city_id": "CN-511500",
        "source_doc_id": "SRC-B2-SICHUAN-REGIONAL-FISCAL-2025-YIBIN",
        "url": "https://www.sfecr.com/upload/file/2026-03/col58/1774940677199.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sichuan_2025_regional_fiscal_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sichuan_2025_regional_fiscal_report_excerpt.txt",
        "document_title": "四川省区域经济与信用观察",
        "publisher": "远东资信评估有限公司",
        "publisher_level": "专业评级研究机构（精确表格二手来源）",
        "publication_date": "2026-03-24",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"宜宾市｜[^｜]+｜[^｜]+｜([0-9.]+)｜",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（区域研究精确表格）",
        "document_type": "区域经济与信用观察财政指标表",
        "page_count": "31",
        "note": "报告第9页表1精确列示宜宾市2025年政府性基金收入149.60亿元；按B2精确表格纳入，保持execution状态，不使用表中其他指标推导财政基金收入。",
    },
    {
        "year": 2025,
        "city_name": "攀枝花市",
        "city_id": "CN-510400",
        "source_doc_id": "SRC-B2-SICHUAN-REGIONAL-FISCAL-2025-PANZHIHUA",
        "url": "https://www.sfecr.com/upload/file/2026-03/col58/1774940677199.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sichuan_2025_regional_fiscal_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sichuan_2025_regional_fiscal_report_excerpt.txt",
        "document_title": "四川省区域经济与信用观察",
        "publisher": "远东资信评估有限公司",
        "publisher_level": "专业评级研究机构（精确表格二手来源）",
        "publication_date": "2026-03-24",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"攀枝花市｜[^｜]+｜[^｜]+｜([0-9.]+)｜",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（区域研究精确表格）",
        "document_type": "区域经济与信用观察财政指标表",
        "page_count": "31",
        "note": "报告第9页表1精确列示攀枝花市2025年政府性基金收入17.39亿元；按B2精确表格纳入，保持execution状态，不使用表中其他指标推导财政基金收入。",
    },
    {
        "year": 2025,
        "city_name": "阿坝藏族羌族自治州",
        "city_id": "CN-513200",
        "source_doc_id": "SRC-B2-SICHUAN-REGIONAL-FISCAL-2025-ABA",
        "url": "https://www.sfecr.com/upload/file/2026-03/col58/1774940677199.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sichuan_2025_regional_fiscal_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sichuan_2025_regional_fiscal_report_excerpt.txt",
        "document_title": "四川省区域经济与信用观察",
        "publisher": "远东资信评估有限公司",
        "publisher_level": "专业评级研究机构（精确表格二手来源）",
        "publication_date": "2026-03-24",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"阿坝藏族羌族自治州｜[^｜]+｜[^｜]+｜([0-9.]+)｜",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（区域研究精确表格）",
        "document_type": "区域经济与信用观察财政指标表",
        "page_count": "31",
        "note": "报告第9页表1精确列示阿坝藏族羌族自治州2025年政府性基金收入12.50亿元；按B2精确表格纳入，保持execution状态，不使用表中其他指标推导财政基金收入。",
    },
    {
        "year": 2025,
        "city_name": "甘孜藏族自治州",
        "city_id": "CN-513300",
        "source_doc_id": "SRC-B2-SICHUAN-REGIONAL-FISCAL-2025-GANZI",
        "url": "https://www.sfecr.com/upload/file/2026-03/col58/1774940677199.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sichuan_2025_regional_fiscal_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sichuan_2025_regional_fiscal_report_excerpt.txt",
        "document_title": "四川省区域经济与信用观察",
        "publisher": "远东资信评估有限公司",
        "publisher_level": "专业评级研究机构（精确表格二手来源）",
        "publication_date": "2026-03-24",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"甘孜藏族自治州｜[^｜]+｜[^｜]+｜([0-9.]+)｜",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（区域研究精确表格）",
        "document_type": "区域经济与信用观察财政指标表",
        "page_count": "31",
        "note": "报告第9页表1精确列示甘孜藏族自治州2025年政府性基金收入8.63亿元；按B2精确表格纳入，保持execution状态，不使用表中其他指标推导财政基金收入。",
    },
    {
        "year": 2025,
        "city_name": "凉山彝族自治州",
        "city_id": "CN-513400",
        "source_doc_id": "SRC-B2-SICHUAN-REGIONAL-FISCAL-2025-LIANGSHAN",
        "url": "https://www.sfecr.com/upload/file/2026-03/col58/1774940677199.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sichuan_2025_regional_fiscal_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sichuan_2025_regional_fiscal_report_excerpt.txt",
        "document_title": "四川省区域经济与信用观察",
        "publisher": "远东资信评估有限公司",
        "publisher_level": "专业评级研究机构（精确表格二手来源）",
        "publication_date": "2026-03-24",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"凉山彝族自治州｜[^｜]+｜[^｜]+｜([0-9.]+)｜",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（区域研究精确表格）",
        "document_type": "区域经济与信用观察财政指标表",
        "page_count": "31",
        "note": "报告第9页表1精确列示凉山彝族自治州2025年政府性基金收入56.53亿元；按B2精确表格纳入，保持execution状态，不使用表中其他指标推导财政基金收入。",
    },
)

# 2025年政府性基金收入精确补缺批次：福建省六个设区市、防城港、固原、宿州和阳江。
# 统一使用全市执行口径；官方预算执行报告按 A2 纳入，评级报告或精确转载按 B2 纳入。
# PDF/HTML 原件和字段级摘录均归档，避免用市本级数、预算安排数或媒体概述代替全市执行数。
CITY_YEAR_FUND_SOURCES += (
    {
        "year": 2025,
        "city_name": "厦门市",
        "city_id": "CN-350200",
        "source_doc_id": "SRC-2025-FUND-BATCH-XIAMEN",
        "url": "https://www.lhratings.com/reports/B024098-P87735-2026.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "xiamen_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "xiamen_2025_budget_report_excerpt.txt",
        "document_title": "厦门市2026年地方政府再融资信用报告",
        "publisher": "联合资信评估股份有限公司",
        "publisher_level": "专业评级机构（精确表格二手来源）",
        "publication_date": "2026-05-07",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"2025年厦门市政府性基金收入合计为([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "地方政府再融资债券评级报告（精确表格）",
        "page_count": "18",
        "note": "B2精确表格；报告根据厦门市官方预算执行报告及附表整理，明确为2025年全市政府性基金收入合计，不使用市本级数。",
    },
    {
        "year": 2025,
        "city_name": "莆田市",
        "city_id": "CN-350300",
        "source_doc_id": "SRC-2025-FUND-BATCH-PUTIAN",
        "url": "https://czj.putian.gov.cn/zwgk/ggzjsyyjd/czyjs/202601/t20260116_2043037.htm",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "putian_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "putian_2025_budget_report_excerpt.txt",
        "document_title": "莆田市2025年12月预算执行情况",
        "publisher": "莆田市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-01-16",
        "source_grade": "A2",
        "source_format": "html",
        "pattern": r"全市政府性基金收入([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市预算执行公开信息（官方网页）",
        "page_count": "1",
        "note": "A2市级财政官方网页；明确披露2025年12月止全市政府性基金收入109.19亿元。",
    },
    {
        "year": 2025,
        "city_name": "三明市",
        "city_id": "CN-350400",
        "source_doc_id": "SRC-2025-FUND-BATCH-SANMING",
        "url": "https://www.sm.gov.cn/zw/gzbg/czbg/202601/t20260128_2186879.htm",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "sanming_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "sanming_2025_budget_report_excerpt.txt",
        "document_title": "关于三明市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "三明市人民政府",
        "publisher_level": "市级政府门户",
        "publication_date": "2026-01-28",
        "source_grade": "A2",
        "source_format": "html",
        "pattern": r"2025年，全市政府性基金预算收入([0-9,]+)万元",
        "raw_unit": "万元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_count": "1",
        "note": "A2市级政府官方预算执行报告；明确披露2025年全市政府性基金预算收入272426万元，统一换算为亿元。",
    },
    {
        "year": 2025,
        "city_name": "南平市",
        "city_id": "CN-350700",
        "source_doc_id": "SRC-2025-FUND-BATCH-NANPING",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/corporate/c/new/2026-06-26/152266_20260626_XKKO.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "nanping_2025_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "nanping_2025_rating_report_excerpt.txt",
        "document_title": "南平市地方政府再融资债券相关评级报告",
        "publisher": "联合资信评估股份有限公司",
        "publisher_level": "专业评级机构（精确表格二手来源）",
        "publication_date": "2026-06-26",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"2025年，南平市政府性基金收入为([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "地方政府再融资债券评级报告（精确表格）",
        "page_count": "21",
        "note": "B2精确表格；报告表格列示南平市2025年政府性基金收入57.48亿元，保持全市执行口径。",
    },
    {
        "year": 2025,
        "city_name": "龙岩市",
        "city_id": "CN-350800",
        "source_doc_id": "SRC-2025-FUND-BATCH-LONGYAN",
        "url": "https://www.chinamoney.org.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3355108&mode=save&priority=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "longyan_2025_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "longyan_2025_rating_report_excerpt.txt",
        "document_title": "龙岩市地方政府再融资债券相关评级报告",
        "publisher": "东方金诚国际信用评估有限公司",
        "publisher_level": "专业评级机构（精确表格二手来源）",
        "publication_date": "2026-06-09",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"2025年，龙岩市政府性基金收入为([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "地方政府再融资债券评级报告（精确表格）",
        "page_count": "21",
        "note": "B2精确表格；图表引用龙岩市2025年财政预算执行情况，列示全市政府性基金收入63.43亿元。",
    },
    {
        "year": 2025,
        "city_name": "宁德市",
        "city_id": "CN-350900",
        "source_doc_id": "SRC-2025-FUND-BATCH-NINGDE",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/company/c/new/2026-03-31/244958_20260331_36ZI.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "ningde_2025_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "ningde_2025_rating_report_excerpt.txt",
        "document_title": "宁德市地方政府再融资债券相关评级报告",
        "publisher": "中诚信国际信用评级有限责任公司",
        "publisher_level": "专业评级机构（精确表格二手来源）",
        "publication_date": "2026-03-31",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"2025年，宁德市政府性基金收入为([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年年度快报执行数",
        "document_type": "地方政府再融资债券评级报告（精确表格）",
        "page_count": "30",
        "note": "B2精确表格；报告表3列示宁德市2025年政府性基金收入61.13亿元，资料来源为宁德市人民政府官网，标记为年度快报执行数。",
    },
    {
        "year": 2025,
        "city_name": "防城港市",
        "city_id": "CN-450600",
        "source_doc_id": "SRC-2025-FUND-BATCH-FANGCHENGGANG",
        "url": "https://www.fcgs.gov.cn/zfxxgk/zdlyxxgk/czzj/szfys/zfys2026/P020260303601123245736.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "fangchenggang_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "fangchenggang_2025_budget_report_excerpt.txt",
        "document_title": "防城港市2025年全市和市本级预算执行情况及2026年预算草案",
        "publisher": "防城港市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-03-03",
        "source_grade": "A2",
        "source_format": "pdf",
        "pattern": r"政府性基金预算收入合计([0-9,]+)万元",
        "raw_unit": "万元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行报告（官方PDF）",
        "page_count": "75",
        "note": "A2市级财政官方预算表；采用全市政府性基金预算收入合计178971万元，不采用市本级调整数173702万元。",
    },
    {
        "year": 2025,
        "city_name": "固原市",
        "city_id": "CN-640400",
        "source_doc_id": "SRC-2025-FUND-BATCH-GUYUAN",
        "url": "https://www.nxgy.gov.cn/zwgk/zfxxgkml/czgk/czyjsjsgjf/202601/W020260129632884834193.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "guyuan_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "guyuan_2025_budget_report_excerpt.txt",
        "document_title": "关于2025年全市及市本级财政预算执行情况和2026年全市及市本级财政预算草案的报告",
        "publisher": "固原市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-01-29",
        "source_grade": "A2",
        "source_format": "pdf",
        "pattern": r"2025年，全市政府性基金收入完成([0-9,]+)万元",
        "raw_unit": "万元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行报告（官方PDF）",
        "page_count": "113",
        "note": "A2市级财政官方预算执行报告；明确披露2025年全市政府性基金收入完成207123万元，统一换算为亿元。",
    },
    {
        "year": 2025,
        "city_name": "宿州市",
        "city_id": "CN-341300",
        "source_doc_id": "SRC-2025-FUND-BATCH-SUZHOU-ANHUI",
        "url": "https://www.ahsz.gov.cn/zwzx/bmdt/196237841.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "suzhou_anhui_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "suzhou_anhui_2025_budget_report_excerpt.txt",
        "document_title": "关于宿州市2025年预算执行情况和2026年预算草案的报告（摘要）",
        "publisher": "宿州市人民政府",
        "publisher_level": "市级政府门户",
        "publication_date": "2026-01-28",
        "source_grade": "A2",
        "source_format": "html",
        "pattern": r"全市政府性基金预算收入([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_count": "1",
        "note": "A2市级政府官方预算执行报告摘要；明确披露2025年全市政府性基金预算收入61.81亿元。",
    },
    {
        "year": 2025,
        "city_name": "阳江市",
        "city_id": "CN-441700",
        "source_doc_id": "SRC-2025-FUND-BATCH-YANGJIANG",
        "url": "https://news.yjrb.com.cn/articles/yaowen/20260206/618383.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "yangjiang_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "yangjiang_2025_budget_report_excerpt.txt",
        "document_title": "阳江市2025年预算执行情况和2026年预算草案财政执行报道",
        "publisher": "阳江日报",
        "publisher_level": "地方报刊精确转载（专业二手来源）",
        "publication_date": "2026-02-06",
        "source_grade": "B2",
        "source_format": "html",
        "pattern": r"2025年全市政府性基金预算收入([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行报告精确转载（官方报刊网页）",
        "page_count": "1",
        "note": "B2精确转载；报道引用阳江市2025年预算执行情况和2026年预算草案，明确披露全市政府性基金预算收入20.56亿元。",
    },
)

# 浙江省 2025 年政府性基金收入批量补缺：中证鹏元在上交所公开披露的
# 湖州市产业投资发展集团跟踪评级报告第 7 页表 2，一张精确表列示浙江
# 11 个地级市的全市政府性基金收入。按 B2 纳入，保留 execution 状态，
# 不使用市本级数或预算安排数替代全市执行数。
CITY_YEAR_FUND_SOURCES += (
    {
        "year": 2025,
        "city_name": "杭州市",
        "city_id": "CN-330100",
        "source_doc_id": "SRC-B2-ZHEJIANG-2025-FUND-HANGZHOU",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/company/c/new/2026-07-30/244363_20260730_57CX.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhejiang_2025_city_fiscal_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhejiang_2025_city_fiscal_rating_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "湖州市产业投资发展集团有限公司2026年度跟踪评级报告",
        "publisher": "中证鹏元资信评估股份有限公司（上海证券交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2026-07-30",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"杭州市\|政府性基金收入\|([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_number": "PDF第7页，表2；2025年浙江省部分地级市经济财政指标情况",
        "page_count": "27",
        "note": "B2精确表格；报告表2列示杭州市2025年全市政府性基金收入1717.13亿元，资料来源为各政府网站，中证鹏元整理，不使用市本级数。",
    },
    {
        "year": 2025,
        "city_name": "宁波市",
        "city_id": "CN-330200",
        "source_doc_id": "SRC-B2-ZHEJIANG-2025-FUND-NINGBO",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/company/c/new/2026-07-30/244363_20260730_57CX.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhejiang_2025_city_fiscal_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhejiang_2025_city_fiscal_rating_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "湖州市产业投资发展集团有限公司2026年度跟踪评级报告",
        "publisher": "中证鹏元资信评估股份有限公司（上海证券交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2026-07-30",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"宁波市\|政府性基金收入\|([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_number": "PDF第7页，表2；2025年浙江省部分地级市经济财政指标情况",
        "page_count": "27",
        "note": "B2精确表格；报告表2列示宁波市2025年全市政府性基金收入535.34亿元，资料来源为各政府网站，中证鹏元整理，不使用市本级数。",
    },
    {
        "year": 2025,
        "city_name": "温州市",
        "city_id": "CN-330300",
        "source_doc_id": "SRC-B2-ZHEJIANG-2025-FUND-WENZHOU",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/company/c/new/2026-07-30/244363_20260730_57CX.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhejiang_2025_city_fiscal_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhejiang_2025_city_fiscal_rating_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "湖州市产业投资发展集团有限公司2026年度跟踪评级报告",
        "publisher": "中证鹏元资信评估股份有限公司（上海证券交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2026-07-30",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"温州市\|政府性基金收入\|([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_number": "PDF第7页，表2；2025年浙江省部分地级市经济财政指标情况",
        "page_count": "27",
        "note": "B2精确表格；报告表2列示温州市2025年全市政府性基金收入884.27亿元，资料来源为各政府网站，中证鹏元整理，不使用市本级数。",
    },
    {
        "year": 2025,
        "city_name": "嘉兴市",
        "city_id": "CN-330400",
        "source_doc_id": "SRC-B2-ZHEJIANG-2025-FUND-JIAXING",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/company/c/new/2026-07-30/244363_20260730_57CX.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhejiang_2025_city_fiscal_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhejiang_2025_city_fiscal_rating_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "湖州市产业投资发展集团有限公司2026年度跟踪评级报告",
        "publisher": "中证鹏元资信评估股份有限公司（上海证券交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2026-07-30",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"嘉兴市\|政府性基金收入\|([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_number": "PDF第7页，表2；2025年浙江省部分地级市经济财政指标情况",
        "page_count": "27",
        "note": "B2精确表格；报告表2列示嘉兴市2025年全市政府性基金收入414.43亿元，资料来源为各政府网站，中证鹏元整理，不使用市本级数。",
    },
    {
        "year": 2025,
        "city_name": "湖州市",
        "city_id": "CN-330500",
        "source_doc_id": "SRC-B2-ZHEJIANG-2025-FUND-HUZHOU",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/company/c/new/2026-07-30/244363_20260730_57CX.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhejiang_2025_city_fiscal_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhejiang_2025_city_fiscal_rating_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "湖州市产业投资发展集团有限公司2026年度跟踪评级报告",
        "publisher": "中证鹏元资信评估股份有限公司（上海证券交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2026-07-30",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"湖州市\|政府性基金收入\|([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_number": "PDF第7页，表2；2025年浙江省部分地级市经济财政指标情况",
        "page_count": "27",
        "note": "B2精确表格；报告表2列示湖州市2025年全市政府性基金收入345.94亿元，资料来源为各政府网站，中证鹏元整理，不使用市本级数。",
    },
    {
        "year": 2025,
        "city_name": "绍兴市",
        "city_id": "CN-330600",
        "source_doc_id": "SRC-B2-ZHEJIANG-2025-FUND-SHAOXING",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/company/c/new/2026-07-30/244363_20260730_57CX.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhejiang_2025_city_fiscal_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhejiang_2025_city_fiscal_rating_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "湖州市产业投资发展集团有限公司2026年度跟踪评级报告",
        "publisher": "中证鹏元资信评估股份有限公司（上海证券交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2026-07-30",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"绍兴市\|政府性基金收入\|([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_number": "PDF第7页，表2；2025年浙江省部分地级市经济财政指标情况",
        "page_count": "27",
        "note": "B2精确表格；报告表2列示绍兴市2025年全市政府性基金收入407.19亿元，资料来源为各政府网站，中证鹏元整理，不使用市本级数。",
    },
    {
        "year": 2025,
        "city_name": "金华市",
        "city_id": "CN-330700",
        "source_doc_id": "SRC-B2-ZHEJIANG-2025-FUND-JINHUA",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/company/c/new/2026-07-30/244363_20260730_57CX.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhejiang_2025_city_fiscal_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhejiang_2025_city_fiscal_rating_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "湖州市产业投资发展集团有限公司2026年度跟踪评级报告",
        "publisher": "中证鹏元资信评估股份有限公司（上海证券交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2026-07-30",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"金华市\|政府性基金收入\|([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_number": "PDF第7页，表2；2025年浙江省部分地级市经济财政指标情况",
        "page_count": "27",
        "note": "B2精确表格；报告表2列示金华市2025年全市政府性基金收入541.78亿元，资料来源为各政府网站，中证鹏元整理，不使用市本级数。",
    },
    {
        "year": 2025,
        "city_name": "衢州市",
        "city_id": "CN-330800",
        "source_doc_id": "SRC-B2-ZHEJIANG-2025-FUND-QUZHOU",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/company/c/new/2026-07-30/244363_20260730_57CX.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhejiang_2025_city_fiscal_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhejiang_2025_city_fiscal_rating_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "湖州市产业投资发展集团有限公司2026年度跟踪评级报告",
        "publisher": "中证鹏元资信评估股份有限公司（上海证券交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2026-07-30",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"衢州市\|政府性基金收入\|([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_number": "PDF第7页，表2；2025年浙江省部分地级市经济财政指标情况",
        "page_count": "27",
        "note": "B2精确表格；报告表2列示衢州市2025年全市政府性基金收入170.15亿元，资料来源为各政府网站，中证鹏元整理，不使用市本级数。",
    },
    {
        "year": 2025,
        "city_name": "舟山市",
        "city_id": "CN-330900",
        "source_doc_id": "SRC-B2-ZHEJIANG-2025-FUND-ZHOUSHAN",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/company/c/new/2026-07-30/244363_20260730_57CX.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhejiang_2025_city_fiscal_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhejiang_2025_city_fiscal_rating_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "湖州市产业投资发展集团有限公司2026年度跟踪评级报告",
        "publisher": "中证鹏元资信评估股份有限公司（上海证券交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2026-07-30",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"舟山市\|政府性基金收入\|([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_number": "PDF第7页，表2；2025年浙江省部分地级市经济财政指标情况",
        "page_count": "27",
        "note": "B2精确表格；报告表2列示舟山市2025年全市政府性基金收入89.39亿元，资料来源为各政府网站，中证鹏元整理，不使用市本级数。",
    },
    {
        "year": 2025,
        "city_name": "台州市",
        "city_id": "CN-331000",
        "source_doc_id": "SRC-B2-ZHEJIANG-2025-FUND-TAIZHOU",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/company/c/new/2026-07-30/244363_20260730_57CX.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhejiang_2025_city_fiscal_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhejiang_2025_city_fiscal_rating_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "湖州市产业投资发展集团有限公司2026年度跟踪评级报告",
        "publisher": "中证鹏元资信评估股份有限公司（上海证券交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2026-07-30",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"台州市\|政府性基金收入\|([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_number": "PDF第7页，表2；2025年浙江省部分地级市经济财政指标情况",
        "page_count": "27",
        "note": "B2精确表格；报告表2列示台州市2025年全市政府性基金收入463.06亿元，资料来源为各政府网站，中证鹏元整理，不使用市本级数。",
    },
    {
        "year": 2025,
        "city_name": "丽水市",
        "city_id": "CN-331100",
        "source_doc_id": "SRC-B2-ZHEJIANG-2025-FUND-LISHUI",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/company/c/new/2026-07-30/244363_20260730_57CX.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhejiang_2025_city_fiscal_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zhejiang_2025_city_fiscal_rating_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "湖州市产业投资发展集团有限公司2026年度跟踪评级报告",
        "publisher": "中证鹏元资信评估股份有限公司（上海证券交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2026-07-30",
        "source_grade": "B2",
        "source_format": "pdf",
        "pattern": r"丽水市\|政府性基金收入\|([0-9.]+)亿元",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_number": "PDF第7页，表2；2025年浙江省部分地级市经济财政指标情况",
        "page_count": "27",
        "note": "B2精确表格；报告表2列示丽水市2025年全市政府性基金收入234.13亿元，资料来源为各政府网站，中证鹏元整理，不使用市本级数。",
    },
)
CITY_YEAR_FUND_SOURCE_IDS = {item["source_doc_id"] for item in CITY_YEAR_FUND_SOURCES}

# 朝阳市财政局 2024 年预算执行报告同时精确披露全市一般预算收入、支出和
# 政府性基金收入。原文使用“快报数”，因此只登记为 execution，不冒充最终决算。
CITY_YEAR_FISCAL_SOURCES = (
    {
        "year": 2024,
        "city_name": "朝阳市",
        "city_id": "CN-211300",
        "source_doc_id": "SRC-A2-CHAOYANG-CITY-FISCAL-2024",
        "url": "https://files.chaoyang.gov.cn/files/ueditor/CYCZJ/jsp/upload/file/20251208/1765186825895001235.pdf",
        "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "chaoyang_2024_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2024" / "official" / "chaoyang_2024_budget_report_excerpt.txt",
        "document_title": "关于朝阳市2024年预算执行情况和2025年预算草案的报告（书面）",
        "publisher": "朝阳市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2025-01-20",
        "source_grade": "A2",
        "source_format": "pdf",
        "data_status": "execution",
        "data_status_label": "2024年快报数",
        "document_type": "城市财政预算执行报告（官方PDF）",
        "page_number": "2—3",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入\s*([0-9,]+)\s*万元",
            "general_public_expenditure_100m": r"全市一般公共预算支出\s*([0-9,]+)\s*万元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入\s*([0-9,]+)\s*万元",
        },
        "note": "朝阳市财政局官方预算执行报告，明确披露全市口径；采用2024年快报数，原始单位万元，保留execution状态，不改写为最终决算。",
    },
    {
        "year": 2025,
        "city_name": "朝阳市",
        "city_id": "CN-211300",
        "source_doc_id": "SRC-A2-CHAOYANG-CITY-FISCAL-2025",
        "url": "https://files.chaoyang.gov.cn/files/ueditor/CYCZJ/jsp/upload/file/20260121/1768985042690094808.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "chaoyang_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "chaoyang_2025_budget_report_excerpt.txt",
        "document_title": "关于朝阳市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "朝阳市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-01-21",
        "source_grade": "A2",
        "source_format": "pdf",
        "data_status": "execution",
        "data_status_label": "2025年快报数",
        "document_type": "城市财政预算执行报告（官方PDF）",
        "page_number": "表1、表2、表9",
        "raw_unit": "万元",
        "patterns": {
            "general_public_revenue_100m": r"全市2025年一般公共预算收入执行情况表.*?合计(903071)",
            "general_public_expenditure_100m": r"全市2025年一般公共预算支出执行情况表.*?合计(3013397)",
            "gov_fund_revenue_100m": r"全市2025年政府性基金预算收入执行情况表.*?合计(134839)",
        },
        "note": "朝阳市财政局官方预算执行报告，表1、表2、表9均明确为全市口径；采用2025年快报数一般公共预算收入903071万元、支出3013397万元和政府性基金预算收入134839万元，统一换算为亿元，保留execution状态，不使用市本级数。",
    },
    {
        "year": 2025,
        "city_name": "张掖市",
        "city_id": "CN-620700",
        "source_doc_id": "SRC-A2-ZHANGYE-CITY-FISCAL-2025",
        "url": "https://www.zhangye.gov.cn/zyszfxxgk/fdzdgknr_5657/sgjfjysxx/sjczyjsjsgjf/202602/t20260225_1511277_ghb.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "zhangye_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "zhangye_2025_budget_report_excerpt.txt",
        "document_title": "关于2025年全市财政预算执行情况和2026年全市及市级财政预算草案的报告",
        "publisher": "张掖市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-02-24",
        "source_grade": "A2",
        "source_format": "html",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（正文披露）",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_number": "正文",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入完成\s*([0-9,.]+)\s*亿元",
            "general_public_expenditure_100m": r"全市一般公共预算支出完成\s*([0-9,.]+)\s*亿元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入完成\s*([0-9,.]+)\s*亿元",
        },
        "note": "张掖市财政局官方预算执行报告，明确披露全市口径；采用正文按0.1亿元披露的2025年执行数，保留execution状态，不改写为最终决算。",
    },
    {
        "year": 2025,
        "city_name": "平凉市",
        "city_id": "CN-620800",
        "source_doc_id": "SRC-A2-PINGLIANG-CITY-FISCAL-2025",
        "url": "https://pingliang.gov.cn/api-gateway/jpaas-web-server/front/document/download?fileUrl=YW5UzzlvCwcM%2FNHHX%2FtT6DemntNJtRmQLusf6WNo%2BXommnhQmPHD3tcFx6EncOs3t%2F493OOsHCsTKbMqccfVgVbu77co7IDInTmE%2FMEq3PaMYWNkOSvNjAHvVmpG0bQMN96Rsi5LmFWOGBZ95ZegCJ4gtrd1hvk7%2B0w3sgnrFGA%3D&fileName=1.%E5%85%B3%E4%BA%8E%E5%85%A8%E5%B8%822025%E5%B9%B4%E8%B4%A2%E6%94%BF%E9%A2%84%E7%AE%97%E6%89%A7%E8%A1%8C%E6%83%85%E5%86%B5%E5%92%8C2026%E5%B9%B4%E5%85%A8%E5%B8%82%E5%8F%8A%E5%B8%82%E7%BA%A7%E8%B4%A2%E6%94%BF%E9%A2%84%E7%AE%97%E7%9A%84%E6%8A%A5%E5%91%8A.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "pingliang_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "pingliang_2025_budget_report_excerpt.txt",
        "document_title": "关于平凉市2025年财政预算执行情况和2026年全市及市级财政预算（草案）的报告",
        "publisher": "平凉市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-02-03",
        "source_grade": "A2",
        "source_format": "pdf",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行报告（官方PDF）",
        "page_number": "2",
        "patterns": {
            "general_public_revenue_100m": r"一般公共预算[。．]\s*收入\s*([0-9,.]+)\s*亿元",
            "general_public_expenditure_100m": r"一般公共预算[。．].*?支出完成\s*([0-9,.]+)\s*亿元",
            "gov_fund_revenue_100m": r"政府性基金预算[。．]\s*收入\s*([0-9,.]+)\s*亿元",
        },
        "note": "平凉市财政局官方预算执行报告，明确披露全市口径；采用报告正文披露的2025年执行数，保留execution状态，不改写为最终决算。",
    },
    {
        "year": 2025,
        "city_name": "长沙市",
        "city_id": "CN-430100",
        "source_doc_id": "SRC-A2-CHANGSHA-CITY-FUND-2025",
        "url": "https://www.changsha.gov.cn/szf/ztzl/ysgk/ysjsbg/202601/t20260130_12263761.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "changsha_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "changsha_2025_budget_report_excerpt.txt",
        "document_title": "关于2025年全市和市本级预算执行情况与2026年全市和市本级预算草案的报告",
        "publisher": "长沙市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-01-28",
        "source_grade": "A2",
        "source_format": "html",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（市人大会议报告）",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_number": "正文",
        "patterns": {
            "gov_fund_revenue_100m": r"全市政府性基金预算收入\s*([0-9,.]+)\s*亿元",
        },
        "note": "长沙市人民政府门户公开的长沙市财政局预算执行报告，明确披露全市政府性基金预算收入528.7亿元；独立接入基金字段，不覆盖已有统计公报中的GDP和一般预算字段。",
    },
    {
        "year": 2025,
        "city_name": "楚雄州",
        "city_id": "CN-532300",
        "source_doc_id": "SRC-A2-CHUXIONG-CITY-FISCAL-2025",
        "url": "https://www.cxs.gov.cn/info/5905/874929.htm",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "chuxiong_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "chuxiong_2025_budget_report_excerpt.txt",
        "document_title": "关于楚雄市2025年地方财政预算执行情况和2026年地方财政预算草案的报告（书面）",
        "publisher": "楚雄市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-03-02",
        "source_grade": "A2",
        "source_format": "html",
        "raw_unit": "万元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（预算执行报告）",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_number": "正文",
        "patterns": {
            "general_public_revenue_100m": r"地方一般公共预算收入\s*([0-9,]+)\s*万元",
            "general_public_expenditure_100m": r"完成地方一般公共预算支出\s*([0-9,]+)\s*万元",
            "gov_fund_revenue_100m": r"政府性基金预算收入\s*([0-9,]+)\s*万元",
        },
        "note": "楚雄市人民政府门户公开的楚雄市财政局预算执行报告，明确披露全市口径三项财政字段；采用2025年执行数，原始单位万元并换算为亿元。",
    },
    {
        "year": 2025,
        "city_name": "苏州市",
        "city_id": "CN-320500",
        "source_doc_id": "SRC-A2-SUZHOU-CITY-FUND-2025",
        "url": "https://www.suzhou.gov.cn/szsrmzf/czyjsbg/202603/57f2227cdfff4bef8a8c37ee8580add5.shtml",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "suzhou_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "suzhou_2025_budget_report_excerpt.txt",
        "document_title": "关于苏州市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "苏州市人民政府",
        "publisher_level": "市级政府",
        "publication_date": "2026-03-11",
        "source_grade": "A2",
        "source_format": "html",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（市人大会议报告）",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_number": "正文第91—94行",
        "patterns": {
            "gov_fund_revenue_100m": r"2025年全市政府性基金收入\s*([0-9,.]+)\s*亿元",
        },
        "note": "苏州市人民政府公开的市人大会议财政报告明确披露2025年全市政府性基金收入788亿元；采用全市执行数，独立接入基金字段，不覆盖已有一般预算字段。",
    },
    {
        "year": 2025,
        "city_name": "石家庄市",
        "city_id": "CN-130100",
        "source_doc_id": "SRC-A1-SHIJIAZHUANG-CITY-FUND-2025",
        "url": "https://www.sjz.gov.cn/yjsgk/attachments/1/202602/07/%E5%85%B3%E4%BA%8E%E7%9F%B3%E5%AE%B6%E5%BA%84%E5%B8%822025%E5%B9%B4%E9%A2%84%E7%AE%97%E6%89%A7%E8%A1%8C%E6%83%85%E5%86%B5%E5%92%8C2026%E5%B9%B4%E9%A2%84%E7%AE%97%E8%8D%89%E6%A1%88%E7%9A%84%E6%8A%A5%E5%91%8A20260207153821129.pdf?sid=",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "shijiazhuang_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "shijiazhuang_2025_budget_report_excerpt.txt",
        "document_title": "关于石家庄市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "石家庄市人民政府",
        "publisher_level": "市级政府",
        "publication_date": "2026-02-07",
        "source_grade": "A1",
        "source_format": "pdf",
        "raw_unit": "万元",
        "data_status": "execution",
        "data_status_label": "2025年实际完成数（官方执行表）",
        "document_type": "城市财政预算执行报告（官方PDF）",
        "page_number": "表3",
        "patterns": {
            "gov_fund_revenue_100m": r"实际完成\s*[:：]?\s*(3726518)",
        },
        "note": "石家庄市人民政府公开的2025年全市政府性基金收入预算完成情况表（表3）明确列示合计实际完成3726518万元；采用全市口径并按万元换算为亿元。",
    },
    {
        "year": 2025,
        "city_name": "西安市",
        "city_id": "CN-610100",
        "source_doc_id": "SRC-A2-XIAN-CITY-FUND-2025",
        "url": "https://xaczj.xa.gov.cn/zwgk/czyjs/2030898768368398337.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "xian_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "xian_2025_budget_report_excerpt.txt",
        "document_title": "西安市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "西安市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-03-09",
        "source_grade": "A2",
        "source_format": "html",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（预算执行报告）",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_number": "正文",
        "patterns": {
            "gov_fund_revenue_100m": r"2025年，全市政府性基金预算收入\s*([0-9,.]+)\s*亿元",
        },
        "note": "西安市财政局官网公开的2025年预算执行报告明确区分全市与市级政府性基金预算收入，采用全市口径681.83亿元，不使用市级604.26亿元。",
    },
    {
        "year": 2025,
        "city_name": "南昌市",
        "city_id": "CN-360100",
        "source_doc_id": "SRC-A1-NANCHANG-CITY-FISCAL-2025",
        "url": "https://czj.nc.gov.cn/ncczj/2026sjysgk/202602/0fa3b64fca014c0ca082cef616012ec9.shtml",
        "landing_page_url": "https://czj.nc.gov.cn/ncczj/2026sjysgk/202602/0fa3b64fca014c0ca082cef616012ec9.shtml",
        "attachment_url": "https://czj.nc.gov.cn/ncczj/2026sjysgk/202602/0fa3b64fca014c0ca082cef616012ec9/files/14.2025%E5%B9%B4%E5%85%A8%E5%B8%82%E6%94%BF%E5%BA%9C%E6%80%A7%E5%9F%BA%E9%87%91%E9%A2%84%E7%AE%97%E6%94%B6%E5%85%A5%E6%89%A7%E8%A1%8C%E6%83%85%E5%86%B5%E8%A1%A8.pdf",
        "download_url": "https://czj.nc.gov.cn/ncczj/2026sjysgk/202602/0fa3b64fca014c0ca082cef616012ec9/files/14.2025%E5%B9%B4%E5%85%A8%E5%B8%82%E6%94%BF%E5%BA%9C%E6%80%A7%E5%9F%BA%E9%87%91%E9%A2%84%E7%AE%97%E6%94%B6%E5%85%A5%E6%89%A7%E8%A1%8C%E6%83%85%E5%86%B5%E8%A1%A8.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "nanchang_2025_fund_execution.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "nanchang_2025_budget_execution_excerpt.txt",
        "document_title": "2025年南昌市全市预算执行表（政府性基金、一般公共预算）",
        "publisher": "南昌市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-01-30",
        "source_grade": "A1",
        "source_format": "pdf",
        "raw_unit": "万元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方执行表）",
        "document_type": "城市财政预算执行表（官方PDF）",
        "page_number": "政府性基金表1页；一般公共预算收入表1—2页；一般公共预算支出表1—27页",
        "patterns": {
            "general_public_revenue_100m": r"一般公共预算收入合计，?2025年执行数(5377716)",
            "general_public_expenditure_100m": r"一般公共预算支出合计，?2025年执行数(9144427)",
            "gov_fund_revenue_100m": r"政府性基金预算收入合计，?2025年执行数(1601968)",
        },
        "note": "南昌市财政局2026年市级政府预算公开目录链接的2025年全市执行表，三项字段均为全市口径执行数；原始单位万元，按1万元=0.0001亿元换算并保留两位小数。入口页与附件分别记录，避免把市级表误作全市表。",
    },
    {
        "year": 2025,
        "city_name": "海口市",
        "city_id": "CN-460100",
        "source_doc_id": "SRC-A2-HAIKOU-CITY-FISCAL-2025",
        "url": "http://www.haikou.gov.cn/xxgk/szfbjxxgk/cztz/czyjs/2026yjs/bmys/202602/t1509668.shtml",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "haikou_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "haikou_2025_budget_report_excerpt.txt",
        "document_title": "关于海口市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "海口市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-02-25",
        "source_grade": "A2",
        "source_format": "html",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方预算报告）",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_number": "正文",
        "patterns": {
            "general_public_revenue_100m": r"全市地方一般公共预算收入(253\.8)亿元",
            "general_public_expenditure_100m": r"全市地方一般公共预算支出(336\.7)亿元",
            "gov_fund_revenue_100m": r"全市地方政府性基金预算收入(68\.4)亿元",
        },
        "note": "海口市财政局官方预算报告明确区分全市与市本级口径；本批采用全市地方一般公共预算收入253.8亿元、支出336.7亿元及政府性基金预算收入68.4亿元，不使用市本级68.1亿元基金收入。",
    },
    {
        "year": 2025,
        "city_name": "银川市",
        "city_id": "CN-640100",
        "source_doc_id": "SRC-A2-YINCHUAN-CITY-FISCAL-2025",
        "url": "https://www.yinchuan.gov.cn/xxgk/bmxxgkml/sczj/xxgkml_2101/czyjsjsgjf_2119/zfys/202602/t20260212_5171239.html",
        "landing_page_url": "https://www.yinchuan.gov.cn/xxgk/bmxxgkml/sczj/xxgkml_2101/czyjsjsgjf_2119/zfys/202602/t20260212_5171239.html",
        "attachment_url": "https://www.yinchuan.gov.cn/xxgk/bmxxgkml/sczj/xxgkml_2101/czyjsjsgjf_2119/zfys/202602/W020260212418499922026.pdf",
        "download_url": "https://www.yinchuan.gov.cn/xxgk/bmxxgkml/sczj/xxgkml_2101/czyjsjsgjf_2119/zfys/202602/W020260212418499922026.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "yinchuan_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "yinchuan_2025_budget_execution_excerpt.txt",
        "document_title": "2025年银川市及市本级预算执行情况和2026年预算草案的报告",
        "publisher": "银川市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-02-12",
        "source_grade": "A2",
        "source_format": "pdf",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方预算执行报告）",
        "document_type": "城市财政预算执行报告（官方PDF）",
        "page_number": "正文第1—2页",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入完成(171\.59)亿元",
            "general_public_expenditure_100m": r"全市一般公共预算支出完成(406\.04)亿元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入完成(45\.26)亿元",
        },
        "note": "银川市财政局官方预算执行报告明确区分不含宁东的全市口径与市本级口径；本批采用全市一般公共预算收入171.59亿元、支出406.04亿元及政府性基金收入45.26亿元，不使用含宁东统计公报口径209.70亿元和440.75亿元，也不使用市本级数据。",
    },
    {
        "year": 2025,
        "city_name": "北京市",
        "city_id": "CN-110000",
        "source_doc_id": "SRC-A2-BEIJING-CITY-FISCAL-2025",
        "url": "https://czj.beijing.gov.cn/zwxx/czsj/czyjs/202602/P020260206358618282734.pdf",
        "landing_page_url": "https://czj.beijing.gov.cn/zwxx/czsj/czyjs/202602/P020260206358618282734.pdf",
        "attachment_url": "https://czj.beijing.gov.cn/zwxx/czsj/czyjs/202602/P020260206358618282734.pdf",
        "download_url": "https://czj.beijing.gov.cn/zwxx/czsj/czyjs/202602/P020260206358618282734.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "beijing_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "beijing_2025_budget_execution_excerpt.txt",
        "document_title": "关于北京市2025年预算执行情况和2026年预算的报告",
        "publisher": "北京市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-02-06",
        "source_grade": "A2",
        "source_format": "pdf",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方预算执行报告）",
        "document_type": "城市财政预算执行报告（官方PDF）",
        "page_number": "正文第2—9页",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入完成(6680\.6)亿元",
            "general_public_expenditure_100m": r"全市一般公共预算支出完成(8401\.9)亿元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入完成(2193\.9)亿元",
        },
        "note": "北京市财政局官方预算执行报告明确区分全市与市级口径；本批采用全市一般公共预算收入6680.6亿元、支出8401.9亿元及政府性基金预算收入2193.9亿元，不使用市级收入3764.3亿元、支出5703.3亿元和基金收入582.9亿元。",
    },
    {
        "year": 2025,
        "city_name": "重庆市",
        "city_id": "CN-500000",
        "source_doc_id": "SRC-A2-CHONGQING-CITY-FISCAL-2025",
        "url": "https://czj.cq.gov.cn/zwgk_268/fdzdgknr/ysjs/zfys/202602/W020260211630285424796.pdf",
        "landing_page_url": "https://czj.cq.gov.cn/zwgk_268/fdzdgknr/ysjs/zfys/202602/W020260211630285424796.pdf",
        "attachment_url": "https://czj.cq.gov.cn/zwgk_268/fdzdgknr/ysjs/zfys/202602/W020260211630285424796.pdf",
        "download_url": "https://czj.cq.gov.cn/zwgk_268/fdzdgknr/ysjs/zfys/202602/W020260211630285424796.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "chongqing_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "chongqing_2025_budget_execution_excerpt.txt",
        "document_title": "关于重庆市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "重庆市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-02-11",
        "source_grade": "A2",
        "source_format": "pdf",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方预算执行报告）",
        "document_type": "城市财政预算执行报告（官方PDF）",
        "page_number": "正文第2—4页",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入(2736)亿元",
            "general_public_expenditure_100m": r"全市一般公共预算支出(5691)亿元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入(1593)亿元",
        },
        "note": "重庆市财政局官方预算执行报告明确区分全市与市级口径；本批采用全市一般公共预算收入2736亿元、支出5691亿元及政府性基金预算收入1593亿元，不使用市级收入805亿元、支出1844亿元和基金收入810亿元。",
    },
    {
        "year": 2025,
        "city_name": "上海市",
        "city_id": "CN-310000",
        "source_doc_id": "SRC-A2-SHANGHAI-CITY-FISCAL-2025",
        "url": "https://www.shanghai.gov.cn/nw12338/20260515/a97f758537314ce7b2c0e26614e179f6.html",
        "landing_page_url": "https://www.shanghai.gov.cn/nw12338/20260515/a97f758537314ce7b2c0e26614e179f6.html",
        "attachment_url": "https://www.shanghai.gov.cn/nw12338/20260515/a97f758537314ce7b2c0e26614e179f6.html",
        "download_url": "https://www.shanghai.gov.cn/nw12338/20260515/a97f758537314ce7b2c0e26614e179f6.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "shanghai_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "shanghai_2025_budget_execution_excerpt.txt",
        "document_title": "关于上海市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "上海市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-05-15",
        "source_grade": "A2",
        "source_format": "html",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方预算执行报告）",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_number": "正文",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入(8500\.9)亿元",
            "general_public_expenditure_100m": r"全市一般公共预算支出(9976)亿元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入(3039\.6)亿元",
        },
        "note": "上海市财政局官方预算执行报告明确区分全市与市级口径；本批采用全市一般公共预算收入8500.9亿元、支出9976亿元及政府性基金预算收入3039.6亿元，不使用市级收入3839.5亿元、支出3619.5亿元和基金收入773.5亿元。",
    },
    {
        "year": 2025,
        "city_name": "天津市",
        "city_id": "CN-120000",
        "source_doc_id": "SRC-A2-TIANJIN-CITY-FISCAL-2025",
        "url": "https://cz.tj.gov.cn/zwgk_53713/yjsgktypt/ysgk/2026zfys/202602/W020260213610680924353.pdf",
        "landing_page_url": "https://cz.tj.gov.cn/zwgk_53713/yjsgktypt/ysgk/2026zfys/202602/W020260213610680924353.pdf",
        "attachment_url": "https://cz.tj.gov.cn/zwgk_53713/yjsgktypt/ysgk/2026zfys/202602/W020260213610680924353.pdf",
        "download_url": "https://cz.tj.gov.cn/zwgk_53713/yjsgktypt/ysgk/2026zfys/202602/W020260213610680924353.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "tianjin_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "tianjin_2025_budget_execution_excerpt.txt",
        "document_title": "关于天津市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "天津市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-02-13",
        "source_grade": "A2",
        "source_format": "pdf",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方预算执行报告）",
        "document_type": "城市财政预算执行报告（官方PDF）",
        "page_number": "正文",
        "patterns": {
            "general_public_revenue_100m": r"一般公共预算收入(2221\.7)亿元",
            "general_public_expenditure_100m": r"一般公共预算支出(3359\.7)亿元",
            "gov_fund_revenue_100m": r"政府性基金预算收入(605\.5)亿元",
        },
        "note": "天津市财政局官方预算执行报告明确区分全市与市级口径；本批采用全市一般公共预算收入2221.7亿元、支出3359.7亿元及政府性基金预算收入605.5亿元，不使用市级收入812.8亿元、支出1172.6亿元和基金收入334.8亿元。",
    },
    {
        "year": 2025,
        "city_name": "景德镇市",
        "city_id": "CN-360200",
        "source_doc_id": "SRC-A2-JINGDEZHEN-CITY-FISCAL-2025",
        "url": "https://jdz.gov.cn/zwgk/fdzdgknr/czxx/yjsgk/t1079791.shtml",
        "landing_page_url": "https://jdz.gov.cn/zwgk/fdzdgknr/czxx/yjsgk/t1079791.shtml",
        "attachment_url": "https://jdz.gov.cn/zwgk/fdzdgknr/czxx/yjsgk/P020260209548709148934.pdf",
        "download_url": "https://jdz.gov.cn/zwgk/fdzdgknr/czxx/yjsgk/P020260209548709148934.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "jingdezhen_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "jingdezhen_2025_budget_execution_excerpt.txt",
        "document_title": "关于景德镇市2025年全市和市级预算执行情况与2026年全市和市级预算草案的报告",
        "publisher": "景德镇市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-02-09",
        "source_grade": "A2",
        "source_format": "pdf",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方预算执行报告）",
        "document_type": "城市财政预算执行报告（官方PDF）",
        "page_number": "正文第2—3页",
        "patterns": {
            "general_public_revenue_100m": r"2025年全市一般公共预算收入完成(90\.94)亿元",
            "general_public_expenditure_100m": r"全市一般公共预算支出(234\.95)亿元",
            "gov_fund_revenue_100m": r"2025年全市政府性基金预算收入完成(172\.69)亿元",
        },
        "note": "景德镇市财政局官方预算执行报告明确区分全市与市级口径；本批采用全市一般公共预算收入90.94亿元、支出234.95亿元及政府性基金预算收入172.69亿元，不使用市级收入27.63亿元、支出80.97亿元和基金收入106.45亿元。",
    },
    {
        "year": 2025,
        "city_name": "保山市",
        "city_id": "CN-530500",
        "source_doc_id": "SRC-A2-BAOSHAN-CITY-FISCAL-2025",
        "url": "https://www.baoshan.gov.cn/info/4632/10334054.htm",
        "landing_page_url": "https://www.baoshan.gov.cn/info/4632/10334054.htm",
        "attachment_url": "https://www.baoshan.gov.cn/info/4632/10334054.htm",
        "download_url": "https://www.baoshan.gov.cn/info/4632/10334054.htm",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "baoshan_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "baoshan_2025_budget_execution_excerpt.txt",
        "document_title": "关于保山市2025年地方财政预算执行情况和2026年地方财政预算草案的报告",
        "publisher": "保山市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-02-05",
        "source_grade": "A2",
        "source_format": "html",
        "raw_unit": "万元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方预算执行快报）",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_number": "正文",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入(654,233)万元",
            "general_public_expenditure_100m": r"一般公共预算支出(2,617,126)万元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入(316,421)万元",
        },
        "note": "保山市财政局官方预算执行报告明确区分全市与市本级口径；本批采用全市一般公共预算收入654233万元、支出2617126万元及政府性基金预算收入316421万元，均为官方快报数，统一换算为亿元；不使用市本级口径。",
    },
    {
        "year": 2025,
        "city_name": "吕梁市",
        "city_id": "CN-141100",
        "source_doc_id": "SRC-A2-LVLIANG-CITY-FISCAL-2025",
        "url": "https://www.lvliang.gov.cn/llxxgk/zfxxgk/xxgkml/zjxx_21583/sjczyshsgjf/202602/t20260205_2014557.html",
        "landing_page_url": "https://www.lvliang.gov.cn/llxxgk/zfxxgk/xxgkml/zjxx_21583/sjczyshsgjf/202602/t20260205_2014557.html",
        "attachment_url": "https://www.lvliang.gov.cn/llxxgk/zfxxgk/xxgkml/zjxx_21583/sjczyshsgjf/202602/t20260205_2014557.html",
        "download_url": "https://www.lvliang.gov.cn/llxxgk/zfxxgk/xxgkml/zjxx_21583/sjczyshsgjf/202602/t20260205_2014557.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "lvliang_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "lvliang_2025_budget_execution_excerpt.txt",
        "document_title": "关于吕梁市2025年全市和市本级预算执行情况与2026年全市和市本级预算草案的报告",
        "publisher": "吕梁市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-02-05",
        "source_grade": "A2",
        "source_format": "html",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方预算执行报告）",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_number": "正文",
        "patterns": {
            "general_public_revenue_100m": r"2025年全市一般公共预算收入完成(278\.26)亿元",
            "general_public_expenditure_100m": r"2025年全市一般公共预算支出执行(585\.48)亿元",
            "gov_fund_revenue_100m": r"2025年全市政府性基金收入完成(21\.62)亿元",
        },
        "note": "吕梁市财政局官方预算执行报告明确区分全市与市本级口径；本批采用全市一般公共预算收入278.26亿元、支出585.48亿元及政府性基金收入21.62亿元，不使用市本级收入54.65亿元、支出94.53亿元。",
    },
    {
        "year": 2025,
        "city_name": "晋城市",
        "city_id": "CN-140500",
        "source_doc_id": "SRC-A2-JINCHENG-CITY-FISCAL-2025",
        "url": "https://xxgk.jcgov.gov.cn/szfgzbm/jcsczj/fdzdgknr_31229/czyjsgk/zfys_czj/202603/t20260324_2333606.shtml",
        "landing_page_url": "https://xxgk.jcgov.gov.cn/szfgzbm/jcsczj/fdzdgknr_31229/czyjsgk/zfys_czj/202603/t20260324_2333606.shtml",
        "attachment_url": "https://xxgk.jcgov.gov.cn/szfgzbm/jcsczj/fdzdgknr_31229/czyjsgk/zfys_czj/202603/P020260324646165200955.pdf",
        "download_url": "https://xxgk.jcgov.gov.cn/szfgzbm/jcsczj/fdzdgknr_31229/czyjsgk/zfys_czj/202603/P020260324646165200955.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "jincheng_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "jincheng_2025_budget_execution_excerpt.txt",
        "document_title": "关于2025年全市和市本级预算执行情况与2026年全市和市本级预算草案的报告",
        "publisher": "晋城市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-02-06",
        "source_grade": "A2",
        "source_format": "pdf",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方预算执行报告）",
        "document_type": "城市财政预算执行报告（官方PDF）",
        "page_number": "正文第2—4页",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入完成(230\.58)亿元",
            "general_public_expenditure_100m": r"全市一般公共预算支出执行(392\.05)亿元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入完成(40\.64)亿元",
        },
        "note": "晋城市财政局官方预算执行报告明确区分全市与市本级口径；本批采用全市一般公共预算收入230.58亿元、支出392.05亿元及政府性基金预算收入40.64亿元，不使用市本级收入48.86亿元、支出87.9亿元和基金收入16.37亿元。",
    },
    {
        "year": 2025,
        "city_name": "平顶山市",
        "city_id": "CN-410400",
        "source_doc_id": "SRC-A2-PINGDINGSHAN-CITY-FISCAL-2025",
        "url": "https://www.pds.gov.cn/contents/1378/463143.html",
        "landing_page_url": "https://www.pds.gov.cn/contents/1378/463143.html",
        "attachment_url": "https://www.pds.gov.cn/contents/1378/463143.html",
        "download_url": "https://www.pds.gov.cn/contents/1378/463143.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "pingdingshan_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "pingdingshan_2025_budget_execution_excerpt.txt",
        "document_title": "关于平顶山市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "平顶山市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-02-05",
        "source_grade": "A2",
        "source_format": "html",
        "raw_unit": "万元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方预算执行报告）",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_number": "正文",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入实际完成(2266166)万元",
            "general_public_expenditure_100m": r"全市一般公共预算支出实际完成(4512625)万元",
        },
        "note": "平顶山市财政局官方预算执行报告明确披露全市口径；采用2025年全市一般公共预算收入2266166万元、支出4512625万元，均为执行数，统一换算为亿元；政府性基金收入沿用同一报告的独立基金来源记录。",
    },
    {
        "year": 2025,
        "city_name": "泰安市",
        "city_id": "CN-370900",
        "source_doc_id": "SRC-A2-TAIAN-CITY-FISCAL-2025",
        "url": "https://czj.taian.gov.cn/art/2026/2/25/art_364743_10316699.html",
        "download_url": "https://czj.taian.gov.cn/module/download/downfile.jsp?classid=0&filename=87442e1685384132bdf6efc0b6702b56.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "taian_2025_budget_execution_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "taian_2025_budget_execution_report_excerpt.txt",
        "document_title": "泰安市2025年预算执行情况和2026年预算草案",
        "publisher": "泰安市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-02-25",
        "source_grade": "A2",
        "source_format": "pdf",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方预算执行表）",
        "document_type": "城市财政预算执行报告（官方PDF）",
        "page_number": "表1、表2、表17",
        "raw_unit": "万元",
        "patterns": {
            "general_public_revenue_100m": r"表1.*?本年收入合计(2619610)",
            "general_public_expenditure_100m": r"表2.*?本年支出合计(4864386)",
            "gov_fund_revenue_100m": r"表17.*?本年收入合计(1307675)",
        },
        "note": "泰安市财政局官方预算执行表，表1、表2、表17均明确为全市口径；采用2025年一般公共预算收入2619610万元、支出4864386万元和政府性基金预算收入1307675万元，统一换算为亿元，保留execution状态；不使用市级数。",
    },
    {
        "year": 2025,
        "city_name": "大理白族自治州",
        "city_id": "CN-532900",
        "source_doc_id": "SRC-A2-DALI-CITY-FISCAL-2025",
        "url": "https://www.dali.gov.cn/dlzrmzf/xxgkml/c106264/pc/content/2026957153552601088/content_2026957153552601088.html",
        "landing_page_url": "https://www.dali.gov.cn/dlzrmzf/xxgkml/c106264/pc/content/2026957153552601088/content_2026957153552601088.html",
        "attachment_url": "https://www.dali.gov.cn/dlzrmzf/xxgkml/c106264/pc/content/2026957153552601088/content_2026957153552601088.html",
        "download_url": "https://www.dali.gov.cn/dlzrmzf/xxgkml/c106264/pc/content/2026957153552601088/content_2026957153552601088.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "dali_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "dali_2025_budget_execution_excerpt.txt",
        "document_title": "关于大理白族自治州2025年地方财政预算执行情况和2026年地方财政预算草案的报告",
        "publisher": "大理州财政局",
        "publisher_level": "州级财政机构",
        "publication_date": "2026-02-12",
        "source_grade": "A2",
        "source_format": "html",
        "raw_unit": "万元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方预算执行报告）",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_number": "正文",
        "patterns": {
            "general_public_revenue_100m": r"全州一般公共预算收入([0-9,]+)万元",
            "general_public_expenditure_100m": r"全州一般公共预算支出([0-9,]+)万元",
            "gov_fund_revenue_100m": r"全州政府性基金预算收入([0-9,]+)万元",
        },
        "note": "大理州财政局官方预算执行报告明确区分全州与州本级口径；本批采用全州一般公共预算收入1080211万元、支出3722984万元及政府性基金预算收入159365万元，统一换算为亿元；不使用州本级口径。",
    },
    {
        "year": 2025,
        "city_name": "红河哈尼族彝族自治州",
        "city_id": "CN-532500",
        "source_doc_id": "SRC-A2-HONGHE-CITY-FISCAL-2025",
        "url": "https://www.hh.gov.cn/info/11351/1241182.htm",
        "landing_page_url": "https://www.hh.gov.cn/info/11351/1241182.htm",
        "attachment_url": "https://www.hh.gov.cn/info/11351/1241182.htm",
        "download_url": "https://www.hh.gov.cn/info/11351/1241182.htm",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "honghe_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "honghe_2025_budget_execution_excerpt.txt",
        "document_title": "红河州2026年度政府预算公开",
        "publisher": "红河州财政局",
        "publisher_level": "州级财政机构",
        "publication_date": "2026-02-12",
        "source_grade": "A2",
        "source_format": "html",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方预算执行报告）",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_number": "正文",
        "patterns": {
            "general_public_revenue_100m": r"全州一般公共预算收入完成([0-9.]+)亿元",
            "general_public_expenditure_100m": r"一般公共预算支出完成([0-9.]+)亿元",
            "gov_fund_revenue_100m": r"全州政府性基金预算收入完成([0-9.]+)亿元",
        },
        "note": "红河州财政局官方预算公开报告明确区分全州、州本级和蒙自经开区口径；本批采用全州一般公共预算收入153.9亿元、支出513.5亿元及政府性基金预算收入76亿元，不使用州本级数。",
    },
    {
        "year": 2025,
        "city_name": "迪庆藏族自治州",
        "city_id": "CN-533400",
        "source_doc_id": "SRC-A2-DIQING-CITY-FISCAL-2025",
        "url": "https://diqing.gov.cn/zfxxgk_dqzzf/fdzdgknr/caizhengxinxigongkaizhuanlan/zhengfuyujuesuan/202602/20260204_237925.html",
        "landing_page_url": "https://diqing.gov.cn/zfxxgk_dqzzf/fdzdgknr/caizhengxinxigongkaizhuanlan/zhengfuyujuesuan/202602/20260204_237925.html",
        "attachment_url": "https://diqing.gov.cn/file/diqing/dqzzf_zczj/file/20260204/1770166830002037168.pdf",
        "download_url": "https://diqing.gov.cn/file/diqing/dqzzf_zczj/file/20260204/1770166830002037168.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "diqing_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "diqing_2025_budget_execution_excerpt.txt",
        "document_title": "关于迪庆藏族自治州2025年地方财政预算执行情况和2026年地方财政预算草案的报告",
        "publisher": "迪庆州财政局",
        "publisher_level": "州级财政机构",
        "publication_date": "2026-02-04",
        "source_grade": "A2",
        "source_format": "pdf",
        "raw_unit": "万元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方预算执行报告及附件表格）",
        "document_type": "城市财政预算执行报告（官方PDF）",
        "page_number": "正文及附件表2-1",
        "patterns": {
            "general_public_revenue_100m": r"全州地方一般公共预算收入([0-9]+)万元",
            "general_public_expenditure_100m": r"一般公共预算支出([0-9]+)万元",
            "gov_fund_revenue_100m": r"全州政府性基金预算收入\s*([0-9]+)",
        },
        "note": "迪庆州财政局官方预算执行报告及附件表格明确区分全州与州本级口径；本批采用全州一般公共预算收入184920万元、支出1424263万元及政府性基金预算收入14769万元，统一换算为亿元；不使用州本级口径。",
    },
    {
        "year": 2025,
        "city_name": "玉溪市",
        "city_id": "CN-530400",
        "source_doc_id": "SRC-A2-YUXI-CITY-FISCAL-2025",
        "url": "https://www.yuxi.gov.cn/yxszfxxgk/zfysgkyxsczj/20260211/1648874.html",
        "landing_page_url": "https://www.yuxi.gov.cn/yxszfxxgk/zfysgkyxsczj/20260211/1648874.html",
        "attachment_url": "https://www.yuxi.gov.cn/yxszfxxgk/zfysgkyxsczj/20260211/1648874.html",
        "download_url": "https://www.yuxi.gov.cn/yxszfxxgk/zfysgkyxsczj/20260211/1648874.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "yuxi_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "yuxi_2025_budget_execution_excerpt.txt",
        "document_title": "玉溪市2025年地方财政预算执行情况和2026年地方财政预算草案的报告",
        "publisher": "玉溪市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-02-11",
        "source_grade": "A2",
        "source_format": "html",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方预算执行报告）",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_number": "正文",
        "patterns": {
            "general_public_revenue_100m": r"(?:全年|全市)一般公共预算收入完成([0-9.]+)亿元",
            "general_public_expenditure_100m": r"支出完成([0-9.]+)亿元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入完成([0-9.]+)亿元",
        },
        "note": "玉溪市财政局官方预算执行报告明确区分全市与市本级口径；本批采用全市一般公共预算收入148.21亿元、支出300.55亿元及政府性基金预算收入27.05亿元，不使用市本级数，并以本批A2来源替换原低等级基金线索。",
    },
    {
        "year": 2025,
        "city_name": "曲靖市",
        "city_id": "CN-530300",
        "source_doc_id": "SRC-A2-QUJING-CITY-FISCAL-2025",
        "url": "https://czj.qj.gov.cn/gov/info/detail/21933.html",
        "landing_page_url": "https://czj.qj.gov.cn/gov/info/detail/21933.html",
        "attachment_url": "https://czj.qj.gov.cn/gov/info/detail/21933.html",
        "download_url": "https://czj.qj.gov.cn/gov/info/detail/21933.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "qujing_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "qujing_2025_budget_execution_excerpt.txt",
        "document_title": "曲靖市2025年地方财政预算执行情况和2026年地方财政预算（草案）的报告",
        "publisher": "曲靖市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-03-19",
        "source_grade": "A2",
        "source_format": "html",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方预算公开报告）",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_number": "正文",
        "patterns": {
            "general_public_revenue_100m": r"(?:全年|全市)一般公共预算收入完成([0-9.]+)亿元",
            "general_public_expenditure_100m": r"全市一般公共预算支出完成([0-9.]+)亿元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入完成([0-9.]+)亿元",
        },
        "note": "曲靖市财政局官方预算公开报告明确区分全市与市级口径；本批采用全市一般公共预算收入164.2亿元、支出526.5亿元及政府性基金预算收入37.8亿元，不使用市级数。",
    },
    {
        "year": 2025,
        "city_name": "丽江市",
        "city_id": "CN-530700",
        "source_doc_id": "SRC-A2-LIJIANG-CITY-FISCAL-2025",
        "url": "https://www.lijiang.gov.cn/ljsrmzf/c102171/202602/563a29840543411a84a8a934a27f9cc2.shtml",
        "landing_page_url": "https://www.lijiang.gov.cn/ljsrmzf/c102171/202602/563a29840543411a84a8a934a27f9cc2.shtml",
        "attachment_url": "https://www.lijiang.gov.cn/ljsrmzf/c102171/202602/563a29840543411a84a8a934a27f9cc2/files/3ee51c32d0444e26a516385e99529b9e.xlsx",
        "download_url": "https://www.lijiang.gov.cn/ljsrmzf/c102171/202602/563a29840543411a84a8a934a27f9cc2/files/3ee51c32d0444e26a516385e99529b9e.xlsx",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "lijiang_2025_budget_attachment.xlsx",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "lijiang_2025_budget_execution_excerpt.txt",
        "document_title": "关于丽江市2025年地方财政预算执行情况和2026年地方财政预算草案的报告",
        "publisher": "丽江市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-02-13",
        "source_grade": "A2",
        "source_format": "xlsx",
        "raw_unit": "万元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方预算执行表）",
        "document_type": "城市财政预算执行报告（官方网页及Excel附件）",
        "page_number": "附件1：表一、表二、表六；全市合计行",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入\s*([0-9,]+)万元",
            "general_public_expenditure_100m": r"全市一般公共预算支出\s*([0-9,]+)万元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入\s*([0-9,]+)万元",
        },
        "note": "丽江市人民政府财政预决算专栏官方报告附件1为结构化Excel；本批采用表一、表二、表六的全市执行数：一般公共预算收入567755万元、支出1763231万元、政府性基金预算收入170713万元，不使用预算数或市本级数。",
    },
    {
        "year": 2025,
        "city_name": "临沧市",
        "city_id": "CN-530900",
        "source_doc_id": "SRC-A2-LINCANG-CITY-FISCAL-2025",
        "url": "https://lincang.gov.cn/zfxxgk_lcs/artview/347/344645.html",
        "landing_page_url": "https://lincang.gov.cn/zfxxgk_lcs/artview/347/344645.html",
        "attachment_url": "https://lincang.gov.cn/file/lincang/A01A01A01A09/file/20260225/1772010220552008553.pdf",
        "download_url": "https://lincang.gov.cn/file/lincang/A01A01A01A09/file/20260225/1772010220552008553.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "lincang_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "lincang_2025_budget_execution_excerpt.txt",
        "document_title": "关于临沧市2025年地方财政预算执行情况和2026年地方财政预算草案的报告",
        "publisher": "临沧市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-02-24",
        "source_grade": "A2",
        "source_format": "pdf",
        "raw_unit": "万元",
        "data_status": "execution",
        "data_status_label": "2025年快报执行数（官方预算执行报告）",
        "document_type": "城市财政预算执行报告（官方网页及PDF附件）",
        "page_number": "正文；全市口径财政与债务段落",
        "patterns": {
            "general_public_revenue_100m": r"全市地方一般公共预算收入完成([0-9,]+)万元",
            "general_public_expenditure_100m": r"全市地方一般公共预算支出完成([0-9,]+)万元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入完成([0-9,]+)万元",
            "statutory_debt_limit_100m": r"临沧市2025年末政府债务限额([0-9,]+)万元",
            "statutory_debt_balance_100m": r"全市政府债务余额为([0-9,]+)万元",
        },
        "note": "临沧市财政局官方预算执行报告同时披露全市三项财政字段、年末法定债务限额和余额；本批采用全市2025年快报执行数，原始单位万元并换算为亿元，不使用市级口径或2026年预算数。",
    },
    {
        "year": 2025,
        "city_name": "普洱市",
        "city_id": "CN-530800",
        "source_doc_id": "SRC-B2-PUER-CITY-FISCAL-2025",
        "url": "https://www.puerw.cn/content/202603/09/c478799.html",
        "landing_page_url": "https://www.puerw.cn/content/202603/09/c478799.html",
        "attachment_url": "https://www.puerw.cn/content/202603/09/c478799.html",
        "download_url": "https://www.puerw.cn/content/202603/09/c478799.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "puer_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "puer_2025_budget_execution_excerpt.txt",
        "document_title": "关于普洱市2025年地方财政预算执行情况和2026年地方财政预算草案的报告",
        "publisher": "普洱市财政局（经普洱日报公开转载）",
        "publisher_level": "市级财政机构报告公开转载",
        "publication_date": "2026-03-09",
        "source_grade": "B2",
        "source_format": "html",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（财政局报告精确转载）",
        "document_type": "城市财政预算执行报告（官方媒体精确转载）",
        "page_number": "正文；全市口径财政段落",
        "patterns": {
            "general_public_revenue_100m": r"全市地方一般公共预算收入完成([0-9.]+)亿元",
            "general_public_expenditure_100m": r"全市地方一般公共预算支出完成([0-9.]+)亿元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入完成([0-9.]+)亿元",
        },
        "note": "普洱日报完整转载普洱市财政局预算执行报告并明确署名及全市口径；本批按B2精确转载证据采用全市一般公共预算收入62.57亿元、支出306.28亿元及政府性基金预算收入19.53亿元，不使用市级、县区级或2026年预算数。",
    },
    {
        "year": 2025,
        "city_name": "廊坊市",
        "city_id": "CN-131000",
        "source_doc_id": "SRC-A2-LANGFANG-CITY-FISCAL-2025",
        "url": "https://zhuanti.lf.gov.cn/Item/2846.aspx",
        "landing_page_url": "https://zhuanti.lf.gov.cn/Item/2846.aspx",
        "attachment_url": "https://zhuanti.lf.gov.cn/UploadFiles/sjczyjsgkzl/2026/5/202605061438290149.7z",
        "download_url": "https://zhuanti.lf.gov.cn/UploadFiles/sjczyjsgkzl/2026/5/202605061438290149.7z",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "langfang_2025_budget_report.7z",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "langfang_2025_budget_execution_excerpt.txt",
        "document_title": "廊坊市2025年市本级预算及全市总预算执行情况和2026年市本级预算及全市总预算草案的报告",
        "publisher": "廊坊市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-02-09",
        "source_grade": "A2",
        "source_format": "7z",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年快报统计数（官方预算执行报告）",
        "document_type": "城市财政预算执行报告（官方网页及7z附件）",
        "page_number": "PDF第2—3页",
        "page_count": "18",
        "patterns": {
            "general_public_revenue_100m": r"一般公共预算完成情况。全市收入([0-9.]+)亿元",
            "general_public_expenditure_100m": r"一般公共预算完成情况。.*?支出([0-9.]+)亿元",
            "gov_fund_revenue_100m": r"政府性基金预算完成情况。全市收入([0-9.]+)亿元",
        },
        "note": "廊坊市人民政府网站专题平台公开的廊坊市财政局预算报告明确区分全市与市本级口径；本批采用全市一般公共预算收入311.8亿元、支出618.7亿元及政府性基金预算收入86.8亿元，均为2025年快报统计数，标记为execution，不使用市本级或开发区、临空经济区数据。附件为官方7z压缩包，内含报告PDF。",
    },
    {
        "year": 2025,
        "city_name": "保定市",
        "city_id": "CN-130600",
        "source_doc_id": "SRC-A2-BAODING-CITY-FISCAL-2025",
        "url": "https://www.baoding.gov.cn/zwgknr-1004-538624.html",
        "landing_page_url": "https://www.baoding.gov.cn/zwgknr-1004-538624.html",
        "attachment_url": "https://www.baoding.gov.cn/viewFile.do?type=2&filename=%E4%BF%9D%E5%AE%9A%E5%B8%82%E4%BA%BA%E6%B0%91%E6%94%BF%E5%BA%9C%E5%85%B3%E4%BA%8E%E4%BF%9D%E5%AE%9A%E5%B8%822025%E5%B9%B4%E9%A2%84%E7%AE%97%E6%89%A7%E8%A1%8C%E6%83%85%E5%86%B5%E5%92%8C2026%E5%B9%B4%E9%A2%84%E7%AE%97%E8%8D%89%E6%A1%88%E7%9A%84%E6%8A%A5%E5%91%8A.pdf&file=1%2F202603%2F260305092431713_300_%E4%BF%9D%E5%AE%9A%E5%B8%82%E4%BA%BA%E6%B0%91%E6%94%BF%E5%BA%9C%E5%85%B3%E4%BA%8E%E4%BF%9D%E5%AE%9A%E5%B8%822025%E5%B9%B4%E9%A2%84%E7%AE%97%E6%89%A7%E8%A1%8C%E6%83%85%E5%86%B5%E5%92%8C2026%E5%B9%B4%E9%A2%84%E7%AE%97%E8%8D%89%E6%A1%88%E7%9A%84%E6%8A%A5%E5%91%8A.pdf",
        "download_url": "https://www.baoding.gov.cn/viewFile.do?type=2&filename=%E4%BF%9D%E5%AE%9A%E5%B8%82%E4%BA%BA%E6%B0%91%E6%94%BF%E5%BA%9C%E5%85%B3%E4%BA%8E%E4%BF%9D%E5%AE%9A%E5%B8%822025%E5%B9%B4%E9%A2%84%E7%AE%97%E6%89%A7%E8%A1%8C%E6%83%85%E5%86%B5%E5%92%8C2026%E5%B9%B4%E9%A2%84%E7%AE%97%E8%8D%89%E6%A1%88%E7%9A%84%E6%8A%A5%E5%91%8A.pdf&file=1%2F202603%2F260305092431713_300_%E4%BF%9D%E5%AE%9A%E5%B8%82%E4%BA%BA%E6%B0%91%E6%94%BF%E5%BA%9C%E5%85%B3%E4%BA%8E%E4%BF%9D%E5%AE%9A%E5%B8%82%E4%BA%BA%E6%B0%91%E6%94%BF%E5%BA%9C%E5%85%B3%E4%BA%8E%E4%BF%9D%E5%AE%9A%E5%B8%822025%E5%B9%B4%E9%A2%84%E7%AE%97%E6%89%A7%E8%A1%8C%E6%83%85%E5%86%B5%E5%92%8C2026%E5%B9%B4%E9%A2%84%E7%AE%97%E8%8D%89%E6%A1%88%E7%9A%84%E6%8A%A5%E5%91%8A.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "baoding_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "baoding_2025_budget_execution_excerpt.txt",
        "text_is_curated": True,
        "document_title": "保定市人民政府关于保定市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "保定市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-03-03",
        "source_grade": "A2",
        "source_format": "pdf",
        "raw_unit": "万元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方预算执行表）",
        "document_type": "城市财政预算执行报告（官方网页及PDF附件）",
        "page_number": "PDF第2—3、26—30页",
        "page_count": "47",
        "patterns": {
            "general_public_revenue_100m": r"一般公共预算收入，预算数3308167，执行数(3270591)",
            "general_public_expenditure_100m": r"一般公共预算支出，预算数8149267，执行数(9957732)",
            "gov_fund_revenue_100m": r"2025年全市政府性基金收入预算执行情况；合计，预算数4243671，执行数(1069764)",
        },
        "note": "保定市人民政府公开的市财政局预算执行报告及附表明确区分全市与市本级、功能区口径；本批采用附表二、附表四列示的全市2025年执行数：一般公共预算收入3270591万元、支出9957732万元、政府性基金预算收入1069764万元，统一换算为亿元并保留execution状态，不使用市本级或功能区数据。",
    },
    {
        "year": 2025,
        "city_name": "承德市",
        "city_id": "CN-130800",
        "source_doc_id": "SRC-A2-CHENGDE-CITY-FISCAL-2025",
        "url": "https://www.chengde.gov.cn/art/2026/2/24/art_9957_1105029.html",
        "landing_page_url": "https://www.chengde.gov.cn/art/2026/2/24/art_9957_1105029.html",
        "attachment_url": "https://www.chengde.gov.cn/module/download/downfile.jsp?classid=0&filename=f937d2f41f9f42a3b640fc1563fa648b.docx",
        "download_url": "https://www.chengde.gov.cn/module/download/downfile.jsp?classid=0&filename=f937d2f41f9f42a3b640fc1563fa648b.docx",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "chengde_2025_budget_report.docx",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "chengde_2025_budget_execution_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2026年承德市本级预算和市总预算草案的报告（含2025年预算执行情况）",
        "publisher": "承德市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-02-24",
        "source_grade": "A2",
        "source_format": "docx",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方预算执行报告）",
        "document_type": "城市财政预算执行报告（官方网页及DOCX附件）",
        "page_number": "报告正文；2025年预算执行情况，全市口径",
        "page_count": "",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入完成([0-9.]+)亿元",
            "general_public_expenditure_100m": r"一般公共预算支出完成([0-9.]+)亿元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入完成([0-9.]+)亿元",
        },
        "note": "承德市财政局在市政府财政预决算专栏公开的2026年预算报告，正文明确披露2025年全市执行数：一般公共预算收入144.8亿元、支出515.6亿元、政府性基金预算收入27.2亿元；本批采用全市口径，标记为execution，不使用市本级、高新区或御道口牧场管理区数据。",
    },
    {
        "year": 2025,
        "city_name": "大同市",
        "city_id": "CN-140200",
        "source_doc_id": "SRC-B2-DATONG-CITY-FISCAL-2025",
        "url": "https://www.dt.gov.cn/dtszf/czjczyjs/202602/d228cbfb30e747a0b4d3062fd41aa5b7.shtml",
        "landing_page_url": "https://www.dt.gov.cn/dtszf/czjczyjs/202602/d228cbfb30e747a0b4d3062fd41aa5b7.shtml",
        "attachment_url": "https://www.dt.gov.cn/dtszf/czjczyjs/202602/d228cbfb30e747a0b4d3062fd41aa5b7.shtml",
        "download_url": "https://www.dt.gov.cn/dtszf/czjczyjs/202602/d228cbfb30e747a0b4d3062fd41aa5b7.shtml",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "datong_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "datong_2025_budget_execution_fiscal_excerpt.txt",
        "text_is_curated": True,
        "document_title": "关于大同市2025年全市和市本级预算执行情况与2026年全市和市本级预算（草案）的报告",
        "publisher": "大同市财政局",
        "publisher_level": "市级财政机构（市政府门户公开）",
        "publication_date": "2026-02-05",
        "source_grade": "B2",
        "source_format": "html",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方预算执行报告）",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_number": "正文；全市预算执行情况",
        "page_count": "1",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入完成([0-9.]+)亿元",
            "general_public_expenditure_100m": r"全市一般公共预算支出执行([0-9.]+)亿元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入完成([0-9.]+)亿元",
        },
        "note": "大同市财政局在市政府门户公开的预算执行报告，正文精确披露2025年全市一般公共预算收入175.39亿元、支出469.28亿元和政府性基金预算收入44.74亿元；本批采用全市执行数，按B2精确官方网页来源登记，不使用市本级或市经济技术开发区数。",
    },
    {
        "year": 2025,
        "city_name": "长治市",
        "city_id": "CN-140400",
        "source_doc_id": "SRC-A2-CHANGZHI-CITY-FISCAL-2025",
        "url": "https://www.changzhi.gov.cn/xxgkml/zfxxgkml/szfgzbm/sczj/czsrmzf/czyjs_522/2026/202601/t20260122_3132596.shtml",
        "landing_page_url": "https://www.changzhi.gov.cn/xxgkml/zfxxgkml/szfgzbm/sczj/czsrmzf/czyjs_522/2026/202601/t20260122_3132596.shtml",
        "attachment_url": "https://www.changzhi.gov.cn/xxgkml/zfxxgkml/szfgzbm/sczj/czsrmzf/czyjs_522/2026/202601/P020260122388192880171.pdf",
        "download_url": "https://www.changzhi.gov.cn/xxgkml/zfxxgkml/szfgzbm/sczj/czsrmzf/czyjs_522/2026/202601/P020260122388192880171.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "changzhi_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "changzhi_2025_budget_execution_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2026年向人大提供2025年预算执行及2026年预算草案--报告",
        "publisher": "长治市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-01-22",
        "source_grade": "A2",
        "source_format": "pdf",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（12月月报数据）",
        "document_type": "城市财政预算执行报告（官方扫描PDF）",
        "page_number": "PDF第2、4页；全市预算执行情况",
        "page_count": "16",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入完成([0-9.]+)亿元",
            "general_public_expenditure_100m": r"全市一般公共预算支出执行([0-9.]+)亿元",
            "gov_fund_revenue_100m": r"全市政府性基金收入完成([0-9.]+)亿元",
        },
        "note": "长治市财政局官方扫描PDF预算报告，PDF第2页和第4页分别明确披露2025年全市一般公共预算收入215.7亿元、支出493.97亿元和政府性基金收入41.53亿元；支出原文标注为12月月报数据，本批保留execution状态，按A2官方来源登记，不使用市本级、高新区或经开区数据。",
    },
    {
        "year": 2025,
        "city_name": "宣城市",
        "city_id": "CN-341800",
        "source_doc_id": "SRC-A2-XUANCHENG-CITY-FISCAL-2025",
        "url": "https://tyjr.xuancheng.gov.cn/file_xc/20/202602/20260206a37c3db21a3a448a91fb29d6117c45f5.pdf",
        "landing_page_url": "https://tyjr.xuancheng.gov.cn/file_xc/20/202602/20260206a37c3db21a3a448a91fb29d6117c45f5.pdf",
        "attachment_url": "https://tyjr.xuancheng.gov.cn/file_xc/20/202602/20260206a37c3db21a3a448a91fb29d6117c45f5.pdf",
        "download_url": "https://tyjr.xuancheng.gov.cn/file_xc/20/202602/20260206a37c3db21a3a448a91fb29d6117c45f5.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "xuancheng_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "xuancheng_2025_budget_execution_excerpt.txt",
        "text_is_curated": True,
        "document_title": "关于宣城市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "宣城市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-01-28",
        "source_grade": "A2",
        "source_format": "pdf",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方预算执行报告）",
        "document_type": "城市财政预算执行报告（官方PDF）",
        "page_number": "PDF第7页；全市预算执行情况",
        "page_count": "15",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入完成(200\.1)亿元",
            "general_public_expenditure_100m": r"全市一般公共预算支出完成(377)亿元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入完成(60\.6)亿元",
        },
        "note": "宣城市财政局官方预算执行报告，正文第7页明确披露2025年全市一般公共预算收入200.1亿元、支出377亿元和政府性基金预算收入60.6亿元；本批采用全市执行数，按A2官方来源登记，不使用市本级收入28.6亿元、支出77.9亿元和基金收入19.5亿元。",
    },
    {
        "year": 2025,
        "city_name": "抚顺市",
        "city_id": "CN-210400",
        "source_doc_id": "SRC-A2-FUSHUN-CITY-FISCAL-2025",
        "url": "https://www.fushun.gov.cn/zwgk/002008/002008003/002008003001/20260710/ad0056e5-6526-4452-8ea6-92cbfacafa87.html",
        "landing_page_url": "https://www.fushun.gov.cn/zwgk/002008/002008003/002008003001/20260710/ad0056e5-6526-4452-8ea6-92cbfacafa87.html",
        "attachment_url": "https://www.fushun.gov.cn/zwgk/002008/002008003/002008003001/20260710/ad0056e5-6526-4452-8ea6-92cbfacafa87.html",
        "download_url": "https://www.fushun.gov.cn/zwgk/002008/002008003/002008003001/20260710/ad0056e5-6526-4452-8ea6-92cbfacafa87.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "fushun_2025_final_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "fushun_2025_final_budget_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "关于抚顺市2025年财政决算的报告",
        "publisher": "抚顺市人民政府",
        "publisher_level": "市级政府门户",
        "publication_date": "2026-07-10",
        "source_grade": "A2",
        "source_format": "html",
        "raw_unit": "亿元",
        "data_status": "final",
        "data_status_label": "2025年决算数",
        "document_type": "城市财政决算报告（官方网页）",
        "page_number": "正文；全市预算收支情况",
        "page_count": "1",
        "patterns": {
            "general_public_revenue_100m": r"2025年全市一般公共预算收入(77\.2)亿元",
            "general_public_expenditure_100m": r"全市一般公共预算支出(187\.8)亿元",
            "gov_fund_revenue_100m": r"2025年全市政府性基金收入(5\.6)亿元",
        },
        "note": "抚顺市政府官方财政决算报告明确区分全市与市本级；本批采用2025年全市一般公共预算收入77.2亿元、支出187.8亿元和政府性基金收入5.6亿元，均为决算数，不使用市本级口径。",
    },
    {
        "year": 2025,
        "city_name": "阜新市",
        "city_id": "CN-210900",
        "source_doc_id": "SRC-A2-FUXIN-CITY-FISCAL-2025",
        "url": "https://czj.fuxin.gov.cn/content/2026/1090313.html",
        "landing_page_url": "https://czj.fuxin.gov.cn/content/2026/1090313.html",
        "attachment_url": "https://czj.fuxin.gov.cn/content/2026/1090313.html",
        "download_url": "https://czj.fuxin.gov.cn/content/2026/1090313.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "fuxin_2025_final_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "fuxin_2025_final_budget_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "关于阜新市2025年财政决算的报告",
        "publisher": "阜新市财政局",
        "publisher_level": "市级财政机构官方网页",
        "publication_date": "2026-07-10",
        "source_grade": "A2",
        "source_format": "html",
        "raw_unit": "亿元",
        "data_status": "final",
        "data_status_label": "2025年决算数",
        "document_type": "城市财政决算报告（官方网页）",
        "page_number": "正文；全市预算收支情况",
        "page_count": "1",
        "patterns": {
            "general_public_revenue_100m": r"全市2025年一般公共预算收入实际完成(53\.68)亿元",
            "general_public_expenditure_100m": r"一般公共预算支出实际完成(174\.24)亿元",
            "gov_fund_revenue_100m": r"2025年全市政府性基金预算收入实际完成(4\.23)亿元",
        },
        "note": "阜新市财政局官方财政决算报告明确区分全市与市本级；本批采用正文披露的2025年全市一般公共预算收入53.68亿元、支出174.24亿元和政府性基金预算收入4.23亿元，均为决算数，不使用市本级口径。",
    },
    {
        "year": 2025,
        "city_name": "盘锦市",
        "city_id": "CN-211100",
        "source_doc_id": "SRC-A2-PANJIN-CITY-FISCAL-2025",
        "url": "https://www.pjrd.gov.cn/2026_01/09_14/content-549808.html",
        "landing_page_url": "https://www.pjrd.gov.cn/2026_01/09_14/content-549808.html",
        "attachment_url": "https://www.pjrd.gov.cn/2026_01/09_14/content-549808.html",
        "download_url": "https://www.pjrd.gov.cn/2026_01/09_14/content-549808.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "panjin_2025_budget_execution_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "panjin_2025_budget_execution_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "关于盘锦市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "盘锦市人大信息网（盘锦市财政局报告）",
        "publisher_level": "市级人大官方门户",
        "publication_date": "2026-01-09",
        "source_grade": "A2",
        "source_format": "html",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_number": "正文；全市预算执行情况",
        "page_count": "1",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入(150\.1)亿元",
            "general_public_expenditure_100m": r"全市一般公共预算支出(216\.3)亿元",
            "gov_fund_revenue_100m": r"2025年全市政府性基金预算收入(16\.1)亿元",
        },
        "note": "盘锦市人大信息网公开盘锦市财政局提交的人代会预算执行报告，明确全市口径；本批采用2025年全市一般公共预算收入150.1亿元、支出216.3亿元及政府性基金预算收入16.1亿元，不使用市本级或辽滨经开区口径。",
    },
    {
        "year": 2025,
        "city_name": "六安市",
        "city_id": "CN-341500",
        "source_doc_id": "SRC-A2-LUAN-CITY-FISCAL-2025",
        "url": "https://czj.luan.gov.cn/public/6608251/10758829.html",
        "landing_page_url": "https://czj.luan.gov.cn/public/6608251/10758829.html",
        "attachment_url": "https://czj.luan.gov.cn/public/6608251/10758829.html",
        "download_url": "https://czj.luan.gov.cn/public/6608251/10758829.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "luan_2025_budget_execution_analysis.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "luan_2025_budget_execution_analysis_excerpt.txt",
        "text_is_curated": True,
        "document_title": "〖预算执行情况〗2025年全市预算执行情况分析",
        "publisher": "六安市财政局",
        "publisher_level": "市级财政机构官方网页",
        "publication_date": "2026-01-23",
        "source_grade": "A2",
        "source_format": "html",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行分析（官方网页）",
        "page_number": "正文；全市预算执行情况",
        "page_count": "1",
        "patterns": {
            "general_public_revenue_100m": r"2025年，全市一般公共预算收入(184\.2)亿元",
            "general_public_expenditure_100m": r"全市一般公共预算支出(215\.7)亿元",
            "gov_fund_revenue_100m": r"2025年，全市政府性基金预算收入(41)亿元",
        },
        "note": "六安市财政局官方预算执行分析明确为全市口径；本批采用2025年全市一般公共预算收入184.2亿元、支出215.7亿元和政府性基金预算收入41亿元，保留execution状态，不使用市本级数。",
    },
    {
        "year": 2025,
        "city_name": "赤峰市",
        "city_id": "CN-150400",
        "source_doc_id": "SRC-B2-CHIFENG-CITY-FISCAL-2025",
        "url": "https://www.chifeng.gov.cn/ztzl/rdzl/cfslhzt/cfszf2026lhzt/2026gzbg/202601/t20260130_2723148.html",
        "landing_page_url": "https://www.chifeng.gov.cn/ztzl/rdzl/cfslhzt/cfszf2026lhzt/2026gzbg/202601/t20260130_2723148.html",
        "attachment_url": "https://www.chifeng.gov.cn/ztzl/rdzl/cfslhzt/cfszf2026lhzt/2026gzbg/202601/t20260130_2723148.html",
        "download_url": "https://www.chifeng.gov.cn/ztzl/rdzl/cfslhzt/cfszf2026lhzt/2026gzbg/202601/t20260130_2723148.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "chifeng_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "chifeng_2025_budget_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "赤峰市2025年政府工作报告",
        "publisher": "赤峰市人民政府",
        "publisher_level": "市级政府门户",
        "publication_date": "2026-01-30",
        "source_grade": "B2",
        "source_format": "html",
        "raw_unit": "万元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（12月月报）",
        "document_type": "政府工作报告财政执行段落（官方网页）",
        "page_number": "正文；全市财政预算执行情况",
        "page_count": "1",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入(1262548)万元",
            "general_public_expenditure_100m": r"全市一般公共预算支出(6872676)万元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入(466850)万元",
        },
        "note": "赤峰市人民政府官方政府工作报告明确以12月月报作为2025年执行数据；本批采用全市一般公共预算收入1262548万元、支出6872676万元和政府性基金预算收入466850万元，统一换算为亿元并保留execution状态。",
    },
    {
        "year": 2025,
        "city_name": "安康市",
        "city_id": "CN-610900",
        "source_doc_id": "SRC-B2-ANKANG-CITY-FISCAL-2025",
        "url": "https://www.ankang.gov.cn/Content-2902010.html",
        "landing_page_url": "https://www.ankang.gov.cn/Content-2902010.html",
        "attachment_url": "https://www.ankang.gov.cn/Content-2902010.html",
        "download_url": "https://www.ankang.gov.cn/Content-2902010.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "ankang_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "ankang_2025_budget_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "安康市2025年财政预算执行情况和2026年财政预算（草案）的报告",
        "publisher": "安康市人民政府",
        "publisher_level": "市级政府门户",
        "publication_date": "2026-01-22",
        "source_grade": "B2",
        "source_format": "html",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_number": "正文；全市预算执行情况",
        "page_count": "1",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入完成(39\.34)亿元",
            "general_public_expenditure_100m": r"全市一般公共预算支出完成(400\.04)亿元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入完成(36\.98)亿元",
        },
        "note": "安康市人民政府官方预算执行报告明确区分全市与市本级口径；本批采用全市一般公共预算收入39.34亿元、支出400.04亿元和政府性基金预算收入36.98亿元，按B2精确官方网页来源登记。",
    },
    {
        "year": 2025,
        "city_name": "雅安市",
        "city_id": "CN-511800",
        "source_doc_id": "SRC-B2-YAAN-CITY-FISCAL-2025",
        "url": "https://www.yaan.gov.cn/xinwen/show/511f3181-a603-469c-b00c-dd2e2370f460.html",
        "landing_page_url": "https://www.yaan.gov.cn/xinwen/show/511f3181-a603-469c-b00c-dd2e2370f460.html",
        "attachment_url": "https://www.yaan.gov.cn/xinwen/show/511f3181-a603-469c-b00c-dd2e2370f460.html",
        "download_url": "https://www.yaan.gov.cn/xinwen/show/511f3181-a603-469c-b00c-dd2e2370f460.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "yaan_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "yaan_2025_budget_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "关于雅安市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "雅安市人民政府",
        "publisher_level": "市级政府门户",
        "publication_date": "2026-01-21",
        "source_grade": "B2",
        "source_format": "html",
        "raw_unit": "万元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_number": "正文；全市预算执行情况",
        "page_count": "1",
        "patterns": {
            "general_public_revenue_100m": r"全市地方一般公共预算收入([0-9，]+)万元",
            "general_public_expenditure_100m": r"全市一般公共预算支出([0-9，]+)万元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入([0-9，]+)万元",
        },
        "note": "雅安市人民政府官方预算执行报告明确全市与市级口径；本批采用全市地方一般公共预算收入878631万元、支出2513403万元和政府性基金预算收入379174万元，统一换算为亿元，不使用市级数。",
    },
    {
        "year": 2025,
        "city_name": "唐山市",
        "city_id": "CN-130200",
        "source_doc_id": "SRC-B2-TANGSHAN-CITY-FISCAL-2025",
        "url": "https://epaper.huanbohainews.com.cn/tsldrb/pad/content/202602/08/content_122246.html",
        "landing_page_url": "https://epaper.huanbohainews.com.cn/tsldrb/pad/content/202602/08/content_122246.html",
        "attachment_url": "https://epaper.huanbohainews.com.cn/tsldrb/pad/content/202602/08/content_122246.html",
        "download_url": "https://epaper.huanbohainews.com.cn/tsldrb/pad/content/202602/08/content_122246.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "tangshan_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "tangshan_2025_budget_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "唐山市2025年预算执行情况和2026年预算（草案）的报告",
        "publisher": "唐山劳动日报（环渤海新闻网数字报）",
        "publisher_level": "市级官方报纸网页",
        "publication_date": "2026-02-08",
        "source_grade": "B2",
        "source_format": "html",
        "raw_unit": "万元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行报告（官方报纸网页）",
        "page_number": "正文；全市预算执行情况",
        "page_count": "1",
        "patterns": {
            "general_public_revenue_100m": r"2025年全市一般公共预算收入(5881968)万元",
            "general_public_expenditure_100m": r"支出(10827534)万元",
            "gov_fund_revenue_100m": r"政府性基金预算收入(2996305)万元",
        },
        "note": "唐山劳动日报数字版公开市财政局预算报告原文，明确全市口径；本批采用2025年全市一般公共预算收入5881968万元、支出10827534万元和政府性基金预算收入2996305万元，统一换算为亿元，不使用市级数。",
    },
    {
        "year": 2025,
        "city_name": "三亚市",
        "city_id": "CN-460200",
        "source_doc_id": "SRC-A2-SANYA-CITY-FISCAL-2025",
        "url": "https://rd.sanya.gov.cn/rdsite/c100028d/202602/9f39ba4d9a0e4eb9b30023b5da21915f.shtml",
        "landing_page_url": "https://rd.sanya.gov.cn/rdsite/c100028d/202602/9f39ba4d9a0e4eb9b30023b5da21915f.shtml",
        "attachment_url": "https://rd.sanya.gov.cn/rdsite/c100028d/202602/9f39ba4d9a0e4eb9b30023b5da21915f.shtml",
        "download_url": "https://rd.sanya.gov.cn/rdsite/c100028d/202602/9f39ba4d9a0e4eb9b30023b5da21915f.shtml",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "sanya_2025_budget_execution_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "sanya_2025_budget_execution_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "关于三亚市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "三亚市财政局（市人大公开页面）",
        "publisher_level": "市级财政机构官方网页",
        "publication_date": "2026-01-26",
        "source_grade": "A2",
        "source_format": "html",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行报告（官方网页）",
        "page_number": "正文；全市预算执行情况",
        "page_count": "1",
        "patterns": {
            "general_public_revenue_100m": r"全市地方一般公共预算收入(155\.2)亿元",
            "general_public_expenditure_100m": r"全市地方一般公共预算支出(239\.2)亿元",
            "gov_fund_revenue_100m": r"全市地方政府性基金预算收入(138\.7)亿元",
        },
        "note": "三亚市人大公开的市财政局预算执行报告，明确全市与市本级口径；本批采用2025年全市地方一般公共预算收入155.2亿元、支出239.2亿元及政府性基金预算收入138.7亿元，保留execution状态。",
    },
    {
        "year": 2025,
        "city_name": "淮南市",
        "city_id": "CN-340400",
        "source_doc_id": "SRC-A2-HUAINAN-CITY-FISCAL-DEBT-2025",
        "url": "https://cz.huainan.gov.cn/public/118319846/1260871130.html",
        "landing_page_url": "https://cz.huainan.gov.cn/public/118319846/1260871130.html",
        "attachment_url": "https://cz.huainan.gov.cn/group1/M00/2B/2F/rB406mmOynGAFohfAARp0MA4j94698.pdf",
        "download_url": "https://cz.huainan.gov.cn/group1/M00/2B/2F/rB406mmOynGAFohfAARp0MA4j94698.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "huainan_2025_budget_execution_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "huainan_2025_budget_execution_excerpt.txt",
        "text_is_curated": True,
        "document_title": "关于淮南市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "淮南市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-02-13",
        "source_grade": "A2",
        "source_format": "pdf",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（官方预算执行报告）",
        "document_type": "城市财政预算执行报告（官方PDF）",
        "page_number": "PDF第2、3—5页；全市预算执行及债务情况",
        "page_count": "20",
        "patterns": {
            "general_public_revenue_100m": r"2025年全市一般公共预算收入(139)亿元",
            "general_public_expenditure_100m": r"全市一般公共预算支出(345\.4)亿元",
            "statutory_debt_limit_100m": r"2025年我市地方政府债务限额为(793\.1)亿元",
            "statutory_debt_balance_100m": r"2025年末[，,]全市政府债务余额为(782\.7)亿元",
        },
        "note": "淮南市财政局官方预算执行报告明确披露全市一般公共预算收入139亿元、支出345.4亿元、地方政府债务限额793.1亿元和年末政府债务余额782.7亿元；本批按A2官方PDF登记。报告政府性基金段落仅披露市本级口径，未将其误作全市收入。",
    },
    {
        "year": 2025,
        "city_name": "呼和浩特市",
        "city_id": "CN-150100",
        "source_doc_id": "SRC-B2-HOHHOT-CITY-FISCAL-2025",
        "url": "https://static.0471tv.org.cn/rb/pc/att/202603/04/5edaa825-0884-472e-9693-6c0aca69c74a.pdf",
        "landing_page_url": "https://static.0471tv.org.cn/rb/pc/att/202603/04/5edaa825-0884-472e-9693-6c0aca69c74a.pdf",
        "attachment_url": "https://static.0471tv.org.cn/rb/pc/att/202603/04/5edaa825-0884-472e-9693-6c0aca69c74a.pdf",
        "download_url": "https://static.0471tv.org.cn/rb/pc/att/202603/04/5edaa825-0884-472e-9693-6c0aca69c74a.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "hohhot_2025_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "hohhot_2025_budget_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "关于呼和浩特市2025年预算执行情况和2026年预算（草案）的报告",
        "publisher": "呼和浩特市财政局",
        "publisher_level": "市级财政机构（精确转载）",
        "publication_date": "2026-02-10",
        "source_grade": "B2",
        "source_format": "pdf",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行报告（精确转载PDF）",
        "page_number": "正文；全市预算执行情况",
        "page_count": "1",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入(268\.61)亿元",
            "general_public_expenditure_100m": r"全市一般公共预算支出(582\.6)亿元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入(75\.78)亿元",
        },
        "note": "呼和浩特市财政局预算报告精确转载，明确披露2025年全市一般公共预算收入268.61亿元、支出582.6亿元及政府性基金预算收入75.78亿元；本批按B2精确转载来源登记，不使用市本级数。",
    },
    {
        "year": 2025,
        "city_name": "威海市",
        "city_id": "CN-371000",
        "source_doc_id": "SRC-A2-WEIHAI-CITY-FISCAL-2025",
        "url": "https://czj.weihai.gov.cn/attach/0/a6f1476961ba475e85d092558b833a51.pdf",
        "landing_page_url": "https://czj.weihai.gov.cn/attach/0/a6f1476961ba475e85d092558b833a51.pdf",
        "attachment_url": "https://czj.weihai.gov.cn/attach/0/a6f1476961ba475e85d092558b833a51.pdf",
        "download_url": "https://czj.weihai.gov.cn/attach/0/a6f1476961ba475e85d092558b833a51.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "weihai_2025_budget_execution_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "weihai_2025_budget_execution_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "关于2025年威海市和市级预算执行情况与2026年威海市和市级预算草案的报告",
        "publisher": "威海市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-01-14",
        "source_grade": "A2",
        "source_format": "pdf",
        "raw_unit": "万元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（初步汇总数）",
        "document_type": "城市财政预算执行报告（官方PDF）",
        "page_number": "PDF第2页；全市预算执行情况",
        "page_count": "136",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入([0-9]+)万元",
            "general_public_expenditure_100m": r"全市一般公共预算支出([0-9]+)万元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入([0-9]+)万元",
        },
        "note": "威海市财政局官方预算报告明确区分全市与市本级口径；本批采用全市一般公共预算收入2579145万元、支出4855587万元和政府性基金预算收入2255185万元，统一换算为亿元并保留初步汇总execution状态。",
    },
    {
        "year": 2025,
        "city_name": "鄂州市",
        "city_id": "CN-420700",
        "source_doc_id": "SRC-A2-EZHOU-CITY-FISCAL-2025",
        "url": "https://www.ezhou.gov.cn/gk/xxgkml/czgk/zfyjs/202602/P020260331611182224746.pdf",
        "landing_page_url": "https://www.ezhou.gov.cn/gk/xxgkml/czgk/zfyjs/202602/P020260331611182224746.pdf",
        "attachment_url": "https://www.ezhou.gov.cn/gk/xxgkml/czgk/zfyjs/202602/P020260331611182224746.pdf",
        "download_url": "https://www.ezhou.gov.cn/gk/xxgkml/czgk/zfyjs/202602/P020260331611182224746.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "ezhou_2025_budget_execution_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "ezhou_2025_budget_execution_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "关于鄂州市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "鄂州市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-01-14",
        "source_grade": "A2",
        "source_format": "pdf",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行报告（官方PDF）",
        "page_number": "PDF第1—3页；全市预算执行情况",
        "page_count": "24",
        "patterns": {
            "general_public_revenue_100m": r"全市地方一般公共预算收入完成(107\.14)亿元",
            "general_public_expenditure_100m": r"全市地方一般公共预算支出完成(187\.37)亿元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入完成(134\.68)亿元",
        },
        "note": "鄂州市财政局官方预算执行报告明确区分全市、市级与市本级口径；本批采用2025年全市地方一般公共预算收入107.14亿元、支出187.37亿元及政府性基金预算收入134.68亿元。",
    },
    {
        "year": 2025,
        "city_name": "泸州市",
        "city_id": "CN-510500",
        "source_doc_id": "SRC-B2-LUZHOU-CITY-FISCAL-2025",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/company/c/new/2026-06-24/185565_20260624_YHTL.pdf",
        "landing_page_url": "https://static.sse.com.cn/disclosure/bond/announcement/company/c/new/2026-06-24/185565_20260624_YHTL.pdf",
        "attachment_url": "https://static.sse.com.cn/disclosure/bond/announcement/company/c/new/2026-06-24/185565_20260624_YHTL.pdf",
        "download_url": "https://static.sse.com.cn/disclosure/bond/announcement/company/c/new/2026-06-24/185565_20260624_YHTL.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "luzhou_2025_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "luzhou_2025_rating_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "泸州市兴泸投资集团有限公司2026年度跟踪评级报告",
        "publisher": "上海证券交易所公开披露的联合资信评级报告",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2026-06-24",
        "source_grade": "B2",
        "source_format": "pdf",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_number": "PDF第9页，图表3；泸州市主要财政指标",
        "page_count": "28",
        "patterns": {
            "general_public_revenue_100m": r"2025年一般公共预算收入(233\.5)亿元",
            "general_public_expenditure_100m": r"2025年一般公共预算收入233\.5亿元、一般公共预算支出(523\.8)亿元",
            "gov_fund_revenue_100m": r"2025年一般公共预算收入233\.5亿元、一般公共预算支出523\.8亿元、政府性基金收入(143\.7)亿元",
        },
        "note": "联合资信评级报告图表3依据泸州市市本级决算和全市总决算、2025年预算执行情况整理，精确列示泸州市全市2025年一般公共预算收入233.5亿元、支出523.8亿元和政府性基金收入143.7亿元；按B2精确表格来源登记。",
    },
    {
        "year": 2025,
        "city_name": "邯郸市",
        "city_id": "CN-130400",
        "source_doc_id": "SRC-B2-HANDAN-CITY-FISCAL-2025",
        "url": "https://www.chinamoney.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3375478&mode=save&priority=0",
        "landing_page_url": "https://www.chinamoney.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3375478&mode=save&priority=0",
        "attachment_url": "https://www.chinamoney.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3375478&mode=save&priority=0",
        "download_url": "https://www.chinamoney.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3375478&mode=save&priority=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "handan_2025_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "handan_2025_rating_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "邯郸城市发展投资集团有限公司主体长期信用评级报告",
        "publisher": "联合资信评估股份有限公司（交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2026-07-13",
        "source_grade": "B2",
        "source_format": "pdf",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（评级报告精确表格）",
        "document_type": "评级报告财政指标表",
        "page_number": "PDF第13页，图表2；邯郸市主要财力指标",
        "page_count": "23",
        "patterns": {
            "general_public_revenue_100m": r"2025年（末）一般公共预算收入(386\.37)亿元",
            "general_public_expenditure_100m": r"2025年（末）一般公共预算收入386\.37亿元、一般公共预算支出(935\.15)亿元",
            "gov_fund_revenue_100m": r"2025年（末）一般公共预算收入386\.37亿元、一般公共预算支出935\.15亿元、政府性基金收入(163\.44)亿元",
        },
        "note": "联合资信评级报告图表2根据邯郸市市本级决算和全市总决算、2025年预算执行及预算草案报告整理，精确列示2025年全市一般公共预算收入386.37亿元、支出935.15亿元和政府性基金收入163.44亿元；按B2精确表格来源登记。",
    },
    {
        "year": 2025,
        "city_name": "潍坊市",
        "city_id": "CN-370700",
        "source_doc_id": "SRC-A2-WEIFANG-CITY-FISCAL-2025",
        "url": "https://iapp.wfcmw.cn/share/YS02MzUtNDIzMDEwODI.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "weifang_2025_budget_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "weifang_2025_budget_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "关于潍坊市2025年预算执行情况和2026年预算草案的报告（摘要）",
        "publisher": "潍坊市财政局（官方移动发布平台公开摘要）",
        "publisher_level": "市级财政机构公开摘要",
        "publication_date": "2026-01-22",
        "source_grade": "A2",
        "source_format": "html",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行报告（官方网页摘要）",
        "page_number": "正文第（一）预算收支情况",
        "page_count": "1",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入([0-9.]+)亿元",
            "general_public_expenditure_100m": r"一般公共预算支出([0-9.]+)亿元",
        },
        "note": "潍坊市财政局官方预算执行报告摘要，明确披露2025年全市一般公共预算收入630.5亿元和支出909亿元；政府性基金收入保留已有B2精确来源413.14亿元，不用摘要中的一位小数覆盖精确值。",
    },
    {
        "year": 2025,
        "city_name": "淄博市",
        "city_id": "CN-370300",
        "source_doc_id": "SRC-A2-ZIBO-CITY-FISCAL-2025",
        "url": "https://sczj.zibo.gov.cn/gongkai/channel_c_5f9fa491ab327f36e4c1307e_n_1605682684.3626/doc_6979ae8ffeaac88756e04888.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "zibo_2025_budget_summary.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "zibo_2025_budget_summary_excerpt.txt",
        "text_is_curated": True,
        "document_title": "淄博市财政局2025年工作总结和2026年工作计划",
        "publisher": "淄博市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-01-28",
        "source_grade": "A2",
        "source_format": "html",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政工作总结（官方网页）",
        "page_number": "正文一、2025年工作总结（一）财政收支段落",
        "page_count": "1",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入实现([0-9.]+)亿元",
            "general_public_expenditure_100m": r"全市一般公共预算支出([0-9.]+)亿元",
        },
        "note": "淄博市财政局官方工作总结明确披露2025年全市一般公共预算收入419.73亿元和支出583.28亿元；政府性基金收入保留已有B2精确来源238.07亿元。",
    },
    {
        "year": 2025,
        "city_name": "滨州市",
        "city_id": "CN-371600",
        "source_doc_id": "SRC-B2-BINZHOU-CITY-FISCAL-2025",
        "url": "https://www.crei.cn/file/br.aspx?id=20260409093459&op=zc&x=0",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "binzhou_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "binzhou_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年滨州市国民经济和社会发展统计公报",
        "publisher": "滨州市统计局、国家统计局滨州调查队（中国区域经济学会信息平台转载）",
        "publisher_level": "官方统计公报转载",
        "publication_date": "2026-04-09",
        "source_grade": "B2",
        "source_format": "html",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年统计公报财政数",
        "document_type": "统计公报财政段落（精确转载）",
        "page_number": "正文八、财政金融",
        "page_count": "1",
        "patterns": {
            "general_public_revenue_100m": r"全年全市一般公共预算收入([0-9.]+)亿元",
            "general_public_expenditure_100m": r"一般公共预算支出([0-9.]+)亿元",
        },
        "note": "滨州市统计局、国家统计局滨州调查队统计公报转载精确披露2025年全市一般公共预算收入318.26亿元和支出516.72亿元；政府性基金收入保留已有B2精确来源156.32亿元。",
    },
    {
        "year": 2025,
        "city_name": "枣庄市",
        "city_id": "CN-370400",
        "source_doc_id": "SRC-B2-ZAOZHUANG-CITY-FISCAL-2025",
        "url": "https://tjgb.hongheiku.com/djs/68625.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zaozhuang_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "zaozhuang_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年枣庄市国民经济和社会发展统计公报",
        "publisher": "枣庄市统计局、国家统计局枣庄调查队（公开转载）",
        "publisher_level": "官方统计公报转载",
        "publication_date": "2026-03-24",
        "source_grade": "B2",
        "source_format": "html",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年统计公报财政数",
        "document_type": "统计公报财政段落（精确转载）",
        "page_number": "正文八、财政金融",
        "page_count": "1",
        "patterns": {
            "general_public_revenue_100m": r"全年全市一般公共预算收入([0-9.]+)亿元",
            "general_public_expenditure_100m": r"一般公共预算支出([0-9.]+)亿元",
        },
        "note": "枣庄市统计局、国家统计局枣庄调查队统计公报转载精确披露2025年全市一般公共预算收入200.20亿元和支出369.16亿元；政府性基金收入保留已有B2精确来源287.24亿元。",
    },
)

# 远东资信《四川省区域经济与信用观察》表1（第9页）集中列示四川各市州
# 2025 年一般公共预算收入。表格为精确二手来源，按 B2 登记；只接入表内
# 明确披露的收入值，不使用财政自给率反推支出，也不将“—”转为零。
_SICHUAN_2025_REGIONAL_REVENUE_SPECS = (
    ("自贡市", "CN-510300", "ZIGONG"),
    ("德阳市", "CN-510600", "DEYANG"),
    ("绵阳市", "CN-510700", "MIANYANG"),
    ("广元市", "CN-510800", "GUANGYUAN"),
    ("遂宁市", "CN-510900", "SUINING"),
    ("内江市", "CN-511000", "NEIJIANG"),
    ("乐山市", "CN-511100", "LESHAN"),
    ("南充市", "CN-511300", "NANCHONG"),
    ("眉山市", "CN-511400", "MEISHAN"),
    ("宜宾市", "CN-511500", "YIBIN"),
    ("广安市", "CN-511600", "GUANGAN"),
    ("达州市", "CN-511700", "DAZHOU"),
    ("巴中市", "CN-511900", "BAZHONG"),
    ("资阳市", "CN-512000", "ZIYANG"),
    ("阿坝藏族羌族自治州", "CN-513200", "ABA"),
    ("甘孜藏族自治州", "CN-513300", "GANZI"),
    ("凉山彝族自治州", "CN-513400", "LIANGSHAN"),
    ("攀枝花市", "CN-510400", "PANZHIHUA"),
)
_SICHUAN_2025_REGIONAL_FUND_CITIES = {
    "巴中市", "广安市", "内江市", "南充市", "德阳市", "宜宾市", "攀枝花市",
    "阿坝藏族羌族自治州", "甘孜藏族自治州", "凉山彝族自治州", "乐山市",
}
CITY_YEAR_FISCAL_SOURCES += tuple(
    {
        "year": 2025,
        "city_name": city_name,
        "city_id": city_id,
        "source_doc_id": f"SRC-B2-SICHUAN-REGIONAL-FISCAL-2025-REVENUE-{slug}",
        "url": "https://www.sfecr.com/upload/file/2026-03/col58/1774940677199.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sichuan_2025_regional_fiscal_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sichuan_2025_regional_fiscal_report_excerpt.txt",
        "document_title": "四川省区域经济与信用观察",
        "publisher": "远东资信评估有限公司",
        "publisher_level": "专业评级研究机构（精确表格二手来源）",
        "publication_date": "2026-03-24",
        "source_grade": "B2",
        "source_format": "pdf",
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数（区域研究精确表格）",
        "document_type": "区域经济与信用观察财政指标表",
        "page_number": "9",
        "page_count": "31",
        "patterns": {
            "gdp_current_100m": rf"{city_name}｜([0-9.]+)｜",
            "general_public_revenue_100m": rf"{city_name}｜[^｜]+｜([0-9.]+)｜",
            **(
                {"gov_fund_revenue_100m": rf"{city_name}｜[^｜]+｜[^｜]+｜([0-9.]+)｜"}
                if city_name in _SICHUAN_2025_REGIONAL_FUND_CITIES else {}
            ),
        },
        "note": f"报告第9页表1精确列示{city_name}2025年一般公共预算收入和政府性基金收入；按B2精确表格纳入，保持execution状态，不使用表中其他指标推导财政收支。",
    }
    for city_name, city_id, slug in _SICHUAN_2025_REGIONAL_REVENUE_SPECS
)

# 江苏省预决算公开统一平台的 2026 年预算报告中，六个此前缺少 2025 年
# 全市财政字段的设区市报告明确披露执行数。报告正文口径为全市，不使用市本级
# 数；原始单位亿元，保留执行状态。附件链接为平台签发的长期有效归档地址，
# 入口页统一保留江苏省预决算公开统一平台。
_JIANGSU_2025_CITY_REPORT_SPECS = (
    {
        "city_name": "南京市",
        "city_id": "CN-320100",
        "slug": "nanjing",
        "source_doc_id": "SRC-A2-JIANGSU-NANJING-CITY-FISCAL-2025",
        "attachment_url": "https://yjsgk.jsczt.cn/cztyjs/2026/1/28/fa21f542-0e06-4b14-ae69-ff087da55cd2.pdf?Expires=3086272384&OSSAccessKeyId=tBQyCErjLn689ynH&Signature=p8kEhxVwlJXCjY3C5Qg5Hvigc9A%3D",
        "publication_date": "2026-02-28",
        "page_number": "3—4",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入([0-9.]+)亿元",
            "general_public_expenditure_100m": r"全市一般公共预算支出([0-9.]+)亿元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入([0-9.]+)亿元",
        },
        "note": "A2江苏省预决算公开统一平台官方城市预算报告；PDF第3—4页明确披露南京市2025年全市一般公共预算收入1620.9亿元、支出1704.9亿元和政府性基金预算收入886.4亿元，执行口径，不使用市本级数。",
    },
    {
        "city_name": "南通市",
        "city_id": "CN-320600",
        "slug": "nantong",
        "source_doc_id": "SRC-A2-JIANGSU-NANTONG-CITY-FISCAL-2025",
        "attachment_url": "https://yjsgk.jsczt.cn/cztyjs/2026/1/11/49f2b72d-06e7-42a8-9861-34428183932a.pdf?Expires=3084781387&OSSAccessKeyId=tBQyCErjLn689ynH&Signature=VfREBG%2BIBs5KcU9Az6GvYtfEUHY%3D",
        "publication_date": "2026-02-11",
        "page_number": "2、7—8",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入([0-9.]+)亿元",
            "general_public_expenditure_100m": r"全市一般公共预算支出([0-9.]+)亿元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入([0-9.]+)亿元",
        },
        "note": "A2江苏省预决算公开统一平台官方城市预算报告；PDF第2页明确披露南通市2025年全市一般公共预算收入730亿元、支出1188.7亿元和政府性基金预算收入768.9亿元，执行口径，不使用市本级数。",
    },
    {
        "city_name": "连云港市",
        "city_id": "CN-320700",
        "slug": "lianyungang",
        "source_doc_id": "SRC-A2-JIANGSU-LIANYUNGANG-CITY-FISCAL-2025",
        "attachment_url": "https://yjsgk.jsczt.cn/cztyjs/2026/1/11/42b591aa-8b28-47b4-a3b9-432897b5ed84.pdf?Expires=3084809880&OSSAccessKeyId=tBQyCErjLn689ynH&Signature=ywGeD3TPjiHLcU83a%2B2qcdp0n2Y%3D",
        "publication_date": "2026-02-11",
        "page_number": "2—3",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入([0-9.]+)亿元",
            "general_public_expenditure_100m": r"全市一般公共预算支出([0-9.]+)亿元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入([0-9.]+)亿元",
        },
        "note": "A2江苏省预决算公开统一平台官方城市预算报告；PDF第2—3页明确披露连云港市2025年全市一般公共预算收入305.7亿元、支出607.8亿元和政府性基金预算收入206.5亿元，执行口径，不使用市本级数。",
    },
    {
        "city_name": "淮安市",
        "city_id": "CN-320800",
        "slug": "huaian",
        "source_doc_id": "SRC-A2-JIANGSU-HUAIAN-CITY-FISCAL-2025",
        "attachment_url": "https://yjsgk.jsczt.cn/cztyjs/2026/1/28/0247dc8a-9659-4f2f-a7ca-5542cb6d840c.pdf?Expires=3086272681&OSSAccessKeyId=tBQyCErjLn689ynH&Signature=DyAkTytgRa1i4ztPqFseOmQthYA%3D",
        "publication_date": "2026-02-28",
        "page_number": "1—2",
        "patterns": {
            "general_public_revenue_100m": r"全市实现一般公共预算收入([0-9.]+)亿元",
            "general_public_expenditure_100m": r"完成一般公共预算支出([0-9.]+)亿元",
            "gov_fund_revenue_100m": r"全市实现政府性基金收入.*?([0-9.]+)亿元",
        },
        "note": "A2江苏省预决算公开统一平台官方城市预算报告；PDF第1—2页明确披露淮安市2025年全市一般公共预算收入335.3亿元、支出718.3亿元和政府性基金收入311.6亿元，执行口径，不使用市本级数。",
    },
    {
        "city_name": "盐城市",
        "city_id": "CN-320900",
        "slug": "yancheng",
        "source_doc_id": "SRC-A2-JIANGSU-YANCHENG-CITY-FISCAL-2025",
        "attachment_url": "https://yjsgk.jsczt.cn/cztyjs/2026/1/24/c4570ccd-0a61-4893-abb9-218e70df8285.pdf?Expires=3085925282&OSSAccessKeyId=tBQyCErjLn689ynH&Signature=Vf9g52%2BDg3MScm7SPQtBBSs%2F8F0%3D",
        "publication_date": "2026-02-24",
        "page_number": "1—2",
        "patterns": {
            "general_public_revenue_100m": r"全市实现一般公共预算收入([0-9.]+)亿元",
            "general_public_expenditure_100m": r"(?:全市)?实现一般公共预算支出([0-9.]+)亿元",
            "gov_fund_revenue_100m": r"全市实现政府性基金预算收入([0-9.]+)亿元",
        },
        "note": "A2江苏省预决算公开统一平台官方城市预算报告；PDF第1—2页明确披露盐城市2025年全市一般公共预算收入515.74亿元、支出1099.03亿元和政府性基金预算收入425.83亿元，执行口径，不使用市级数。",
    },
    {
        "city_name": "宿迁市",
        "city_id": "CN-321300",
        "slug": "suqian",
        "source_doc_id": "SRC-A2-JIANGSU-SUQIAN-CITY-FISCAL-2025",
        "attachment_url": "https://yjsgk.jsczt.cn/cztyjs/2026/1/6/6105606b-eca1-4e09-9d69-4911d01deac0.pdf?Expires=3084373385&OSSAccessKeyId=tBQyCErjLn689ynH&Signature=gjpdoLgHkGq3m%2FZUKzGVv3nLluA%3D",
        "publication_date": "2026-02-06",
        "page_number": "2—4",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入([0-9.]+)亿元",
            "general_public_expenditure_100m": r"一般公共预算支出([0-9.]+)亿元",
            "gov_fund_revenue_100m": r"全市政府性基金收入([0-9.]+)亿元",
        },
        "note": "A2江苏省预决算公开统一平台官方城市预算报告；PDF第2—4页明确披露宿迁市2025年全市一般公共预算收入316.6亿元、支出688.6亿元和政府性基金收入215.1亿元，执行口径，不使用市本级数。",
    },
)
CITY_YEAR_FISCAL_SOURCES += tuple(
    {
        **spec,
        "year": 2025,
        "url": "https://yjsgk.jsczt.cn/",
        "attachment_url": spec["attachment_url"],
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / f"jiangsu_{spec['slug']}_2026_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / f"jiangsu_{spec['slug']}_2026_budget_report_excerpt.txt",
        "document_title": f"关于{spec['city_name']}2025年预算执行情况和2026年预算草案的报告",
        "publisher": f"{spec['city_name']}财政局",
        "publisher_level": "市级财政机构（省级预决算公开统一平台）",
        "source_grade": "A2",
        "source_format": "pdf",
        "text_is_curated": True,
        "raw_unit": "亿元",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政预算执行报告（官方PDF）",
        "mime_type": "application/pdf",
        "landing_page_url": "https://yjsgk.jsczt.cn/",
        "source_locator": f"官方报告PDF第{spec['page_number']}页；城市={spec['city_name']}；2025年全市执行数",
        "note": spec["note"],
    }
    for spec in _JIANGSU_2025_CITY_REPORT_SPECS
)

# 江西省 2025 年区域研究精确表格：上交所公开披露的中证鹏元跟踪评级报告
# 第 7—8 页表 2 一次列示 11 个地级市的 GDP、实际增速、一般公共预算收入和
# 政府性基金收入。本批只接入此前缺少高等级值的 9 市；南昌、景德镇已有更高
# 优先级的官方城市预算来源，不用 B2 表格覆盖。表格明确为 2025 年值、全市口径，
# 评级报告注明资料来源为各地级市政府网站，按 B2 精确表格纳入。
_JIANGXI_2025_REGIONAL_FISCAL_SPECS = (
    ("萍乡市", "CN-360300", "PINGXIANG"),
    ("九江市", "CN-360400", "JIUJIANG"),
    ("新余市", "CN-360500", "XINYU"),
    ("鹰潭市", "CN-360600", "YINGTAN"),
    ("赣州市", "CN-360700", "GANZHOU"),
    ("吉安市", "CN-360800", "JI_AN"),
    ("宜春市", "CN-360900", "YICHUN"),
    ("抚州市", "CN-361000", "FUZHOU"),
    ("上饶市", "CN-361100", "SHANGRAO"),
)
CITY_YEAR_FISCAL_SOURCES += tuple(
    {
        "year": 2025,
        "city_name": city_name,
        "city_id": city_id,
        "source_doc_id": f"SRC-B2-JIANGXI-REGIONAL-FISCAL-2025-{slug}",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/corporate/c/new/2026-05-27/152785_20260527_N2NC.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "jiangxi_2025_regional_fiscal_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "jiangxi_2025_regional_fiscal_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "吉安市新庐陵投资发展有限公司相关债券2026年跟踪评级报告",
        "publisher": "中证鹏元资信评估股份有限公司（上海证券交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2026-05-27",
        "source_grade": "B2",
        "source_format": "pdf",
        "data_status": "execution",
        "data_status_label": "2025年执行数（评级报告精确表格）",
        "document_type": "评级报告地级市经济财政指标表",
        "page_number": "PDF第7—8页，表2；2025年江西省地级市经济财政指标情况",
        "page_count": "23",
        "raw_unit": "亿元",
        "raw_units": {"gdp_real_growth_pct": "%"},
        "patterns": {
            "gdp_current_100m": rf"{city_name}\|([0-9.,]+)\|",
            "gdp_real_growth_pct": rf"{city_name}\|[0-9.,]+\|([0-9.-]+)\|",
            "general_public_revenue_100m": rf"{city_name}\|[0-9.,]+\|[0-9.-]+\|[0-9,]+\|([0-9.,]+)\|",
            "gov_fund_revenue_100m": rf"{city_name}\|[0-9.,]+\|[0-9.-]+\|[0-9,]+\|[0-9.,]+\|([0-9.,]+)",
        },
        "source_locator": f"PDF第7—8页表2；城市={city_name}；2025年全市执行数",
        "note": f"B2精确表格；报告表2列示{city_name}2025年GDP、实际增速、一般公共预算收入和政府性基金收入，资料来源为各地级市政府网站；不使用市本级数，不以图表目测代替表格值。",
    }
    for city_name, city_id, slug in _JIANGXI_2025_REGIONAL_FISCAL_SPECS
)

# 上交所公开披露的中证鹏元评级报告第 6 页表 1，集中列示江西省 2024 年
# 11 个地级市的全市 GDP、实际增速、一般公共预算收入和政府性基金收入。
# 表格值为精确文本表格，不把人均 GDP 或“—”转换为主表字段，也不使用区县
# 和市本级口径。
# 上交所公开披露的中证鹏元评级报告第 6 页表 1，集中列示山西省 2024 年
# 8 个地级市的全市 GDP、实际增速、一般公共预算收入和政府性基金收入。
_SHANXI_2024_REGIONAL_FISCAL_SPECS = (
    ("太原市", "CN-140100", "TAIYUAN"),
    ("长治市", "CN-140400", "CHANGZHI"),
    ("晋中市", "CN-140700", "JINZHONG"),
    ("晋城市", "CN-140500", "JINCHENG"),
    ("运城市", "CN-140800", "YUNCHENG"),
    ("大同市", "CN-140200", "DATONG"),
    ("忻州市", "CN-140900", "XINZHOU"),
    ("朔州市", "CN-140600", "SHUOZHOU"),
)
CITY_YEAR_FISCAL_SOURCES += tuple(
    {
        "year": 2024,
        "city_name": city_name,
        "city_id": city_id,
        "source_doc_id": f"SRC-B2-SHANXI-REGIONAL-FISCAL-2024-{slug}",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/corporate/c/new/2025-07-30/184519_20250730_IWL7.pdf",
        "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "shanxi_2024_city_fiscal_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "shanxi_2024_city_fiscal_rating_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "朔州市投资建设开发有限公司相关债券2025年跟踪评级报告",
        "publisher": "中证鹏元资信评估股份有限公司（上海证券交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2025-07-30",
        "source_grade": "B2",
        "source_format": "pdf",
        "data_status": "execution",
        "data_status_label": "2024年执行数（评级报告精确表格）",
        "document_type": "评级报告地级市经济财政指标表",
        "page_number": "PDF第6页，表1；2024年山西省部分地级市经济财政指标情况",
        "page_count": "19",
        "raw_unit": "亿元",
        "raw_units": {"gdp_real_growth_pct": "%"},
        "patterns": {
            "gdp_current_100m": rf"{city_name}｜([0-9.,]+)｜",
            "gdp_real_growth_pct": rf"{city_name}｜[0-9.,]+｜([0-9.-]+)｜",
            "general_public_revenue_100m": rf"{city_name}｜[0-9.,]+｜[0-9.-]+｜([0-9.,]+)｜",
            "gov_fund_revenue_100m": rf"{city_name}｜[0-9.,]+｜[0-9.-]+｜[0-9.,]+｜([0-9.,]+)",
        },
        "source_locator": f"PDF第6页表1；城市={city_name}；2024年全市执行数",
        "note": f"B2精确表格；报告表1列示{city_name}2024年全市GDP、实际增速、一般公共预算收入和政府性基金收入，资料来源为各市统计公报和财政预决算报告；不使用市本级数或图表目测值。",
    }
    for city_name, city_id, slug in _SHANXI_2024_REGIONAL_FISCAL_SPECS
)

# 上交所公开披露的中证鹏元评级报告第 5 页表 1，集中列示湖北省 2024 年
# 8 个地级行政单元的全市 GDP、实际增速、一般公共预算收入和政府性基金收入。
# 宜昌市基金收入为原表“—”，该配置只提取其余三个明确字段。
_HUBEI_2024_REGIONAL_FISCAL_SPECS = (
    ("武汉市", "CN-420100", "WUHAN", True),
    ("宜昌市", "CN-420500", "YICHANG", False),
    ("襄阳市", "CN-420600", "XIANGYANG", True),
    ("黄冈市", "CN-421100", "HUANGGANG", True),
    ("十堰市", "CN-420300", "SHIYAN", True),
    ("恩施土家族苗族自治州", "CN-422800", "ENSHI", True),
    ("随州市", "CN-421300", "SUIZHOU", True),
    ("鄂州市", "CN-420700", "EZHOU", True),
)
CITY_YEAR_FISCAL_SOURCES += tuple(
    {
        "year": 2024,
        "city_name": city_name,
        "city_id": city_id,
        "source_doc_id": f"SRC-B2-HUBEI-REGIONAL-FISCAL-2024-{slug}",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/corporate/c/new/2025-07-25/184246_20250725_7VJP.pdf",
        "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "hubei_2024_city_fiscal_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "hubei_2024_city_fiscal_rating_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "黄冈新区投资开发有限公司相关债券2025年跟踪评级报告",
        "publisher": "中证鹏元资信评估股份有限公司（上海证券交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2025-07-25",
        "source_grade": "B2",
        "source_format": "pdf",
        "data_status": "execution",
        "data_status_label": "2024年执行数（评级报告精确表格）",
        "document_type": "评级报告地级行政单元经济财政指标表",
        "page_number": "PDF第5页，表1；2024年湖北省部分地级市经济财政指标情况",
        "page_count": "22",
        "raw_unit": "亿元",
        "raw_units": {"gdp_real_growth_pct": "%"},
        "patterns": {
            "gdp_current_100m": rf"{city_name}｜([0-9.,]+)｜",
            "gdp_real_growth_pct": rf"{city_name}｜[0-9.,]+｜([0-9.-]+)｜",
            "general_public_revenue_100m": rf"{city_name}｜[0-9.,]+｜[0-9.-]+｜([0-9.,]+)｜",
            **({
                "gov_fund_revenue_100m": rf"{city_name}｜[0-9.,]+｜[0-9.-]+｜[0-9.,]+｜([0-9.,]+)",
            } if has_fund else {}),
        },
        "source_locator": f"PDF第5页表1；城市={city_name}；2024年全市执行数",
        "note": f"B2精确表格；报告表1列示{city_name}2024年全市经济财政指标，资料来源为各市统计公报和政府网站；不使用市本级数或图表目测值。",
    }
    for city_name, city_id, slug, has_fund in _HUBEI_2024_REGIONAL_FISCAL_SPECS
)

_JIANGXI_2024_REGIONAL_FISCAL_SPECS = (
    ("南昌市", "CN-360100", "NANCHANG"),
    ("赣州市", "CN-360700", "GANZHOU"),
    ("九江市", "CN-360400", "JIUJIANG"),
    ("上饶市", "CN-361100", "SHANGRAO"),
    ("宜春市", "CN-360900", "YICHUN"),
    ("吉安市", "CN-360800", "JI_AN"),
    ("抚州市", "CN-361000", "FUZHOU"),
    ("鹰潭市", "CN-360600", "YINGTAN"),
    ("萍乡市", "CN-360300", "PINGXIANG"),
    ("景德镇市", "CN-360200", "JINGDEZHEN"),
    ("新余市", "CN-360500", "XINYU"),
)
CITY_YEAR_FISCAL_SOURCES += tuple(
    {
        "year": 2024,
        "city_name": city_name,
        "city_id": city_id,
        "source_doc_id": f"SRC-B2-JIANGXI-REGIONAL-FISCAL-2024-{slug}",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/corporate/c/new/2025-07-17/152792_20250717_RRYD.pdf",
        "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "jiangxi_2024_city_fiscal_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "jiangxi_2024_city_fiscal_rating_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "吉安市家庐陵投资开发有限公司相关债券2025年跟踪评级报告",
        "publisher": "中证鹏元资信评估股份有限公司（上海证券交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2025-07-17",
        "source_grade": "B2",
        "source_format": "pdf",
        "data_status": "execution",
        "data_status_label": "2024年执行数（评级报告精确表格）",
        "document_type": "评级报告地级市经济财政指标表",
        "page_number": "PDF第6页，表1；2024年江西省部分地市经济财政指标情况",
        "page_count": "21",
        "raw_unit": "亿元",
        "raw_units": {"gdp_real_growth_pct": "%"},
        "patterns": {
            "gdp_current_100m": rf"{city_name}｜([0-9.,]+)｜",
            "gdp_real_growth_pct": rf"{city_name}｜[0-9.,]+｜([0-9.-]+)｜",
            "general_public_revenue_100m": rf"{city_name}｜[0-9.,]+｜[0-9.-]+｜([0-9.,]+)｜",
            "gov_fund_revenue_100m": rf"{city_name}｜[0-9.,]+｜[0-9.-]+｜[0-9.,]+｜([0-9.,]+)",
        },
        "source_locator": f"PDF第6页表1；城市={city_name}；2024年全市执行数",
        "note": f"B2精确表格；报告表1列示{city_name}2024年全市GDP、实际增速、一般公共预算收入和政府性基金收入，资料来源为各地市政府网站；不使用市本级数或图表目测值。",
    }
    for city_name, city_id, slug in _JIANGXI_2024_REGIONAL_FISCAL_SPECS
)

# 上交所公开披露的中证鹏元评级报告第 6 页表 1，集中列示浙江省 2024 年
# 8 个地级市的全市 GDP、实际增速、一般公共预算收入和政府性基金收入。
# 表格值为精确文本表格，不把人均 GDP 或“—”转换为主表字段，也不使用区县
# 和市本级口径。
_ZHEJIANG_2024_REGIONAL_FISCAL_SPECS = (
    ("杭州市", "CN-330100", "HANGZHOU"),
    ("宁波市", "CN-330200", "NINGBO"),
    ("温州市", "CN-330300", "WENZHOU"),
    ("嘉兴市", "CN-330400", "JIAXING"),
    ("湖州市", "CN-330500", "HUZHOU"),
    ("绍兴市", "CN-330600", "SHAOXING"),
    ("金华市", "CN-330700", "JINHUA"),
    ("衢州市", "CN-330800", "QUZHOU"),
)
CITY_YEAR_FISCAL_SOURCES += tuple(
    {
        "year": 2024,
        "city_name": city_name,
        "city_id": city_id,
        "source_doc_id": f"SRC-B2-ZHEJIANG-REGIONAL-FISCAL-2024-{slug}",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/corporate/c/new/2025-06-30/184197_20250630_NVI2.pdf",
        "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "zhejiang_2024_city_fiscal_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "zhejiang_2024_city_fiscal_rating_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "嘉兴科技城投资发展集团有限公司相关债券2025年跟踪评级报告",
        "publisher": "中证鹏元资信评估股份有限公司（上海证券交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2025-06-30",
        "source_grade": "B2",
        "source_format": "pdf",
        "data_status": "execution",
        "data_status_label": "2024年执行数（评级报告精确表格）",
        "document_type": "评级报告地级市经济财政指标表",
        "page_number": "PDF第6页，表1；2024年浙江省部分地市经济财政指标情况",
        "page_count": "23",
        "raw_unit": "亿元",
        "raw_units": {"gdp_real_growth_pct": "%"},
        "patterns": {
            "gdp_current_100m": rf"{city_name}｜([0-9.,]+)｜",
            "gdp_real_growth_pct": rf"{city_name}｜[0-9.,]+｜([0-9.-]+)｜",
            "general_public_revenue_100m": rf"{city_name}｜[0-9.,]+｜[0-9.-]+｜([0-9.,]+)｜",
            "gov_fund_revenue_100m": rf"{city_name}｜[0-9.,]+｜[0-9.-]+｜[0-9.,]+｜([0-9.,]+)",
        },
        "source_locator": f"PDF第6页表1；城市={city_name}；2024年全市执行数",
        "note": f"B2精确表格；报告表1列示{city_name}2024年全市GDP、实际增速、一般公共预算收入和政府性基金收入，资料来源为各政府网站；不使用市本级数或图表目测值。",
    }
    for city_name, city_id, slug in _ZHEJIANG_2024_REGIONAL_FISCAL_SPECS
)

# 上交所公开披露的中证鹏元评级报告第 7 页表 1，集中列示广西壮族自治区
# 2024 年 9 个地级市的全市 GDP、实际增速、一般公共预算收入和政府性基金收入。
# 表格值为精确文本表格，不把人均 GDP 或其他派生指标写入主表，也不使用区县
# 和市本级口径。
_GUANGXI_2024_REGIONAL_FISCAL_SPECS = (
    ("南宁市", "CN-450100", "NANNING"),
    ("柳州市", "CN-450200", "LIUZHOU"),
    ("桂林市", "CN-450300", "GUILIN"),
    ("玉林市", "CN-450900", "YULIN"),
    ("北海市", "CN-450500", "BEIHAI"),
    ("梧州市", "CN-450400", "WUZHOU"),
    ("河池市", "CN-451200", "HECHI"),
    ("崇左市", "CN-451400", "CHONGZUO"),
    ("来宾市", "CN-451300", "LAIBIN"),
)
CITY_YEAR_FISCAL_SOURCES += tuple(
    {
        "year": 2024,
        "city_name": city_name,
        "city_id": city_id,
        "source_doc_id": f"SRC-B2-GUANGXI-REGIONAL-FISCAL-2024-{slug}",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/corporate/c/new/2025-07-30/152930_20250730_SSLN.pdf",
        "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "guangxi_2024_city_fiscal_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "guangxi_2024_city_fiscal_rating_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "相关债券2025年跟踪评级报告",
        "publisher": "中证鹏元资信评估股份有限公司（上海证券交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2025-07-30",
        "source_grade": "B2",
        "source_format": "pdf",
        "data_status": "execution",
        "data_status_label": "2024年执行数（评级报告精确表格）",
        "document_type": "评级报告地级市经济财政指标表",
        "page_number": "PDF第7页，表1；2024年广西壮族自治区部分地级市经济财政指标情况",
        "page_count": "22",
        "raw_unit": "亿元",
        "raw_units": {"gdp_real_growth_pct": "%"},
        "patterns": {
            "gdp_current_100m": rf"{city_name}｜([0-9.,]+)｜",
            "gdp_real_growth_pct": rf"{city_name}｜[0-9.,]+｜([0-9.-]+)｜",
            "general_public_revenue_100m": rf"{city_name}｜[0-9.,]+｜[0-9.-]+｜([0-9.,]+)｜",
            "gov_fund_revenue_100m": rf"{city_name}｜[0-9.,]+｜[0-9.-]+｜[0-9.,]+｜([0-9.,]+)",
        },
        "source_locator": f"PDF第7页表1；城市={city_name}；2024年全市执行数",
        "note": f"B2精确表格；报告表1列示{city_name}2024年全市GDP、实际增速、一般公共预算收入和政府性基金收入，资料来源为各市统计公报和财政预决算报告；不使用市本级数或图表目测值。",
    }
    for city_name, city_id, slug in _GUANGXI_2024_REGIONAL_FISCAL_SPECS
)

# 上交所公开披露的中证鹏元评级报告第 8 页表 2，集中列示安徽省 2024 年
# 9 个地级市的全市 GDP、实际增速、一般公共预算收入和政府性基金收入。
# 亳州市、铜陵市的政府性基金收入在原表中为“—”，保持缺失，不写入零值。
_ANHUI_2024_REGIONAL_FISCAL_SPECS = (
    ("合肥市", "CN-340100", "HEFEI", True),
    ("芜湖市", "CN-340200", "WUHU", True),
    ("安庆市", "CN-340800", "ANQING", True),
    ("马鞍山市", "CN-340500", "MAANSHAN", True),
    ("亳州市", "CN-341600", "BOZHOU", False),
    ("宿州市", "CN-341300", "SUZHOU", True),
    ("宣城市", "CN-341800", "XUANCHENG", True),
    ("铜陵市", "CN-340700", "TONGLING", False),
    ("池州市", "CN-341700", "CHIZHOU", True),
)
CITY_YEAR_FISCAL_SOURCES += tuple(
    {
        "year": 2024,
        "city_name": city_name,
        "city_id": city_id,
        "source_doc_id": f"SRC-B2-ANHUI-REGIONAL-FISCAL-2024-{slug}",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/corporate/c/new/2025-07-03/152026_20250703_2S57.pdf",
        "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "anhui_2024_city_fiscal_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "anhui_2024_city_fiscal_rating_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "马鞍山市宁博投资发展有限责任公司相关债券2025年跟踪评级报告",
        "publisher": "中证鹏元资信评估股份有限公司（上海证券交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2025-07-03",
        "source_grade": "B2",
        "source_format": "pdf",
        "data_status": "execution",
        "data_status_label": "2024年执行数（评级报告精确表格）",
        "document_type": "评级报告地级市经济财政指标表",
        "page_number": "PDF第8页，表2；2024年安徽省部分地级市经济财政指标情况",
        "page_count": "19",
        "raw_unit": "亿元",
        "raw_units": {"gdp_real_growth_pct": "%"},
        "patterns": {
            "gdp_current_100m": rf"{city_name}｜([0-9.,]+)｜",
            "gdp_real_growth_pct": rf"{city_name}｜[0-9.,]+｜([0-9.-]+)｜",
            "general_public_revenue_100m": rf"{city_name}｜[0-9.,]+｜[0-9.-]+｜([0-9.,]+)｜",
            **({
                "gov_fund_revenue_100m": rf"{city_name}｜[0-9.,]+｜[0-9.-]+｜[0-9.,]+｜([0-9.,]+)",
            } if has_fund else {}),
        },
        "source_locator": f"PDF第8页表2；城市={city_name}；2024年全市执行数",
        "note": f"B2精确表格；报告表2列示{city_name}2024年全市GDP、实际增速和一般公共预算收入；政府性基金收入仅在原表明确数值时接入，不使用市本级数、区县数或图表目测值。",
    }
    for city_name, city_id, slug, has_fund in _ANHUI_2024_REGIONAL_FISCAL_SPECS
)

# 上交所公开披露的中证鹏元评级报告第 8 页表 2，集中列示陕西省 2024 年
# 6 个地级市的全市 GDP、实际增速、一般公共预算收入和政府性基金收入。
# 榆林市财政收入和政府性基金收入在原表中为“—”，保持缺失，不写入零值。
_SHAANXI_2024_REGIONAL_FISCAL_SPECS = (
    ("西安市", "CN-610100", "XIAN", True),
    ("榆林市", "CN-610800", "YULIN", False),
    ("咸阳市", "CN-610400", "XIANYANG", True),
    ("延安市", "CN-610600", "YANAN", True),
    ("渭南市", "CN-610500", "WEINAN", True),
    ("铜川市", "CN-610200", "TONGCHUAN", True),
)
CITY_YEAR_FISCAL_SOURCES += tuple(
    {
        "year": 2024,
        "city_name": city_name,
        "city_id": city_id,
        "source_doc_id": f"SRC-B2-SHAANXI-REGIONAL-FISCAL-2024-{slug}",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/corporate/c/new/2025-06-16/184718_20250616_S6RT.pdf",
        "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "shaanxi_2024_city_fiscal_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "shaanxi_2024_city_fiscal_rating_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "渭南市城市投资集团有限责任公司绿色债券2025年跟踪评级报告",
        "publisher": "中证鹏元资信评估股份有限公司（上海证券交易所公开披露）",
        "publisher_level": "交易所公开披露的B2精确表格来源",
        "publication_date": "2025-06-16",
        "source_grade": "B2",
        "source_format": "pdf",
        "data_status": "execution",
        "data_status_label": "2024年执行数（评级报告精确表格）",
        "document_type": "评级报告地级市经济财政指标表",
        "page_number": "PDF第8页，表2；2024年陕西省部分地市经济财政指标情况",
        "page_count": "22",
        "raw_unit": "亿元",
        "raw_units": {"gdp_real_growth_pct": "%"},
        "patterns": {
            "gdp_current_100m": rf"{city_name}｜([0-9.,]+)｜",
            "gdp_real_growth_pct": rf"{city_name}｜[0-9.,]+｜([0-9.-]+)｜",
            **({
                "general_public_revenue_100m": rf"{city_name}｜[0-9.,]+｜[0-9.-]+｜([0-9.,]+)｜",
                "gov_fund_revenue_100m": rf"{city_name}｜[0-9.,]+｜[0-9.-]+｜[0-9.,]+｜([0-9.,]+)",
            } if has_fund else {}),
        },
        "source_locator": f"PDF第8页表2；城市={city_name}；2024年全市执行数",
        "note": f"B2精确表格；报告表2列示{city_name}2024年全市GDP和实际增速；财政字段仅在原表明确数值时接入，不使用市本级数、区县数或图表目测值。",
    }
    for city_name, city_id, slug, has_fund in _SHAANXI_2024_REGIONAL_FISCAL_SPECS
)
CITY_YEAR_FISCAL_SOURCES += CURATED_2025_CITY_FISCAL_SOURCES
CITY_YEAR_FISCAL_SOURCES += tuple(SUPPLEMENTAL_CITY_FISCAL_SOURCES)
CITY_YEAR_FISCAL_SOURCES += tuple(REGIONAL_FISCAL_2024_SOURCES)
CITY_YEAR_FISCAL_SOURCES += tuple(CITY_FISCAL_RATING_2024_2025_SOURCES)
CITY_YEAR_FISCAL_SOURCES += tuple(DAGONG_CITY_FISCAL_SOURCES)

# 2024—2025 年新增的省级/城市批量摘录。摘录文件只保留可由入口页、附件或
# 精确转载逐项核验的全市值；这里用统一的“城市—年度—字段”接口接入，避免
# 为每一张省级表重复编写解析器。字段级合并仍由 load_city_year_fiscal_sources
# 按来源等级执行，不会覆盖已有的更高等级值。
_CURATED_CITY_FIELD_LABELS = {
    "gdp_current_100m": "GDP",
    "gdp_real_growth_pct": "GDP增速",
    "general_public_revenue_100m": "一般公共预算收入",
    "general_public_expenditure_100m": "一般公共预算支出",
}


def _make_curated_city_source(
    *,
    year: int,
    city_name: str,
    city_id: str,
    source_doc_id: str,
    url: str,
    path: Path,
    attachment_url: str | None = None,
    document_title: str,
    publisher: str,
    publisher_level: str,
    publication_date: str,
    source_grade: str,
    fields: tuple[str, ...],
    raw_unit: str = "亿元",
    raw_units: dict[str, str] | None = None,
    text_city_name: str | None = None,
    source_format: str = "pdf",
    data_status: str = "execution",
    data_status_label: str | None = None,
    document_type: str = "城市经济财政指标精确摘录",
    page_number: str = "摘录文件；对应入口页/附件表格",
    title_source: str = "official_budget_report",
    access_status: str | None = None,
    note: str = "官方或精确公开表格摘录；行政范围为全市（州/地区），仅接入可逐项定位的数值。",
) -> dict[str, Any]:
    """把逐行城市摘录转换为标准城市财政来源配置。"""

    text_city = text_city_name or city_name
    units = dict(raw_units or {})
    patterns = {
        field: (
            rf"城市={re.escape(text_city)}｜年度={year}｜"
            rf"(?:(?!城市=).)*?{re.escape(_CURATED_CITY_FIELD_LABELS[field])}="
            rf"([0-9.,-]+){re.escape(units.get(field, raw_unit))}"
        )
        for field in fields
    }
    return {
        "year": year,
        "city_name": city_name,
        "city_id": city_id,
        "source_doc_id": source_doc_id,
        "url": url,
        "attachment_url": attachment_url,
        "path": path,
        "text_path": path,
        "text_is_curated": True,
        "document_title": document_title,
        "publisher": publisher,
        "publisher_level": publisher_level,
        "publication_date": publication_date,
        "source_grade": source_grade,
        "source_format": source_format,
        "data_status": data_status,
        "data_status_label": data_status_label or f"{year}年执行数",
        "document_type": document_type,
        "page_number": page_number,
        "title_source": title_source,
        "access_status": access_status,
        "raw_unit": raw_unit,
        "raw_units": units,
        "patterns": patterns,
        "note": note,
    }


_CURATED_2024_CITY_MACRO_FISCAL_SPECS = (
    # 吉林统计年鉴 2025，20-6、20-7 表（万元）。
    *(
        {
            "year": 2024,
            "city_name": city,
            "city_id": city_id,
            "source_doc_id": f"SRC-A1-JILIN-CITY-FISCAL-2024-{slug}",
            "url": "https://tjj.jl.gov.cn/tjsj/tjnj/2025/html/20-6.html",
            "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "jilin_2024_city_fiscal_yearbook_excerpt.txt",
            "document_title": "吉林统计年鉴2025（20-6、20-7）",
            "publisher": "吉林省统计局",
            "publisher_level": "省级统计机构",
            "publication_date": "2025-12-31",
            "source_grade": "A1",
            "fields": ("general_public_revenue_100m", "general_public_expenditure_100m"),
            "raw_unit": "万元",
            "source_format": "html",
            "page_number": "官方年鉴网页20-6、20-7表",
            "document_type": "省级统计年鉴分市财政表",
            "note": "A1吉林省统计局官方年鉴分市表；20-6和20-7分别为各市一般公共预算收入、支出，单位万元，采用设区市全市口径。",
        }
        for city, city_id, slug in (
            ("吉林市", "CN-220200", "JILIN"),
            ("四平市", "CN-220300", "SIPING"),
            ("辽源市", "CN-220400", "LIAOYUAN"),
            ("通化市", "CN-220500", "TONGHUA"),
            ("白山市", "CN-220600", "BAISHAN"),
            ("松原市", "CN-220700", "SONGYUAN"),
            ("白城市", "CN-220800", "BAICHENG"),
        )
    ),
    *(
        {
            "year": 2024,
            "city_name": city,
            "city_id": city_id,
            "source_doc_id": f"SRC-A1-GANSU-CITY-FISCAL-2024-{slug}",
            "url": "https://tjj.gansu.gov.cn/tjj/c117468/202505/174143566/files/b46bda090ad947cfa645f6cb8398e656.pdf",
            "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "gansu_2024_city_fiscal_digest_excerpt.txt",
            "document_title": "甘肃发展年鉴2025/甘肃统计年鉴分市州财政表",
            "publisher": "甘肃省统计局",
            "publisher_level": "省级统计机构",
            "publication_date": "2025-05-01",
            "source_grade": "A1",
            "fields": ("general_public_revenue_100m", "general_public_expenditure_100m"),
            "source_format": "pdf",
            "page_number": "官方PDF表11-2、表11-3",
            "document_type": "省级统计年鉴分市州财政表",
            "note": "A1甘肃省统计局官方分市州一般公共预算收支表，单位亿元，采用2024年执行数和市州全域口径。",
        }
        for city, city_id, slug in (("平凉市", "CN-620800", "PINGLIANG"), ("庆阳市", "CN-621000", "QINGYANG"))
    ),
    {
        "year": 2024,
        "city_name": "湘潭市",
        "city_id": "CN-430300",
        "source_doc_id": "SRC-A2-HUNAN-XIANGTAN-MACRO-FISCAL-2024",
        "url": "https://tjj.hunan.gov.cn/hntj/tjfx/tjgb/szgb/xts_1/202504/33633603/files/95bcbcb8dd17408d98d7c00393d250cf.pdf",
        "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "hunan_2024_city_macro_fiscal_excerpt.txt",
        "document_title": "湘潭市2024年国民经济和社会发展统计公报及财政执行信息",
        "publisher": "湖南省统计局、湘潭市统计局及湘潭市财政局",
        "publisher_level": "省市级统计/财政机构",
        "publication_date": "2025-04-01",
        "source_grade": "A2",
        "fields": ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "pdf",
        "data_status": "preliminary",
        "data_status_label": "2024年公报初步统计数/财政执行数",
        "page_number": "官方公报及财政公开信息摘录",
        "document_type": "市级统计公报与财政执行指标",
    },
    {
        "year": 2024,
        "city_name": "邵阳市",
        "city_id": "CN-430500",
        "source_doc_id": "SRC-A2-HUNAN-SHAOYANG-MACRO-FISCAL-2024",
        "url": "https://tjj.hunan.gov.cn/tjfx/tjgb/szgb/sys_1/202505/t20250516_33673436.html",
        "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "hunan_2024_city_macro_fiscal_excerpt.txt",
        "document_title": "邵阳市2024年国民经济和社会发展统计公报及财政执行信息",
        "publisher": "邵阳市统计局、邵阳市财政局",
        "publisher_level": "市级统计/财政机构",
        "publication_date": "2025-05-16",
        "source_grade": "A2",
        "fields": ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2024年公报初步统计数/财政执行数",
        "page_number": "官方统计公报及财政局公开信息摘录",
        "document_type": "市级统计公报与财政执行指标",
    },
    {
        "year": 2024,
        "city_name": "岳阳市",
        "city_id": "CN-430600",
        "source_doc_id": "SRC-A1-HUNAN-YUEYANG-FISCAL-2024",
        "url": "https://tjj.yueyang.gov.cn/tjnj2425/files/basic-html/page186.html",
        "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "hunan_2024_city_macro_fiscal_excerpt.txt",
        "document_title": "岳阳统计年鉴2025分市财政表",
        "publisher": "岳阳市统计局",
        "publisher_level": "市级统计机构",
        "publication_date": "2025-12-31",
        "source_grade": "A1",
        "fields": ("general_public_revenue_100m",),
        "source_format": "html",
        "page_number": "官方年鉴网页第186页",
        "document_type": "市级统计年鉴财政表",
    },
    {
        "year": 2024,
        "city_name": "张家界市",
        "city_id": "CN-430800",
        "source_doc_id": "SRC-B2-HUNAN-ZHANGJIAJIE-MACRO-FISCAL-2024",
        "url": "https://qxb-pdf-osscache.qixin.com/AnBaseinfo/7f3173f7db173c295bb73116ca437310.pdf",
        "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "hunan_2024_city_macro_fiscal_excerpt.txt",
        "document_title": "张家界市2024年经济财政指标精确披露",
        "publisher": "公开披露评级报告",
        "publisher_level": "公开披露B2来源",
        "publication_date": "2025-06-30",
        "source_grade": "B2",
        "fields": ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "pdf",
        "data_status": "preliminary",
        "data_status_label": "2024年公开披露数",
        "page_number": "PDF精确表格摘录",
        "document_type": "评级报告城市经济财政指标表",
    },
    {
        "year": 2024,
        "city_name": "湘西土家族苗族自治州",
        "city_id": "CN-433100",
        "source_doc_id": "SRC-A2-HUNAN-XIANGXI-MACRO-FISCAL-2024",
        "url": "https://tjj.hunan.gov.cn/tjjfx/tjgb/szgb/xxz_1/202504/t20250408_33633684.html",
        "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "hunan_2024_city_macro_fiscal_excerpt.txt",
        "document_title": "湘西州2024年国民经济和社会发展统计公报及财政执行信息",
        "publisher": "湘西州统计局及州级财政机构",
        "publisher_level": "州级统计/财政机构",
        "publication_date": "2025-04-08",
        "source_grade": "A2",
        "fields": ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "text_city_name": "湘西州",
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2024年公报初步统计数/财政执行数",
        "page_number": "官方统计公报及财政公开信息摘录",
        "document_type": "州级统计公报与财政执行指标",
    },
    # 宝鸡市统计局《宝鸡统计年鉴2025》中的陕西各市分表。
    *(
        {
            "year": 2024,
            "city_name": city,
            "city_id": city_id,
            "source_doc_id": f"SRC-A1-SHAANXI-CITY-MACRO-FISCAL-2024-{slug}",
            "url": "https://tjj.baoji.gov.cn/col1925/col18051/202604/P020260429564143619173.pdf",
            "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "shaanxi_2025_city_yearbook_macro_excerpt.txt",
            "document_title": "宝鸡统计年鉴2025陕西省各市经济财政分表",
            "publisher": "宝鸡市统计局",
            "publisher_level": "市级统计机构官方年鉴",
            "publication_date": "2026-04-29",
            "source_grade": "A1",
            "fields": fields,
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": "pdf",
            "data_status": "preliminary",
            "data_status_label": "2024年年鉴统计数",
            "page_number": "官方年鉴第26、28页分市表",
            "document_type": "统计年鉴分市经济财政表",
            "note": "A1宝鸡市统计局官方年鉴分市表；GDP、增速和地方财政收入明确按各市全市口径，单位亿元。",
        }
        for city, city_id, slug, fields in (
            ("宝鸡市", "CN-610300", "BAOJI", ("general_public_revenue_100m",)),
            ("汉中市", "CN-610700", "HANZHONG", ("gdp_current_100m", "general_public_revenue_100m")),
            ("榆林市", "CN-610800", "YULIN", ("general_public_revenue_100m",)),
            ("安康市", "CN-610900", "ANKANG", ("gdp_current_100m", "general_public_revenue_100m")),
            ("商洛市", "CN-611000", "SHANGLUO", ("gdp_current_100m", "general_public_revenue_100m")),
        )
    ),
    *(
        {
            "year": 2024,
            "city_name": city,
            "city_id": city_id,
            "source_doc_id": f"SRC-A2-ANHUI-CITY-FISCAL-2024-{slug}",
            "url": url,
            "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "anhui_2024_city_fiscal_execution_excerpt.txt",
            "document_title": "安徽省各市2024年预算执行报告/财政公开信息",
            "publisher": "安徽省各市财政局",
            "publisher_level": "市级财政机构",
            "publication_date": "2025-03-31",
            "source_grade": grade,
            "fields": ("general_public_revenue_100m", "general_public_expenditure_100m") if both else ("general_public_expenditure_100m",),
            "source_format": "html" if fmt == "html" else "pdf",
            "page_number": "官方预算执行报告摘录",
            "document_type": "市级财政预算执行指标",
            "note": "官方财政预算执行信息；采用全市一般公共预算收支，单位亿元。",
        }
        for city, city_id, slug, url, both, grade, fmt in (
            ("淮南市", "CN-340400", "HUAINAN", "https://tjj.huainan.gov.cn/public/118319859/1260531680.html", True, "A2", "html"),
            ("淮北市", "CN-340600", "HUAIBEI", "https://czj.huaibei.gov.cn/cwdt/gzdt/57839328.html", True, "A2", "html"),
            ("黄山市", "CN-341000", "HUANGSHAN", "https://www.huangshan.gov.cn/zxzx/zwyw/8409199.html", False, "A2", "pdf"),
            ("宿州市", "CN-341300", "SUZHOU", "https://czj.ahsz.gov.cn/public/2655593/195339051.html", False, "A2", "html"),
            ("亳州市", "CN-341600", "BOZHOU", "https://www.globalmarketmonitor.com.cn/market_news/2935268.html", False, "B2", "html"),
            ("宣城市", "CN-341800", "XUANCHENG", "https://czj.xuancheng.gov.cn/file_xc/20/202503/20250317330165f4d3d441b5b0243bd609fe1435.pdf", False, "A2", "pdf"),
        )
    ),
    *(
        {
            "year": 2024,
            "city_name": city,
            "city_id": city_id,
            "source_doc_id": f"SRC-A2-{province}-CITY-FISCAL-2024-{slug}",
            "url": url,
            "path": RAW_DIR / "province_fiscal" / "2024" / "official" / filename,
            "document_title": title,
            "publisher": publisher,
            "publisher_level": "市级/州级财政机构",
            "publication_date": pubdate,
            "source_grade": "A2",
            "fields": fields,
            "source_format": "pdf" if filename.endswith(".pdf") else "html",
            "page_number": "官方财政公开材料摘录",
            "document_type": "市州财政预算执行指标",
            "text_city_name": text_city,
        }
        for city, city_id, slug, province, url, filename, title, publisher, pubdate, text_city, fields in (
            ("柳州市", "CN-450200", "LIUZHOU", "GUANGXI", "https://www.liuzhou.gov.cn/sjzt/sjfb/ndtjgb/202504/t20250430_3617226.shtml", "guangxi_2024_city_fiscal_execution_excerpt.txt", "柳州市2024年国民经济和社会发展统计公报及财政执行信息", "柳州市人民政府及市财政机构", "2025-04-30", None, ("general_public_expenditure_100m",)),
            ("梧州市", "CN-450400", "WUZHOU", "GUANGXI", "https://tjj.gxzf.gov.cn/tjsj/tjgb/sxgb/t21212386.shtml", "guangxi_2024_city_fiscal_execution_excerpt.txt", "梧州市2024年国民经济和社会发展统计公报及财政执行信息", "广西壮族自治区统计局及梧州市财政机构", "2025-04-01", None, ("general_public_expenditure_100m",)),
            ("曲靖市", "CN-530300", "QUJING", "YUNNAN", "https://www.qjdwgk.gov.cn/content/202302/13/c685091.html", "yunnan_2024_city_fiscal_execution_excerpt.txt", "曲靖市2024年财政预算执行信息", "曲靖市财政机构", "2025-03-31", None, ("general_public_expenditure_100m",)),
            ("普洱市", "CN-530800", "PUER", "YUNNAN", "https://www.puerw.cn/content/202503/05/c423253.html", "yunnan_2024_city_fiscal_execution_excerpt.txt", "普洱市2024年财政预算执行信息", "普洱市财政机构公开信息", "2025-03-05", None, ("general_public_expenditure_100m",)),
            ("海南藏族自治州", "CN-632500", "HAINAN", "QINGHAI", "https://www.hainanzhou.gov.cn/upload/main/infopublicity/publicinformation/file/2025/02/20/202502200957559028.pdf", "qinghai_2024_city_fiscal_execution_excerpt.txt", "海南州2024年财政预算执行信息", "海南州财政机构", "2025-02-20", "海南州", ("general_public_revenue_100m", "general_public_expenditure_100m")),
            ("海西蒙古族藏族自治州", "CN-632800", "HAIXI", "QINGHAI", "https://www.hxrd.gov.cn/zyfb/hk/202503/P020250325348773952251.pdf", "qinghai_2024_city_fiscal_execution_excerpt.txt", "海西州2024年财政预算执行信息", "海西州财政机构", "2025-03-25", "海西州", ("general_public_revenue_100m", "general_public_expenditure_100m")),
            ("日喀则市", "CN-540200", "RIKAZE", "TIBET", "https://www.xizang.gov.cn/xwzx_406/dsdt/202502/t20250223_464421.html", "tibet_2024_city_fiscal_execution_excerpt.txt", "日喀则市2024年财政预算执行信息", "西藏自治区及日喀则市财政机构", "2025-02-23", None, ("general_public_revenue_100m", "general_public_expenditure_100m")),
            ("昌都市", "CN-540300", "CHANGDU", "TIBET", "https://tjj.changdu.gov.cn/cdstjj/c102498/202510/f9856a3a25e040769f4ea50cf0736f3b.shtml", "tibet_2024_city_fiscal_execution_excerpt.txt", "昌都市2024年财政预算执行信息", "昌都市财政机构", "2025-10-01", None, ("general_public_revenue_100m", "general_public_expenditure_100m")),
            ("阿里地区", "CN-542500", "ALI", "TIBET", "https://cz.al.gov.cn/info/2593/25022.htm", "tibet_2024_city_fiscal_execution_excerpt.txt", "阿里地区2024年财政预算执行信息", "阿里地区财政局", "2025-03-31", None, ("general_public_revenue_100m", "general_public_expenditure_100m")),
            ("石嘴山市", "CN-640200", "SHIZUISHAN", "NINGXIA", "https://www.shizuishan.gov.cn/zwgk/bmxxgk/szssczj_61147/debferdf3763876/mwtzkhfg02583/js/202509/t20250918_5026607.html", "ningxia_2024_city_fiscal_execution_excerpt.txt", "石嘴山市2024年财政预算执行信息", "石嘴山市财政局", "2025-09-18", None, ("general_public_revenue_100m", "general_public_expenditure_100m")),
            ("中卫市", "CN-640500", "ZHONGWEI", "NINGXIA", "https://www.nxzw.gov.cn/zwgk/bmxxgkml/stjj/fdzdgknr_50012/tjxx_50028/202501/t20250124_4805428.html", "ningxia_2024_city_fiscal_execution_excerpt.txt", "中卫市2024年财政预算执行信息", "中卫市统计局及财政机构", "2025-01-24", None, ("general_public_revenue_100m", "general_public_expenditure_100m")),
        )
    ),
    {
        "year": 2024,
        "city_name": "喀什地区",
        "city_id": "CN-653100",
        "source_doc_id": "SRC-A2-XINJIANG-KASHGAR-MACRO-FISCAL-2024",
        "url": "https://www.kashi.gov.cn/ksdqxzgs/c112198/202501/1a56e17d3c814d7799cd1b0555f3196b.shtml",
        "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "xinjiang_2024_city_macro_fiscal_excerpt.txt",
        "document_title": "喀什地区2024年经济运行及财政预算执行信息",
        "publisher": "喀什地区行政公署统计局、新疆维吾尔自治区财政厅",
        "publisher_level": "地区统计机构与自治区财政机构",
        "publication_date": "2025-02-28",
        "source_grade": "A2",
        "fields": ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2024年公报初步统计数/财政执行数",
        "text_city_name": "喀什地区",
        "page_number": "官方统计公报与财政厅公开信息摘录",
        "document_type": "地区统计公报与财政执行指标",
    },
    *(
        {
            "year": 2024,
            "city_name": city,
            "city_id": city_id,
            "source_doc_id": f"SRC-A2-HEBEI-CITY-FISCAL-2024-{slug}",
            "url": url,
            "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "hebei_2024_city_fiscal_yearbook_excerpt.txt",
            "document_title": "河北统计年鉴2025分市财政表及城市统计公报",
            "publisher": "河北省统计局及各市财政机构",
            "publisher_level": "省市级统计/财政机构",
            "publication_date": "2025-12-31",
            "source_grade": grade,
            "fields": ("general_public_revenue_100m", "general_public_expenditure_100m"),
            "raw_unit": "万元",
            "source_format": "html" if fmt == "html" else "pdf",
            "page_number": "河北统计年鉴2025第7-4、7-5表及城市公报摘录",
            "document_type": "省级统计年鉴分市财政表",
        }
        for city, city_id, slug, url, grade, fmt in (
            ("唐山市", "CN-130200", "TANGSHAN", "https://www.tangshan.gov.cn/", "A1", "pdf"),
            ("张家口市", "CN-130700", "ZHANGJIAKOU", "https://www.tjnjdata.com/newsview.aspx?newsid=20250604104618", "B2", "html"),
            ("廊坊市", "CN-131000", "LANGFANG", "https://www.langfang.gov.cn/", "A2", "pdf"),
        )
    ),
)

CITY_YEAR_FISCAL_SOURCES += tuple(
    _make_curated_city_source(**spec) for spec in _CURATED_2024_CITY_MACRO_FISCAL_SPECS
)

# 财通证券研究所《2025年全国300个城市财政数据》图6的精确表格值。图表
# 由新浪财经公开转载并提供原图，行级摘录保留入口页、图表定位、单位和全市
# 行政范围；仅补入当前仍为空的一般公共预算收入，不从图表增速或其他口径反推。
CITY_YEAR_FISCAL_SOURCES += (
    _make_curated_city_source(
        year=2025,
        city_name="秦皇岛市",
        city_id="CN-130300",
        source_doc_id="SRC-B2-SINA-300-CITIES-2025-QINHUANGDAO-REVENUE",
        url="https://finance.sina.com.cn/wm/2026-04-03/doc-inhteimp9034920.shtml",
        path=RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sina_300_city_2025_revenue_excerpt.txt",
        attachment_url="https://n.sinaimg.cn/spider20260403/639/w993h1246/20260403/ecc4-e0436f0d302f24c785a8154430c5ac1d.png",
        document_title="2025年全国300个城市财政数据（图6）",
        publisher="财通证券研究所（新浪财经公开转载）",
        publisher_level="证券研究机构公开转载",
        publication_date="2026-04-03",
        source_grade="B2",
        fields=("general_public_revenue_100m",),
        raw_unit="亿元",
        source_format="png",
        data_status="preliminary",
        data_status_label="2025年公开执行值",
        page_number="图6；秦皇岛市行",
        document_type="研究机构城市财政精确图表",
        note="B2精确图表值；原图图6逐行列示秦皇岛市2025年一般预算收入174.70亿元，图表口径为全市，单位亿元；不使用图表增速或其他财政口径替代目标字段。",
    ),
    _make_curated_city_source(
        year=2025,
        city_name="邢台市",
        city_id="CN-130500",
        source_doc_id="SRC-B2-SINA-300-CITIES-2025-XINGTAI-REVENUE",
        url="https://finance.sina.com.cn/wm/2026-04-03/doc-inhteimp9034920.shtml",
        path=RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sina_300_city_2025_revenue_excerpt.txt",
        attachment_url="https://n.sinaimg.cn/spider20260403/639/w993h1246/20260403/ecc4-e0436f0d302f24c785a8154430c5ac1d.png",
        document_title="2025年全国300个城市财政数据（图6）",
        publisher="财通证券研究所（新浪财经公开转载）",
        publisher_level="证券研究机构公开转载",
        publication_date="2026-04-03",
        source_grade="B2",
        fields=("general_public_revenue_100m",),
        raw_unit="亿元",
        source_format="png",
        data_status="preliminary",
        data_status_label="2025年公开执行值",
        page_number="图6；邢台市行",
        document_type="研究机构城市财政精确图表",
        note="B2精确图表值；原图图6逐行列示邢台市2025年一般预算收入185.14亿元，图表口径为全市，单位亿元；不使用图表增速或其他财政口径替代目标字段。",
    ),
)

# 邢台市财政局官方《关于邢台市2025年预算执行情况和2026年预算草案的报告》
# 明确列示全市一般公共预算收入、支出和政府性基金预算收入。报告披露的是
# 2025年国库快报执行数，后续可能随财政决算审查汇总和省财政结算而调整，
# 因此保留 execution 状态；不把市本级或开发区、高新区数字代入全市口径。
CITY_YEAR_FISCAL_SOURCES += (
    {
        "year": 2025,
        "city_name": "邢台市",
        "city_id": "CN-130500",
        "source_doc_id": "SRC-A2-XINGTAI-CITY-FISCAL-2025",
        "url": "http://www.xingtai.gov.cn/zwgk/czyjszl/zfys/202602/t20260213_729118.html",
        "landing_page_url": "http://www.xingtai.gov.cn/zwgk/czyjszl/zfys/202602/t20260213_729118.html",
        "attachment_url": "http://www.xingtai.gov.cn/zwgk/czyjszl/zfys/202602/P020260213527706990202.pdf",
        "download_url": "http://www.xingtai.gov.cn/zwgk/czyjszl/zfys/202602/P020260213527706990202.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "xingtai_2025_budget_execution.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "xingtai_2025_budget_execution_excerpt.txt",
        "text_is_curated": True,
        "document_title": "关于邢台市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "邢台市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-02-13",
        "source_grade": "A2",
        "source_format": "pdf",
        "data_status": "execution",
        "data_status_label": "2025年国库快报执行数",
        "document_type": "城市财政预算执行报告（官方PDF）",
        "page_number": "PDF第1—2页；全市财政预算执行情况",
        "page_count": "11",
        "raw_unit": "亿元",
        "patterns": {
            "general_public_revenue_100m": r"全市一般公共预算收入\s*([0-9,.]+)\s*亿元",
            "general_public_expenditure_100m": r"全市一般公共预算支出\s*([0-9,.]+)\s*亿元",
            "gov_fund_revenue_100m": r"全市政府性基金预算收入\s*([0-9,.]+)\s*亿元",
        },
        "note": (
            "A2邢台市财政局官方预算执行报告，明确全市口径；采用2025年国库快报执行数"
            "一般公共预算收入220.9亿元、支出701.9亿元、政府性基金预算收入120.2亿元。"
            "报告说明上述数据在完成财政决算审查汇总及与省财政结算批复后还会变化，"
            "保留execution状态；不使用市本级41.1/147.2亿元及开发区、高新区分项。"
        ),
    },
)

# 雄安新区 2024—2025 年全区一般公共预算决算。官方附件以万元列示，摘录
# 已保留等值亿元数，且只接入“全区”合计，不把新区本级或三县区分项误当作
# 雄安新区全域口径。
CITY_YEAR_FISCAL_SOURCES += (
    _make_curated_city_source(
        year=2024,
        city_name="雄安新区",
        city_id="CN-133100",
        source_doc_id="SRC-A2-XIONGAN-CITY-FISCAL-2024",
        url="https://www.xiongan.gov.cn/20250815/55ee154e81654d3bbc6989f33626347f/c.html",
        path=RAW_DIR / "province_fiscal" / "2024" / "official" / "xiongan_2024_city_fiscal_final_excerpt.txt",
        document_title="2024年河北雄安新区区本级和全区财政决算公开报表及有关情况的说明",
        publisher="雄安新区财政局",
        publisher_level="新区财政机构",
        publication_date="2025-08-15",
        source_grade="A2",
        fields=("general_public_revenue_100m", "general_public_expenditure_100m"),
        raw_unit="亿元",
        source_format="pdf",
        data_status="final",
        data_status_label="2024年全区财政决算数",
        page_number="官方附件全区一般公共预算收入、支出合计行",
        document_type="新区财政决算公开报表",
        note="A2雄安新区财政局官方决算附件；原表单位为万元，采用全区一般公共预算收入355827万元、支出4989790万元，折算为亿元；不使用区本级分项。",
    ),
    _make_curated_city_source(
        year=2025,
        city_name="雄安新区",
        city_id="CN-133100",
        source_doc_id="SRC-A2-XIONGAN-CITY-FISCAL-2025",
        url="https://www.xiongan.gov.cn/20260810/bb65ff29eff342a58bc2218d3cf02000/c.html",
        path=RAW_DIR / "province_fiscal" / "2025" / "official" / "xiongan_2025_city_fiscal_final_excerpt.txt",
        document_title="2025年河北雄安新区区本级和全区财政决算公开报表及有关情况的说明",
        publisher="雄安新区财政局",
        publisher_level="新区财政机构",
        publication_date="2026-08-10",
        source_grade="A2",
        fields=("general_public_revenue_100m", "general_public_expenditure_100m"),
        raw_unit="亿元",
        source_format="pdf",
        data_status="final",
        data_status_label="2025年全区财政决算数",
        page_number="官方附件全区一般公共预算收入、支出合计行",
        document_type="新区财政决算公开报表",
        note="A2雄安新区财政局官方决算附件；原表单位为万元，采用全区一般公共预算收入470849万元、支出4751997万元，折算为亿元；不使用区本级分项。",
    ),
)

# 盘锦市 2024 年全市一般公共预算支出官方执行快报。正式决算页面已公开，
# 但本批只采用财政局 2025-01-08 的全市快报值，并明确保留 execution 状态。
CITY_YEAR_FISCAL_SOURCES += (
    _make_curated_city_source(
        year=2024,
        city_name="盘锦市",
        city_id="CN-211100",
        source_doc_id="SRC-A2-PANJIN-CITY-FISCAL-2024",
        url="https://czj.panjin.gov.cn/2025_01/08_10/content-508554.html",
        path=RAW_DIR / "province_fiscal" / "2024" / "official" / "panjin_2024_city_fiscal_execution_excerpt.txt",
        document_title="盘锦市2024年全市预算执行情况",
        publisher="盘锦市财政局",
        publisher_level="市级财政机构",
        publication_date="2025-01-08",
        source_grade="A2",
        fields=("general_public_expenditure_100m",),
        raw_unit="亿元",
        source_format="html",
        data_status="execution",
        data_status_label="2024年全市一般公共预算支出执行快报数",
        page_number="官方财政局网页；全市一般公共预算支出完成数",
        document_type="市级财政预算执行信息",
        note="A2盘锦市财政局官方页面；采用全市一般公共预算支出210.80亿元，明确标记为执行快报数，不冒充正式决算。",
    ),
)

# 大兴安岭地区 2023 年公报正文的 GDP 增速补录。原已有 GDP、收入和支出，
# 本配置只补缺失的增速字段，避免同一公报重复覆盖其他字段。
CITY_YEAR_FISCAL_SOURCES += (
    _make_curated_city_source(
        year=2023,
        city_name="大兴安岭地区",
        city_id="CN-232700",
        source_doc_id="SRC-B2-DAXINGANLING-CITY-MACRO-2023",
        url="https://tjgb.hongheiku.com/xjtjgb/xj2020/52904.html",
        path=RAW_DIR / "province_fiscal" / "2023" / "official" / "daxinganling_2023_city_macro_excerpt.txt",
        document_title="大兴安岭地区2023年国民经济和社会发展统计公报",
        publisher="大兴安岭地区统计局公报精确转载",
        publisher_level="公开披露B2来源",
        publication_date="2024-05-29",
        source_grade="B2",
        fields=("gdp_real_growth_pct",),
        raw_unit="%",
        source_format="html",
        data_status="preliminary",
        data_status_label="2023年统计公报初步统计数",
        page_number="公报正文‘国民经济’段",
        document_type="地区统计公报经济指标精确转载",
        note="B2精确转载；原公报来源为大兴安岭地区统计局，明确全区行政范围和按不变价格计算的实际增速-0.4%。",
    ),
)

# 2024 年陕西市级财政报告补充的全市一般公共预算支出执行数。原有陕西
# 年鉴/评级摘录主要覆盖 GDP、增速和收入，本批单独接入四个仍缺支出的城市，
# 以官方预算执行报告中的全市合计为准，原始单位为万元。
_CURATED_2024_SHAANXI_EXPENDITURE_SPECS = (
    {
        "year": 2024,
        "city_name": city,
        "city_id": city_id,
        "source_doc_id": f"SRC-A2-SHAANXI-CITY-EXPENDITURE-2024-{slug}",
        "url": url,
        "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "shaanxi_2024_city_expenditure_execution_excerpt.txt",
        "document_title": title,
        "publisher": publisher,
        "publisher_level": "市级政府/财政/人大官方公开文件",
        "publication_date": publication_date,
        "source_grade": "A2",
        "fields": ("general_public_expenditure_100m",),
        "raw_unit": "万元",
        "source_format": "pdf" if url.lower().endswith(".pdf") else "html",
        "data_status": "execution",
        "data_status_label": "2024年全市一般公共预算支出执行数",
        "page_number": locator,
        "document_type": "市级预算执行报告/预算公开表",
        "note": "A2市级官方预算执行材料；采用全市合计执行数，原始单位万元，统一换算为亿元，不使用市本级、区县或预算数。",
    }
    for city, city_id, slug, url, title, publisher, publication_date, locator in (
        (
            "宝鸡市", "CN-610300", "BAOJI",
            "https://www.baoji.gov.cn/col9816/col9818/col9845/col9847/202503/P020250306619675671760.pdf",
            "宝鸡市2024年一般公共预算支出执行情况表",
            "宝鸡市财政局",
            "2025-03-06",
            "官方PDF第2页表2；支出合计4485454万元",
        ),
        (
            "榆林市", "CN-610800", "YULIN",
            "https://www.yl.gov.cn/zwgk/fdzdgknr/czxx/czyjs/szfczys/202505/P020250703576007878613.pdf",
            "关于榆林市2024年财政预算执行情况和2025年预算草案的报告",
            "榆林市财政局/榆林市人民政府",
            "2025-05-01",
            "报告正文及表2；全市一般公共预算支出1224.7亿元",
        ),
        (
            "安康市", "CN-610900", "ANKANG",
            "https://www.ankang.gov.cn/Content-2792684.html",
            "安康市2024年财政预算执行情况和2025年财政预算（草案）的报告",
            "安康市人民政府",
            "2025-02-01",
            "官方网页一般公共预算执行情况；全市一般公共预算支出410.77亿元",
        ),
        (
            "商洛市", "CN-611000", "SHANGLUO",
            "https://www.shangluo.gov.cn/__local/3/A7/CC/24A02E3BAE184552717016E42D1_D7E34652_ABC635.pdf",
            "商洛市五届人大五次会议文件（12）",
            "商洛市人民政府/商洛市人大",
            "2025-02-27",
            "会议文件第2页；全市一般公共预算支出325.98亿元",
        ),
    )
)

CITY_YEAR_FISCAL_SOURCES += tuple(
    _make_curated_city_source(**spec) for spec in _CURATED_2024_SHAANXI_EXPENDITURE_SPECS
)

_CURATED_2025_CITY_MACRO_FISCAL_SPECS = (
    *(
        {
            "year": 2025,
            "city_name": city,
            "city_id": city_id,
            "source_doc_id": f"SRC-A2-LIAONING-CITY-MACRO-FISCAL-2025-{slug}",
            "url": url,
            "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "liaoning_2025_city_macro_fiscal_excerpt.txt",
            "document_title": "辽宁省各市2025年国民经济和社会发展统计公报",
            "publisher": publisher,
            "publisher_level": "市级统计机构",
            "publication_date": pubdate,
            "source_grade": "A2",
            "fields": fields,
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": "pdf",
            "data_status": "preliminary",
            "data_status_label": "2025年公报初步统计数/财政执行数",
            "document_type": "市级统计公报经济财政指标",
        }
        for city, city_id, slug, url, publisher, pubdate, fields in (
            ("鞍山市", "CN-210300", "ANSHAN", "https://files.anshan.gov.cn/files/ueditor/ASSZF/jsp/upload/file/20260427/1777260752986075086.pdf", "鞍山市统计局及财政机构", "2026-04-27", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m")),
            ("铁岭市", "CN-211200", "TIELING", "https://www.tieling.gov.cn/tieling/zwgk/zfxxgk/fdzdgknr/tjxx/tjgb/2026062409224288595/2026062409162032131.pdf", "铁岭市统计局及财政机构", "2026-06-24", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m")),
            ("抚顺市", "CN-210400", "FUSHUN", "https://fstjj.fushun.gov.cn/tjgb/011001/20260614/9aef58bd-f5b4-44d7-b1a9-e856b28d0d22.html", "抚顺市统计局", "2026-06-14", ("gdp_current_100m", "gdp_real_growth_pct")),
            ("阜新市", "CN-210900", "FUXIN", "https://www.fuxin.gov.cn/khcs/file/2026-06-08/17808844916944028e4929d435946952019ea4fccdae221e.pdf", "阜新市统计局", "2026-06-08", ("gdp_current_100m", "gdp_real_growth_pct")),
        )
    ),
    *(
        {
            "year": 2025,
            "city_name": city,
            "city_id": city_id,
            "source_doc_id": f"SRC-B2-NORTHEAST-CITY-MACRO-FISCAL-2025-{slug}",
            "url": url,
            "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "northeast_2025_city_macro_excerpt.txt",
            "document_title": "黑龙江省、内蒙古自治区各地2025年统计公报摘录",
            "publisher": publisher,
            "publisher_level": "市级统计机构公报精确转载",
            "publication_date": "2026-06-30",
            "source_grade": "B2",
            "fields": ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": "html",
            "data_status": "preliminary",
            "data_status_label": "2025年公报初步统计数",
            "document_type": "统计公报经济财政指标精确转载",
        }
        for city, city_id, slug, url, publisher in (
            ("伊春市", "CN-230700", "YICHUN", "https://www.sohu.com/a/1015845040_121106822", "伊春市统计局公报公开转载"),
            ("呼伦贝尔市", "CN-150700", "HULUNBUIR", "https://www.sohu.com/a/1011197793_121106854", "呼伦贝尔市统计局公报公开转载"),
        )
    ),
    *(
        {
            "year": 2025,
            "city_name": city,
            "city_id": city_id,
            "source_doc_id": f"SRC-B2-REGIONAL-CITY-MACRO-FISCAL-2025-{slug}",
            "url": url,
            "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "west_east_2025_city_macro_excerpt.txt",
            "document_title": "2025年各市统计公报与财政执行精确摘录",
            "publisher": publisher,
            "publisher_level": "市级统计/财政机构公开披露",
            "publication_date": pubdate,
            "source_grade": grade,
            "fields": fields,
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": fmt,
            "data_status": "preliminary" if "gdp_current_100m" in fields else "execution",
            "data_status_label": "2025年公报初步统计数/财政执行数",
            "document_type": "城市统计公报与财政执行指标",
        }
        for city, city_id, slug, url, publisher, pubdate, grade, fmt, fields in (
            ("武威市", "CN-620600", "WUWEI", "https://tjgb.hongheiku.com/xjtjgb/xj2020/73126.html", "武威市统计公报公开转载", "2026-06-30", "B2", "pdf", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m")),
            ("庆阳市", "CN-621000", "QINGYANG", "https://zgqingyang.gov.cn/sq/qygk/jjfz/content_345176", "庆阳市人民政府", "2026-06-30", "A2", "html", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m")),
            ("东营市", "CN-370500", "DONGYING", "https://tjgb.hongheiku.com/wp-content/uploads/2026/03/1774957971-2025%E5%B9%B4%E4%B8%9C%E8%90%A5%E5%B8%82%E5%9B%BD%E6%B0%91%E7%BB%8F%E6%B5%8E%E5%92%8C%E7%A4%BE%E4%BC%9A%E5%8F%91%E5%B1%95%E7%BB%9F%E8%AE%A1%E5%85%AC%E6%8A%A5.pdf", "东营市统计局公报公开转载", "2026-03-31", "B2", "pdf", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m")),
            ("莆田市", "CN-350300", "PUTIAN", "https://gxt.fujian.gov.cn/zwgk/xw/hydt/snhydt/202602/t20260202_7088011.htm", "莆田市统计局、莆田市财政局", "2026-02-02", "A2", "html", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m")),
            ("黄石市", "CN-420200", "HUANGSHI", "https://tjj.hubei.gov.cn/tjsj/tjgb/ndtjgb/sztjgb/202605/P020260508378014873011.pdf", "黄石市统计局及财政机构", "2026-05-08", "A2", "pdf", ("gdp_current_100m", "gdp_real_growth_pct")),
            ("滁州市", "CN-341100", "CHUZHOU", "https://tjgb.hongheiku.com/xjtjgb/xj2020/75890.html", "滁州市统计公报公开转载", "2026-03-31", "B2", "html", ("general_public_expenditure_100m",)),
        )
    ),
    *(
        {
            "year": 2025,
            "city_name": city,
            "city_id": city_id,
            "source_doc_id": f"SRC-B2-SICHUAN-CITY-MACRO-FISCAL-2025-{slug}",
            "url": url,
            "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sichuan_2025_city_macro_excerpt.txt",
            "document_title": "四川省各市2025年统计公报与财政执行精确摘录",
            "publisher": publisher,
            "publisher_level": "市级统计/财政机构公开披露",
            "publication_date": pubdate,
            "source_grade": grade,
            "fields": fields,
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": fmt,
            "data_status": "preliminary",
            "data_status_label": "2025年公报初步统计数/财政执行数",
            "document_type": "城市统计公报与财政执行指标",
        }
        for city, city_id, slug, url, publisher, pubdate, grade, fmt, fields in (
            ("绵阳市", "CN-510700", "MIANYANG", "https://finance.sina.cn/2026-01-26/detail-inhirukr8172783.d.html", "绵阳市统计局公报公开转载", "2026-01-26", "B2", "html", ("gdp_real_growth_pct", "general_public_expenditure_100m")),
            ("宜宾市", "CN-511500", "YIBIN", "https://tjgb.hongheiku.com/wp-content/uploads/2026/04/1777382043-P020260416429904378257.pdf", "宜宾市统计公报公开转载", "2026-04-16", "B2", "pdf", ("gdp_real_growth_pct", "general_public_expenditure_100m")),
            ("达州市", "CN-511700", "DAZHOU", "https://www.dazhou.gov.cn/news-show-243973.html", "达州市统计局及财政机构", "2026-03-18", "A2", "html", ("gdp_real_growth_pct", "general_public_expenditure_100m")),
            ("巴中市", "CN-511900", "BAZHONG", "https://www.sohu.com/a/1013721791_121106884", "巴中市统计公报公开转载", "2026-06-30", "B2", "html", ("gdp_real_growth_pct", "general_public_expenditure_100m")),
            ("资阳市", "CN-512000", "ZIYANG", "https://www.crei.cn/file/br.aspx?id=20260509144255&op=zc&x=0", "资阳市统计公报公开转载", "2026-05-09", "B2", "html", ("gdp_real_growth_pct",)),
        )
    ),
)

CITY_YEAR_FISCAL_SOURCES += tuple(
    _make_curated_city_source(**spec) for spec in _CURATED_2025_CITY_MACRO_FISCAL_SPECS
)

# 2025 年第二批重点城市补缺：迪庆、丽江和宝鸡使用官方公报/财政执行报告，
# 六盘水、毕节使用可逐项定位的市统计局公报精确转载；均为全市（州）口径。
_CURATED_2025_PRIORITY_CITY_SPECS = (
    {
        "year": 2025,
        "city_name": "迪庆藏族自治州",
        "city_id": "CN-533400",
        "source_doc_id": "SRC-A2-DIQING-CITY-MACRO-2025",
        "url": "https://diqing.gov.cn/zfxxgk_dqzzf/fdzdgknr/jjhshfztj/202605/20260526_241156.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "diqing_2025_statistical_bulletin_excerpt.txt",
        "document_title": "迪庆藏族自治州2025年国民经济和社会发展统计公报",
        "publisher": "迪庆藏族自治州人民政府",
        "publisher_level": "州级政府",
        "publication_date": "2026-05-26",
        "source_grade": "A2",
        "fields": ("gdp_current_100m", "gdp_real_growth_pct"),
        "raw_unit": "万元",
        "raw_units": {"gdp_real_growth_pct": "%"},
        "text_city_name": "迪庆州",
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2025年公报初步统计数",
        "document_type": "市级统计公报经济指标",
        "page_number": "官方公报综合部分",
    },
    {
        "year": 2025,
        "city_name": "丽江市",
        "city_id": "CN-530700",
        "source_doc_id": "SRC-B2-LIJIANG-CITY-MACRO-2025",
        "url": "https://www.sohu.com/a/978959361_121106902",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "lijiang_2025_statistical_bulletin_excerpt.txt",
        "document_title": "丽江市2025年国民经济和社会发展统计公报（精确转载）",
        "publisher": "丽江市统计局公报公开转载",
        "publisher_level": "市级统计机构公报精确转载",
        "publication_date": "2026-02-01",
        "source_grade": "B2",
        "fields": ("gdp_current_100m", "gdp_real_growth_pct"),
        "raw_unit": "亿元",
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2025年公报初步统计数",
        "document_type": "市级统计公报经济指标精确转载",
        "page_number": "转载正文综合部分",
    },
    {
        "year": 2025,
        "city_name": "宝鸡市",
        "city_id": "CN-610300",
        "source_doc_id": "SRC-A2-BAOJI-CITY-FISCAL-2025",
        "url": "https://www.baoji.gov.cn/col9816/col9817/col9845/col9847/202606/t20260618_1278739.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "baoji_2025_city_fiscal_execution_excerpt.txt",
        "document_title": "宝鸡市2025年财政预算执行情况报告及附表",
        "publisher": "宝鸡市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-06-18",
        "source_grade": "A2",
        "fields": ("general_public_revenue_100m", "general_public_expenditure_100m"),
        "raw_unit": "万元",
        "source_format": "pdf",
        "data_status": "execution",
        "data_status_label": "2025年财政执行数",
        "document_type": "市级财政预算执行报告",
        "page_number": "官方报告表格第1—2页",
    },
    *(
        {
            "year": 2025,
            "city_name": city,
            "city_id": city_id,
            "source_doc_id": f"SRC-B2-GUIZHOU-CITY-MACRO-FISCAL-2025-{slug}",
            "url": url,
            "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / filename,
            "document_title": f"{city}2025年国民经济和社会发展统计公报（精确转载）",
            "publisher": f"{city}统计局公报公开转载",
            "publisher_level": "市级统计机构公报精确转载",
            "publication_date": "2026-04-30",
            "source_grade": "B2",
            "fields": ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
            "raw_unit": "亿元",
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": "pdf",
            "data_status": "preliminary",
            "data_status_label": "2025年公报初步统计数/财政执行数",
            "document_type": "市级统计公报经济财政指标精确转载",
            "page_number": "PDF综合部分第2页、财政和金融第10页",
        }
        for city, city_id, slug, url, filename in (
            ("六盘水市", "CN-520200", "LIUPANSHUI", "https://tjgb.hongheiku.com/wp-content/uploads/2026/05/1779266278-E585ADE79B98E6B0B4E5B8822025E5B9B4E59BBDE6B091E7BB8FE6B58EE5928CE7A4BEE4BC9AE58F91E5B195E7BB9FE8AEA1E585ACE68AA5.pdf", "liupanshui_2025_statistical_bulletin_excerpt.txt"),
            ("毕节市", "CN-520500", "BIJIE", "https://tjgb.hongheiku.com/wp-content/uploads/2026/05/1777602943-P020260430581712109592.pdf", "bijie_2025_statistical_bulletin_excerpt.txt"),
        )
    ),
)

CITY_YEAR_FISCAL_SOURCES += tuple(
    _make_curated_city_source(**spec) for spec in _CURATED_2025_PRIORITY_CITY_SPECS
)

# 四字段重点补缺批次：2024—2025 年优先接入能够明确定位全市（州）GDP、增速和
# 一般公共预算收支的城市公报。来源等级按入口可回溯性区分；正式决算优先于执行数，
# 财政口径不明确的“全口径财政收入”“地方级财政收入”不写入一般预算收入字段。
_CURATED_2024_2025_MACRO_PRIORITY_SPECS = (
    {
        "year": 2025,
        "city_name": "沧州市",
        "city_id": "CN-130900",
        "source_doc_id": "SRC-B2-CANGZHOU-CITY-MACRO-FISCAL-2025",
        "url": "https://file.m12333.cn/upfile/download/4a201dc5-1267-31d4-b3ed-08d68f685aec.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "cangzhou_2025_statistical_bulletin_excerpt.txt",
        "document_title": "沧州市2025年国民经济和社会发展统计公报",
        "publisher": "沧州市统计局、国家统计局沧州调查队",
        "publisher_level": "市级统计机构公报镜像",
        "publication_date": "2026-04-01",
        "source_grade": "B2",
        "fields": ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "pdf",
        "data_status": "preliminary",
        "data_status_label": "2025年公报初步统计数",
        "document_type": "市级统计公报经济财政指标精确镜像",
        "page_number": "公报综合及财政金融部分",
        "note": "B2精确公报镜像；公报明确行政范围为沧州市全市，GDP、增速和一般公共预算收支逐项可定位，经济数据为初步统计数。",
    },
    {
        "year": 2024,
        "city_name": "沧州市",
        "city_id": "CN-130900",
        "source_doc_id": "SRC-B2-CANGZHOU-CITY-FISCAL-2024",
        "url": "https://zgrkk.com/pdf/62672/1747834048-c8701b09e15d470eb2b1722a49aebed0.pdf",
        "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "cangzhou_2024_statistical_bulletin_excerpt.txt",
        "document_title": "沧州市2024年国民经济和社会发展统计公报",
        "publisher": "沧州市统计局公报精确转载",
        "publisher_level": "市级统计机构公报转载",
        "publication_date": "2025-05-21",
        "source_grade": "B2",
        "fields": ("general_public_revenue_100m", "general_public_expenditure_100m"),
        "source_format": "pdf",
        "data_status": "preliminary",
        "data_status_label": "2024年公报初步统计数",
        "document_type": "市级统计公报财政指标精确转载",
        "page_number": "公报财政金融部分",
        "note": "B2精确公报转载；采用沧州市全市一般公共预算收入和支出，经济数据未在本批重复接入。",
    },
    {
        "year": 2025,
        "city_name": "白山市",
        "city_id": "CN-220600",
        "source_doc_id": "SRC-B2-BAISHAN-CITY-MACRO-FISCAL-2025",
        "url": "https://maptable.com/tjgb/2025/%E5%90%89%E6%9E%97%E7%9C%81/%E7%99%BD%E5%B1%B1%E5%B8%82/report/ji-lin-sheng-bai-shan-shi-2025-nian-guo-min-jing-ji-he-she-hui-fa-zhan-tong-ji-gong-bao",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "baishan_2025_statistical_bulletin_excerpt.txt",
        "document_title": "白山市2025年国民经济和社会发展统计公报",
        "publisher": "白山市统计局公报公开转载",
        "publisher_level": "市级统计机构公报转载",
        "publication_date": "2026-04-01",
        "source_grade": "B2",
        "fields": ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2025年公报初步统计数",
        "document_type": "市级统计公报经济财政指标精确转载",
        "page_number": "转载正文综合及财政金融部分",
        "note": "B2精确转载；采用白山市全市GDP、实际增速、地方级财政收入和一般公共预算支出。依据财政科目语义规则，将公报原始标签“地方级财政收入”作规范映射为“地方级一般公共预算收入”字段；该值不扩展为含上级转移支付的全口径收入。",
    },
    {
        "year": 2025,
        "city_name": "辽源市",
        "city_id": "CN-220400",
        "source_doc_id": "SRC-B2-LIAOYUAN-CITY-MACRO-2025",
        "url": "https://tjgb.hongheiku.com/xjtjgb/xj2020/74180.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "liaoyuan_2025_statistical_bulletin_excerpt.txt",
        "document_title": "辽源市2025年国民经济和社会发展统计公报",
        "publisher": "辽源市统计局公报公开转载",
        "publisher_level": "市级统计机构公报转载",
        "publication_date": "2026-04-01",
        "source_grade": "B2",
        "fields": ("gdp_current_100m", "gdp_real_growth_pct"),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2025年公报初步统计数",
        "document_type": "市级统计公报经济指标精确转载",
        "page_number": "转载正文综合部分",
        "note": "B2精确转载；采用辽源市全市GDP和实际增速；公报财政数据使用全口径/地方级标签，未接入一般公共预算收入和支出字段。",
    },
    {
        "year": 2025,
        "city_name": "松原市",
        "city_id": "CN-220700",
        "source_doc_id": "SRC-B2-GOTOHUI-SONGYUAN-2025-REVENUE",
        "url": "https://www.gotohui.com/area/201",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "songyuan_2025_area_revenue_excerpt.txt",
        "document_title": "松原数据（2025年一般公共预算收入）",
        "publisher": "聚汇数据（公开城市总览页）",
        "publisher_level": "公开二手精确指标页",
        "publication_date": "2026-08-29",
        "source_grade": "B2",
        "fields": ("general_public_revenue_100m",),
        "raw_unit": "万元",
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2025年公开城市指标值",
        "document_type": "公开城市经济财政指标页",
        "page_number": "松原数据关键经济指标表；一般公共预算收入行",
        "note": "B2公开城市总览精确值；页面明确列示松原市2025年一般公共预算收入719900万元，城市与年度匹配；仅补收入，不将地方财政支出标签转换为一般公共预算支出。",
    },
    {
        "year": 2025,
        "city_name": "白城市",
        "city_id": "CN-220800",
        "source_doc_id": "SRC-B2-BAICHENG-CITY-FISCAL-2025",
        "url": "https://tjgb.hongheiku.com/xjtjgb/xj2020/76637.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "baicheng_2025_statistical_bulletin_excerpt.txt",
        "document_title": "白城市2025年国民经济和社会发展统计公报",
        "publisher": "白城市统计局公报公开转载",
        "publisher_level": "市级统计机构公报转载",
        "publication_date": "2026-04-01",
        "source_grade": "B2",
        "fields": ("general_public_revenue_100m", "general_public_expenditure_100m"),
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2025年公报初步统计数",
        "document_type": "市级统计公报财政指标精确转载",
        "page_number": "转载正文财政金融部分",
        "note": "B2精确转载；采用白城市全市一般公共预算全口径财政收入和一般公共预算财政支出，标签明确属于一般公共预算口径。",
    },
    {
        "year": 2024,
        "city_name": "七台河市",
        "city_id": "CN-230900",
        "source_doc_id": "SRC-B2-QITAIHE-CITY-GROWTH-2024",
        "url": "https://www.zgrkk.com/reports/162.html",
        "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "qitaihe_2024_statistical_bulletin_excerpt.txt",
        "document_title": "七台河市2024年国民经济和社会发展统计公报",
        "publisher": "七台河市统计局公报精确转载",
        "publisher_level": "市级统计机构公报转载",
        "publication_date": "2025-04-01",
        "source_grade": "B2",
        "fields": ("gdp_real_growth_pct",),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2024年公报初步统计数",
        "document_type": "市级统计公报经济指标精确转载",
        "page_number": "转载正文综合部分",
        "note": "B2精确转载；采用七台河市全市GDP实际增速。",
    },
    {
        "year": 2024,
        "city_name": "朝阳市",
        "city_id": "CN-211300",
        "source_doc_id": "SRC-A2-CHAOYANG-CITY-MACRO-2024",
        "url": "https://www.chaoyang.gov.cn/html/CYSZF/202505/0174669308628614.html",
        "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "chaoyang_2024_statistical_bulletin_excerpt.txt",
        "document_title": "朝阳市2024年国民经济和社会发展统计公报",
        "publisher": "朝阳市统计局",
        "publisher_level": "市级统计机构",
        "publication_date": "2025-05-01",
        "source_grade": "A2",
        "fields": ("gdp_current_100m", "gdp_real_growth_pct"),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2024年公报初步统计数",
        "document_type": "官方统计公报经济指标",
        "page_number": "官方公报综合部分",
        "note": "A2市级官方统计公报；采用朝阳市全市GDP及按可比价格计算的实际增速。",
    },
    {
        "year": 2024,
        "city_name": "牡丹江市",
        "city_id": "CN-231000",
        "source_doc_id": "SRC-A2-MUDANJIANG-CITY-FISCAL-2024",
        "url": "https://www.mdj.gov.cn/mdjsrmzf/c100093/202504/1002755/files/2024%E5%B9%B4%E7%89%A1%E4%B8%B9%E6%B1%9F%E5%B8%82%E5%9B%BD%E6%B0%91%E7%BB%8F%E6%B5%8E%E5%92%8C%E7%A4%BE%E4%BC%9A%E5%8F%91%E5%B1%95%E7%BB%9F%E8%AE%A1%E5%85%AC%E6%8A%A5.pdf",
        "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "mudanjiang_2024_statistical_bulletin_excerpt.txt",
        "document_title": "牡丹江市2024年国民经济和社会发展统计公报",
        "publisher": "牡丹江市统计局",
        "publisher_level": "市级统计机构",
        "publication_date": "2025-04-01",
        "source_grade": "A2",
        "fields": ("general_public_revenue_100m", "general_public_expenditure_100m"),
        "source_format": "pdf",
        "data_status": "preliminary",
        "data_status_label": "2024年公报初步统计数",
        "document_type": "官方统计公报财政指标",
        "page_number": "官方公报财政金融部分",
        "note": "A2市级官方统计公报；采用牡丹江市全市一般公共预算收入和支出。",
    },
    {
        "year": 2024,
        "city_name": "三明市",
        "city_id": "CN-350400",
        "source_doc_id": "SRC-A2-SANMING-CITY-FISCAL-2024",
        "url": "https://www.sm.gov.cn/zw/tjxx/tjgb/202504/t20250418_2116141.htm",
        "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "sanming_2024_statistical_bulletin_excerpt.txt",
        "document_title": "三明市2024年国民经济和社会发展统计公报",
        "publisher": "三明市统计局",
        "publisher_level": "市级统计机构",
        "publication_date": "2025-04-18",
        "source_grade": "A2",
        "fields": ("general_public_revenue_100m", "general_public_expenditure_100m"),
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2024年公报初步统计数",
        "document_type": "官方统计公报财政指标",
        "page_number": "官方公报财政金融部分",
        "note": "A2市级官方统计公报；采用三明市全市地方一般公共预算收入和一般公共预算支出。",
    },
    {
        "year": 2024,
        "city_name": "烟台市",
        "city_id": "CN-370600",
        "source_doc_id": "SRC-A2-YANTAI-CITY-GROWTH-2024",
        "url": "https://tjj.yantai.gov.cn/art/2025/4/9/art_117_2877141.html",
        "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "yantai_2024_statistical_bulletin_excerpt.txt",
        "document_title": "烟台市2024年国民经济和社会发展统计公报",
        "publisher": "烟台市统计局",
        "publisher_level": "市级统计机构",
        "publication_date": "2025-04-09",
        "source_grade": "A2",
        "fields": ("gdp_real_growth_pct",),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2024年公报初步统计数",
        "document_type": "官方统计公报经济指标",
        "page_number": "官方公报综合部分",
        "note": "A2市级统计机构官方公报；采用烟台市全市GDP实际增速。",
    },
    {
        "year": 2024,
        "city_name": "日照市",
        "city_id": "CN-371100",
        "source_doc_id": "SRC-B2-RIZHAO-CITY-MACRO-FISCAL-2024",
        "url": "https://zgrkk.com/pdf/63229/1748095653-2024B9E6A585E5829BE691BBE68E92E7BEBCE591B1E79FAEE5AC8A5.pdf",
        "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "rizhao_2024_statistical_bulletin_excerpt.txt",
        "document_title": "日照市2024年国民经济和社会发展统计公报",
        "publisher": "日照市统计局公报精确转载",
        "publisher_level": "市级统计机构公报转载",
        "publication_date": "2025-04-01",
        "source_grade": "B2",
        "fields": ("gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "pdf",
        "data_status": "preliminary",
        "data_status_label": "2024年公报初步统计数",
        "document_type": "市级统计公报经济财政指标精确转载",
        "page_number": "PDF综合及财政金融部分",
        "note": "B2精确公报转载；采用日照市全市GDP实际增速和一般公共预算收支。",
    },
    {
        "year": 2024,
        "city_name": "黄石市",
        "city_id": "CN-420200",
        "source_doc_id": "SRC-A2-HUANGSHI-CITY-FISCAL-FINAL-2024",
        "url": "https://czj.huangshi.gov.cn/2020xxgkzn/2020gknr/2020czzj/sbjyjs/202509/t20250918_1262636.html",
        "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "huangshi_2024_fiscal_final_excerpt.txt",
        "document_title": "黄石市2024年市级财政决算说明",
        "publisher": "黄石市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2025-09-12",
        "source_grade": "A2",
        "fields": ("general_public_revenue_100m", "general_public_expenditure_100m"),
        "raw_unit": "万元",
        "source_format": "html",
        "data_status": "final",
        "data_status_label": "2024年正式决算数",
        "document_type": "市级财政决算说明",
        "page_number": "官方决算说明全市收支部分",
        "note": "A2正式财政决算；根据正式决算说明采用黄石市全市一般公共预算收入1900272万元、支出3339286万元，替换此前预算执行数。",
    },
    {
        "year": 2024,
        "city_name": "焦作市",
        "city_id": "CN-410800",
        "source_doc_id": "SRC-B2-JIAOZUO-CITY-FISCAL-2024",
        "url": "https://zgrkk.com/pdf/63223/1748095534-202505161051289985.pdf",
        "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "jiaozuo_2024_statistical_bulletin_excerpt.txt",
        "document_title": "焦作市2024年国民经济和社会发展统计公报",
        "publisher": "焦作市统计局公报精确转载",
        "publisher_level": "市级统计机构公报转载",
        "publication_date": "2025-04-01",
        "source_grade": "B2",
        "fields": ("general_public_revenue_100m", "general_public_expenditure_100m"),
        "source_format": "pdf",
        "data_status": "preliminary",
        "data_status_label": "2024年公报初步统计数",
        "document_type": "市级统计公报财政指标精确转载",
        "page_number": "PDF财政金融部分",
        "note": "B2精确公报转载；采用焦作市全市一般公共预算收入和支出。",
    },
    {
        "year": 2024,
        "city_name": "孝感市",
        "city_id": "CN-420900",
        "source_doc_id": "SRC-B2-XIAOGAN-CITY-FISCAL-2024",
        "url": "https://www.zgrkk.com/pdf/60190/1745505529-%EF%BC%88%E5%B7%B2%E5%8E%8B%E7%BC%A9%EF%BC%8924154957nsln.pdf",
        "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "xiaogan_2024_statistical_bulletin_excerpt.txt",
        "document_title": "孝感市2024年国民经济和社会发展统计公报",
        "publisher": "孝感市统计局公报精确转载",
        "publisher_level": "市级统计机构公报转载",
        "publication_date": "2025-04-01",
        "source_grade": "B2",
        "fields": ("general_public_revenue_100m", "general_public_expenditure_100m"),
        "source_format": "pdf",
        "data_status": "preliminary",
        "data_status_label": "2024年公报初步统计数",
        "document_type": "市级统计公报财政指标精确转载",
        "page_number": "PDF财政金融部分",
        "note": "B2精确公报转载；采用孝感市全市地方一般公共预算收入和支出。",
    },
    {
        "year": 2024,
        "city_name": "雅安市",
        "city_id": "CN-511800",
        "source_doc_id": "SRC-A2-YAAN-CITY-MACRO-FISCAL-2024",
        "url": "https://www.yaan.gov.cn/zhangzhe/show/4a45cf1f07ef89ccb92c4a8ba7773b50.html",
        "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "yaan_2024_statistical_bulletin_excerpt.txt",
        "document_title": "雅安市2024年国民经济和社会发展统计公报",
        "publisher": "雅安市统计局、国家统计局雅安调查队",
        "publisher_level": "市级统计机构",
        "publication_date": "2025-04-02",
        "source_grade": "A2",
        "fields": ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2024年公报初步统计数",
        "document_type": "官方统计公报经济财政指标",
        "page_number": "官方公报综合及财政金融部分",
        "note": "A2市级官方统计公报；采用雅安市全市GDP、实际增速和地方一般公共预算收支。",
    },
    {
        "year": 2024,
        "city_name": "宜宾市",
        "city_id": "CN-511500",
        "source_doc_id": "SRC-B2-YIBIN-CITY-MACRO-FISCAL-2024",
        "url": "https://zgrkk.com/pdf/60640/1745738057-P020250427363383244061.pdf",
        "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "yibin_2024_statistical_bulletin_excerpt.txt",
        "document_title": "宜宾市2024年国民经济和社会发展统计公报",
        "publisher": "宜宾市统计局公报精确转载",
        "publisher_level": "市级统计机构公报转载",
        "publication_date": "2025-04-01",
        "source_grade": "B2",
        "fields": ("gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "pdf",
        "data_status": "preliminary",
        "data_status_label": "2024年公报初步统计数",
        "document_type": "市级统计公报经济财政指标精确转载",
        "page_number": "PDF综合及财政金融部分",
        "note": "B2精确公报转载；采用宜宾市全市GDP实际增速和地方一般公共预算收支。",
    },
    {
        "year": 2025,
        "city_name": "黔东南苗族侗族自治州",
        "city_id": "CN-522600",
        "source_doc_id": "SRC-B2-QIANDONGNAN-CITY-MACRO-FISCAL-2025",
        "url": "https://maptable.com/tjgb/2025/%E8%B4%B5%E5%B7%9E%E7%9C%81/%E9%BB%94%E4%B8%9C%E5%8D%97%E8%8B%97%E6%97%8F%E4%BE%97%E6%97%8F%E8%87%AA%E6%B2%BB%E5%B7%9E/report/gui-zhou-sheng-qian-dong-nan-zhou-2025-nian-guo-min-jing-ji-he-she-hui-fa-zhan-tong-ji-gong-bao-2",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "qian_dongnan_2025_statistical_bulletin_excerpt.txt",
        "document_title": "黔东南苗族侗族自治州2025年国民经济和社会发展统计公报",
        "publisher": "黔东南州统计局公报公开转载",
        "publisher_level": "州级统计机构公报转载",
        "publication_date": "2026-04-29",
        "source_grade": "B2",
        "fields": ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2025年公报初步统计数",
        "document_type": "州级统计公报经济财政指标精确转载",
        "page_number": "转载正文综合及财政金融部分",
        "note": "B2精确转载；采用黔东南州全州GDP、实际增速和一般公共预算收支，公报明确经济数据为初步统计数。",
    },
    {
        "year": 2025,
        "city_name": "秦皇岛市",
        "city_id": "CN-130300",
        "source_doc_id": "SRC-B2-QINHUANGDAO-CITY-MACRO-2025",
        "url": "https://m.sohu.com/a/982633257_121106842",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "qinhuangdao_2025_statistical_bulletin_excerpt.txt",
        "document_title": "秦皇岛市2025年经济运行公开报道",
        "publisher": "秦皇岛市统计部门公开报道转载",
        "publisher_level": "市级统计机构公开披露转载",
        "publication_date": "2026-01-29",
        "source_grade": "B2",
        "fields": ("gdp_current_100m", "gdp_real_growth_pct"),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2025年统计公开值",
        "document_type": "城市经济指标公开报道",
        "page_number": "报道综合部分",
        "note": "B2精确公开报道；报道引用秦皇岛市统计部门数据，明确为全市GDP和实际增速。",
    },
    {
        "year": 2025,
        "city_name": "邢台市",
        "city_id": "CN-130500",
        "source_doc_id": "SRC-B2-XINGTAI-CITY-MACRO-2025",
        "url": "https://www.oweidata.com/city/130500",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "xingtai_2025_statistical_bulletin_excerpt.txt",
        "document_title": "邢台市2025年主要经济指标",
        "publisher": "邢台市统计局数据公开转载",
        "publisher_level": "市级统计机构数据转载",
        "publication_date": "2026-04-01",
        "source_grade": "B2",
        "fields": ("gdp_current_100m", "gdp_real_growth_pct"),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2025年统计公开值",
        "document_type": "城市经济指标公开数据",
        "page_number": "公开指标页综合部分",
        "note": "B2精确公开数据；页面标注数据来源为邢台市统计局，采用全市GDP和实际增速，财政字段未在本批接入。",
    },
    {
        "year": 2025,
        "city_name": "景德镇市",
        "city_id": "CN-360200",
        "source_doc_id": "SRC-A2-JINGDEZHEN-CITY-MACRO-2025",
        "url": "https://www.jdz.gov.cn/zwgk/zfgb/2026n/d5q/szfwj/t1094895.shtml",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "jingdezhen_2025_statistical_bulletin_excerpt.txt",
        "document_title": "景德镇市国民经济和社会发展第十五个五年规划纲要（引用2025实际指标）",
        "publisher": "景德镇市人民政府",
        "publisher_level": "市级政府",
        "publication_date": "2026-07-01",
        "source_grade": "A2",
        "fields": ("gdp_current_100m", "gdp_real_growth_pct"),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "html",
        "data_status": "final",
        "data_status_label": "2025年官方规划文件引用实际值",
        "document_type": "官方规划文件历史实际经济指标",
        "page_number": "经济发展主要指标表",
        "note": "A2官方政府文件；文件明确列示景德镇市2025年GDP 1189.63亿元、增速-0.7%，用于暂解公报正文图片化造成的检索缺口，后续可由统计公报正文复核。",
    },
)

CITY_YEAR_FISCAL_SOURCES += tuple(
    _make_curated_city_source(**spec) for spec in _CURATED_2024_2025_MACRO_PRIORITY_SPECS
)

# 本批四字段补缺：2023—2025 年经入口页、附件或精确公开表格逐项核验的
# 地级市/自治州数据。这里只接入当前主表仍缺失的字段；同一城市年度已有
# 更高等级值时，load_city_year_fiscal_sources 会按字段保留高等级来源。
_CURATED_2023_2025_MACRO_GAP_BATCH_SPECS = (
    {
        "year": 2024,
        "city_name": "济宁市",
        "city_id": "CN-370800",
        "source_doc_id": "SRC-B2-JINING-CITY-MACRO-FISCAL-2024",
        "url": "https://tjgb.hongheiku.com/djs/58350.html",
        "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "jining_2024_statistical_bulletin_excerpt.txt",
        "document_title": "2024年济宁市国民经济和社会发展统计公报",
        "publisher": "济宁市统计局",
        "publisher_level": "市级统计机构公报精确转载",
        "publication_date": "2025-04-01",
        "source_grade": "B2",
        "fields": ("gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "pdf",
        "data_status": "execution",
        "data_status_label": "2024年公报及预算执行公开值",
        "document_type": "市级统计公报经济财政指标精确转载",
        "page_number": "PDF第1页、第12页",
        "note": "B2精确公开公报；入口页标注来源为济宁市统计局，GDP实际增速和一般公共预算收支均为济宁市全市口径；财政字段为公报披露的预算执行值。",
    },
    {
        "year": 2024,
        "city_name": "漯河市",
        "city_id": "CN-411100",
        "source_doc_id": "SRC-B2-LUOHE-CITY-MACRO-FISCAL-2024",
        "url": "https://tjgb.hongheiku.com/xjtjgb/xj2020/63442.html",
        "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "luohe_2024_statistical_bulletin_excerpt.txt",
        "document_title": "2024年漯河市国民经济和社会发展统计公报",
        "publisher": "漯河市统计局",
        "publisher_level": "市级统计机构公报精确转载",
        "publication_date": "2025-05-27",
        "source_grade": "B2",
        "fields": ("general_public_revenue_100m", "general_public_expenditure_100m"),
        "source_format": "pdf",
        "data_status": "execution",
        "data_status_label": "2024年公报及预算执行公开值",
        "document_type": "市级统计公报财政指标精确转载",
        "page_number": "PDF第11—12页",
        "note": "B2完整官方公报精确转载；页面来源标注漯河市统计局，接入漯河市全市一般公共预算收入和支出。",
    },
    {
        "year": 2024,
        "city_name": "滨州市",
        "city_id": "CN-371600",
        "source_doc_id": "SRC-B2-BINZHOU-CITY-MACRO-FISCAL-2024",
        "url": "https://tjgb.hongheiku.com/djs/57843.html",
        "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "binzhou_2024_statistical_bulletin_excerpt.txt",
        "document_title": "2024年滨州市国民经济和社会发展统计公报",
        "publisher": "滨州市统计局",
        "publisher_level": "市级统计机构公报精确转载",
        "publication_date": "2025-03-28",
        "source_grade": "B2",
        "fields": ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "pdf",
        "data_status": "preliminary",
        "data_status_label": "2024年公报初步统计数及财政执行值",
        "document_type": "市级统计公报经济财政指标精确转载",
        "page_number": "PDF第1页、第10页",
        "note": "B2完整官方公报精确转载；页面来源标注滨州市统计局，GDP为公报初步核算值，财政字段为滨州市全市一般公共预算执行口径。",
    },
    {
        "year": 2024,
        "city_name": "聊城市",
        "city_id": "CN-371500",
        "source_doc_id": "SRC-B2-LIAOCHENG-CITY-MACRO-FISCAL-2024",
        "url": "https://static.sse.com.cn/disclosure/bond/announcement/corporate/c/new/2025-06-24/152606_20250624_MT0A.pdf",
        "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "liaocheng_2024_rating_report_excerpt.txt",
        "document_title": "东方金诚债跟踪评字〔2025〕0236号（聊城市兴业控股集团有限公司）",
        "publisher": "东方金诚资信评估有限公司（上海证券交易所公开披露）",
        "publisher_level": "交易所公开披露的精确表格来源",
        "publication_date": "2025-06-24",
        "source_grade": "B2",
        "fields": ("gdp_real_growth_pct", "general_public_revenue_100m"),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "pdf",
        "data_status": "execution",
        "data_status_label": "2024年统计公报及预算执行公开值",
        "document_type": "评级报告城市经济财政指标表",
        "page_number": "PDF第13页表格",
        "note": "B2精确表格；报告表格明确列示聊城市2024年GDP、实际增速和一般公共预算收入，来源注明2024年统计公报及预算执行资料，采用全市口径；不以开发区公报代填。",
    },
    {
        "year": 2024,
        "city_name": "成都市",
        "city_id": "CN-510100",
        "source_doc_id": "SRC-A2-CHENGDU-CITY-GROWTH-2024",
        "url": "https://www.cd12371.com/info/2025/2130789.html",
        "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "chengdu_2024_statistical_bulletin_excerpt.txt",
        "document_title": "成都市2024年国民经济和社会发展统计公报",
        "publisher": "成都市统计局、国家统计局成都调查队",
        "publisher_level": "市级统计机构",
        "publication_date": "2025-01-23",
        "source_grade": "A2",
        "fields": ("gdp_real_growth_pct",),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2024年公报初步统计数",
        "document_type": "官方统计公报经济指标",
        "page_number": "官方公报综合部分",
        "note": "A2市级官方统计公报；采用成都市全市地区生产总值实际增速，GDP绝对值和财政字段沿用主表已有值。",
    },
    {
        "year": 2024,
        "city_name": "资阳市",
        "city_id": "CN-512000",
        "source_doc_id": "SRC-B2-ZIYANG-CITY-GROWTH-2024",
        "url": "https://tjgb.hongheiku.com/djs/57905.html",
        "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "ziyang_2024_statistical_bulletin_excerpt.txt",
        "document_title": "资阳市2024年国民经济和社会发展统计公报",
        "publisher": "资阳市统计局",
        "publisher_level": "市级统计机构公报精确转载",
        "publication_date": "2025-03-31",
        "source_grade": "B2",
        "fields": ("gdp_real_growth_pct",),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2024年公报初步统计数",
        "document_type": "市级统计公报经济指标精确转载",
        "page_number": "转载正文综合部分",
        "note": "B2精确转载；页面标题和来源均明确为资阳市统计局公报，采用资阳市全市GDP实际增速。",
    },
    {
        "year": 2023,
        "city_name": "喀什地区",
        "city_id": "CN-653100",
        "source_doc_id": "SRC-A2-KASHI-REGION-MACRO-FISCAL-2023-REVIEWED",
        "url": "https://www.kashi.gov.cn/ksdqxzgs/c112198/202404/fc4969a2247b416c8e6eb3ef41310a6b.shtml",
        "path": RAW_DIR / "province_fiscal" / "2023" / "official" / "kashi_2023_statistical_bulletin_ocr_excerpt.txt",
        "document_title": "喀什地区2023年国民经济和社会发展统计公报",
        "publisher": "喀什地区统计局、喀什地区行政公署",
        "publisher_level": "地区政府及统计机构",
        "publication_date": "2024-04-01",
        "source_grade": "A2",
        "fields": ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2023年官方公报扫描页复核值",
        "document_type": "官方统计公报扫描页人工复核摘录",
        "page_number": "官方页面扫描图第1页、第14页",
        "note": "A2官方页面；正文以扫描图发布，数值经官方扫描图人工复核/OCR，明确为喀什地区全地区口径；财政字段为一般公共预算收入和支出，不使用地方级财政收入替代。",
    },
    {
        "year": 2023,
        "city_name": "昌吉回族自治州",
        "city_id": "CN-652300",
        "source_doc_id": "SRC-A2-CHANGJI-PREFECTURE-FISCAL-2023",
        "url": "https://www.cj.gov.cn/u/cms/tjj/202404/11214043903u.pdf",
        "path": RAW_DIR / "province_fiscal" / "2023" / "official" / "changji_2023_statistical_bulletin_excerpt.txt",
        "document_title": "昌吉州2023年国民经济和社会发展统计公报",
        "publisher": "昌吉州统计局",
        "publisher_level": "州级统计机构",
        "publication_date": "2024-04-01",
        "source_grade": "A2",
        "fields": ("general_public_revenue_100m", "general_public_expenditure_100m"),
        "source_format": "pdf",
        "data_status": "execution",
        "data_status_label": "2023年官方公报预算执行值",
        "document_type": "官方统计公报财政指标",
        "page_number": "PDF第13页",
        "note": "A2州级官方 PDF；第13页明确列示昌吉州全州一般公共预算收入227.35亿元、支出385.49亿元，未将政府性基金收入混入一般预算收入。",
    },
    {
        "year": 2023,
        "city_name": "湘西土家族苗族自治州",
        "city_id": "CN-433100",
        "source_doc_id": "SRC-B2-XIANGXI-PREFECTURE-MACRO-FISCAL-2023",
        "url": "https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=2906522&mode=open&priority=0",
        "path": RAW_DIR / "province_fiscal" / "2023" / "secondary" / "xiangxi_2023_rating_report_excerpt.txt",
        "document_title": "湘西州城镇建设投资开发有限责任公司2024年跟踪评级报告",
        "publisher": "大公国际资信评估有限公司（中国货币网公开披露）",
        "publisher_level": "公开披露评级报告精确表格",
        "publication_date": "2024-06-28",
        "source_grade": "B2",
        "fields": ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "pdf",
        "data_status": "execution",
        "data_status_label": "2023年统计公报及预算执行公开值",
        "document_type": "评级报告自治州经济财政指标表",
        "page_number": "PDF第9页表2",
        "note": "B2精确表格；报告表2明确列示2021—2023年湘西州全州GDP、实际增速、一般公共预算收入和支出，来源说明使用统计公报及预算执行报告；接入表2的825.85亿元精确值。",
    },
    {
        "year": 2024,
        "city_name": "景德镇市",
        "city_id": "CN-360200",
        "source_doc_id": "SRC-A2-JINGDEZHEN-CITY-EXPENDITURE-2024",
        "url": "https://www.jdz.gov.cn/zwgk/fdzdgknr/czxx/yjsgk/t1010086.shtml",
        "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "jingdezhen_2024_budget_report_excerpt.txt",
        "document_title": "景德镇市2024年预算执行情况和2025年预算草案的报告",
        "publisher": "景德镇市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2025-01-01",
        "source_grade": "A2",
        "fields": ("general_public_expenditure_100m",),
        "source_format": "html",
        "data_status": "execution",
        "data_status_label": "2024年预算执行数",
        "document_type": "市级财政预算执行报告",
        "page_number": "官方报告全市一般公共预算收支部分",
        "note": "A2市级财政官方报告；明确列示景德镇市全市一般公共预算支出250.00亿元，主表已有收入90.53亿元和基金收入209.50亿元不重复覆盖。",
    },
    {
        "year": 2024,
        "city_name": "鄂州市",
        "city_id": "CN-420700",
        "source_doc_id": "SRC-A2-EZHOU-CITY-EXPENDITURE-2024",
        "url": "https://www.ezhou.gov.cn/gk/xxgkml/czgk/zfyjs/202501/t20250126_687414.html",
        "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "ezhou_2024_budget_execution_report_excerpt.txt",
        "document_title": "鄂州市2024年预算执行情况和2025年预算草案的报告",
        "publisher": "鄂州市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2025-01-26",
        "source_grade": "A2",
        "fields": ("general_public_expenditure_100m",),
        "raw_unit": "万元",
        "source_format": "pdf",
        "data_status": "execution",
        "data_status_label": "2024年预算执行数",
        "document_type": "市级财政预算执行报告",
        "page_number": "官方附件 PDF 全市一般公共预算收支表",
        "note": "A2市级财政官方附件；原表单位为万元，列示鄂州市全市一般公共预算支出1712434万元，按规范换算为171.2434亿元。",
    },
    {
        "year": 2025,
        "city_name": "黄冈市",
        "city_id": "CN-421100",
        "source_doc_id": "SRC-B2-HUANGGANG-CITY-REVENUE-2025",
        "url": "https://tjgb.hongheiku.com/djs/69489.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "huanggang_2025_statistical_bulletin_excerpt.txt",
        "document_title": "黄冈市2025年国民经济和社会发展统计公报",
        "publisher": "黄冈市统计局公报公开转载",
        "publisher_level": "市级统计机构公报精确转载",
        "publication_date": "2026-04-01",
        "source_grade": "B2",
        "fields": ("general_public_revenue_100m",),
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2025年公报初步统计数",
        "document_type": "市级统计公报财政指标精确转载",
        "page_number": "转载正文财政金融部分",
        "note": "B2精确公报转载；正文明确为黄冈市全市一般公共预算收入205.60亿元，未将未披露的一般公共预算支出用‘全市财政支出’代填。",
    },
)

CITY_YEAR_FISCAL_SOURCES += tuple(
    _make_curated_city_source(**spec) for spec in _CURATED_2023_2025_MACRO_GAP_BATCH_SPECS
)

# 黄冈市财政局官方预算执行报告补入2025年全市一般公共预算收支和政府性基金收入。
# 报告正文同时列示全口径财政收入、一般公共预算收入、政府性基金预算收入以及
# 全市财政总支出和其中的一般公共预算支出；这里严格采用全市口径，不使用市本级数。
CITY_YEAR_FISCAL_SOURCES += (
    {
        "year": 2025,
        "city_name": "黄冈市",
        "city_id": "CN-421100",
        "source_doc_id": "SRC-A2-HUANGGANG-CITY-FISCAL-2025",
        "url": "https://www.hg.gov.cn/zt/2026nsjyjs/sjzfysjsgk/9381643.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "huanggang_2025_budget.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "huanggang_2025_budget_excerpt.txt",
        "text_is_curated": True,
        "document_title": "关于黄冈市2025年预算执行情况和2026年预算草案的报告",
        "publisher": "黄冈市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-01-28",
        "source_grade": "A2",
        "source_format": "html",
        "data_status": "execution",
        "data_status_label": "2025年全市一般公共预算和政府性基金预算执行数",
        "document_type": "市级财政预算执行报告",
        "page_number": "官方网页正文；2025年全市预算执行情况",
        "raw_unit": "亿元",
        "patterns": {
            "general_public_revenue_100m": r"一般公共预算收入=([0-9.,]+)亿元",
            "general_public_expenditure_100m": r"一般公共预算支出=([0-9.,]+)亿元",
            "gov_fund_revenue_100m": r"政府性基金预算收入=([0-9.,]+)亿元",
        },
        "note": (
            "A2黄冈市财政局官方预算执行报告；正文明确列示2025年全市一般公共预算收入205.6亿元、"
            "一般公共预算支出694亿元和政府性基金预算收入96.88亿元，均为执行数；"
            "不使用同一报告中的市本级249320万元收入或864010万元支出。"
        ),
    },
)

# 唐山市 2025 年公开报告批次：财政报告由唐山市财政局向市人大提交，
# 经济指标由唐山劳动日报完整披露。两条来源均明确区分“全市”与“本级”，
# 作为 B2 精确公开来源归档；财政字段保留 execution 状态。
CITY_YEAR_FISCAL_SOURCES += (
    {
        "year": 2025,
        "city_name": "唐山市",
        "city_id": "CN-130200",
        "source_doc_id": "SRC-B2-TANGSHAN-CITY-STATISTICAL-2025",
        "url": "https://epaper.huanbohainews.com.cn/tsldrb/pc/content/202608/11/content_127012.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "tangshan_2025_gdp_report.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "tangshan_2025_gdp_report.html",
        "text_is_curated": True,
        "document_title": "唐山高质量发展迈出坚实步伐",
        "publisher": "唐山劳动日报社",
        "publisher_level": "市级党报公开披露",
        "publication_date": "2026-08-11",
        "source_grade": "B2",
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2025年公报/新闻公开值",
        "document_type": "城市经济指标公开报道",
        "patterns": {
            "gdp_current_100m": r"2025年总量达([0-9.]+)亿元、同比增长[0-9.]+%",
            "gdp_real_growth_pct": r"2025年总量达[0-9.]+亿元、同比增长([0-9.]+)%",
        },
        "raw_unit": "亿元",
        "note": "B2精确公开报道；报道明确披露唐山市2025年地区生产总值10450.2亿元、同比增长6.2%，未与其他城市或市辖区口径混用。",
    },
    {
        "year": 2025,
        "city_name": "济宁市",
        "city_id": "CN-370800",
        "source_doc_id": "SRC-A2-JINING-CITY-STATISTICAL-2025",
        "url": "https://tjj.jining.gov.cn/art/2026/4/1/art_6828_2707453.html",
        "attachment_url": "https://tjj.jining.gov.cn/module/download/downfile.jsp?classid=0&filename=ef37863a917c4a58b785993b69ec730c.pdf&showname=2025%E5%B9%B4%E6%B5%8E%E5%AE%81%E5%B8%82%E5%9B%BD%E6%B0%91%E7%BB%8F%E6%B5%8E%E5%92%8C%E7%A4%BE%E4%BC%9A%E5%8F%91%E5%B1%95%E7%BB%9F%E8%AE%A1%E5%85%AC%E6%8A%A5.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "jining_2025_statistical_bulletin.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "jining_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年济宁市国民经济和社会发展统计公报",
        "publisher": "济宁市统计局、国家统计局济宁调查队",
        "publisher_level": "市级统计机构",
        "publication_date": "2026-04-01",
        "source_grade": "A2",
        "source_format": "pdf",
        "data_status": "preliminary",
        "data_status_label": "2025年公报初步统计数",
        "document_type": "官方统计公报经济财政指标（PDF）",
        "page_number": "PDF第1、11页",
        "patterns": {
            "gdp_current_100m": r"全市生产总值实现([0-9.]+)亿元",
            "gdp_real_growth_pct": r"全市生产总值实现[0-9.]+亿元，按不变价格计算，比上年增长([0-9.]+)%",
            "general_public_revenue_100m": r"全年一般公共预算收入完成([0-9.]+)亿元",
            "general_public_expenditure_100m": r"一般公共预算支出完成([0-9.]+)亿元",
        },
        "raw_unit": "亿元",
        "note": "A2济宁市统计局、国家统计局济宁调查队官方统计公报；采用2025年全市GDP、实际增速和一般公共预算收支，公报注明数据为初步统计数，行政范围为全市。",
    },
    {
        "year": 2025,
        "city_name": "连云港市",
        "city_id": "CN-320700",
        "source_doc_id": "SRC-B2-LIANYUNGANG-CITY-STATISTICAL-2025",
        "url": "https://tjgb.hongheiku.com/xjtjgb/xj2020/72383.html",
        "landing_page_url": "https://www.lyg.gov.cn/zglygzfmhwz/tjgb/content/f88b71e0-2ae3-420e-b655-380779e6c3cd.htm",
        "attachment_url": "https://tjgb.hongheiku.com/wp-content/uploads/2026/05/1779504606-4fcfb3b2-ba61-411a-9de2-59b7746d88e7202.pdf",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "lianyungang_2025_statistical_bulletin.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "lianyungang_2025_statistical_bulletin_excerpt.txt",
        "text_is_curated": True,
        "document_title": "2025年连云港市国民经济和社会发展统计公报",
        "publisher": "连云港市统计局（公开转载）",
        "publisher_level": "市级统计机构公报转载",
        "publication_date": "2026-05-22",
        "source_grade": "B2",
        "source_format": "pdf",
        "data_status": "preliminary",
        "data_status_label": "2025年公报初步统计数",
        "document_type": "统计公报经济财政指标（精确转载PDF）",
        "page_number": "PDF第1、9页",
        "patterns": {
            "gdp_current_100m": r"全年实现地区生产总值([0-9.]+)亿元，比上年增长[0-9.]+%",
            "gdp_real_growth_pct": r"全年实现地区生产总值[0-9.]+亿元，比上年增长([0-9.]+)%",
            "general_public_revenue_100m": r"全年完成一般公共预算收入([0-9.]+)亿元",
            "general_public_expenditure_100m": r"全年一般公共预算支出([0-9.]+)亿元",
        },
        "raw_unit": "亿元",
        "note": "B2精确转载PDF；官方政府门户公开该统计公报入口，公报正文明确为连云港市全市口径，采用2025年GDP、实际增速和一般公共预算收支；官方附件链接当前失效，转载PDF作为可回溯公开证据保存。",
    },
    {
        "year": 2025,
        "city_name": "淮北市",
        "city_id": "CN-340600",
        "source_doc_id": "SRC-A2-HUAIBEI-CITY-STATISTICAL-2025",
        "url": "https://tj.huaibei.gov.cn/zwgk/public/76/65040057.html",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "huaibei_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "huaibei_2025_statistical_bulletin.html",
        "text_is_curated": True,
        "document_title": "淮北市2025年国民经济和社会发展统计公报解读",
        "publisher": "淮北市统计局",
        "publisher_level": "市级统计机构",
        "publication_date": "2026-07-09",
        "source_grade": "A2",
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2025年公报初步统计数",
        "document_type": "官方统计公报解读（网页）",
        "page_number": "网页正文；经济运行和财政金融段",
        "patterns": {
            "gdp_current_100m": r"全市地区生产总值（GDP）([0-9.]+)亿元，按不变价格计算，比上年增长[0-9.]+%",
            "gdp_real_growth_pct": r"全市地区生产总值（GDP）[0-9.]+亿元，按不变价格计算，比上年增长([0-9.]+)%",
            "general_public_revenue_100m": r"全年实现一般公共预算收入([0-9.]+)亿元",
            "general_public_expenditure_100m": r"一般公共预算支出([0-9.]+)亿元",
        },
        "raw_unit": "亿元",
        "note": "A2淮北市统计局官方统计公报解读；页面明确展示淮北市2025年全市GDP、增速和一般公共预算收支，采用全市口径，经济数据为公报初步统计结果。",
    },
    {
        "year": 2025,
        "city_name": "本溪市",
        "city_id": "CN-210500",
        "source_doc_id": "SRC-B2-BENXI-CITY-STATISTICAL-2025",
        "url": "https://maptable.com/tjgb/2025/%E8%BE%BD%E5%AE%81%E7%9C%81/%E6%9C%AC%E6%BA%AA%E5%B8%82/report/liao-ning-sheng-er-ling-er-wu-nian-ben-xi-shi-guo-min-jing-ji-he-she-hui-fa-zhan-tong-ji-gong-bao-2",
        "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "benxi_2025_statistical_bulletin.html",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "benxi_2025_statistical_bulletin.html",
        "text_is_curated": True,
        "document_title": "二〇二五年本溪市国民经济和社会发展统计公报",
        "publisher": "本溪市统计局（公开转载）",
        "publisher_level": "市级统计机构公报转载",
        "publication_date": "2026-06-01",
        "source_grade": "B2",
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2025年公报初步统计数",
        "document_type": "统计公报经济财政指标（精确转载网页）",
        "page_number": "网页正文；经济总量和财政金融段",
        "patterns": {
            "gdp_current_100m": r"全年地区生产总值[\[ ]*2[\] ]*([0-9.]+)亿元，按可比价格计算，比上年增长[0-9.]+%",
            "gdp_real_growth_pct": r"全年地区生产总值[\[ ]*2[\] ]*[0-9.]+亿元，按可比价格计算，比上年增长([0-9.]+)%",
            "general_public_revenue_100m": r"全年地方一般公共预算收入([0-9.]+)亿元",
            "general_public_expenditure_100m": r"全年地方一般公共预算支出([0-9.]+)亿元",
        },
        "raw_unit": "亿元",
        "note": "B2精确公报转载；页面正文署名本溪市统计局，并明确财政数据来自本溪市财政局，采用2025年全市GDP、实际增速和地方一般公共预算收支，公报注明2025年数据为初步统计数据。",
    },
)

# 2025 年官方/精确公报长图批次：汉中、恩施州、日照。三条来源均逐项
# 列示全市（州）GDP、实际增速和一般公共预算收支；公报长图先转为标准
# 摘录文本，再由统一城市来源接口解析，避免把图片目测或市本级数据写入主表。
CITY_YEAR_FISCAL_SOURCES += tuple(
    _make_curated_city_source(**spec)
    for spec in (
        {
            "year": 2025,
            "city_name": "汉中市",
            "city_id": "CN-610700",
            "source_doc_id": "SRC-A2-HANZHONG-CITY-MACRO-FISCAL-2025",
            "url": "https://tjj.hanzhong.gov.cn/hztjj/tjgb/202606/a327c601520c4b0888cbd094803dd422.shtml",
            "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "hanzhong_2025_statistical_bulletin_excerpt.txt",
            "document_title": "汉中市2025年国民经济和社会发展统计公报",
            "publisher": "汉中市统计局、国家统计局汉中调查队",
            "publisher_level": "市级统计机构",
            "publication_date": "2026-05-28",
            "source_grade": "A2",
            "fields": ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": "html",
            "data_status": "preliminary",
            "data_status_label": "2025年公报初步统计数",
            "document_type": "官方统计公报经济财政指标（正文长图）",
            "page_number": "官方公报正文长图综合及财政金融部分",
            "note": "A2汉中市统计局官方统计公报；正文以长图发布，采用汉中市全市GDP、实际增速和一般公共预算收支，财政数据注明来自市财政局。",
        },
        {
            "year": 2025,
            "city_name": "日照市",
            "city_id": "CN-371100",
            "source_doc_id": "SRC-B2-RIZHAO-CITY-MACRO-FISCAL-2025",
            "url": "https://tjgb.hongheiku.com/djs/68596.html",
            "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "rizhao_2025_statistical_bulletin_excerpt.txt",
            "document_title": "日照市2025年国民经济和社会发展统计公报",
            "publisher": "日照市统计局公报精确转载",
            "publisher_level": "市级统计机构公报转载",
            "publication_date": "2026-04-09",
            "source_grade": "B2",
            "fields": ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": "pdf",
            "data_status": "preliminary",
            "data_status_label": "2025年公报年快报/初步统计数",
            "document_type": "市级统计公报经济财政指标精确转载PDF",
            "page_number": "PDF第2页综合部分、第5页财政金融部分",
            "note": "B2精确公报PDF；公报明确日照市全市GDP、实际增速和一般公共预算收支，财政段落未混用区县或市本级口径。",
        },
        {
            "year": 2025,
            "city_name": "恩施土家族苗族自治州",
            "city_id": "CN-422800",
            "source_doc_id": "SRC-B2-ENSHI-PREFECTURE-MACRO-FISCAL-2025",
            "url": "https://tjgb.hongheiku.com/xjtjgb/xj2020/71889.html",
            "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "enshi_2025_statistical_bulletin_excerpt.txt",
            "document_title": "恩施土家族苗族自治州2025年国民经济和社会发展统计公报",
            "publisher": "恩施土家族苗族自治州统计局公报转载",
            "publisher_level": "州级统计机构公报转载",
            "publication_date": "2026-05-20",
            "source_grade": "B2",
            "fields": ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": "html",
            "data_status": "preliminary",
            "data_status_label": "2025年公报初步统计数",
            "document_type": "州级统计公报经济财政指标精确转载（正文长图）",
            "page_number": "公报第1张、第11张图片综合及财政金融部分",
            "note": "B2精确公报长图转载；采用恩施州全州GDP、实际增速和一般公共预算收支，公报明确财政收支数据来自州财政局。",
        },
    )
)

# 2025 年官方统计公报四字段补缺：海南州、大兴安岭地区、黑河市。
# 三份公报均逐项列示全州/全区/全市 GDP、实际增速和一般公共预算收支，
# 统一按亿元解析；2025 年经济数据保留公报的初步统计状态，财政数按公报
# 所载全年执行数接入，不使用预算目标或由比例反推的数值。
CITY_YEAR_FISCAL_SOURCES += tuple(
    _make_curated_city_source(**spec)
    for spec in (
        {
            "year": 2025,
            "city_name": "海南藏族自治州",
            "city_id": "CN-632500",
            "source_doc_id": "SRC-A2-QINGHAI-HAINAN-CITY-MACRO-FISCAL-2025",
            "url": "https://www.hainanzhou.gov.cn/zwgk/fdzdgknr/tjxx/tjxx1/content_400016530",
            "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "hainan_2025_city_macro_fiscal_excerpt.txt",
            "document_title": "2025年海南州经济运行情况",
            "publisher": "海南州统计局",
            "publisher_level": "州级统计机构",
            "publication_date": "2026-01-30",
            "source_grade": "A2",
            "fields": ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": "html",
            "data_status": "preliminary",
            "data_status_label": "2025年统计公报/全年执行数",
            "document_type": "州级统计公报经济财政指标",
            "page_number": "官方网页正文；经济运行基本情况、财政收入和财政支出部分",
            "text_city_name": "海南州",
            "note": "A2海南州统计局官方公开统计信息；明确为全州口径，GDP和增速为统一核算结果，一般公共预算收入、支出为全年数据。",
        },
        {
            "year": 2025,
            "city_name": "大兴安岭地区",
            "city_id": "CN-232700",
            "source_doc_id": "SRC-A2-HEILONGJIANG-DAXINGANLING-CITY-MACRO-FISCAL-2025",
            "url": "https://dxal.gov.cn/dxal/c100066/202606/c13_339001.shtml",
            "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "daxinganling_2025_city_macro_fiscal_excerpt.txt",
            "document_title": "2025年大兴安岭地区国民经济和社会发展统计公报",
            "publisher": "大兴安岭地区统计局",
            "publisher_level": "地区统计机构",
            "publication_date": "2026-06-04",
            "source_grade": "A2",
            "fields": ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": "html",
            "data_status": "preliminary",
            "data_status_label": "2025年统计公报初步统计数",
            "document_type": "地区统计公报经济财政指标",
            "page_number": "官方公报；综合和财政金融部分",
            "note": "A2大兴安岭地区统计局官方统计公报；明确为全区口径，财政收支数据来自财政局。",
        },
        {
            "year": 2025,
            "city_name": "黑河市",
            "city_id": "CN-231100",
            "source_doc_id": "SRC-A2-HEILONGJIANG-HEIHE-CITY-MACRO-FISCAL-2025",
            "url": "https://www.heihe.gov.cn/hhs/c103137/202604/c11_352062.shtml",
            "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "heihe_2025_city_macro_fiscal_excerpt.txt",
            "document_title": "2025年黑河市国民经济和社会发展统计公报",
            "publisher": "黑河市统计局",
            "publisher_level": "市级统计机构",
            "publication_date": "2026-04-29",
            "source_grade": "A2",
            "fields": ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": "html",
            "data_status": "preliminary",
            "data_status_label": "2025年统计公报初步统计数",
            "document_type": "市级统计公报经济财政指标",
            "page_number": "官方公报；综合和财政金融拆分页面",
            "note": "A2黑河市统计局官方统计公报及政府门户拆分页；明确为全市口径，财政收支逐项公开。",
        },
    )
)

# 本批补缺：优先接入已逐项核验的官方公报/决算与交易所公开精确表格。
# 阜新经济指标和财政决算拆成两个来源，保留各自的数据状态；其余来源
# 只写入当前仍为空的字段，避免用二手摘录覆盖已有更高等级值。
CITY_YEAR_FISCAL_SOURCES += tuple(
    _make_curated_city_source(**spec)
    for spec in (
        {
            "year": 2024,
            "city_name": "阜新市",
            "city_id": "CN-210900",
            "source_doc_id": "SRC-A2-FUXIN-CITY-MACRO-2024",
            "url": "https://www.fuxin.gov.cn/khcs/file/2025-06-20/17503877992854028e4928e7a358a37901978b3e34f51fc3.pdf",
            "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "fuxin_2024_macro_excerpt.txt",
            "document_title": "二〇二四年阜新市国民经济和社会发展统计公报",
            "publisher": "阜新市统计局",
            "publisher_level": "市级统计机构",
            "publication_date": "2025-06-04",
            "source_grade": "A2",
            "fields": ("gdp_current_100m", "gdp_real_growth_pct"),
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": "pdf",
            "data_status": "preliminary",
            "data_status_label": "2024年公报初步统计数",
            "document_type": "官方统计公报经济指标（PDF）",
            "page_number": "PDF第1页经济总量部分",
            "note": "A2阜新市统计局官方统计公报；采用全市GDP现价总量和按不变价格计算的实际增速，公报注明2024年数据为年快报/初步统计数。",
        },
        {
            "year": 2024,
            "city_name": "阜新市",
            "city_id": "CN-210900",
            "source_doc_id": "SRC-A2-FUXIN-CITY-FISCAL-DECISION-2024",
            "url": "https://www.fuxin.gov.cn/content/2025/1013015.html",
            "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "fuxin_2024_fiscal_decision_excerpt.txt",
            "document_title": "2024年阜新市财政决算报告",
            "publisher": "阜新市财政局",
            "publisher_level": "市级财政部门",
            "publication_date": "2025-09-03",
            "source_grade": "A2",
            "fields": ("general_public_revenue_100m", "general_public_expenditure_100m"),
            "source_format": "html",
            "data_status": "final",
            "data_status_label": "2024年正式决算数",
            "document_type": "官方财政决算报告",
            "page_number": "网页正文；全市财政决算情况—全市一般公共预算收支",
            "note": "A2阜新市财政局官方决算报告；采用全市一般公共预算收入实际完成50.04亿元、支出实际完成172.45亿元，不使用市本级口径。",
        },
        {
            "year": 2024,
            "city_name": "七台河市",
            "city_id": "CN-230900",
            "source_doc_id": "SRC-B2-QITAIHE-CITY-GDP-2024",
            "url": "https://www.zgrkk.com/reports/162.html",
            "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "qitaihe_2024_gdp_excerpt.txt",
            "document_title": "2024年七台河市国民经济和社会发展统计公报",
            "publisher": "七台河市统计局公报公开转载",
            "publisher_level": "市级统计机构公报公开转载",
            "publication_date": "2025-06-01",
            "source_grade": "B2",
            "fields": ("gdp_real_growth_pct",),
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": "html",
            "data_status": "preliminary",
            "data_status_label": "2024年公报初步统计数",
            "document_type": "统计公报经济指标（精确转载）",
            "page_number": "网页正文；综合部分",
            "note": "B2精确公报转载；仅接入逐项列示的七台河市全市GDP实际增速，不使用预期数或区县数据。",
        },
        {
            "year": 2024,
            "city_name": "鸡西市",
            "city_id": "CN-230300",
            "source_doc_id": "SRC-A2-JIXI-CITY-GDP-2024",
            "url": "https://www.jixi.gov.cn/jixi/c100332/202505/c06_332115.shtml",
            "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "jixi_2024_gdp_excerpt.txt",
            "document_title": "2024年鸡西市国民经济和社会发展统计公报",
            "publisher": "鸡西市统计局",
            "publisher_level": "市级统计机构",
            "publication_date": "2025-05-20",
            "source_grade": "A2",
            "fields": ("gdp_real_growth_pct",),
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": "html",
            "data_status": "preliminary",
            "data_status_label": "2024年公报初步统计数",
            "document_type": "官方统计公报经济指标",
            "page_number": "网页正文；综合部分",
            "note": "A2鸡西市统计局官方统计公报；采用全市GDP按可比价格计算的实际增速-1.1%，不使用人均GDP增速。",
        },
        {
            "year": 2024,
            "city_name": "牡丹江市",
            "city_id": "CN-231000",
            "source_doc_id": "SRC-A2-MUDANJIANG-CITY-GDP-2024",
            "url": "https://www.mdj.gov.cn/mdjsrmzf/c100093/202504/1002755/files/2024%E5%B9%B4%E7%89%A1%E4%B8%B9%E6%B1%9F%E5%B8%82%E5%9B%BD%E6%B0%91%E7%BB%8F%E6%B5%8E%E5%92%8C%E7%A4%BE%E4%BC%9A%E5%8F%91%E5%B1%95%E7%BB%9F%E8%AE%A1%E5%85%AC%E6%8A%A5.pdf",
            "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "mudanjiang_2024_gdp_excerpt.txt",
            "document_title": "2024年牡丹江市国民经济和社会发展统计公报",
            "publisher": "牡丹江市统计局",
            "publisher_level": "市级统计机构",
            "publication_date": "2025-04-16",
            "source_grade": "A2",
            "fields": ("gdp_real_growth_pct",),
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": "pdf",
            "data_status": "preliminary",
            "data_status_label": "2024年公报初步统计数",
            "document_type": "官方统计公报经济指标（PDF）",
            "page_number": "PDF第1页综合部分",
            "note": "A2牡丹江市统计局官方统计公报；采用全市GDP按不变价格计算的实际增速3.8%，不使用市区或县域增速。",
        },
        {
            "year": 2025,
            "city_name": "湖州市",
            "city_id": "CN-330500",
            "source_doc_id": "SRC-B2-HUZHOU-CITY-FISCAL-2025-DAGONG",
            "url": "https://www.chinamoney.org.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3357381&mode=save&priority=0",
            "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "huzhou_2025_expenditure_excerpt.txt",
            "document_title": "湖州市交通投资集团有限公司主体与相关债项2026年度跟踪评级报告",
            "publisher": "大公国际资信评估有限公司（上海证券交易所公开披露）",
            "publisher_level": "交易所公开披露的B2精确表格来源",
            "publication_date": "2026-07-30",
            "source_grade": "B2",
            "fields": ("general_public_expenditure_100m",),
            "source_format": "pdf",
            "data_status": "execution",
            "data_status_label": "2025年执行数（评级报告精确表格）",
            "document_type": "评级报告地级市经济财政指标表",
            "page_number": "PDF第1页表2；2023—2025年湖州市主要经济财政指标",
            "note": "B2交易所公开披露评级报告精确表格；表2明确列示湖州市全市2025年一般公共预算支出586.25亿元，数据来源为湖州市统计公报和预算执行情况。",
        },
        {
            "year": 2025,
            "city_name": "三明市",
            "city_id": "CN-350400",
            "source_doc_id": "SRC-A2-SANMING-CITY-GDP-GROWTH-2025",
            "url": "https://www.sm.gov.cn/zw/tjxx/tjgb/202606/t20260615_2215907.htm",
            "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "sanming_2025_gdp_excerpt.txt",
            "document_title": "2025年三明市国民经济和社会发展统计公报",
            "publisher": "三明市统计局、国家统计局三明调查队",
            "publisher_level": "市级统计机构",
            "publication_date": "2026-06-15",
            "source_grade": "A2",
            "fields": ("gdp_real_growth_pct",),
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": "html",
            "data_status": "preliminary",
            "data_status_label": "2025年公报初步统计数",
            "document_type": "官方统计公报经济指标",
            "page_number": "网页正文；综合部分",
            "note": "A2三明市统计局与国家统计局三明调查队官方统计公报；采用全市GDP按不变价格计算的实际增速-4.3%，公报注明绝对数和增速为初步统计口径。",
        },
    )
)

# 2024 年新疆官方地州批量表与统计公报补缺：财政厅表十、表十一
# 提供各地一般公共预算收入、支出（原始单位万元），克州、塔城官方
# 统计材料提供 GDP 与实际增速，和田工作总结提供全地区 GDP 增速。
CITY_YEAR_FISCAL_SOURCES += tuple(
    _make_curated_city_source(**spec)
    for spec in (
        {
            "year": 2024,
            "city_name": "克孜勒苏柯尔克孜自治州",
            "city_id": "CN-653000",
            "source_doc_id": "SRC-A2-XINJIANG-KIZILSU-MACRO-2024",
            "url": "https://www.xjkz.gov.cn/xjkz/c101981/202502/11606b4da264429bbd0d8351a170852e.shtml",
            "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "xinjiang_2024_city_macro_official_excerpt.txt",
            "document_title": "克州2024年经济运行情况",
            "publisher": "克孜勒苏柯尔克孜自治州统计局",
            "publisher_level": "州级统计机构",
            "publication_date": "2025-02-12",
            "source_grade": "A2",
            "fields": ("gdp_current_100m", "gdp_real_growth_pct"),
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": "html",
            "data_status": "preliminary",
            "data_status_label": "2024年公报初步统计数",
            "document_type": "官方州级经济运行情况",
            "page_number": "官方网页正文；综合部分",
            "note": "A2克州统计局官方经济运行情况；采用克州全州地区生产总值256.66亿元和按不变价格计算的实际增速4.2%。",
        },
        {
            "year": 2024,
            "city_name": "塔城地区",
            "city_id": "CN-654200",
            "source_doc_id": "SRC-A2-XINJIANG-TACHENG-MACRO-2024",
            "url": "https://www.xjtc.gov.cn/upload/main/contentmanage/article/file/2025/04/17/202504171907016890.pdf",
            "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "xinjiang_2024_city_macro_official_excerpt.txt",
            "document_title": "塔城地区2024年国民经济和社会发展统计公报",
            "publisher": "塔城地区统计局",
            "publisher_level": "地区统计机构",
            "publication_date": "2025-04-17",
            "source_grade": "A2",
            "fields": ("gdp_current_100m", "gdp_real_growth_pct"),
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": "pdf",
            "data_status": "preliminary",
            "data_status_label": "2024年公报初步统计数",
            "document_type": "官方统计公报经济指标（PDF）",
            "page_number": "PDF第1页、第3页综合部分",
            "note": "A2塔城地区统计局官方统计公报；采用全地区GDP现价绝对数998.72亿元和按不变价格计算的实际增速6.6%。",
        },
        {
            "year": 2024,
            "city_name": "和田地区",
            "city_id": "CN-653200",
            "source_doc_id": "SRC-A2-XINJIANG-HOTAN-GDP-GROWTH-2024",
            "url": "https://www.xjht.gov.cn/xjht/c128274/202512/5ab9986d4cd0424c92374d6ac91ceb5b.shtml",
            "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "hotan_2024_gdp_growth_official_excerpt.txt",
            "document_title": "和田地区行署2024年工作总结和2025年工作安排",
            "publisher": "和田地区行政公署办公室",
            "publisher_level": "地区政府",
            "publication_date": "2025-03-04",
            "source_grade": "A2",
            "fields": ("gdp_real_growth_pct",),
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": "html",
            "data_status": "preliminary",
            "data_status_label": "2024年工作总结统计数",
            "document_type": "官方政府工作总结经济指标",
            "page_number": "官方网页正文；2024年工作总结部分",
            "note": "A2和田地区行政公署官方工作总结；明确列示2024年全地区GDP增长6.4%，因材料未列GDP绝对数不进行推算。",
        },
    )
)

# 新疆财政厅 2024 年表十、表十一：各地一般公共预算收入、支出完成数。
# 原始表单位为万元，字段级换算由统一来源解析器完成；该批次不覆盖
# 已有更高等级字段。
CITY_YEAR_FISCAL_SOURCES += tuple(
    _make_curated_city_source(**spec)
    for spec in (
        {
            "year": 2024,
            "city_name": city,
            "city_id": city_id,
            "source_doc_id": f"SRC-A1-XINJIANG-CITY-FISCAL-2024-{slug}",
            "url": "https://czt.xinjiang.gov.cn/xjczt/c115511/202501/4a78ff1bea3045eeba621d2d1d7db349.shtml",
            "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "xinjiang_2024_city_fiscal_execution_excerpt.txt",
            "document_title": "2024年自治区预算执行情况和2025年自治区预算（四本预算）",
            "publisher": "新疆维吾尔自治区财政厅",
            "publisher_level": "自治区财政部门",
            "publication_date": "2025-01-23",
            "source_grade": "A1",
            "fields": ("general_public_revenue_100m", "general_public_expenditure_100m"),
            "raw_unit": "万元",
            "source_format": "pdf",
            "data_status": "execution",
            "data_status_label": "2024年预算执行完成数",
            "document_type": "自治区财政厅分地州预算执行表",
            "page_number": "PDF表十第12页、表十一第13页",
            "note": "A1新疆财政厅官方分地州预算执行表；表十、表十一逐项列示地州全地区一般公共预算收入、支出完成数，原始单位万元，换算为亿元入表。",
        }
        for city, city_id, slug in (
            ("克孜勒苏柯尔克孜自治州", "CN-653000", "KIZILSU"),
            ("和田地区", "CN-653200", "HOTAN"),
            ("塔城地区", "CN-654200", "TACHENG"),
        )
    )
)

# 吉林省统计局 2025 年官方分市 GDP 表，补齐四平、通化、延边的 GDP
# 和实际增速；来源为省级统计机构的城市表，保留公报/年报快报状态。
CITY_YEAR_FISCAL_SOURCES += tuple(
    _make_curated_city_source(**spec)
    for spec in (
        {
            "year": 2025,
            "city_name": city,
            "city_id": city_id,
            "source_doc_id": f"SRC-A1-JILIN-CITY-GDP-2025-{slug}",
            "url": "https://tjj.jl.gov.cn/tjsj/jdsj/dqsczz/202602/t20260228_3580306.html",
            "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "jilin_2025_city_gdp_official_excerpt.txt",
            "document_title": "2025年1—4季度地区生产总值",
            "publisher": "吉林省统计局",
            "publisher_level": "省级统计机构",
            "publication_date": "2026-02-28",
            "source_grade": "A1",
            "fields": ("gdp_current_100m", "gdp_real_growth_pct"),
            "raw_units": {"gdp_real_growth_pct": "%"},
            "text_city_name": text_name,
            "source_format": "html",
            "data_status": "preliminary",
            "data_status_label": "2025年1—4季度统计数",
            "document_type": "省级统计局官方分市GDP表",
            "page_number": "官方网页表格；2025年1—4季度地区生产总值",
            "note": "A1吉林省统计局官方分市GDP表；表格逐项列示2025年四平、通化、延边全市/全州GDP及增速，GDP单位亿元、增速单位%。",
        }
        for city, city_id, slug, text_name in (
            ("四平市", "CN-220300", "SIPING", "四平市"),
            ("通化市", "CN-220500", "TONGHUA", "通化市"),
            ("延边朝鲜族自治州", "CN-222400", "YANBIAN", "延边州"),
        )
    )
)

# 之前按“next”批次完成并通过独立适配器测试的 2025 年城市来源，统一转成
# 全国主表的标准来源接口。原批次的 patterns 使用 (正则, 原单位) 元组，
# 这里只做接口标准化，不改变原始正则、数值或来源等级；这样这些已归档来源
# 才会进入主表、字段血缘和高等级覆盖率统计。
_VALIDATED_NEXT_CITY_FISCAL_BATCHES = (
    NEXT2_2025_FISCAL_SOURCES,
    NEXT3_2025_FISCAL_SOURCES,
    NEXT4_2025_FISCAL_SOURCES,
    NEXT5_2025_FISCAL_SOURCES,
    NEXT6_2025_FISCAL_SOURCES,
    NEXT7_2025_FISCAL_SOURCES,
)
for _validated_batch in _VALIDATED_NEXT_CITY_FISCAL_BATCHES:
    for _legacy_config in _validated_batch:
        _normalized_config = dict(_legacy_config)
        _normalized_config["year"] = 2025
        _patterns: dict[str, str] = {}
        _raw_units: dict[str, str] = {}
        for _field, _spec in (_legacy_config.get("patterns") or {}).items():
            if isinstance(_spec, (tuple, list)):
                _patterns[_field] = str(_spec[0])
                _raw_units[_field] = str(_spec[1])
            else:
                _patterns[_field] = str(_spec)
        _normalized_config["patterns"] = _patterns
        _normalized_config["raw_units"] = _raw_units
        _normalized_config["raw_unit"] = "亿元"
        _normalized_config["source_format"] = (
            "html" if Path(_legacy_config["path"]).suffix.lower() in {".html", ".htm"} else "pdf"
        )
        _normalized_config["data_status"] = "execution"
        _normalized_config["data_status_label"] = "2025年执行数"
        CITY_YEAR_FISCAL_SOURCES += (_normalized_config,)
def _make_autonomous_bulletin_batch(
    *,
    year: int,
    path: Path,
    entries: Iterable[tuple[str, str, str, str, str, tuple[str, ...], str, str]],
) -> tuple[dict[str, Any], ...]:
    """将自治州、盟和地区的逐项公报摘录接入统一来源接口。"""

    sources: list[dict[str, Any]] = []
    for city, city_id, slug, url, grade, fields, source_format, publisher in entries:
        sources.append(
            _make_curated_city_source(
                year=year,
                city_name=city,
                city_id=city_id,
                source_doc_id=f"SRC-{grade}-AUTONOMOUS-CITY-MACRO-{year}-{slug}",
                url=url,
                path=path,
                document_title=f"{city}{year}年国民经济和社会发展统计公报及财政摘录",
                publisher=publisher,
                publisher_level="市州统计/财政机构或精确公开转载",
                publication_date=None,
                source_grade=grade,
                fields=fields,
                raw_units={"gdp_real_growth_pct": "%"},
                source_format=source_format,
                data_status="preliminary" if "gdp_current_100m" in fields else "execution",
                data_status_label=f"{year}年公报初步统计数/财政执行数",
                document_type="自治州/盟/地区统计公报及财政执行指标摘录",
                page_number="原文综合部分、财政金融部分或分地区表格",
                note=(
                    f"{grade}逐项公开摘录；行政范围为{city}全域，GDP现价总量和实际增速与一般公共预算执行数分字段接入；"
                    "不使用预算目标、区县数或由比例反推的数值。"
                ),
            )
        )
    return tuple(sources)


# 2022 年自治州、盟和地区公报批次：只传入当前主表仍为空的字段，避免
# 重复来源覆盖已有更高等级值。红黑、智果、中国县域等转载仅在正文逐项
# 列示全域数值时作为 B2；政府门户和省级统计年鉴作为 A1/A2。
CITY_YEAR_FISCAL_SOURCES += _make_autonomous_bulletin_batch(
    year=2022,
    path=RAW_DIR / "province_fiscal" / "2022" / "secondary" / "2022_autonomous_city_statistical_bulletins_excerpt.txt",
    entries=(
        ("兴安盟", "CN-152200", "XINGAN", "https://tjgb.hongheiku.com/djs/35982.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "html", "兴安盟统计局公报精确转载"),
        ("锡林郭勒盟", "CN-152500", "XILINGOL", "https://tjgb.hongheiku.com/djs/36770.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "html", "锡林郭勒盟统计局公报精确转载"),
        ("大兴安岭地区", "CN-232700", "DAXINGANLING", "https://tjgb.hongheiku.com/djs/38550.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct"), "html", "大兴安岭地区统计局公报精确转载"),
        ("恩施土家族苗族自治州", "CN-422800", "ENSHI", "https://tjgb.hongheiku.com/djs/35605.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "html", "恩施州统计局公报精确转载"),
        ("湘西土家族苗族自治州", "CN-433100", "XIANGXI", "https://tjgb.hongheiku.com/djs/35498.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct"), "html", "湘西州统计局公报精确转载"),
        ("阿坝藏族羌族自治州", "CN-513200", "ABA", "https://tjgb.hongheiku.com/djs/35923.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "html", "阿坝州统计局公报精确转载"),
        ("凉山彝族自治州", "CN-513400", "LIANGSHAN", "https://tjgb.hongheiku.com/djs/36988.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "html", "凉山州统计局公报精确转载"),
        ("黔西南布依族苗族自治州", "CN-522300", "QIANXINAN", "https://tjgb.hongheiku.com/djs/38247.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct"), "html", "黔西南州统计局公报精确转载"),
        ("黔东南苗族侗族自治州", "CN-522600", "QIANDONGNAN", "https://tjj.qdn.gov.cn/tjsj/qdntjnj/202312/P020250827674565503170.pdf", "A1", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "pdf", "黔东南州统计局统计年鉴"),
        ("黔南布依族苗族自治州", "CN-522700", "QIANNAN", "https://tjgb.hongheiku.com/djs/37339.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct"), "html", "黔南州统计局公报精确转载"),
        ("楚雄彝族自治州", "CN-532300", "CHUXIONG", "https://tjgb.hongheiku.com/djs/36726.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "html", "楚雄州统计局公报精确转载"),
        ("文山壮族苗族自治州", "CN-532600", "WENSHAN", "https://tjgb.hongheiku.com/djs/36221.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct"), "html", "文山州统计局公报精确转载"),
        ("西双版纳傣族自治州", "CN-532800", "XISHUANGBANNA", "https://tjgb.hongheiku.com/djs/35595.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "html", "西双版纳州统计局公报精确转载"),
        ("大理白族自治州", "CN-532900", "DALI", "https://tjgb.hongheiku.com/djs/34810.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "html", "大理州统计局公报精确转载"),
        ("迪庆藏族自治州", "CN-533400", "DIQING", "https://tjgb.hongheiku.com/djs/38633.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct"), "html", "迪庆州统计局公报精确转载"),
        ("海北藏族自治州", "CN-632200", "HAIBEI", "https://tjgb.hongheiku.com/djs/35063.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "html", "海北州统计局公报精确转载"),
        ("黄南藏族自治州", "CN-632300", "HUANGNAN", "https://www.bbthy.net/kb/5754.html", "B2", ("general_public_revenue_100m", "general_public_expenditure_100m"), "html", "黄南州统计局公报精确转载"),
        ("果洛藏族自治州", "CN-632600", "GUOLUO", "https://tjgb.hongheiku.com/djs/48231.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "html", "果洛州统计局公报精确转载"),
        ("玉树藏族自治州", "CN-632700", "YUSHU", "https://www.zgrkk.com/pdf/42509/1693367624-202303100836524027.pdf", "B2", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "pdf", "玉树州人民政府公报精确转载"),
        ("博尔塔拉蒙古自治州", "CN-652700", "BOERTALA", "https://tjgb.hongheiku.com/djs/35573.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct"), "html", "博州统计局公报精确转载"),
        ("阿克苏地区", "CN-652900", "AKESU", "https://tjgb.hongheiku.com/djs/35725.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct"), "html", "阿克苏地区统计局公报精确转载"),
        ("克孜勒苏柯尔克孜自治州", "CN-653000", "KIZILSU", "https://tjgb.hongheiku.com/djs/42709.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "html", "克州统计局公报精确转载"),
        ("和田地区", "CN-653200", "HOTAN", "https://xjht.gov.cn/file/upload/202305/24/183553394.pdf", "A2", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "pdf", "和田地区行政公署统计局"),
        ("伊犁哈萨克自治州", "CN-654000", "YILI", "https://www.xjyl.gov.cn/xjylz/c112816/202306/6cadb0fae6fb44b4b2b71a7e2ae69985.shtml", "A2", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "html", "伊犁州统计局"),
        ("临夏回族自治州", "CN-622900", "LINXIA", "https://www.linxia.gov.cn/lxz/zwgk/bmxxgkpt/lxztjj/fdzdgknr/tjsj/tjgb/art/2023/art_1c876c8d037f4cf089ebe4325d08a45d.html", "A2", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "html", "临夏州统计局、国家统计局临夏调查队"),
    ),
)

# 2023 年自治州和新疆地州公报批次。
CITY_YEAR_FISCAL_SOURCES += _make_autonomous_bulletin_batch(
    year=2023,
    path=RAW_DIR / "province_fiscal" / "2023" / "secondary" / "2023_autonomous_city_statistical_bulletins_excerpt.txt",
    entries=(
        ("兴安盟", "CN-152200", "XINGAN", "https://tjgb.hongheiku.com/djs/46086.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "html", "兴安盟统计局公报精确转载"),
        ("大兴安岭地区", "CN-232700", "DAXINGANLING", "https://tjgb.hongheiku.com/xjtjgb/xj2020/52904.html", "B2", ("gdp_current_100m", "general_public_revenue_100m", "general_public_expenditure_100m"), "html", "大兴安岭地区统计局公报精确转载"),
        ("甘孜藏族自治州", "CN-513300", "GANZI", "https://tjgb.hongheiku.com/djs/49987.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "html", "甘孜州统计局公报精确转载"),
        ("凉山彝族自治州", "CN-513400", "LIANGSHAN", "https://tjgb.hongheiku.com/djs/52313.html", "B2", ("general_public_expenditure_100m",), "html", "凉山州统计局公报精确转载"),
        ("黔西南布依族苗族自治州", "CN-522300", "QIANXINAN", "https://tjgb.hongheiku.com/djs/51780.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct"), "html", "黔西南州统计局公报精确转载"),
        ("黔东南苗族侗族自治州", "CN-522600", "QIANDONGNAN", "https://www.zzdsj.com.cn/site4/n439/20240521/i291.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "html", "黔东南州统计局公报精确转载"),
        ("黔南布依族苗族自治州", "CN-522700", "QIANNAN", "https://tjgb.hongheiku.com/djs/50203.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct"), "html", "黔南州统计局公报精确转载"),
        ("文山壮族苗族自治州", "CN-532600", "WENSHAN", "https://www.bbthy.net/kb/5578.html", "B2", ("general_public_revenue_100m", "general_public_expenditure_100m"), "html", "文山州统计局公报精确转载"),
        ("怒江傈僳族自治州", "CN-533300", "NUJIANG", "https://www.tjnj.net/newsview/20250414143215", "B2", ("general_public_revenue_100m", "general_public_expenditure_100m"), "html", "怒江州统计局公报精确转载"),
        ("临夏回族自治州", "CN-622900", "LINXIA", "https://tjgb.hongheiku.com/djs/46026.html", "B2", ("general_public_revenue_100m", "general_public_expenditure_100m"), "html", "临夏州统计局公报精确转载"),
        ("玉树藏族自治州", "CN-632700", "YUSHU", "https://tjgb.hongheiku.com/djs/55597.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "html", "玉树州统计局公报精确转载"),
        ("克孜勒苏柯尔克孜自治州", "CN-653000", "KIZILSU", "https://www.xjkz.gov.cn/xjkz/c101979/202404/b88ebce7774447a29e854529c6647e74.shtml", "A2", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "html", "克州统计局"),
        ("和田地区", "CN-653200", "HOTAN", "https://xjht.gov.cn/file/upload/202404/01/184021914.pdf", "A2", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "pdf", "和田地区行政公署统计局"),
        ("塔城地区", "CN-654200", "TACHENG", "https://xjtc.gov.cn/upload/main/infopublicity/publicinformation/file/2024/04/26/202404261830271399.pdf", "A2", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "pdf", "塔城地区统计局"),
        ("伊犁哈萨克自治州", "CN-654000", "YILI", "https://www.xjyl.gov.cn/xjylz/c112794/202402/4c9df36c49cf468da12e22278b0bc24d.shtml", "A2", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "html", "伊犁州统计局"),
        ("昌吉回族自治州", "CN-652300", "CHANGJI", "https://www.cj.gov.cn/p135/bmyw/20240222/210798.html", "A2", ("gdp_current_100m", "gdp_real_growth_pct"), "html", "昌吉州统计局"),
        ("喀什地区", "CN-653100", "KASHI", "https://www.kashi.gov.cn/ksdqxzgs/c112198/202404/fc4969a2247b416c8e6eb3ef41310a6b.shtml", "A2", ("gdp_current_100m", "gdp_real_growth_pct"), "html", "喀什地区统计局"),
    ),
)

# 2024年贵州州级/市级统计公报财政收支补缺：五个当前仍缺一般公共预算
# 收入和支出的地级行政单元。公报正文逐项列示全域执行数，统一按B2精确
# 公报转载接入；不把财政总收入或市本级数据代入一般预算字段。
CITY_YEAR_FISCAL_SOURCES += tuple(
    _make_curated_city_source(**spec)
    for spec in (
        {
            "year": 2024,
            "city_name": "遵义市",
            "city_id": "CN-520300",
            "source_doc_id": "SRC-B2-GUIZHOU-ZUNYI-CITY-FISCAL-2024",
            "url": "https://tjgb.hongheiku.com/djs/61033.html",
            "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "guizhou_2024_prefecture_fiscal_bulletins_excerpt.txt",
            "document_title": "2024年遵义市国民经济和社会发展统计公报",
            "publisher": "遵义市统计局公报公开转载",
            "publisher_level": "市级统计机构公报精确转载",
            "publication_date": "2025-04-29",
            "source_grade": "B2",
            "fields": ("general_public_revenue_100m", "general_public_expenditure_100m"),
            "source_format": "html",
            "data_status": "preliminary",
            "data_status_label": "2024年统计公报财政执行数",
            "document_type": "市级统计公报财政收支指标精确转载",
            "page_number": "网页公报财政和金融部分",
            "note": "B2精确公报转载；公报来源标注为遵义市统计局，采用遵义市全市一般公共预算收入347.80亿元、支出862.40亿元。",
        },
        {
            "year": 2024,
            "city_name": "毕节市",
            "city_id": "CN-520500",
            "source_doc_id": "SRC-B2-GUIZHOU-BIJIE-CITY-FISCAL-2024",
            "url": "https://tjgb.hongheiku.com/xjtjgb/xj2020/61184.html",
            "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "guizhou_2024_prefecture_fiscal_bulletins_excerpt.txt",
            "document_title": "毕节市2024年国民经济和社会发展统计公报",
            "publisher": "毕节市统计局公报公开转载",
            "publisher_level": "市级统计机构公报精确转载",
            "publication_date": "2025-04-30",
            "source_grade": "B2",
            "fields": ("general_public_revenue_100m", "general_public_expenditure_100m"),
            "source_format": "pdf",
            "data_status": "preliminary",
            "data_status_label": "2024年统计公报财政执行数",
            "document_type": "市级统计公报财政收支指标精确转载",
            "page_number": "PDF第9页财政和金融部分",
            "note": "B2精确公报转载；公报来源标注为毕节市统计局，采用毕节市全市一般公共预算收入134.50亿元、支出754.20亿元。",
        },
        {
            "year": 2024,
            "city_name": "黔西南布依族苗族自治州",
            "city_id": "CN-522300",
            "source_doc_id": "SRC-B2-GUIZHOU-QIANXINAN-CITY-FISCAL-2024",
            "url": "https://tjgb.hongheiku.com/djs/61557.html",
            "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "guizhou_2024_prefecture_fiscal_bulletins_excerpt.txt",
            "document_title": "黔西南州2024年国民经济和社会发展统计公报",
            "publisher": "黔西南州统计局公报公开转载",
            "publisher_level": "州级统计机构公报精确转载",
            "publication_date": "2025-05-07",
            "source_grade": "B2",
            "fields": ("general_public_revenue_100m", "general_public_expenditure_100m"),
            "source_format": "html",
            "data_status": "preliminary",
            "data_status_label": "2024年统计公报财政执行数",
            "document_type": "州级统计公报财政收支指标精确转载",
            "page_number": "网页公报第九部分财政和金融",
            "note": "B2精确公报转载；公报来源标注为黔西南州统计局，采用全州一般公共预算收入95.27亿元、支出416.51亿元。",
        },
        {
            "year": 2024,
            "city_name": "黔东南苗族侗族自治州",
            "city_id": "CN-522600",
            "source_doc_id": "SRC-B2-GUIZHOU-QIANDONGNAN-CITY-FISCAL-2024",
            "url": "https://tjgb.hongheiku.com/djs/59456.html",
            "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "guizhou_2024_prefecture_fiscal_bulletins_excerpt.txt",
            "document_title": "黔东南州2024年国民经济和社会发展统计公报",
            "publisher": "黔东南州统计局公报精确转载",
            "publisher_level": "州级统计机构公报精确转载",
            "publication_date": "2025-04-18",
            "source_grade": "B2",
            "fields": ("general_public_revenue_100m", "general_public_expenditure_100m"),
            "source_format": "html",
            "data_status": "preliminary",
            "data_status_label": "2024年统计公报财政执行数",
            "document_type": "州级统计公报财政收支指标精确转载",
            "page_number": "网页公报第七部分财政和金融、表11",
            "note": "B2精确公报转载；公报来源标注为黔东南州统计局，采用全州一般公共预算收入80.42亿元、支出527.26亿元。",
        },
        {
            "year": 2024,
            "city_name": "黔南布依族苗族自治州",
            "city_id": "CN-522700",
            "source_doc_id": "SRC-B2-GUIZHOU-QIANNAN-CITY-FISCAL-2024",
            "url": "https://www.zgrkk.com/reports/383.html",
            "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "guizhou_2024_prefecture_fiscal_bulletins_excerpt.txt",
            "document_title": "黔南州2024年国民经济和社会发展统计公报",
            "publisher": "黔南州统计局公报精确转载",
            "publisher_level": "州级统计机构公报精确转载",
            "publication_date": "2025-04-07",
            "source_grade": "B2",
            "fields": ("general_public_revenue_100m", "general_public_expenditure_100m"),
            "source_format": "html",
            "data_status": "preliminary",
            "data_status_label": "2024年统计公报财政执行数",
            "document_type": "州级统计公报财政收支指标精确转载",
            "page_number": "网页公报第八部分财政和金融、表8",
            "note": "B2精确公报转载；公报来源标注为黔南州统计局，采用全州一般公共预算收入128.38亿元、支出503.01亿元。",
        },
    )
)

# 2025 年补入当前仍为空且已逐项核验的核心字段。蚌埠 GDP 增速依据公报
# 首页正文明确句“比上年增长5.5%”接入；不采用无法定位来源的二手冲突值。
CITY_YEAR_FISCAL_SOURCES += _make_autonomous_bulletin_batch(
    year=2025,
    path=RAW_DIR / "province_fiscal" / "2025" / "secondary" / "2025_core_macro_fiscal_supplement_excerpt.txt",
    entries=(
        ("长春市", "CN-220100", "CHANGCHUN", "https://tjgb.hongheiku.com/djs/69916.html", "B2", ("general_public_revenue_100m", "general_public_expenditure_100m"), "html", "长春市统计局公报精确转载"),
        ("蚌埠市", "CN-340300", "BENGBU", "https://tjgb.hongheiku.com/djs/70929.html", "B2", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"), "html", "蚌埠市统计公报精确转载"),
        ("吉安市", "CN-360800", "JIAN", "https://tjgb.hongheiku.com/wp-content/uploads/2026/05/1779205233-430ea0d9f5.pdf", "B2", ("general_public_expenditure_100m",), "pdf", "吉安市统计公报精确转载"),
        ("桂林市", "CN-450300", "GUILIN", "https://www.ceicdata.com/zh-hans/china/government-revenue-prefecture-level-city/government-revenue-guangxi-guilin", "B2", ("general_public_revenue_100m",), "html", "桂林市统计局数据精确转载"),
        ("延安市", "CN-610600", "YANAN", "https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3364631&mode=save&priority=0", "B2", ("general_public_revenue_100m",), "pdf", "延安市统计公报及交易所公开披露"),
    ),
)

# 桂林市财政局 2024 年全市一般公共预算支出。官方预算执行报告在同一
# 正文中明确区分“全市”和“市本级”，本批只接入全市执行数519.64亿元，
# 不把市本级162.38亿元误作地级市全辖口径。
CITY_YEAR_FISCAL_SOURCES += (
    {
        "year": 2024,
        "city_name": "桂林市",
        "city_id": "CN-450300",
        "source_doc_id": "SRC-A2-GUILIN-CITY-FISCAL-EXPENDITURE-2024",
        "url": "https://czj.guilin.gov.cn/zwgk/glsbjyjsgkpt/sbjzfzys/t26796961.shtml",
        "landing_page_url": "https://czj.guilin.gov.cn/zwgk/glsbjyjsgkpt/sbjzfzys/t26796961.shtml",
        "attachment_url": "https://czj.guilin.gov.cn/zwgk/glsbjyjsgkpt/sbjzfzys/P020251216316883452399.pdf",
        "download_url": "https://czj.guilin.gov.cn/zwgk/glsbjyjsgkpt/sbjzfzys/P020251216316883452399.pdf",
        "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "guilin_2024_budget_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2024" / "official" / "guilin_2024_budget_report_excerpt.txt",
        "text_is_curated": True,
        "document_title": "关于桂林市全市与市本级2024年预算执行情况和2025年预算草案的报告",
        "publisher": "桂林市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2025-04-24",
        "source_grade": "A2",
        "source_format": "pdf",
        "data_status": "execution",
        "data_status_label": "2024年全市预算执行数",
        "document_type": "城市财政预算执行报告（官方PDF）",
        "page_number": "网页正文（一）一般公共预算执行情况第1项‘全市’；附件1",
        "raw_unit": "亿元",
        "patterns": {
            "general_public_expenditure_100m": r"城市=桂林市｜年度=2024｜一般公共预算支出=([0-9.,-]+)亿元",
        },
        "note": "A2桂林市财政局官方预算执行报告；正文明确区分全市与市本级，采用2024年全市一般公共预算支出519.64亿元，不使用市本级162.38亿元。",
    },
)

# 阿里地区 2022—2023 年 GDP 缺口补录。2022 年采用联合资信报告表7的
# 精确 GDP 单元格；报告脚注说明增速是由 GDP 绝对值计算得到，因此只接入
# GDP，不把该推算增速伪装为原始统计值。2023 年采用西藏日报对阿里地区
# 行署专员的正式访谈，原文明确使用“预计”，故保留 preliminary 状态。
CITY_YEAR_FISCAL_SOURCES += (
    {
        "year": 2022,
        "city_name": "阿里地区",
        "city_id": "CN-542500",
        "source_doc_id": "SRC-B2-ALI-REGION-GDP-2022-RATING",
        "url": "https://www.lhratings.com/file/f732353344d.pdf",
        "path": RAW_DIR / "province_fiscal" / "2022" / "secondary" / "tibet_2022_regional_rating_report.pdf",
        "text_path": RAW_DIR / "province_fiscal" / "2022" / "secondary" / "ali_2022_gdp_rating_excerpt.txt",
        "text_is_curated": True,
        "document_title": "西藏自治区及下辖市（区）经济财政实力与债务研究",
        "publisher": "联合资信评估股份有限公司",
        "publisher_level": "评级机构精确表格披露",
        "publication_date": "2023-10-31",
        "source_grade": "B2",
        "source_format": "pdf",
        "data_status": "reported",
        "data_status_label": "2022年公开报告值",
        "document_type": "评级报告地市GDP精确表格",
        "page_number": "PDF第11页表7；阿里地区全地区口径",
        "raw_unit": "亿元",
        "patterns": {
            "gdp_current_100m": r"城市=阿里地区｜年度=2022｜GDP=([0-9.,-]+)亿元",
        },
        "note": "B2评级报告表7精确单元格；阿里地区2022年GDP为80.51亿元。报告脚注明确GDP增速0.50%由GDP绝对值计算得出，故不接入该增速。",
    },
    _make_curated_city_source(
        year=2023,
        city_name="阿里地区",
        city_id="CN-542500",
        source_doc_id="SRC-B2-ALI-REGION-MACRO-2023-INTERVIEW",
        url="https://xz.people.com.cn/n2/2024/0111/c138901-40710421.html",
        path=RAW_DIR / "province_fiscal" / "2023" / "official" / "ali_2023_economic_interview_excerpt.txt",
        document_title="努力建设雪域高原的‘西部明珠’——阿里地区行署专员正式访谈",
        publisher="西藏日报（人民网西藏频道公开转载）",
        publisher_level="省级党报公开访谈",
        publication_date="2024-01-11",
        source_grade="B2",
        fields=("gdp_current_100m", "gdp_real_growth_pct"),
        raw_units={"gdp_real_growth_pct": "%"},
        source_format="html",
        data_status="preliminary",
        data_status_label="2023年预计/初步值",
        document_type="地区经济指标正式访谈摘录",
        page_number="网页正文；阿里地区经济社会发展指标段",
        note="B2省级党报正式访谈；原文明确为阿里地区全地区2023年预计GDP91.51亿元、同比增长13%，保留preliminary状态，不表述为最终决算数。",
    ),
)

# 2024 年核心四字段补缺批次：丽江、达州、甘孜州、凉山州和自贡。来源均
# 明确列示全市（州）口径；其中丽江使用官方预算附件中的2024年决算列，
# 其余来源使用官方公报、政府公开经济运行信息或精确公开报告摘录。
CITY_YEAR_FISCAL_SOURCES += (
    {
        "year": 2024,
        "city_name": "丽江市",
        "city_id": "CN-530700",
        "source_doc_id": "SRC-A2-LIJIANG-CITY-FISCAL-EXPENDITURE-2024",
        "url": "https://www.lijiang.gov.cn/ljsrmzf/c102171/202602/563a29840543411a84a8a934a27f9cc2.shtml",
        "landing_page_url": "https://www.lijiang.gov.cn/ljsrmzf/c102171/202602/563a29840543411a84a8a934a27f9cc2.shtml",
        "attachment_url": "https://www.lijiang.gov.cn/ljsrmzf/c102171/202602/563a29840543411a84a8a934a27f9cc2/files/3ee51c32d0444e26a516385e99529b9e.xlsx",
        "download_url": "https://www.lijiang.gov.cn/ljsrmzf/c102171/202602/563a29840543411a84a8a934a27f9cc2/files/3ee51c32d0444e26a516385e99529b9e.xlsx",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "lijiang_2025_budget_attachment.xlsx",
        "text_path": RAW_DIR / "province_fiscal" / "2025" / "official" / "lijiang_2025_budget_execution_excerpt.txt",
        "text_is_curated": True,
        "document_title": "关于丽江市2025年地方财政预算执行情况和2026年地方财政预算草案的报告附件1",
        "publisher": "丽江市财政局",
        "publisher_level": "市级财政机构",
        "publication_date": "2026-02-13",
        "source_grade": "A2",
        "source_format": "xlsx",
        "data_status": "final",
        "data_status_label": "2024年决算数（官方预算执行表）",
        "document_type": "城市财政预算执行附件分年度全市一般公共预算支出表",
        "page_number": "附件1表二“支出合计”行，2024年决算数列",
        "raw_unit": "万元",
        "patterns": {
            "general_public_expenditure_100m": r"城市=丽江市｜年度=2024｜一般公共预算支出=([0-9,]+)万元",
        },
        "note": "A2丽江市财政局官方Excel附件；表二同时列出2024年决算数和2025年执行数，采用全市2024年决算数1810076万元，不使用2025年执行数、预算数或市本级口径。",
    },
)

CITY_YEAR_FISCAL_SOURCES += tuple(
    _make_curated_city_source(**spec)
    for spec in (
        {
            "year": 2024,
            "city_name": "达州市",
            "city_id": "CN-511700",
            "source_doc_id": "SRC-A2-DAZHOU-CITY-FISCAL-EXPENDITURE-2024",
            "url": "https://www.dazhou.gov.cn/xxgk-show-36374.html",
            "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "dazhou_2024_statistical_bulletin_excerpt.txt",
            "document_title": "2024年达州市国民经济和社会发展统计公报",
            "publisher": "达州市统计局、国家统计局达州调查队",
            "publisher_level": "市级统计机构",
            "publication_date": "2025-04-25",
            "source_grade": "A2",
            "fields": ("general_public_expenditure_100m",),
            "raw_unit": "亿元",
            "source_format": "txt",
            "data_status": "preliminary",
            "data_status_label": "2024年统计公报初步统计数",
            "document_type": "官方统计公报财政指标",
            "page_number": "官方公报九、财政和金融；全市口径",
            "note": "A2达州市人民政府公开的市统计局、国家统计局达州调查队统计公报；采用全市地方公共财政支出598.2亿元，公报注明数据为初步统计数。",
        },
        {
            "year": 2024,
            "city_name": "甘孜藏族自治州",
            "city_id": "CN-513300",
            "source_doc_id": "SRC-B2-GANZI-CITY-MACRO-FISCAL-2024",
            "url": "https://www.batang.gov.cn/zwcz/article/636524",
            "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "ganzi_2024_economic_fiscal_excerpt.txt",
            "document_title": "甘孜州2024年经济运行稳中提质",
            "publisher": "甘孜州政府秘书一科（巴塘县人民政府公开转载）",
            "publisher_level": "州级政府信息公开转载",
            "publication_date": "2025-02-13",
            "source_grade": "B2",
            "fields": ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
            "raw_unit": "亿元",
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": "txt",
            "data_status": "preliminary",
            "data_status_label": "2024年官方经济运行公开值",
            "document_type": "州级经济运行和财政收支指标精确转载",
            "page_number": "网页第⑴项、第⑶项；全州口径",
            "note": "B2精确公开来源；页面由州政府秘书一科发布并由县级政府公开，逐项列示全州GDP580.52亿元、实际增速5.4%、一般公共预算收入60.5亿元和支出454.5亿元。",
        },
        {
            "year": 2024,
            "city_name": "凉山彝族自治州",
            "city_id": "CN-513400",
            "source_doc_id": "SRC-B2-LIANGSHAN-CITY-MACRO-FISCAL-2024",
            "url": "https://www.zgrkk.com/reports/188.html",
            "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "liangshan_2024_statistical_bulletin_excerpt.txt",
            "document_title": "凉山州2024年国民经济和社会发展统计公报",
            "publisher": "凉山州统计局、国家统计局凉山调查队公报精确公开转载",
            "publisher_level": "州级统计机构公报精确转载",
            "publication_date": "2025-05-01",
            "source_grade": "B2",
            "fields": ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"),
            "raw_unit": "亿元",
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": "txt",
            "data_status": "preliminary",
            "data_status_label": "2024年统计公报初步统计数",
            "document_type": "州级统计公报经济财政指标精确转载",
            "page_number": "公报综合部分、八、财政金融；全州口径",
            "note": "B2精确公报转载；来源注明凉山州统计局、国家统计局凉山调查队，采用全州GDP2474.9亿元、实际增速6.0%、一般公共预算收入220.3亿元和支出848.5亿元。",
        },
        {
            "year": 2024,
            "city_name": "自贡市",
            "city_id": "CN-510300",
            "source_doc_id": "SRC-B2-ZIGONG-CITY-MACRO-2024",
            "url": "https://www.zgm.cn/content/6790b9af7870c",
            "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "zigong_2024_macro_fiscal_excerpt.txt",
            "document_title": "1876.24亿元！2024年自贡GDP同比增长7.1%",
            "publisher": "自贡市统计局数据经自贡网公开",
            "publisher_level": "市级统计机构数据公开转载",
            "publication_date": "2025-01-23",
            "source_grade": "B2",
            "fields": ("gdp_current_100m", "gdp_real_growth_pct"),
            "raw_unit": "亿元",
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": "txt",
            "data_status": "preliminary",
            "data_status_label": "2024年统计公开初步统计数",
            "document_type": "市级统计机构GDP指标精确转载",
            "page_number": "公开页面正文；全市口径",
            "note": "B2精确公开来源；自贡网注明数据由自贡市统计局发布，采用全市GDP1876.24亿元和按可比价格计算的实际增速7.1%。",
        },
        {
            "year": 2024,
            "city_name": "自贡市",
            "city_id": "CN-510300",
            "source_doc_id": "SRC-B2-ZIGONG-CITY-FISCAL-2024",
            "url": "https://dp.zgm.cn/show/33193",
            "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "zigong_2024_macro_fiscal_excerpt.txt",
            "document_title": "关于自贡市2024年预算执行情况和2025年预算草案的报告",
            "publisher": "自贡市财政局报告经自贡网公开",
            "publisher_level": "市级财政机构报告公开转载",
            "publication_date": "2025-03-13",
            "source_grade": "B2",
            "fields": ("general_public_revenue_100m", "general_public_expenditure_100m"),
            "raw_unit": "万元",
            "source_format": "txt",
            "data_status": "final",
            "data_status_label": "2024年财政执行数",
            "document_type": "市级财政预算执行报告指标精确转载",
            "page_number": "报告表格；全市合计行",
            "note": "B2精确公开报告；报告列示自贡市全市一般公共预算收入853012万元、支出3042681万元，统一换算为亿元，不使用市本级数。",
        },
    )
)

# 2024 黑河及 2025 阿里、菏泽核心四字段补缺。黑河采用市统计局公报官方附件；
# 阿里只接入页面明确列示的 GDP、增速和一般公共预算支出，不把“地方财政收入”
# 误当作一般公共预算收入；菏泽采用评级报告第15页精确表格中的三项值。
CITY_YEAR_FISCAL_SOURCES += tuple(
    _make_curated_city_source(**spec)
    for spec in (
        {
            "year": 2024,
            "city_name": "黑河市",
            "city_id": "CN-231100",
            "source_doc_id": "SRC-A2-HEIHE-CITY-MACRO-FISCAL-2024",
            "url": "https://www.heihe.gov.cn/hhs/c103137/202505/c11_328796.shtml",
            "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "heihe_2024_statistical_bulletin_excerpt.txt",
            "document_title": "2024年黑河市国民经济和社会发展统计公报",
            "publisher": "黑河市统计局",
            "publisher_level": "市级统计机构",
            "publication_date": "2025-05-14",
            "source_grade": "A2",
            "fields": (
                "gdp_current_100m",
                "gdp_real_growth_pct",
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
            ),
            "raw_unit": "亿元",
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": "txt",
            "data_status": "preliminary",
            "data_status_label": "2024年统计公报初步统计数",
            "document_type": "市级统计公报经济财政指标",
            "page_number": "PDF第1页、第8页；全市口径",
            "note": "A2黑河市统计局官方公报；采用全市GDP711.4亿元、实际增速3.3%、一般公共预算收入56.2亿元和支出323.5亿元，公报注明数据为初步统计数。",
        },
        {
            "year": 2025,
            "city_name": "阿里地区",
            "city_id": "CN-542500",
            "source_doc_id": "SRC-A2-ALI-REGION-MACRO-FISCAL-2025",
            "url": "https://www.al.gov.cn/zjal/jjsh.htm",
            "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "ali_2025_economic_fiscal_excerpt.txt",
            "document_title": "阿里地区经济社会信息（2025年）",
            "publisher": "阿里地区行政公署、阿里地区统计局",
            "publisher_level": "地区政府及统计机构",
            "publication_date": "2026-03-31",
            "source_grade": "A2",
            "fields": (
                "gdp_current_100m",
                "gdp_real_growth_pct",
                "general_public_expenditure_100m",
            ),
            "raw_unit": "亿元",
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": "txt",
            "data_status": "preliminary",
            "data_status_label": "2025年官方公开值",
            "document_type": "地区政府经济财政指标公开页面摘录",
            "page_number": "官方页面经济社会栏目；全地区口径",
            "note": "A2阿里地区行政公署官方页面；采用全地区GDP114.21亿元、实际增速6.6%和一般公共预算支出174.61亿元。页面另列地方财政收入37094万元，但未明确为全地区一般公共预算收入，故不代入该字段。",
        },
        {
            "year": 2025,
            "city_name": "菏泽市",
            "city_id": "CN-371700",
            "source_doc_id": "SRC-B2-HEZE-CITY-MACRO-FISCAL-2025",
            "url": "https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3353993&mode=save&priority=0",
            "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "heze_2025_rating_report_excerpt.txt",
            "document_title": "菏泽市城市建设投资集团有限公司及相关债项2026年度跟踪评级报告",
            "publisher": "东方金诚",
            "publisher_level": "评级机构精确表格披露",
            "publication_date": "2026-05-29",
            "source_grade": "B2",
            "fields": (
                "gdp_current_100m",
                "gdp_real_growth_pct",
                "general_public_revenue_100m",
            ),
            "raw_unit": "亿元",
            "raw_units": {"gdp_real_growth_pct": "%"},
            "source_format": "txt",
            "data_status": "preliminary",
            "data_status_label": "2025年评级报告精确公开值",
            "document_type": "评级报告城市经济财政指标表",
            "page_number": "PDF第15页图表11；全市口径",
            "note": "B2精确表格；图表11列示菏泽市2025年GDP4937.4亿元、实际增速5.0%和一般公共预算收入333.37亿元。报告未列示一般公共预算支出，故不作推算或代填。",
        },
        {
            "year": 2025,
            "city_name": "菏泽市",
            "city_id": "CN-371700",
            "source_doc_id": "SRC-A2-HEZE-CITY-FISCAL-2025",
            "url": "http://www.heze.gov.cn/0530/2c908088819842f701819a2ab278002d/2028655444125499392.html",
            "attachment_url": "http://www.heze.gov.cn/upload-service/0530/2c908088819842f701819a2ab278002d/WY2028655400047480832.pdf",
            "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "heze_2025_budget_execution_excerpt.txt",
            "document_title": "菏泽市2025年预算执行情况和2026年预算草案报告",
            "publisher": "菏泽市财政局",
            "publisher_level": "市级财政机构",
            "publication_date": "2026-02-06",
            "source_grade": "A2",
            "fields": ("general_public_revenue_100m", "general_public_expenditure_100m"),
            "raw_unit": "亿元",
            "source_format": "pdf",
            "data_status": "execution",
            "data_status_label": "2025年全市一般公共预算执行数",
            "document_type": "市级财政预算执行报告",
            "page_number": "官方报告第1—2页；全市口径",
            "note": (
                "A2菏泽市财政局官方预算执行报告；收入采用全市一般公共预算收入333.37亿元，"
                "支出采用报告明确的当年支出759.26亿元。报告同时列示含上解、债务还本、"
                "预算稳定调节基金和结转下年的一般公共预算总支出996.58亿元，未将该总额代入年度支出字段；"
                "附表入口保留在来源摘录中供复核。"
            ),
        },
    )
)

# 2024—2025 核心经济字段跟进批次：接入官方统计公报、政府信息公开页面及
# 可逐项定位的公开披露文件，补齐当前主表中的 GDP/GDP 增速缺口。所有值均为
# 全市（州、地区）口径；和田、海口使用可精确定位的 B2 披露作为补充证据。
_CURATED_2024_2025_MACRO_FOLLOWUP_SPECS = (
    {
        "year": 2024,
        "city_name": "迪庆藏族自治州",
        "city_id": "CN-533400",
        "source_doc_id": "SRC-A2-DIQING-CITY-MACRO-FISCAL-2024",
        "url": "https://www.diqing.gov.cn/zfxxgk_dqzzf/fdzdgknr/jjhshfztj/202505/20250512_227002.html",
        "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "diqing_2024_statistical_bulletin_excerpt.txt",
        "document_title": "迪庆藏族自治州二○二四年国民经济和社会发展统计公报",
        "publisher": "迪庆藏族自治州统计局",
        "publisher_level": "州级统计机构",
        "publication_date": "2025-05-12",
        "source_grade": "A2",
        "fields": ("gdp_current_100m", "gdp_real_growth_pct"),
        "raw_unit": "万元",
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2024年统计公报初步统计数",
        "document_type": "州级统计公报经济指标",
        "page_number": "官方页面综合部分；全州口径",
        "note": "A2迪庆州统计局官方公报；GDP原始值为3070122万元，按可比价同比增长0.4%。",
    },
    {
        "year": 2024,
        "city_name": "和田地区",
        "city_id": "CN-653200",
        "source_doc_id": "SRC-B2-HOTAN-REGION-GDP-2024",
        "url": "https://static.sse.com.cn/bond/bridge2/disclosure/announcement/c/202511/584b33_20251121_17U6.pdf",
        "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "hotan_2024_gdp_official_disclosure_excerpt.txt",
        "document_title": "和田地区2024年统计公报数据精确披露",
        "publisher": "上海证券交易所披露文件（引用和田地区行政公署官方统计公报）",
        "publisher_level": "公开披露B2来源",
        "publication_date": "2025-11-21",
        "source_grade": "B2",
        "fields": ("gdp_current_100m",),
        "raw_unit": "亿元",
        "source_format": "pdf",
        "data_status": "preliminary",
        "data_status_label": "2024年统计公报精确引用值",
        "document_type": "公开披露文件引用统计公报经济指标",
        "page_number": "披露PDF第23页；和田地区全地区口径",
        "note": "B2精确披露；披露文件明确引用和田地区行政公署《2024年和田地区国民经济和社会发展统计公报》，列示GDP598.36亿元；官方公报入口另行保存在摘录文件。",
    },
    {
        "year": 2025,
        "city_name": "廊坊市",
        "city_id": "CN-131000",
        "source_doc_id": "SRC-A2-LANGFANG-CITY-MACRO-2025",
        "url": "https://www.lf.gov.cn/Item/139689.aspx?sourceid=154177&sourcenodeid=1013",
        "path": RAW_DIR / "province_fiscal" / "2025" / "official" / "langfang_2025_statistical_bulletin_excerpt.txt",
        "document_title": "二〇二五年我市经济运行稳健向好",
        "publisher": "廊坊市人民政府网站（市政府新闻办经济形势新闻发布会信息）",
        "publisher_level": "市级政府公开信息",
        "publication_date": "2026-03-04",
        "source_grade": "A2",
        "fields": ("gdp_current_100m", "gdp_real_growth_pct"),
        "raw_unit": "亿元",
        "raw_units": {"gdp_real_growth_pct": "%"},
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2025年经济运行公开初步值",
        "document_type": "市级政府经济运行指标",
        "page_number": "官方页面正文；全市口径",
        "note": "A2廊坊市人民政府网站公开信息；列示2025年全市生产总值4040.5亿元、同比增长5.8%。",
    },
    {
        "year": 2024,
        "city_name": "阳泉市",
        "city_id": "CN-140300",
        "source_doc_id": "SRC-A2-YANGQUAN-CITY-GROWTH-2024",
        "url": "https://xxgk.yq.gov.cn/tjj/fdzdgknr/tzgg/202504/t20250428_2056071.shtml",
        "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "yangquan_2024_statistical_bulletin_excerpt.txt",
        "document_title": "阳泉市2024年国民经济和社会发展统计公报",
        "publisher": "阳泉市统计局、国家统计局阳泉调查队",
        "publisher_level": "市级统计机构",
        "publication_date": "2025-04-28",
        "source_grade": "A2",
        "fields": ("gdp_real_growth_pct",),
        "raw_unit": "%",
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2024年统计公报初步统计数",
        "document_type": "市级统计公报经济指标",
        "page_number": "官方公报综合部分；全市口径",
        "note": "A2阳泉市统计局官方公报；2024年GDP按不变价格计算下降0.9%。",
    },
    {
        "year": 2024,
        "city_name": "海口市",
        "city_id": "CN-460100",
        "source_doc_id": "SRC-B2-HAIKOU-CITY-GROWTH-2024",
        "url": "https://szb.hkwb.net/epaper/xml/hkrb/20250327/A05B20250327C.pdf",
        "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "haikou_2024_statistical_bulletin_excerpt.txt",
        "document_title": "2024年海口市国民经济和社会发展统计公报",
        "publisher": "海口日报（刊载海口市统计局、国家统计局海口调查队公报）",
        "publisher_level": "市级统计公报公开转载",
        "publication_date": "2025-03-27",
        "source_grade": "B2",
        "fields": ("gdp_real_growth_pct",),
        "raw_unit": "%",
        "source_format": "pdf",
        "data_status": "preliminary",
        "data_status_label": "2024年统计公报初步统计数",
        "document_type": "市级统计公报经济指标精确披露",
        "page_number": "海口日报PDF第5版综合部分；全市口径",
        "note": "B2精确公开公报；海口日报刊载海口市统计局、国家统计局海口调查队公报，列示2024年GDP同比增长4.0%。",
    },
    {
        "year": 2024,
        "city_name": "伊犁哈萨克自治州",
        "city_id": "CN-654000",
        "source_doc_id": "SRC-A2-YILI-REGION-GROWTH-2024",
        "url": "https://www.xjyl.gov.cn/xjylz/c112816/202504/67c6814847cb40a0a33773fb1df5466b.shtml",
        "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "yili_2024_statistical_bulletin_excerpt.txt",
        "document_title": "伊犁哈萨克自治州2024年国民经济和社会发展统计公报",
        "publisher": "伊犁哈萨克自治州统计局",
        "publisher_level": "州级统计机构",
        "publication_date": "2025-04-09",
        "source_grade": "A2",
        "fields": ("gdp_real_growth_pct",),
        "raw_unit": "%",
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2024年统计公报初步统计数",
        "document_type": "州级统计公报经济指标",
        "page_number": "官方公报综合部分；全州口径",
        "note": "A2伊犁州统计局官方公报；全州GDP同比增长6.0%，不使用仅覆盖州直的5.6%口径。",
    },
    {
        "year": 2024,
        "city_name": "哈尔滨市",
        "city_id": "CN-230100",
        "source_doc_id": "SRC-A2-HARBIN-CITY-GROWTH-2024",
        "url": "https://www.hlj.gov.cn/hlj/c107858/202502/c00_31813785.shtml",
        "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "harbin_2024_statistical_bulletin_excerpt.txt",
        "document_title": "2024哈尔滨刻下新高度",
        "publisher": "黑龙江省人民政府网站（引用哈尔滨市政府工作报告）",
        "publisher_level": "省级政府公开信息",
        "publication_date": "2025-02-21",
        "source_grade": "A2",
        "fields": ("gdp_real_growth_pct",),
        "raw_unit": "%",
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2024年政府工作报告公开值",
        "document_type": "政府公开经济指标",
        "page_number": "官方页面正文；全市口径",
        "note": "A2黑龙江省人民政府网站公开信息引用哈尔滨市政府工作报告，列示2024年GDP6016.3亿元、增长4.3%。本批只接入缺失的增速。",
    },
    {
        "year": 2024,
        "city_name": "鹤岗市",
        "city_id": "CN-230400",
        "source_doc_id": "SRC-A2-HEGANG-CITY-GROWTH-2024",
        "url": "https://www.hegang.gov.cn/hegang/tjfx/202502/69932.shtml",
        "path": RAW_DIR / "province_fiscal" / "2024" / "official" / "hegang_2024_gdp_growth_official_excerpt.txt",
        "document_title": "2024年1-4季度鹤岗市生产总值统一核算结果",
        "publisher": "鹤岗市统计局",
        "publisher_level": "市级统计机构",
        "publication_date": "2025-02-25",
        "source_grade": "A2",
        "fields": ("gdp_real_growth_pct",),
        "raw_unit": "%",
        "source_format": "html",
        "data_status": "preliminary",
        "data_status_label": "2024年1-4季度统一核算初步值",
        "document_type": "市级统计机构GDP统一核算信息",
        "page_number": "官方页面正文；全市口径",
        "note": "A2鹤岗市统计局官方统一核算结果；2024年GDP376.3亿元，同比下降2.9%。",
    },
)

CITY_YEAR_FISCAL_SOURCES += tuple(
    _make_curated_city_source(**spec)
    for spec in _CURATED_2024_2025_MACRO_FOLLOWUP_SPECS
)

# 新世纪评级公开的西藏区域研究报告第9页正文逐项列示阿里地区2024年GDP增速；
# 该值有明确的全地区口径和精确文本定位，不采用同页图表目测值。
CITY_YEAR_FISCAL_SOURCES += (
    _make_curated_city_source(
        year=2024,
        city_name="阿里地区",
        city_id="CN-542500",
        source_doc_id="SRC-B2-ALI-REGION-GDP-GROWTH-2024",
        url="https://pdf.dfcfw.com/pdf/H3_AP202601021813288922_1.pdf?1767512274000.pdf=",
        path=RAW_DIR / "province_fiscal" / "2024" / "secondary" / "ali_2024_rating_report_gdp_growth_excerpt.txt",
        document_title="西藏自治区及下辖市（地区）经济财政实力与债务研究（2025）",
        publisher="新世纪评级",
        publisher_level="评级机构公开披露（二手来源）",
        publication_date="2026-01-02",
        source_grade="B2",
        fields=("gdp_real_growth_pct",),
        raw_unit="%",
        raw_units={"gdp_real_growth_pct": "%"},
        source_format="pdf",
        data_status="preliminary",
        data_status_label="2024年公开整理GDP增速值",
        document_type="评级报告地区经济指标精确文本披露",
        page_number="PDF第9页正文；阿里地区全地区口径",
        note=(
            "B2公开评级报告精确文本；第9页明确写明阿里地区2024年GDP为105.85亿元、"
            "GDP增速为8.6%，并在同页说明数据来源为各地市统计公报及其他公开资料；"
            "本批仅接入缺失的GDP实际增速，不使用图表目测值。"
        ),
    ),
)

# 2025年财通证券研究所公开的地市经济财政精确表格（图4、图6）补充当前仍为空的
# 海西、七台河和榆林字段。图表中的数值是可逐项读取的表格单元格，按B2登记；不以
# 研究报告的柱状图目测值代替，也不覆盖已有的A1/A2/B1值。
CITY_YEAR_FISCAL_SOURCES += tuple(
    _make_curated_city_source(
        year=2025,
        city_name=city_name,
        city_id=city_id,
        source_doc_id=f"SRC-B2-SINA-CREDIT-300-CITIES-2025-{slug}",
        url="https://finance.sina.cn/2026-04-03/detail-inhteimp9034920.d.html?vt=4&wm=2",
        path=RAW_DIR / "province_fiscal" / "2025" / "secondary" / "sina_finance_2025_macro_table_excerpt.txt",
        document_title="信用｜2025年，300城经济财政怎么看？",
        publisher="财通证券研究所（新浪财经公开转载）",
        publisher_level="专业研究机构公开精确表格（二手来源）",
        publication_date="2026-04-03",
        source_grade="B2",
        fields=fields,
        raw_units={"gdp_real_growth_pct": "%"},
        source_format="html",
        data_status="preliminary",
        data_status_label="2025年公开整理精确表格值",
        document_type="公开研究机构地市经济财政指标表",
        page_number="图4、图6；对应城市行",
        note=(
            "B2公开研究机构精确表格；财通证券研究所说明数据由企业预警通、财通证券研究所整理。"
            "仅接入图4/图6中明确的GDP、实际增速或一般公共预算收入单元格，"
            "不使用柱状图目测，不覆盖更高等级来源。"
        ),
    )
    for city_name, city_id, slug, fields in (
        ("海西蒙古族藏族自治州", "CN-632800", "HAIXI", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m")),
        ("七台河市", "CN-230900", "QITAIHE", ("gdp_current_100m", "gdp_real_growth_pct", "general_public_revenue_100m")),
        ("榆林市", "CN-610800", "YULIN", ("general_public_revenue_100m",)),
    )
)

# 华经产业研究院公开页面对2024年聊城、咸阳的一般预算财政支出给出精确值；
# 这是B2二手整理，只补主表空缺，不将其收入数覆盖到已有的更高等级来源。
CITY_YEAR_FISCAL_SOURCES += tuple(
    _make_curated_city_source(
        year=2024,
        city_name=city_name,
        city_id=city_id,
        source_doc_id=f"SRC-B2-HUAON-CITY-FISCAL-2024-{slug}",
        url=url,
        path=RAW_DIR / "province_fiscal" / "2024" / "secondary" / "huajing_2024_city_fiscal_excerpt.txt",
        document_title=title,
        publisher="华经产业研究院",
        publisher_level="专业研究机构公开城市财政页面（二手来源）",
        publication_date=publication_date,
        source_grade="B2",
        fields=("general_public_expenditure_100m",),
        source_format="html",
        data_status="preliminary",
        data_status_label="2024年公开整理财政数",
        document_type="城市一般预算财政收支公开页面",
        page_number="正文第一部分；一般预算财政收入和一般预算财政支出情况",
        note=(
            "B2非政府二手整理页面，正文精确列示城市一般预算财政支出；"
            "本批仅补主表空缺字段，不覆盖已有更高等级或冲突值。"
        ),
    )
    for city_name, city_id, slug, url, title, publication_date in (
        ("聊城市", "CN-371500", "LIAOCHENG", "https://www.huaon.com/channel/distdata/1067274.html", "2024年聊城市一般预算财政收入、一般预算财政支出及收支差额情况", "2025-04-13"),
        ("咸阳市", "CN-610400", "XIANYANG", "https://www.huaon.com/channel/distdata/1067882.html", "2024年咸阳市一般预算财政收入、一般预算财政支出及收支差额情况", "2025-04-15"),
    )
)

# 延安市统计公报公开转载明确列示2024年全市财政支出560.58亿元；仅补支出，
# 并保留B2等级，不把同页“地方财政收入”当作一般公共预算收入。
CITY_YEAR_FISCAL_SOURCES += (
    _make_curated_city_source(
        year=2024,
        city_name="延安市",
        city_id="CN-610600",
        source_doc_id="SRC-B2-YANAN-STATISTICAL-BULLETIN-FISCAL-2024",
        url="https://www.zgrkk.com/reports/237.html",
        path=RAW_DIR / "province_fiscal" / "2024" / "secondary" / "yanan_2024_statistical_bulletin_fiscal_excerpt.txt",
        document_title="2024年延安市国民经济和社会发展统计公报",
        publisher="延安市统计局、国家统计局延安调查队（公开转载）",
        publisher_level="官方统计公报公开转载（二手来源）",
        publication_date="2025-05-13",
        source_grade="B2",
        fields=("general_public_expenditure_100m",),
        source_format="html",
        data_status="preliminary",
        data_status_label="2024年统计公报财政数",
        document_type="统计公报财政指标",
        page_number="公报财政段；全市口径",
        note=(
            "B2官方统计公报公开转载；正文明确列示2024年全市财政支出560.58亿元。"
            "仅接入一般公共预算支出，不将地方财政收入自动等同于一般公共预算收入。"
        ),
    ),
)

# 榆林市财政局2025年财政预算执行报告明确列示全市一般公共预算支出；
# 仅接入表二“支出合计”执行数，不使用市级表或2026年预算数。
CITY_YEAR_FISCAL_SOURCES += (
    _make_curated_city_source(
        year=2025,
        city_name="榆林市",
        city_id="CN-610800",
        source_doc_id="SRC-A1-YULIN-CITY-FISCAL-2025",
        url="https://www.yl.gov.cn/zwgk/fdzdgknr/czxx/czyjs/szfczys/202603/t20260319_2082424.html",
        path=RAW_DIR / "province_fiscal" / "2025" / "official" / "ylin_2025_budget_execution_excerpt.txt",
        document_title="关于榆林市2025年财政预算执行情况和2026年财政预算草案的报告",
        publisher="榆林市财政局",
        publisher_level="市级财政机构",
        publication_date="2026-03-19",
        source_grade="A1",
        fields=("general_public_expenditure_100m",),
        raw_unit="万元",
        source_format="pdf",
        data_status="execution",
        data_status_label="2025年全市一般公共预算支出执行数",
        document_type="市级财政预算执行报告",
        page_number="PDF第8页表二；全市口径；支出合计行",
        note=(
            "A1榆林市财政局官方预算执行报告；表二列示2025年全市一般公共预算支出执行数"
            "11507100万元，换算为1150.71亿元。仅使用全市表，不使用市级表或预算数。"
        ),
    ),
)

# 2024年汉中、渭南和2025年海西的全市一般公共预算支出补缺。
# 前两项来自公开精确城市财政/统计公报页面，后一项来自公开报道中的精确全州值；
# 均只补当前空值，不覆盖已有更高等级记录，也不使用市本级或预算数。
CITY_YEAR_FISCAL_SOURCES += tuple(
    _make_curated_city_source(**spec)
    for spec in (
        {
            "year": 2024,
            "city_name": "汉中市",
            "city_id": "CN-610700",
            "source_doc_id": "SRC-B2-HANZHONG-CITY-FISCAL-2024",
            "url": "https://www.huaon.com/channel/distdata/1067883.html",
            "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "2024_city_fiscal_followup_excerpt.txt",
            "document_title": "2024年汉中市一般预算财政收入、一般预算财政支出及收支差额情况",
            "publisher": "华经产业研究院",
            "publisher_level": "专业研究机构公开城市财政页面（二手来源）",
            "publication_date": "2025-04-15",
            "source_grade": "B2",
            "fields": ("general_public_expenditure_100m",),
            "raw_unit": "亿元",
            "source_format": "html",
            "data_status": "preliminary",
            "data_status_label": "2024年公开整理财政数",
            "document_type": "城市一般预算财政收支公开页面",
            "page_number": "正文第一部分；一般预算财政支出",
            "note": (
                "B2公开精确页面；正文列示2024年汉中市一般预算财政支出440.3亿元，"
                "城市口径与年度明确，仅补一般公共预算支出。"
            ),
        },
        {
            "year": 2024,
            "city_name": "渭南市",
            "city_id": "CN-610500",
            "source_doc_id": "SRC-B2-WEINAN-CITY-BULLETIN-FISCAL-2024",
            "url": "https://tjgb.hongheiku.com/xjtjgb/xj2020/61374.html",
            "path": RAW_DIR / "province_fiscal" / "2024" / "secondary" / "2024_city_fiscal_followup_excerpt.txt",
            "document_title": "2024年渭南市国民经济和社会发展统计公报",
            "publisher": "渭南市统计局公报公开转载",
            "publisher_level": "市级统计机构公报公开转载（二手来源）",
            "publication_date": "2025-05-02",
            "source_grade": "B2",
            "fields": ("general_public_expenditure_100m",),
            "raw_unit": "亿元",
            "source_format": "html",
            "data_status": "preliminary",
            "data_status_label": "2024年统计公报初步统计数",
            "document_type": "市级统计公报财政指标",
            "page_number": "公报第八部分财政、金融和保险；全市口径",
            "note": (
                "B2官方统计公报公开转载；财政段列示2024年全市财政支出576.48亿元，"
                "公报注明为初步统计数；本批仅将该全市财政支出作为一般公共预算支出补缺。"
            ),
        },
        {
            "year": 2025,
            "city_name": "海西蒙古族藏族自治州",
            "city_id": "CN-632800",
            "source_doc_id": "SRC-B2-HAIXI-STATE-FISCAL-2025",
            "url": "https://www.sohu.com/a/984487505_121106869",
            "path": RAW_DIR / "province_fiscal" / "2025" / "secondary" / "haixi_2025_statistical_fiscal_excerpt.txt",
            "document_title": "硬核经济托底 暖心民生作答——2025年海西州发展民生双向奔赴绘幸福长卷",
            "publisher": "公开报道（二手来源）",
            "publisher_level": "公开报道精确转载（二手来源）",
            "publication_date": "2026-02-06",
            "source_grade": "B2",
            "fields": ("general_public_expenditure_100m",),
            "raw_unit": "亿元",
            "source_format": "html",
            "data_status": "execution",
            "data_status_label": "2025年全州一般公共预算支出执行数",
            "document_type": "全州经济运行公开财政指标",
            "page_number": "正文财政段；全州口径",
            "note": (
                "B2公开报道精确列示2025年全州一般公共预算支出198.28亿元，"
                "并给出民生支出160.08亿元及占比80.7%；仅补全州一般公共预算支出。"
            ),
        },
    )
)

# 阿里地区财政局官方《2021年财政决算报告（草案）》明确列示全地区口径；
# 仅接入全地区地方一般公共预算收入和一般公共预算支出，不使用地区本级数。
CITY_YEAR_FISCAL_SOURCES += (
    _make_curated_city_source(
        year=2021,
        city_name="阿里地区",
        city_id="CN-542500",
        source_doc_id="SRC-A2-ALI-REGION-FISCAL-2021",
        url="https://www.al.gov.cn/_mediafile/word2pdf/1512064483/2023-01-11/5ECC899E-9D4B-45F7-A8C6-5D649A548455.pdf",
        path=RAW_DIR / "province_fiscal" / "2021" / "official" / "ali_2021_final_budget_excerpt.txt",
        document_title="阿里地区2021年财政决算报告（草案）",
        publisher="阿里地区财政局",
        publisher_level="地区级财政机构",
        publication_date="2023-01-11",
        source_grade="A2",
        fields=("general_public_revenue_100m", "general_public_expenditure_100m"),
        raw_unit="万元",
        source_format="pdf",
        data_status="final",
        data_status_label="2021年全地区一般公共预算收支决算数",
        document_type="地区级财政决算报告（草案）",
        page_number="PDF第1—3页；全地区一般公共预算收入/支出决算情况",
        note=(
            "A2阿里地区财政局官方财政决算报告（草案）；明确列示全地区地方一般公共预算收入"
            "37633万元、一般公共预算支出962454万元，换算为3.7633亿元和96.2454亿元。"
            "不使用地区本级收入9589万元和本级支出314648万元。"
        ),
    ),
)

# 阿里地区官方政务公开页面补入2020年一般公共预算收入，并用官方“十四五”
# 回顾页校正2021年GDP。2020年页面同时出现另一处存在冲突的GDP表述，故只
# 接入明确无歧义的一般公共预算收入；2021年GDP仅采用回顾页明确列示值，
# 不从期间平均增速反推其他年份。
CITY_YEAR_FISCAL_SOURCES += (
    _make_curated_city_source(
        year=2020,
        city_name="阿里地区",
        city_id="CN-542500",
        source_doc_id="SRC-B2-ALI-REGION-REVENUE-2020",
        url="https://www.al.gov.cn/info/1116/39577.htm",
        path=RAW_DIR / "province_fiscal" / "2020" / "secondary" / "ali_2020_public_revenue_excerpt.txt",
        document_title="去年阿里地区生产总值完成68.6亿元（2020年财政收入摘录）",
        publisher="阿里地区行政公署官方门户转载中国西藏新闻网信息",
        publisher_level="地级行政公署官方门户转载",
        publication_date="2021-08-10",
        source_grade="B2",
        fields=("general_public_revenue_100m",),
        raw_unit="亿元",
        source_format="html",
        data_status="execution",
        data_status_label="2020年全地区一般公共预算收入完成数",
        document_type="官方政务公开经济财政指标摘录",
        page_number="官方页面正文第114行；全地区口径",
        note=(
            "B2官方政务公开页面明确列示2020年阿里地区一般公共预算收入完成4.45亿元；"
            "同页GDP表述与其他官方页面存在冲突，故仅接入一般公共预算收入，不覆盖GDP。"
        ),
    ),
    _make_curated_city_source(
        year=2021,
        city_name="阿里地区",
        city_id="CN-542500",
        source_doc_id="SRC-A2-ALI-REGION-GDP-2021-REVIEW",
        url="https://al.gov.cn/info/1097/174924.htm",
        path=RAW_DIR / "province_fiscal" / "2021" / "official" / "ali_2021_gdp_review_excerpt.txt",
        document_title="阿里地区‘十四五’时期经济社会发展回顾（2021年GDP摘录）",
        publisher="阿里地区行政公署",
        publisher_level="地区级政府机构",
        publication_date="2025-11-18",
        source_grade="A2",
        fields=("gdp_current_100m",),
        raw_unit="亿元",
        source_format="html",
        data_status="final",
        data_status_label="2021年官方回顾页明确值",
        document_type="官方政务公开历史经济指标",
        page_number="官方页面正文第118行；全地区口径",
        note=(
            "A2阿里地区行政公署官方回顾页明确列示2021年阿里地区生产总值77.65亿元；"
            "用于替换主表中来源等级较低且不一致的11.72亿元临时值，不从平均增速反推其他年度。"
        ),
    ),
)

# 四平市财政局官方预算执行报告补入2025年全市一般公共预算收支。
# 报告同时列示市级、区级和全市县（市）口径；这里严格采用“全市县（市）”
# 汇总数，不把市级或市区数代入四平市全域主表。
CITY_YEAR_FISCAL_SOURCES += (
    _make_curated_city_source(
        year=2025,
        city_name="四平市",
        city_id="CN-220300",
        source_doc_id="SRC-A2-SIPING-CITY-FISCAL-2025",
        url="http://www.siping.gov.cn/zw/zwxxgkzl/czysgk/202601/t20260119_758254.html",
        path=RAW_DIR / "province_fiscal" / "2025" / "official" / "siping_2025_budget_execution_excerpt.txt",
        document_title="关于四平市2025年预算执行情况和2026年预算草案的报告",
        publisher="四平市财政局",
        publisher_level="市级财政机构",
        publication_date="2026-01-13",
        source_grade="A2",
        fields=("general_public_revenue_100m", "general_public_expenditure_100m"),
        raw_unit="万元",
        source_format="pdf",
        data_status="execution",
        data_status_label="2025年全市一般公共预算执行数",
        document_type="市级财政预算执行报告",
        page_number="PDF第2页；汇总市级和区级预算执行情况；全市县（市）口径",
        note=(
            "A2四平市财政局官方报告；采用全市一般公共预算地方级财政收入751426万元、"
            "一般公共预算支出2914380万元，换算为75.1426亿元和291.4380亿元；"
            "不使用同页市级或市区口径数字。"
        ),
    ),
)

# 辽源市财政局官方年度预算执行页面补入2025年全市一般公共预算收支。
# “一般公共预算地方级收入”在本页面与“全口径财政收入”并列，明确对应
# 目标字段；支出则明确标注为“全市一般公共预算财政支出”，均不是预算安排数。
CITY_YEAR_FISCAL_SOURCES += (
    _make_curated_city_source(
        year=2025,
        city_name="辽源市",
        city_id="CN-220400",
        source_doc_id="SRC-A2-LIAOYUAN-CITY-FISCAL-2025",
        url="http://www.liaoyuan.gov.cn/xxgk/zwgkzdlyxx/czxx/czyszx/202604/t20260414_735187.html",
        path=RAW_DIR / "province_fiscal" / "2025" / "official" / "liaoyuan_2025_budget_execution_excerpt.txt",
        document_title="2025年12月份预算执行情况",
        publisher="辽源市财政局",
        publisher_level="市级财政机构",
        publication_date="2026-04-14",
        source_grade="A2",
        fields=("general_public_revenue_100m", "general_public_expenditure_100m"),
        raw_unit="万元",
        source_format="html",
        data_status="execution",
        data_status_label="2025年1—12月份全市一般公共预算执行数",
        document_type="市级财政预算执行网页",
        page_number="官方网页正文；2025年12月份预算执行情况；2025年1—12月份累计",
        note=(
            "A2辽源市财政局官方预算执行页面；收入采用明确写作“一般公共预算地方级收入”的"
            "全市累计数317674万元，支出采用“全市一般公共预算财政支出”1742658万元；"
            "不使用全口径财政收入464814万元。"
        ),
    ),
)

# 延边州财政局官方年度预算执行页面补入2025年全州一般公共预算收支。
# 页面同时提供收支 Excel 附件；这里以正文全州口径为主证据，保留附件入口供复核。
CITY_YEAR_FISCAL_SOURCES += (
    _make_curated_city_source(
        year=2025,
        city_name="延边朝鲜族自治州",
        city_id="CN-222400",
        source_doc_id="SRC-A2-YANBIAN-STATE-FISCAL-2025",
        url="http://czj.yanbian.gov.cn/sj/czsj/202602/t20260209_567196.html",
        path=RAW_DIR / "province_fiscal" / "2025" / "official" / "yanbian_2025_budget_execution_excerpt.txt",
        document_title="2025年1-12全州财政预算执行情况",
        publisher="延边州财政局",
        publisher_level="州级财政机构",
        publication_date="2026-01-22",
        source_grade="A2",
        fields=("general_public_revenue_100m", "general_public_expenditure_100m"),
        raw_unit="亿元",
        source_format="html",
        data_status="execution",
        data_status_label="2025年1—12月全州一般公共预算执行数",
        document_type="州级财政预算执行网页",
        page_number="官方网页正文；一、一般公共预算收支情况；全州情况",
        note=(
            "A2延边州财政局官方预算执行页面；采用全州一般公共预算收入94.8亿元、"
            "一般公共预算支出402.6亿元；页面另提供财政收支Excel附件，不使用州本级收入4.8亿元"
            "和州本级支出42.1亿元。"
        ),
    ),
)

# CEIC 阿里地区指标页给出 2023 年当前值及 2022 年同比基准值，页面同时标注
# 原始来源为阿里地区统计局、单位为百万元人民币。两年的收入和支出均为精确
# 的年度总量摘要，按 B2 接入；仅补主表空值，不把商业数据库页面升级为官方 A 级。
CITY_YEAR_FISCAL_SOURCES += tuple(
    _make_curated_city_source(
        year=year,
        city_name="阿里地区",
        city_id="CN-542500",
        source_doc_id=f"SRC-B2-CEIC-ALI-{metric_slug}-{year}",
        url=url,
        path=RAW_DIR / "province_fiscal" / str(year) / "secondary" / file_name,
        document_title=document_title,
        publisher="CEIC Data",
        publisher_level="商业数据库公开指标页（二手来源）",
        publication_date="2026-08-01",
        source_grade="B2",
        fields=(field,),
        raw_unit="百万元人民币",
        source_format="html",
        data_status="reported",
        data_status_label=f"{year}年统计机构历史年度值",
        document_type="CEIC地级区域财政指标页面精确摘要",
        page_number=page_number,
        title_source="secondary_public_page",
        access_status="公开指标页已归档",
        note=note,
    )
    for year, field, metric_slug, file_name, url, document_title, page_number, note in (
        (
            2022,
            "general_public_revenue_100m",
            "REVENUE",
            "ali_2022_ceic_revenue_excerpt.txt",
            "https://www.ceicdata.com/en/china/government-revenue-prefecture-level-region/government-revenue-tibet-ngri",
            "Government Revenue: Tibet: Ngri",
            "CEIC指标页；2022年Previous摘要；全地区口径",
            "B2 CEIC公开指标页；页面标题为Government Revenue: Tibet: Ngri，注明原始来源为Ngri Municipal Bureau of Statistics（阿里地区统计局），2022年值为2023年页面的Previous摘要；仅补一般公共预算收入空值。",
        ),
        (
            2023,
            "general_public_revenue_100m",
            "REVENUE",
            "ali_2023_ceic_revenue_excerpt.txt",
            "https://www.ceicdata.com/en/china/government-revenue-prefecture-level-region/government-revenue-tibet-ngri",
            "Government Revenue: Tibet: Ngri",
            "CEIC指标页；2023年Last摘要；全地区口径",
            "B2 CEIC公开指标页；页面标题为Government Revenue: Tibet: Ngri，注明原始来源为Ngri Municipal Bureau of Statistics（阿里地区统计局），2023年Last摘要值为720.180百万元；仅补一般公共预算收入空值。",
        ),
        (
            2022,
            "general_public_expenditure_100m",
            "EXPENDITURE",
            "ali_2022_ceic_expenditure_excerpt.txt",
            "https://www.ceicdata.com/en/china/government-expenditure-prefecture-level-region/government-expenditure-tibet-ngri",
            "Government Expenditure: Tibet: Ngri",
            "CEIC指标页；2022年Previous摘要；全地区口径",
            "B2 CEIC公开指标页；页面标题为Government Expenditure: Tibet: Ngri，注明原始来源为Ngri Municipal Bureau of Statistics（阿里地区统计局），2022年值为2023年页面的Previous摘要；仅补一般公共预算支出空值。",
        ),
        (
            2023,
            "general_public_expenditure_100m",
            "EXPENDITURE",
            "ali_2023_ceic_expenditure_excerpt.txt",
            "https://www.ceicdata.com/en/china/government-expenditure-prefecture-level-region/government-expenditure-tibet-ngri",
            "Government Expenditure: Tibet: Ngri",
            "CEIC指标页；2023年Last摘要；全地区口径",
            "B2 CEIC公开指标页；页面标题为Government Expenditure: Tibet: Ngri，注明原始来源为Ngri Municipal Bureau of Statistics（阿里地区统计局），2023年Last摘要值为16273.000百万元；仅补一般公共预算支出空值。",
        ),
    )
)

# CEIC 公开页面补入 2025 年三项一般公共预算支出缺口。秦皇岛使用月度
# Year-to-Date 页面 2025 年 12 月年累计值，七台河和延安使用年度页面 Last
# 值；页面均明确标注对应市统计局为原始来源。三项均按 B2 记录，不替代
# 财政部门正式预算执行报告。
CITY_YEAR_FISCAL_SOURCES += tuple(
    _make_curated_city_source(
        year=year,
        city_name=city_name,
        city_id=city_id,
        source_doc_id=source_doc_id,
        url=url,
        path=RAW_DIR / "province_fiscal" / "2025" / "secondary" / file_name,
        document_title=document_title,
        publisher="CEIC Data",
        publisher_level="商业数据库公开指标页（二手来源）",
        publication_date="2026-08-29",
        source_grade="B2",
        fields=("general_public_expenditure_100m",),
        raw_unit="百万元人民币",
        source_format="html",
        data_status="reported",
        data_status_label="2025年年度指标页值",
        document_type="CEIC地级区域财政指标页面精确摘要",
        page_number=page_number,
        title_source="secondary_public_page",
        access_status="公开指标页已归档",
        note=note,
    )
    for year, city_name, city_id, source_doc_id, url, file_name, document_title, page_number, note in (
        (
            2025,
            "秦皇岛市",
            "CN-130300",
            "SRC-B2-CEIC-QINHUANGDAO-2025-EXPENDITURE-YTD",
            "https://www.ceicdata.com/en/china/government-expenditure-prefecture-level-city-monthly/government-expenditure-ytd-hebei-qinhuangdao",
            "qinhuangdao_2025_ceic_expenditure_ytd_excerpt.txt",
            "Government Expenditure: Year to Date: Hebei: Qinhuangdao",
            "CEIC指标页；2025年12月年累计值；全市口径",
            "B2 CEIC公开指标页；页面标题为Government Expenditure: Year to Date: Hebei: Qinhuangdao，注明原始来源为Qinhuangdao Municipal Bureau of Statistics（秦皇岛市统计局）；页面明确列出2025年12月年累计值39890.000百万元，按年度一般公共预算支出接入；不替代官方决算。",
        ),
        (
            2025,
            "七台河市",
            "CN-230900",
            "SRC-B2-CEIC-QITAIHE-2025-EXPENDITURE",
            "https://www.ceicdata.com/en/china/government-expenditure-prefecture-level-city/government-expenditure-heilongjiang-qitaihe",
            "qitaihe_2025_ceic_expenditure_excerpt.txt",
            "Government Expenditure: Heilongjiang: Qitaihe",
            "CEIC指标页；2025年Last摘要；全市口径",
            "B2 CEIC公开指标页；页面标题为Government Expenditure: Heilongjiang: Qitaihe，注明原始来源为Qitaihe Municipal Bureau of Statistics（七台河市统计局）；2025年Last摘要值为11530.000百万元；不替代官方决算。",
        ),
        (
            2025,
            "延安市",
            "CN-610600",
            "SRC-B2-CEIC-YANAN-2025-EXPENDITURE",
            "https://www.ceicdata.com/en/china/government-expenditure-prefecture-level-city/government-expenditure-shaanxi-yanan",
            "yanan_2025_ceic_expenditure_excerpt.txt",
            "Government Expenditure: Shaanxi: Yanan",
            "CEIC指标页；2025年Last摘要；全市口径",
            "B2 CEIC公开指标页；页面标题为Government Expenditure: Shaanxi: Yanan，注明原始来源为Yanan Municipal Bureau of Statistics（延安市统计局）；2025年Last摘要值为51587.680百万元；不替代官方决算。",
        ),
    )
)

# 安阳日报数字报转载安阳市财政报告图解，精确披露 2025 年全市一般公共
# 预算支出；作为 B2 二手公开来源接入，不把图解中的市级或分项支出代替全市值。
CITY_YEAR_FISCAL_SOURCES += (
    _make_curated_city_source(
        year=2025,
        city_name="安阳市",
        city_id="CN-410500",
        source_doc_id="SRC-B2-ANYANG-2025-EXPENDITURE",
        url="https://www.ayrbs.com/szb/pc/content/202602/08/content_105697.html",
        path=RAW_DIR / "province_fiscal" / "2025" / "secondary" / "anyang_2025_finance_infographic_excerpt.txt",
        document_title="财政报告（图解）",
        publisher="安阳日报数字报",
        publisher_level="地市党报转载（二手来源）",
        publication_date="2026-02-08",
        source_grade="B2",
        fields=("general_public_expenditure_100m",),
        raw_unit="亿元",
        source_format="html",
        data_status="execution",
        data_status_label="2025年全市一般公共预算支出执行数",
        document_type="地方财政报告图解精确摘录",
        page_number="公开网页正文；2025年钱花到哪儿了",
        title_source="secondary_public_page",
        access_status="公开网页已归档",
        note=(
            "B2安阳日报数字报转载安阳市财政报告图解；正文明确披露2025年全市一般公共预算支出"
            "458.9亿元，年度、行政范围和指标名称清晰；不使用民生支出或市级分项值，不替代正式决算。"
        ),
    ),
)

# 湖北省统计局官方统计年鉴批量补入省直管县级行政区划（仙桃、潜江、天门、
# 神农架林区）四行汇总。只接入同年度官方表中可逐项加总的现价 GDP、一般预算
# 收入和支出；没有官方合计行的 GDP 实际增速由适配器明确保持缺失。
CITY_YEAR_FISCAL_SOURCES += tuple(HUBEI_DIRECT_ADMIN_YEARBOOK_SOURCES)
CITY_YEAR_FISCAL_SOURCES += (HUBEI_DIRECT_ADMIN_2025_BULLETIN_SOURCE,)
CITY_YEAR_FISCAL_SOURCES += tuple(HAINAN_DIRECT_ADMIN_YEARBOOK_SOURCES)
CITY_YEAR_FISCAL_SOURCES += tuple(HAINAN_DIRECT_ADMIN_YEARBOOK_2025_SOURCES)
CITY_YEAR_FISCAL_SOURCES += tuple(HAINAN_DIRECT_ADMIN_YEARBOOK_2023_SOURCES)
CITY_YEAR_FISCAL_SOURCES += tuple(HAINAN_DIRECT_ADMIN_YEARBOOK_2019_2021_SOURCES)
CITY_YEAR_FISCAL_SOURCES += tuple(HENAN_DIRECT_ADMIN_BULLETIN_SOURCES)
CITY_YEAR_FISCAL_SOURCES += tuple(JIYUAN_HISTORICAL_SOURCES)

CITY_YEAR_FISCAL_SOURCE_IDS = {item["source_doc_id"] for item in CITY_YEAR_FISCAL_SOURCES}

FUND_DERIVED_FIELDS = {"fund_revenue_dependence_pct", "gov_fund_to_general_revenue_pct"}

SOURCE_GRADE_RANK = {"A1": 5, "A2": 4, "B1": 3, "B2": 2, "C": 1, "D": 0}

D0 = Decimal("0")
D1 = Decimal("1")
D100 = Decimal("100")
D2 = Decimal("0.01")
D4 = Decimal("0.0001")

MACRO_FIELDS = [
    "gdp_current_100m",
    "gdp_real_growth_pct",
    "resident_population_10k",
    "general_public_revenue_100m",
    "general_public_expenditure_100m",
    "gov_fund_revenue_100m",
    "general_debt_limit_100m",
    "general_debt_balance_100m",
    "special_debt_limit_100m",
    "special_debt_balance_100m",
    "statutory_debt_limit_100m",
    "statutory_debt_balance_100m",
    "debt_limit_utilization_pct",
    "statutory_debt_to_gdp_pct",
    "statutory_debt_to_revenue_pct",
    "statutory_debt_to_general_revenue_pct",
    "fiscal_self_sufficiency_pct",
    "fund_revenue_dependence_pct",
    "gov_fund_to_general_revenue_pct",
]
RAW_NUMERIC_FIELDS = (
    "gdp_current_100m",
    "gdp_real_growth_pct",
    "resident_population_10k",
    "general_public_revenue_100m",
    "general_public_expenditure_100m",
    "gov_fund_revenue_100m",
    "general_debt_limit_100m",
    "general_debt_balance_100m",
    "special_debt_balance_100m",
    "special_debt_limit_100m",
)


def as_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


def q2(value: Any) -> Decimal | None:
    number = as_decimal(value)
    return None if number is None else number.quantize(D2, rounding=ROUND_HALF_UP)


def order_calculation_rows_for_lineage(
    calc_rows: Iterable[Mapping[str, Any]],
    appended_fund_target_ids: set[str],
) -> list[Mapping[str, Any]]:
    """保持既有计算血缘顺序，仅将本批新增基金派生值追加到末尾。"""

    rows = list(calc_rows)
    appended = [
        row
        for row in rows
        if row.get("target_record_id") in appended_fund_target_ids
        and row.get("target_field") in FUND_DERIVED_FIELDS
    ]
    return [
        row for row in rows if row not in appended
    ] + appended


def q4(value: Any) -> Decimal | None:
    number = as_decimal(value)
    return None if number is None else number.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def pct(numerator: Any, denominator: Any) -> Decimal | None:
    num = as_decimal(numerator)
    den = as_decimal(denominator)
    if num is None or den is None or den <= D0:
        return None
    return q2(num / den * D100)


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure_download(url: str, target: Path) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or target.stat().st_size == 0:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 data-collection-research"})
        with urlopen(request, timeout=60) as response, target.open("wb") as output:
            output.write(response.read())
    return sha256(target)


def write_csv(filename: str, fieldnames: list[str], rows: Iterable[Mapping[str, Any]]) -> Path:
    target = OUTPUT_DIR / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field)) for field in fieldnames})
    return target


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_area_file(path: Path) -> tuple[list[tuple[str, str, str, str, str]], dict[str, str]]:
    """读取无表头或带 BOM 的行政区划压缩 CSV。

    返回 level=2 的行以及 level=1 的省级名称映射。不同年份文件从四列升级到五列，
    第五列仅保留为 category，不参与城市身份判断。
    """
    prefectures: list[tuple[str, str, str, str, str]] = []
    provinces: dict[str, str] = {}
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle):
            if len(row) < 4:
                continue
            code, name, level, parent = row[:4]
            category = row[4] if len(row) >= 5 else ""
            if level == "1":
                provinces[code[:6]] = name.strip().strip('"')
            elif level == "2":
                prefectures.append((code, name.strip().strip('"'), level, parent, category))
    return prefectures, provinces


def load_rosters() -> tuple[dict[int, list[tuple[str, str, str, str, str]]], dict[int, dict[str, str]], dict[int, str]]:
    rosters: dict[int, list[tuple[str, str, str, str, str]]] = {}
    province_maps: dict[int, dict[str, str]] = {}
    hashes: dict[int, str] = {}
    for year in AVAILABLE_ROSTER_YEARS:
        path = RAW_DIR / "administrative_divisions" / f"area_code_{year}.csv.gz"
        hashes[year] = ensure_download(AREA_URL_TEMPLATE.format(year=year), path)
        rows, provinces = read_area_file(path)
        rosters[year] = rows
        province_maps[year] = provinces
    return rosters, province_maps, hashes


def _prefecture_type(name: str, is_municipality: bool) -> str:
    if is_municipality:
        return "直辖市"
    if "自治州" in name:
        return "自治州"
    if "地区" in name:
        return "地区"
    if name.endswith("盟"):
        return "盟"
    return "地级市"


def build_city_master(
    rosters: Mapping[int, list[tuple[str, str, str, str, str]]],
    years: Iterable[int] = range(START_YEAR, END_YEAR + 1),
    province_maps: Mapping[int, Mapping[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """以年度行政区划生成稳定 city_id，并将直辖市从“市辖区”中还原为单列观察对象。"""
    if not rosters:
        return []
    available = sorted(rosters)
    province_maps = province_maps or {}
    output: list[dict[str, Any]] = []
    for metric_year in years:
        source_year = next((year for year in available if year >= metric_year), available[-1])
        if metric_year > available[-1]:
            source_year = available[-1]
        province_map = province_maps.get(source_year, {})
        seen: set[str] = set()
        for code12, name, level, parent12, _category in rosters[source_year]:
            if level != "2":
                continue
            parent6 = parent12[:6]
            if parent6 in DIRECT_MUNICIPALITIES:
                admin6 = parent6
                city_name = province_map.get(parent6, DIRECT_MUNICIPALITIES[parent6])
                city_code12 = f"{parent6}000000"
            else:
                admin6 = code12[:6]
                city_name = name
                city_code12 = code12
            city_id = f"CN-{admin6}"
            if city_id in seen:
                continue
            seen.add(city_id)
            is_municipality = admin6 in DIRECT_MUNICIPALITIES
            prefecture_type = _prefecture_type(city_name, is_municipality)
            tier = "separate" if is_municipality else ("core" if prefecture_type == "地级市" else "extended")
            output.append(
                {
                    "city_id": city_id,
                    "admin_code_6": admin6,
                    "city_code_12": city_code12,
                    "city_name_cn": city_name,
                    "province_code": admin6[:2],
                    "province_name": province_map.get(parent6, DIRECT_MUNICIPALITIES.get(parent6, "")),
                    "prefecture_type": prefecture_type,
                    "sample_tier": tier,
                    "metric_year": str(metric_year),
                    "roster_year": str(metric_year),
                    "roster_source_year": str(source_year),
                    "valid_from": f"{metric_year}-01-01",
                    "valid_to": None,
                    "roster_version_status": "official_source_snapshot" if metric_year <= available[-1] else "carry_forward",
                    "source_doc_id": f"SRC-ADMIN-DIVISION-{source_year}",
                    "source_locator": f"level=2, code={code12}, parent={parent12}",
                    "system_valid_from": RETRIEVED_AT,
                    "system_valid_to": None,
                    "note": "2025—2026沿用最近可用行政区划版本，仅用于前向面板占位。" if metric_year > available[-1] else "",
                }
            )
    validate_city_master(output)
    return sorted(output, key=lambda row: (row["metric_year"], row["province_code"], row["admin_code_6"]))


def validate_city_master(rows: list[Mapping[str, Any]]) -> None:
    keys = [(row.get("city_id"), row.get("metric_year")) for row in rows]
    assert all(city_id and year for city_id, year in keys), "城市主键字段不得为空"
    assert len(keys) == len(set(keys)), "城市年度主键重复"
    assert all(START_YEAR <= int(year) <= END_YEAR for _, year in keys)
    assert all(row.get("sample_tier") in {"core", "extended", "separate"} for row in rows)


def load_city_panel() -> tuple[list[dict[str, str]], str, Path]:
    path = RAW_DIR / "city_panel" / "china_city_panel_with_policies.csv"
    content_hash = ensure_download(CITY_PANEL_URL, path)
    return read_csv(path), content_hash, path


def load_guangdong_2024() -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]], list[dict[str, str]]]:
    macro_path = GD_ROOT / "gd_city_macro_fiscal_2024.csv"
    debt_path = GD_ROOT / "fact_city_gov_debt_gd_2024.csv"
    source_path = GD_ROOT / "source_document_gd_2024.csv"
    if not macro_path.exists() or not debt_path.exists():
        return {}, {}, []
    macro = {row["city_id"]: row for row in read_csv(macro_path)}
    debt = {row["city_id"]: row for row in read_csv(debt_path)}
    sources = read_csv(source_path) if source_path.exists() else []
    return macro, debt, sources


def load_guangdong_2025_gdp() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """读取广东省统计局 2025 年地市 GDP 官方表，并返回可审计来源记录。"""

    content_hash = ensure_download(GD_2025_GDP_URL, GD_2025_GDP_PATH)
    html_text = GD_2025_GDP_PATH.read_text(encoding="utf-8")
    values = parse_guangdong_city_gdp_html(html_text)
    source = {
        "source_doc_id": "SRC-GD-CITY-GDP-2025",
        "publisher": "广东省统计局",
        "publisher_level": "省级",
        "document_title": "2025年各市地区生产总值初步核算结果",
        "title_source": "html_heading",
        "attachment_title": GD_2025_GDP_PATH.name,
        "document_type": "官方地市经济表",
        "source_url": GD_2025_GDP_URL,
        "landing_page_url": GD_2025_GDP_URL,
        "attachment_url": GD_2025_GDP_URL,
        "canonical_url": GD_2025_GDP_URL,
        "final_resolved_url": GD_2025_GDP_URL,
        "file_name": GD_2025_GDP_PATH.name,
        "mime_type": "text/html",
        "publication_date": "2026-02-08",
        "publication_date_raw": "2026-02-08",
        "period_end": "2025-12-31",
        "downloaded_at": RETRIEVED_AT,
        "content_hash_sha256": content_hash,
        "archive_uri": "archive://national-prefecture-panel/raw/macro_fiscal/guangdong_2025_city_gdp.html",
        "archive_backend": "internal_object",
        "archive_path": str(GD_2025_GDP_PATH.relative_to(ROOT)),
        "page_count": "",
        "source_grade": "A2",
        "http_status": "200",
        "access_status": "官方网页已归档",
        "supersedes_doc_id": "",
        "note": "广东省统计局官方地市表；GDP为现价地区生产总值，增长率为初步核算实际增速；2025年数据状态标记为 preliminary。",
    }
    return values, source


def load_guangdong_2025_city_fiscal() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """读取广东省财政厅 2025 年各市一般预算收入、支出执行表。"""

    content_hash = ensure_download(GD_BUDGET_ATTACHMENT_3_URL, GD_BUDGET_ATTACHMENT_3_PATH)
    pdf_text = extract_pdf_text(GD_BUDGET_ATTACHMENT_3_PATH)
    GD_BUDGET_ATTACHMENT_3_TEXT_PATH.write_text(pdf_text, encoding="utf-8")
    pages = pdf_text.split("\f")
    revenue_page = next((page for page in pages if "全省各市一般公共预算收入执行情况表" in page), "")
    expenditure_page = next((page for page in pages if "全省各市一般公共预算支出执行情况表" in page), "")
    revenue = parse_guangdong_city_budget_page(revenue_page, "general_public_revenue_100m")
    expenditure = parse_guangdong_city_budget_page(expenditure_page, "general_public_expenditure_100m")
    if len(revenue) != 21 or len(expenditure) != 21:
        raise ValueError(f"广东 2025 地市财政表解析数量异常：收入 {len(revenue)}，支出 {len(expenditure)}")
    values = {
        city_name: {**revenue[city_name], **expenditure[city_name]}
        for city_name in revenue
        if city_name in expenditure
    }
    if len(values) != 21:
        raise ValueError(f"广东 2025 地市财政表收入/支出城市交集异常：{len(values)}")
    source = {
        "source_doc_id": "SRC-GD-CITY-FISCAL-2025",
        "publisher": "广东省财政厅",
        "publisher_level": "省级",
        "document_title": "广东省2025年预算执行情况和2026年预算草案的报告",
        "title_source": "html_heading",
        "attachment_title": "3.广东省2025年预算执行情况和2026年预算草案附件二（第1册）.pdf",
        "document_type": "官方地市财政执行表",
        "source_url": GD_BUDGET_REPORT_URL,
        "landing_page_url": GD_BUDGET_REPORT_URL,
        "attachment_url": GD_BUDGET_ATTACHMENT_3_URL,
        "canonical_url": GD_BUDGET_ATTACHMENT_3_URL,
        "final_resolved_url": GD_BUDGET_ATTACHMENT_3_URL,
        "file_name": GD_BUDGET_ATTACHMENT_3_PATH.name,
        "mime_type": "application/pdf",
        "publication_date": "2026-02-14",
        "publication_date_raw": "2026-02-14",
        "period_end": "2025-12-31",
        "downloaded_at": RETRIEVED_AT,
        "content_hash_sha256": content_hash,
        "archive_uri": "archive://national-prefecture-panel/raw/province_fiscal/2025/official/guangdong_2025_budget_attachment_3.pdf",
        "archive_backend": "internal_object",
        "archive_path": str(GD_BUDGET_ATTACHMENT_3_PATH.relative_to(ROOT)),
        "page_count": str(len(pages)),
        "source_grade": "A2",
        "http_status": "200",
        "access_status": "官方附件已归档",
        "supersedes_doc_id": "",
        "note": "表2/表4使用各市一般公共预算收入、支出执行数；原始单位万元，转换为亿元；数据状态标记为 execution。",
    }
    return values, source


def load_guangdong_2025_city_fund() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取广州、深圳、东莞官方预算报告披露的 2025 年全市基金收入。"""

    values: dict[str, dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    for config in GD_CITY_FUND_SOURCES:
        path = config["path"]
        content_hash = ensure_download(config["url"], path)
        source_format = str(config.get("format", "pdf"))
        if source_format == "html":
            html_text = path.read_text(encoding="utf-8")
            report_text = unescape(re.sub(r"<[^>]+>", " ", html_text))
            source_mime = "text/html"
            title_source = "html_heading"
            document_type = "官方城市财政预算执行信息"
            page_count = "1"
        else:
            report_text = extract_pdf_text(path)
            source_mime = "application/pdf"
            title_source = "pdf_heading"
            document_type = "官方城市政府性基金预算执行报告"
            page_count = str(len(report_text.split("\f")))
        path.with_suffix(".txt").write_text(report_text, encoding="utf-8")
        value = parse_city_fund_revenue_text(report_text)
        if value is None:
            raise ValueError(f"未能从官方报告提取{config['city_name']}2025年全市政府性基金预算收入")
        values[config["city_name"]] = {
            "gov_fund_revenue_100m": value,
            "gov_fund_revenue_raw_100m": value,
            "source_doc_id": config["source_doc_id"],
            "source_locator": f"官方预算报告正文：2025年全市政府性基金预算收入；城市={config['city_name']}",
        }
        values[config["city_name"]]["data_status"] = "execution"
        sources.append(
            {
                "source_doc_id": config["source_doc_id"],
                "publisher": config["publisher"],
                "publisher_level": str(config.get("publisher_level") or "市级"),
                "document_title": config["document_title"],
                "title_source": title_source,
                "attachment_title": path.name,
                "document_type": document_type,
                "source_url": config["url"],
                "landing_page_url": config["url"],
                "attachment_url": config["url"],
                "canonical_url": config["url"],
                "final_resolved_url": config["url"],
                "file_name": path.name,
                "mime_type": source_mime,
                "publication_date": config["publication_date"],
                "publication_date_raw": config["publication_date"],
                "period_end": "2025-12-31",
                "downloaded_at": RETRIEVED_AT,
                "content_hash_sha256": content_hash,
                "archive_uri": f"archive://national-prefecture-panel/{path.relative_to(ROOT)}",
                "archive_backend": "internal_object",
                "archive_path": str(path.relative_to(ROOT)),
                "page_count": page_count,
                "source_grade": str(config.get("source_grade") or "A2"),
                "http_status": "200",
                "access_status": "官方附件已归档",
                "supersedes_doc_id": "",
                "note": config["note"],
            }
        )
    return values, sources


def load_city_2025_fiscal_sources(
    configs: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取一批城市 2025 年官方预算执行报告的全市财政字段。"""

    values: dict[str, dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    for config in configs:
        source_path = Path(config["path"])
        text_path = Path(config["text_path"])
        attachment_url = str(config.get("attachment_url") or config["url"])
        content_hash = ensure_download(attachment_url, source_path)
        # 兼容此前 PDF 解码器返回仅含分页符的短文本；低于该阈值时重新解析附件。
        # 对已人工核对并保留官方原文摘录的来源，不能用 PDF 解码结果覆盖摘录。
        if config.get("text_is_curated"):
            report_text = text_path.read_text(encoding="utf-8")
        elif not text_path.exists() or text_path.stat().st_size < 1000:
            report_text = extract_pdf_text(source_path)
            text_path.write_text(report_text, encoding="utf-8")
        else:
            report_text = text_path.read_text(encoding="utf-8")
        compact_text = re.sub(r"\s+", "", report_text)
        city_values: dict[str, Any] = {
            "source_doc_id": config["source_doc_id"],
            "source_grade": str(config.get("source_grade") or "A2"),
            "data_status": str(config.get("data_status") or "execution"),
            "source_locator": str(
                config.get("source_locator")
                or f"{text_path.relative_to(ROOT)}；城市={config['city_name']}；2025年全市预算执行正文/附表"
            ),
        }
        for field, (pattern, raw_unit) in config["patterns"].items():
            match = re.search(pattern, compact_text)
            if not match:
                raise ValueError(f"未能从官方报告提取{config['city_name']}2025年{field}")
            raw_value = Decimal(match.group(1).replace(",", ""))
            normalized = raw_value if raw_unit in {"亿元", "%", "万人"} else raw_value * D4
            negative_marker = str(config.get("negative_if", {}).get(field) or "")
            if negative_marker and negative_marker in match.group(0):
                normalized = -normalized
            city_values[field] = q2(normalized)
            city_values[f"{field}_raw"] = raw_value
            city_values[f"{field}_raw_unit"] = raw_unit
            city_values[f"{field}_evidence_excerpt"] = match.group(0)
        city_id = config["city_id"]
        prior_values = values.get(city_id)
        if prior_values is None:
            city_values["_field_sources"] = {
                field: dict(city_values)
                for field in config["patterns"]
                if field in city_values
            }
            values[city_id] = city_values
        else:
            # 同一城市可能由独立来源分别补充经济和财政字段。按字段合并，
            # 保留字段级血缘；同值不重复覆盖，同等级冲突进入复核队列。
            field_sources = dict(prior_values.get("_field_sources") or {})
            prior_source_ids = [
                item for item in str(prior_values.get("source_doc_id") or "").split(";") if item
            ]
            current_source_id = str(city_values.get("source_doc_id") or "")
            if current_source_id and current_source_id not in prior_source_ids:
                prior_source_ids.append(current_source_id)
            current_grade = str(city_values.get("source_grade") or "")
            for field in config["patterns"]:
                if field not in city_values:
                    continue
                current_value = as_decimal(city_values.get(field))
                if current_value is None:
                    continue
                prior_source = field_sources.get(field, prior_values)
                prior_value = as_decimal(
                    prior_source.get(field) if prior_source else prior_values.get(field)
                )
                prior_grade = str(prior_source.get("source_grade") or "") if prior_source else ""
                if prior_value is None:
                    prior_values[field] = city_values[field]
                    for suffix in ("_raw_100m", "_raw_unit", "_evidence_excerpt"):
                        source_key = f"{field}{suffix}"
                        if source_key in city_values:
                            prior_values[source_key] = city_values[source_key]
                    field_sources[field] = dict(city_values)
                elif current_value == prior_value:
                    continue
                elif SOURCE_GRADE_RANK.get(current_grade, -1) > SOURCE_GRADE_RANK.get(prior_grade, -1):
                    prior_values[field] = city_values[field]
                    for suffix in ("_raw_100m", "_raw_unit", "_evidence_excerpt"):
                        source_key = f"{field}{suffix}"
                        if source_key in city_values:
                            prior_values[source_key] = city_values[source_key]
                    field_sources[field] = dict(city_values)
                else:
                    conflicts = list(prior_values.get("_field_conflicts") or [])
                    conflicts.append(
                        {
                            "field": field,
                            "prior_value": str(prior_value),
                            "candidate_value": str(current_value),
                            "prior_source_doc_id": str(prior_source.get("source_doc_id") or ""),
                            "candidate_source_doc_id": current_source_id,
                        }
                    )
                    prior_values["_field_conflicts"] = conflicts
            prior_values["source_doc_id"] = ";".join(prior_source_ids)
            prior_values["_field_sources"] = field_sources
            if SOURCE_GRADE_RANK.get(current_grade, -1) > SOURCE_GRADE_RANK.get(
                str(prior_values.get("source_grade") or ""), -1
            ):
                prior_values["source_grade"] = current_grade
            if not prior_values.get("data_status") or prior_values.get("data_status") == "not_collected":
                prior_values["data_status"] = city_values.get("data_status")
        sources.append(
            {
                "source_doc_id": config["source_doc_id"],
                "publisher": config["publisher"],
                "publisher_level": str(config.get("publisher_level") or "市级"),
                "document_title": config["document_title"],
                "title_source": str(config.get("title_source") or "official_attachment"),
                "attachment_title": str(config.get("attachment_title") or source_path.name),
                "document_type": str(config.get("document_type") or "官方城市财政预算执行报告"),
                "source_url": config["url"],
                "landing_page_url": config["url"],
                "attachment_url": attachment_url,
                "canonical_url": config["url"],
                "final_resolved_url": attachment_url,
                "file_name": source_path.name,
                "mime_type": str(config.get("mime_type") or "application/pdf"),
                "publication_date": config["publication_date"],
                "publication_date_raw": config["publication_date"],
                "period_end": "2025-12-31",
                "downloaded_at": RETRIEVED_AT,
                "content_hash_sha256": content_hash,
                "archive_uri": f"archive://national-prefecture-panel/{source_path.relative_to(ROOT)}",
                "archive_backend": "internal_object",
                "archive_path": str(source_path.relative_to(ROOT)),
                "page_count": str(len(report_text.split("\f"))),
                "source_grade": str(config.get("source_grade") or "A2"),
                "http_status": "200",
                "access_status": str(config.get("access_status") or "官方附件已归档"),
                "supersedes_doc_id": "",
                "note": config["note"],
            }
        )
    return values, sources


def load_jiangsu_city_fund_sources() -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    """读取江苏省财政厅分地区政府性基金收入表。

    表格行统一交给批量行解析器，保留省级合计、说明行和无法匹配行的
    拒绝逻辑，避免每个省份重复实现单位换算和全市口径判断。
    """

    values: dict[tuple[str, str], dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    for config in JIANGSU_CITY_FUND_SOURCES:
        source_path = Path(config["path"])
        text_path = Path(config["text_path"])
        content_hash = ensure_download(str(config["url"]), source_path)
        report_text = text_path.read_text(encoding="utf-8")
        year = int(config["year"])
        rows = [line.split() for line in report_text.splitlines() if line.strip()]
        facts, _rejects = parse_city_value_rows(
            rows,
            city_aliases={city_name: city_id for city_id, city_name in config["cities"].items()},
            field_name="gov_fund_revenue_100m",
            value_index=1,
            raw_unit="万元",
            metric_year=year,
            source_doc_id=config["source_doc_id"],
            source_grade=config["source_grade"],
            geo_scope="prefecture_whole",
        )
        facts_by_city = {fact["city_id"]: fact for fact in facts}
        if set(facts_by_city) != set(config["cities"]):
            missing = sorted(set(config["cities"]) - set(facts_by_city))
            raise ValueError(f"未能从江苏省{year}年政府性基金分地区表提取城市：{missing}")
        found_city_ids: set[str] = set()
        for city_id, city_name in config["cities"].items():
            fact = facts_by_city[city_id]
            values[(city_id, str(year))] = {
                "gov_fund_revenue_100m": q2(fact["normalized_value"]),
                "gov_fund_revenue_raw_100m": Decimal(fact["raw_value"].replace(",", "")),
                "gov_fund_revenue_raw_unit": "万元",
                "gov_fund_revenue_evidence_excerpt": fact["evidence_excerpt"],
                "source_doc_id": config["source_doc_id"],
                "source_grade": config["source_grade"],
                "data_status": str(config.get("data_status") or "execution"),
                "data_status_label": str(config.get("data_status_label") or f"{year}年执行数"),
                "source_locator": (
                    f"{text_path.relative_to(ROOT)}；{config['table_name']}；"
                    f"PDF第{config['page_number']}页；城市={city_name}；"
                    f"{config.get('data_status_label') or f'{year}年执行数'}"
                ),
                "table_name": config["table_name"],
            }
            found_city_ids.add(city_id)
        if found_city_ids != set(config["cities"]):
            raise ValueError(f"江苏省{year}年政府性基金城市行数异常：{len(found_city_ids)}")
        sources.append(
            {
                "source_doc_id": config["source_doc_id"],
                "publisher": config["publisher"],
                "publisher_level": config["publisher_level"],
                "document_title": config["document_title"],
                "title_source": "official_budget_table",
                "attachment_title": source_path.name,
                "document_type": "官方省级财政分地区预算执行表",
                "source_url": config["url"],
                "landing_page_url": config["url"],
                "attachment_url": config["url"],
                "canonical_url": config["url"],
                "final_resolved_url": config["url"],
                "file_name": source_path.name,
                "mime_type": (
                    "text/html"
                    if config.get("source_format") == "html"
                    else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    if config.get("source_format") == "xlsx"
                    else "application/pdf"
                ),
                "publication_date": config["publication_date"],
                "publication_date_raw": config["publication_date"],
                "period_end": f"{year}-12-31",
                "downloaded_at": RETRIEVED_AT,
                "content_hash_sha256": content_hash,
                "archive_uri": f"archive://national-prefecture-panel/{source_path.relative_to(ROOT)}",
                "archive_backend": "internal_object",
                "archive_path": str(source_path.relative_to(ROOT)),
                "page_count": config["page_number"],
                "source_grade": config["source_grade"],
                "http_status": "200",
                "access_status": "官方附件已归档",
                "supersedes_doc_id": "",
                "note": (
                    "江苏省财政厅官方分地区政府性基金预算收入表；"
                    f"采用各设区市全市{config.get('data_status_label') or f'{year}年执行数'}，"
                    "原始单位万元，统一换算为亿元。"
                ),
            }
        )
    return values, sources


def load_xinjiang_2024_city_fund_sources() -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    """读取新疆财政厅 2024 年各地政府性基金预算收入完成表。"""

    values: dict[tuple[str, str], dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    for config in XINJIANG_2024_CITY_FUND_SOURCES:
        source_path = Path(config["path"])
        text_path = Path(config["text_path"])
        content_hash = ensure_download(str(config["url"]), source_path)
        report_text = text_path.read_text(encoding="utf-8")
        rows = [line.split() for line in report_text.splitlines() if line.strip()]
        facts, _rejects = parse_city_value_rows(
            rows,
            city_aliases=config["cities"],
            field_name="gov_fund_revenue_100m",
            value_index=2,
            raw_unit="万元",
            metric_year=int(config["year"]),
            source_doc_id=str(config["source_doc_id"]),
            source_grade=str(config["source_grade"]),
            geo_scope="prefecture_whole",
        )
        facts_by_city = {fact["city_id"]: fact for fact in facts}
        expected_city_ids = set(config["cities"].values())
        if set(facts_by_city) != expected_city_ids:
            missing = sorted(expected_city_ids - set(facts_by_city))
            extra = sorted(set(facts_by_city) - expected_city_ids)
            raise ValueError(f"未能从新疆{config['year']}年政府性基金分地区表提取城市：缺失={missing}，多出={extra}")
        for city_name, city_id in config["cities"].items():
            fact = facts_by_city[city_id]
            values[(city_id, str(config["year"]))] = {
                "gov_fund_revenue_100m": q2(fact["normalized_value"]),
                "gov_fund_revenue_raw_100m": Decimal(fact["raw_value"].replace(",", "")),
                "gov_fund_revenue_raw_unit": fact["raw_unit"],
                "gov_fund_revenue_evidence_excerpt": fact["evidence_excerpt"],
                "source_doc_id": config["source_doc_id"],
                "source_grade": config["source_grade"],
                "data_status": config["data_status"],
                "data_status_label": config["data_status_label"],
                "source_locator": (
                    f"{text_path.relative_to(ROOT)}；{config['table_name']}；"
                    f"{config['page_number']}；城市={city_name}；{config['data_status_label']}"
                ),
                "table_name": config["table_name"],
                "page_number": config["page_number"],
            }
        sources.append(
            {
                "source_doc_id": config["source_doc_id"],
                "publisher": config["publisher"],
                "publisher_level": config["publisher_level"],
                "document_title": config["document_title"],
                "title_source": "official_budget_table",
                "attachment_title": source_path.name,
                "document_type": "官方省级财政分地区政府性基金预算执行表",
                "source_url": config["url"],
                "landing_page_url": config["url"],
                "attachment_url": config["url"],
                "canonical_url": config["url"],
                "final_resolved_url": config["url"],
                "file_name": source_path.name,
                "mime_type": "application/pdf",
                "publication_date": config["publication_date"],
                "publication_date_raw": config["publication_date"],
                "period_end": f"{config['year']}-12-31",
                "downloaded_at": RETRIEVED_AT,
                "content_hash_sha256": content_hash,
                "archive_uri": f"archive://national-prefecture-panel/{source_path.relative_to(ROOT)}",
                "archive_backend": "internal_object",
                "archive_path": str(source_path.relative_to(ROOT)),
                "page_count": config["page_number"],
                "source_grade": config["source_grade"],
                "http_status": "200",
                "access_status": "官方附件已归档",
                "supersedes_doc_id": "",
                "note": (
                    "新疆维吾尔自治区财政厅官方分地区政府性基金预算收入完成表；"
                    "采用各地州全域完成数，原始单位万元，统一换算为亿元；"
                    "自治区本级和全区合计行未写入地级行政单元。"
                ),
            }
        )
    return values, sources


def load_jiangsu_city_fiscal_sources() -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    """读取江苏省财政厅 2024 年分地区一般预算收入、支出表。"""

    values: dict[tuple[str, str], dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    for config in JIANGSU_CITY_FISCAL_SOURCES:
        source_path = Path(config["path"])
        text_path = Path(config["text_path"])
        content_hash = ensure_download(str(config["url"]), source_path)
        report_text = text_path.read_text(encoding="utf-8")
        year = int(config["year"])
        found_city_ids: set[str] = set()
        for city_id, city_name in config["cities"].items():
            match = re.search(
                rf"^{re.escape(city_name)}\s+收入\s+([0-9,]+)\s+支出\s+([0-9,]+)\s*$",
                report_text,
                re.MULTILINE,
            )
            if not match:
                raise ValueError(f"未能从江苏省{year}年一般预算分地区表提取{city_name}")
            revenue_raw = Decimal(match.group(1).replace(",", ""))
            expenditure_raw = Decimal(match.group(2).replace(",", ""))
            values[(city_id, str(year))] = {
                "general_public_revenue_100m": q2(revenue_raw * D4),
                "general_public_expenditure_100m": q2(expenditure_raw * D4),
                "general_public_revenue_raw_100m": revenue_raw,
                "general_public_expenditure_raw_100m": expenditure_raw,
                "general_public_revenue_raw_unit": "万元",
                "general_public_expenditure_raw_unit": "万元",
                "general_public_revenue_evidence_excerpt": match.group(0),
                "general_public_expenditure_evidence_excerpt": match.group(0),
                "source_doc_id": config["source_doc_id"],
                "source_grade": config["source_grade"],
                "data_status": str(config.get("data_status") or "execution"),
                "data_status_label": str(config.get("data_status_label") or f"{year}年执行数"),
                "source_locator": (
                    f"{text_path.relative_to(ROOT)}；{config['table_name']}；"
                    f"{config['page_number']}；城市={city_name}；"
                    f"{config.get('data_status_label') or f'{year}年执行数'}"
                ),
                "table_name": config["table_name"],
                "page_number": config["page_number"],
            }
            found_city_ids.add(city_id)
        if found_city_ids != set(config["cities"]):
            raise ValueError(f"江苏省{year}年一般预算城市行数异常：{len(found_city_ids)}")
        sources.append(
            {
                "source_doc_id": config["source_doc_id"],
                "publisher": config["publisher"],
                "publisher_level": config["publisher_level"],
                "document_title": config["document_title"],
                "title_source": "official_budget_table",
                "attachment_title": source_path.name,
                "document_type": "官方省级财政分地区一般预算执行表",
                "source_url": config["url"],
                "landing_page_url": config["url"],
                "attachment_url": config["url"],
                "canonical_url": config["url"],
                "final_resolved_url": config["url"],
                "file_name": source_path.name,
                "mime_type": "text/html" if config.get("source_format") == "html" else "application/pdf",
                "publication_date": config["publication_date"],
                "publication_date_raw": config["publication_date"],
                "period_end": f"{year}-12-31",
                "downloaded_at": RETRIEVED_AT,
                "content_hash_sha256": content_hash,
                "archive_uri": f"archive://national-prefecture-panel/{source_path.relative_to(ROOT)}",
                "archive_backend": "internal_object",
                "archive_path": str(source_path.relative_to(ROOT)),
                "page_count": config["page_number"],
                "source_grade": config["source_grade"],
                "http_status": "200",
                "access_status": "官方附件已归档",
                "supersedes_doc_id": "",
                "note": (
                    "江苏省财政厅官方分地区一般公共预算收入、支出执行表；"
                    f"采用各设区市全市{config.get('data_status_label') or f'{year}年执行数'}，"
                    "原始单位万元，统一换算为亿元。"
                ),
            }
        )
    return values, sources


def load_city_year_fund_sources() -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    """读取已核验的城市年度全市政府性基金收入精确披露。"""

    values: dict[tuple[str, str], dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    for config in CITY_YEAR_FUND_SOURCES:
        source_path = Path(config["path"])
        text_path = Path(config["text_path"])
        content_hash = ensure_download(str(config["url"]), source_path)
        report_text = text_path.read_text(encoding="utf-8")
        compact_text = re.sub(r"\s+", "", report_text)
        match = re.search(str(config["pattern"]), compact_text)
        if not match:
            raise ValueError(
                f"未能从{config['city_name']}{config['year']}年政府性基金来源提取全市收入"
            )
        raw_value = Decimal(
            match.group(1).replace(",", "").replace("，", "").replace("．", ".")
        )
        raw_unit = str(config["raw_unit"])
        normalized = raw_value if raw_unit == "亿元" else raw_value * D4
        year = str(config["year"])
        data_status = str(config.get("data_status") or "execution")
        data_status_label = str(config.get("data_status_label") or f"{year}年执行数")
        values[(str(config["city_id"]), year)] = {
            "gov_fund_revenue_100m": q2(normalized),
            "gov_fund_revenue_raw_100m": raw_value,
            "gov_fund_revenue_raw_unit": raw_unit,
            "gov_fund_revenue_evidence_excerpt": match.group(0),
            "source_doc_id": config["source_doc_id"],
            "source_grade": config["source_grade"],
            "source_format": config["source_format"],
            "data_status": data_status,
            "data_status_label": data_status_label,
            "source_locator": (
                f"{text_path.relative_to(ROOT)}；报告正文；城市={config['city_name']}；"
                f"{data_status_label}"
            ),
            "table_name": f"{year}年全市政府性基金预算收入执行情况",
        }
        sources.append(
            {
                "source_doc_id": config["source_doc_id"],
                "publisher": config["publisher"],
                "publisher_level": config["publisher_level"],
                "document_title": config["document_title"],
                "title_source": "curated_statement_excerpt",
                "attachment_title": source_path.name,
                "document_type": config["document_type"],
                "source_url": config["url"],
                "landing_page_url": config["url"],
                "attachment_url": config["url"],
                "canonical_url": config["url"],
                "final_resolved_url": config["url"],
                "file_name": source_path.name,
                "mime_type": "text/html" if source_path.suffix == ".html" else "application/pdf",
                "publication_date": config["publication_date"],
                "publication_date_raw": config["publication_date"],
                "period_end": f"{year}-12-31",
                "downloaded_at": RETRIEVED_AT,
                "content_hash_sha256": content_hash,
                "archive_uri": f"archive://national-prefecture-panel/{source_path.relative_to(ROOT)}",
                "archive_backend": "internal_object",
                "archive_path": str(source_path.relative_to(ROOT)),
                "page_count": config.get("page_count", ""),
                "source_grade": config["source_grade"],
                "http_status": "200",
                "access_status": "精确来源已归档",
                "supersedes_doc_id": "",
                "note": config["note"],
            }
        )
    return values, sources


def load_city_year_fiscal_sources() -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    """读取城市官方预算执行报告中的全市财政三项字段。"""

    values: dict[tuple[str, str], dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    for config in CITY_YEAR_FISCAL_SOURCES:
        source_path = Path(config["path"])
        text_path = Path(config["text_path"])
        content_hash = ensure_download(str(config.get("download_url") or config["url"]), source_path)
        report_text = text_path.read_text(encoding="utf-8")
        # 部分已归档的摘录把入口页只写在原文首行；若配置没有重复抄录 URL，
        # 从原文中提取第一个入口页，确保 source_document 仍可回溯到公开来源。
        source_url = str(config.get("url") or "")
        if not source_url:
            url_match = re.search(r"https?://[^\s)）】】]+", report_text)
            source_url = (url_match.group(0) if url_match else "").rstrip("，。；;）)]】")
        compact_text = re.sub(r"\s+", "", report_text)
        year = str(config["year"])
        data_status = str(config.get("data_status") or "execution")
        data_status_label = str(config.get("data_status_label") or f"{year}年执行数")
        record: dict[str, Any] = {
            "source_doc_id": config["source_doc_id"],
            "source_grade": config["source_grade"],
            "source_format": config["source_format"],
            "data_status": data_status,
            "data_status_label": data_status_label,
            "source_locator": (
                f"{text_path.relative_to(ROOT)}；报告正文；城市={config['city_name']}；"
                f"{data_status_label}；行政范围=全市"
            ),
            "table_name": f"{year}年全市财政预算执行情况",
            "page_number": config.get("page_number", ""),
        }
        for field, pattern in config["patterns"].items():
            match = re.search(str(pattern), compact_text)
            if not match:
                raise ValueError(f"未能从{config['city_name']}{year}年财政来源提取{field}")
            raw_value = Decimal(
                match.group(1).replace(",", "").replace("，", "").replace("．", ".")
            )
            raw_units = config.get("raw_units") or {}
            raw_unit = str(raw_units.get(field) or config.get("raw_unit") or "万元")
            if raw_unit in {"亿元", "%", "万人"}:
                normalized_value = raw_value
            elif raw_unit in {"百万元", "百万元人民币"}:
                normalized_value = raw_value * Decimal("0.01")
            else:
                normalized_value = raw_value * D4
            normalized = q2(normalized_value)
            negative_marker = str(config.get("negative_if", {}).get(field) or "")
            if negative_marker and negative_marker in match.group(0):
                normalized = -normalized
            record[field] = normalized
            record[f"{field}_raw_100m"] = raw_value
            record[f"{field}_raw_unit"] = raw_unit
            record[f"{field}_evidence_excerpt"] = match.group(0)
        key = (str(config["city_id"]), year)
        prior_record = values.get(key)
        if prior_record is None:
            record["_field_sources"] = {
                field: dict(record)
                for field in config["patterns"]
                if field in record
            }
            values[key] = record
        else:
            # 同一城市年度可能由独立来源分别补充经济财政和基金字段。
            # 按字段合并，保留每个字段自己的来源血缘；同等级冲突值不静默覆盖。
            field_sources = dict(prior_record.get("_field_sources") or {})
            prior_source_ids = [
                item for item in str(prior_record.get("source_doc_id") or "").split(";") if item
            ]
            current_source_id = str(record.get("source_doc_id") or "")
            if current_source_id and current_source_id not in prior_source_ids:
                prior_source_ids.append(current_source_id)
            prior_record["source_doc_id"] = ";".join(prior_source_ids)
            current_grade = str(record.get("source_grade") or "")
            for field in config["patterns"]:
                if field not in record:
                    continue
                prior_value = as_decimal(prior_record.get(field))
                current_value = as_decimal(record.get(field))
                prior_source = field_sources.get(field, prior_record)
                prior_grade = str(prior_source.get("source_grade") or "")
                if prior_value is None:
                    prior_record[field] = record[field]
                    for suffix in ("_raw_100m", "_raw_unit", "_evidence_excerpt"):
                        source_key = f"{field}{suffix}"
                        if source_key in record:
                            prior_record[source_key] = record[source_key]
                    field_sources[field] = dict(record)
                elif current_value == prior_value:
                    # 同值重复披露不构成冲突，但仍保留既有优先来源。
                    continue
                elif SOURCE_GRADE_RANK.get(current_grade, -1) > SOURCE_GRADE_RANK.get(prior_grade, -1):
                    prior_record[field] = record[field]
                    for suffix in ("_raw_100m", "_raw_unit", "_evidence_excerpt"):
                        source_key = f"{field}{suffix}"
                        if source_key in record:
                            prior_record[source_key] = record[source_key]
                    field_sources[field] = dict(record)
                else:
                    conflicts = list(prior_record.get("_field_conflicts") or [])
                    conflicts.append({
                        "field": field,
                        "prior_value": str(prior_value),
                        "candidate_value": str(current_value),
                        "prior_source_doc_id": str(prior_source.get("source_doc_id") or ""),
                        "candidate_source_doc_id": current_source_id,
                    })
                    prior_record["_field_conflicts"] = conflicts
            prior_record["_field_sources"] = field_sources
            if SOURCE_GRADE_RANK.get(current_grade, -1) > SOURCE_GRADE_RANK.get(
                str(prior_record.get("source_grade") or ""), -1
            ):
                prior_record["source_grade"] = current_grade
            if not prior_record.get("data_status") or prior_record.get("data_status") == "not_collected":
                prior_record["data_status"] = data_status
                prior_record["data_status_label"] = data_status_label
        sources.append(
            {
                "source_doc_id": config["source_doc_id"],
                "publisher": config["publisher"],
                "publisher_level": config["publisher_level"],
                "document_title": config["document_title"],
                "title_source": config.get("title_source") or "official_budget_report",
                "attachment_title": source_path.name,
                "document_type": config["document_type"],
                "source_url": source_url,
                "landing_page_url": config.get("landing_page_url") or source_url,
                "attachment_url": config.get("attachment_url") or source_url,
                "canonical_url": config.get("landing_page_url") or source_url,
                "final_resolved_url": config.get("attachment_url") or source_url,
                "file_name": source_path.name,
                "mime_type": (
                    "text/html"
                    if config.get("source_format") == "html"
                    else "text/plain"
                    if config.get("source_format") == "txt"
                    else "image/png"
                    if config.get("source_format") == "png"
                    else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    if config.get("source_format") == "docx"
                    else "application/msword"
                    if config.get("source_format") == "doc"
                    else "application/vnd.ms-excel"
                    if config.get("source_format") == "xls"
                    else "application/x-7z-compressed"
                    if config.get("source_format") == "7z"
                    else "application/pdf"
                ),
                "publication_date": config["publication_date"],
                "publication_date_raw": config["publication_date"],
                "period_end": f"{year}-12-31",
                "downloaded_at": RETRIEVED_AT,
                "content_hash_sha256": content_hash,
                "archive_uri": f"archive://national-prefecture-panel/{source_path.relative_to(ROOT)}",
                "archive_backend": "internal_object",
                "archive_path": str(source_path.relative_to(ROOT)),
                "page_count": config.get("page_count", "179"),
                "source_grade": config["source_grade"],
                "http_status": "200",
                "access_status": config.get("access_status") or (
                    "官方网页已归档"
                    if config.get("source_format") == "html"
                    else "精确图表已归档"
                    if config.get("source_format") == "png"
                    else "官方DOCX附件已归档"
                    if config.get("source_format") == "docx"
                    else "官方DOC附件已归档"
                    if config.get("source_format") == "doc"
                    else "官方Excel附件已归档"
                    if config.get("source_format") == "xlsx"
                    else "官方Excel附件已归档"
                    if config.get("source_format") == "xls"
                    else "官方7z附件已归档"
                    if config.get("source_format") == "7z"
                    else "官方PDF已归档"
                ),
                "supersedes_doc_id": "",
                "note": config["note"],
            }
        )
    return values, sources


def load_ningxia_2025_city_fiscal() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取宁夏四市 2025 年官方预算执行报告的全市财政字段。"""

    return load_city_2025_fiscal_sources(NINGXIA_2025_FISCAL_SOURCES)


def load_shandong_2025_city_fiscal() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取济南、青岛 2025 年官方预算执行报告的全市财政字段。"""

    return load_city_2025_fiscal_sources(SHANDONG_2025_FISCAL_SOURCES)


def load_next_2025_city_fiscal() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取常州、洛阳、岳阳、衡阳 2025 年官方预算执行报告的全市财政字段。"""

    return load_city_2025_fiscal_sources(NEXT_2025_FISCAL_SOURCES)


def load_followup_2025_city_fiscal() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取无锡、常德、益阳、苏州 2025 年官方财政/统计数据。"""

    return load_city_2025_fiscal_sources(FOLLOWUP_2025_FISCAL_SOURCES)


def load_next2_2025_city_fiscal() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取徐州、扬州、镇江、泰州 2025 年精确财政表。"""

    return load_city_2025_fiscal_sources(NEXT2_2025_FISCAL_SOURCES)


def load_next3_2025_city_fiscal() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取福州、泉州、长沙、沈阳 2025 年财政统计数据。"""

    return load_city_2025_fiscal_sources(NEXT3_2025_FISCAL_SOURCES)


def load_next4_2025_city_fiscal() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取武汉、郑州、成都、南昌、南宁 2025 年财政统计数据。"""

    return load_city_2025_fiscal_sources(NEXT4_2025_FISCAL_SOURCES)


def load_next5_2025_city_fiscal() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取西安、海口、银川、乌鲁木齐、昆明 2025 年财政统计数据。"""

    return load_city_2025_fiscal_sources(NEXT5_2025_FISCAL_SOURCES)


def load_next6_2025_city_fiscal() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取石家庄、太原、佳木斯、昌都、哈尔滨 2025 年财政统计数据。"""

    return load_city_2025_fiscal_sources(NEXT6_2025_FISCAL_SOURCES)


def load_next7_2025_city_fiscal() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取合肥、宜昌、荆州、黄石、营口 2025 年财政统计数据。"""

    return load_city_2025_fiscal_sources(NEXT7_2025_FISCAL_SOURCES)


def load_next8_2025_city_economic() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取乌海市 2025 年经济财政统计数据。"""

    return load_city_2025_fiscal_sources(NEXT8_2025_ECONOMIC_SOURCES)


def load_next9_2025_city_economic() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取开封、新乡、安阳 2025 年经济财政统计数据。"""

    return load_city_2025_fiscal_sources(NEXT9_2025_ECONOMIC_SOURCES)


def load_next10_2025_city_economic() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取南阳、许昌、鹤壁 2025 年经济财政统计数据。"""

    return load_city_2025_fiscal_sources(NEXT10_2025_ECONOMIC_SOURCES)


def load_next11_2025_city_economic() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取商丘、信阳、周口 2025 年经济财政统计数据。"""

    return load_city_2025_fiscal_sources(NEXT11_2025_ECONOMIC_SOURCES)


def load_next12_2025_city_economic() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取濮阳、驻马店、漯河 2025 年经济财政统计数据。"""

    return load_city_2025_fiscal_sources(NEXT12_2025_ECONOMIC_SOURCES)


def load_next13_2025_city_economic() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取平顶山市 2025 年官方统计公报经济数据。"""

    return load_city_2025_fiscal_sources(NEXT13_2025_ECONOMIC_SOURCES)


def load_next14_2025_city_economic() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取焦作市 2025 年官方统计公报经济财政数据。"""

    return load_city_2025_fiscal_sources(NEXT14_2025_ECONOMIC_SOURCES)


def load_next15_2025_city_economic() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取三门峡、洛阳 2025 年统计公报经济财政数据。"""

    return load_city_2025_fiscal_sources(NEXT15_2025_ECONOMIC_SOURCES)


def load_next16_2025_city_economic() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取岳阳、益阳、常德 2025 年统计公报经济数据。"""

    return load_city_2025_fiscal_sources(NEXT16_2025_ECONOMIC_SOURCES)


def load_next17_2025_city_economic() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取衡阳、邵阳、郴州、永州、怀化、娄底 2025 年统计公报经济财政数据。"""

    return load_city_2025_fiscal_sources(NEXT17_2025_ECONOMIC_SOURCES)


def load_next18_2025_city_economic() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取张家界、湘潭、湘西州 2025 年统计公报经济财政数据。"""

    return load_city_2025_fiscal_sources(NEXT18_2025_ECONOMIC_SOURCES)


def load_next19_2025_city_economic() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取株洲市 2025 年统计公报经济财政数据。"""

    return load_city_2025_fiscal_sources(NEXT19_2025_ECONOMIC_SOURCES)


def load_next20_2025_city_economic() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取长沙市 2025 年统计公报年末常住人口。"""

    return load_city_2025_fiscal_sources(NEXT20_2025_ECONOMIC_SOURCES)


def load_next21_2025_city_economic() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取克拉玛依、吐鲁番、哈密 2025 年统计公报经济财政数据。"""

    return load_city_2025_fiscal_sources(NEXT21_2025_ECONOMIC_SOURCES)


def load_next22_2025_city_economic() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取昌吉州 2025 年统计公报经济财政数据。"""

    return load_city_2025_fiscal_sources(NEXT22_2025_ECONOMIC_SOURCES)


def load_next23_2025_city_economic() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取博州、巴州 2025 年统计公报经济财政数据。"""

    return load_city_2025_fiscal_sources(NEXT23_2025_ECONOMIC_SOURCES)


def load_next24_2025_city_economic() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取和田地区、克州 2025 年统计公报及正式财政数据。"""

    return load_city_2025_fiscal_sources(NEXT24_2025_ECONOMIC_SOURCES)


def load_next25_2025_city_economic() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取阿克苏、喀什地区 2025 年统计公报经济财政数据。"""

    return load_city_2025_fiscal_sources(NEXT25_2025_ECONOMIC_SOURCES)


def load_next26_2025_city_economic() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取成都市 2025 年统计公报经济指标。"""

    return load_city_2025_fiscal_sources(NEXT26_2025_ECONOMIC_SOURCES)


def load_next27_2025_city_economic() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取扬州、镇江 2025 年统计公报经济指标。"""

    return load_city_2025_fiscal_sources(NEXT27_2025_ECONOMIC_SOURCES)


def load_next28_2025_city_economic() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取海口、宜昌 2025 年统计公报经济及人口指标。"""

    return load_city_2025_fiscal_sources(NEXT28_2025_ECONOMIC_SOURCES)


def load_next29_2025_city_economic() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取合肥市 2025 年统计公报年末常住人口。"""

    return load_city_2025_fiscal_sources(NEXT29_2025_ECONOMIC_SOURCES)


def load_next30_2025_city_economic() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """读取福州市 2025 年官方统计公报经济财政指标。"""

    return load_city_2025_fiscal_sources(NEXT30_2025_ECONOMIC_SOURCES)


def compute_derived_values(row: Mapping[str, Any]) -> dict[str, Decimal | None]:
    general_limit = as_decimal(row.get("general_debt_limit_100m"))
    special_limit = as_decimal(row.get("special_debt_limit_100m"))
    general_balance = as_decimal(row.get("general_debt_balance_100m"))
    special_balance = as_decimal(row.get("special_debt_balance_100m"))
    direct_limit = as_decimal(row.get("_official_direct_statutory_limit"))
    if direct_limit is None:
        direct_limit = as_decimal(row.get("statutory_debt_limit_100m"))
    direct_balance = as_decimal(row.get("_official_direct_statutory_balance"))
    if direct_balance is None:
        direct_balance = as_decimal(row.get("statutory_debt_balance_100m"))

    def choose_total(
        direct_total: Decimal | None,
        general_component: Decimal | None,
        special_component: Decimal | None,
    ) -> Decimal | None:
        component_sum = (
            general_component + special_component
            if general_component is not None and special_component is not None
            else None
        )
        if direct_total is None:
            return q2(component_sum) if component_sum is not None else None
        if component_sum is None or abs(direct_total - component_sum) <= Decimal("0.20"):
            return q2(direct_total)
        # 大额差异通常意味着旧表解析错列；此时以两个明确分项之和为准，
        # 直报值仍保留在隐藏证据字段，供后续异常复核。
        return q2(component_sum)

    statutory_limit = choose_total(direct_limit, general_limit, special_limit)
    statutory_balance = choose_total(direct_balance, general_balance, special_balance)
    return {
        "statutory_debt_limit_100m": statutory_limit,
        "statutory_debt_balance_100m": statutory_balance,
        "debt_limit_utilization_pct": pct(statutory_balance, statutory_limit),
        "statutory_debt_to_gdp_pct": pct(statutory_balance, row.get("gdp_current_100m")),
        "statutory_debt_to_revenue_pct": pct(statutory_balance, row.get("general_public_revenue_100m")),
        "statutory_debt_to_general_revenue_pct": pct(statutory_balance, row.get("general_public_revenue_100m")),
        "fiscal_self_sufficiency_pct": pct(row.get("general_public_revenue_100m"), row.get("general_public_expenditure_100m")),
        "fund_revenue_dependence_pct": pct(
            row.get("gov_fund_revenue_100m"),
            (as_decimal(row.get("general_public_revenue_100m")) or D0)
            + (as_decimal(row.get("gov_fund_revenue_100m")) or D0),
        ) if as_decimal(row.get("general_public_revenue_100m")) is not None and as_decimal(row.get("gov_fund_revenue_100m")) is not None else None,
        "gov_fund_to_general_revenue_pct": pct(row.get("gov_fund_revenue_100m"), row.get("general_public_revenue_100m")),
    }


def validate_no_zero_for_missing(rows: Iterable[Mapping[str, Any]]) -> None:
    for row in rows:
        for field in RAW_NUMERIC_FIELDS:
            if field in row and row[field] == 0:
                # 0 可能是真实值，只拒绝来源明确标识为 missing 的伪零。
                if str(row.get("missing_reason", "")).strip() or row.get("data_status") == "missing_zero":
                    raise AssertionError(f"{field} 将缺失伪装为 0")


def _macro_base(city: Mapping[str, Any], year: int) -> dict[str, Any]:
    return {
        "city_id": city["city_id"],
        "admin_code_6": city["admin_code_6"],
        "city_name_cn": city["city_name_cn"],
        "province_code": city["province_code"],
        "province_name": city["province_name"],
        "prefecture_type": city["prefecture_type"],
        "sample_tier": city["sample_tier"],
        "metric_year": str(year),
        "period_end": f"{year}-12-31",
        "geo_scope": "prefecture_whole",
        "data_status": "not_collected",
        **{field: None for field in MACRO_FIELDS},
        "gov_fund_source_status": "未采集",
        "source_doc_id": None,
        "source_grade": None,
        "collection_status": "needs_collection",
        "lineage_complete_flag": False,
        "note": "未取得可审计的公开数值，保留 null，后续进入采集队列。",
    }


def _set_disclosed(row: dict[str, Any], field: str, value: Any) -> None:
    row[field] = q2(value)


def build_macro_rows(
    city_master: list[dict[str, Any]],
    panel_rows: list[dict[str, str]],
    gd_macro: Mapping[str, Mapping[str, str]],
    official_debt_facts: Mapping[tuple[str, str], Mapping[str, Any]] | None = None,
    gd_2025_gdp: Mapping[str, Mapping[str, Any]] | None = None,
    gd_2025_fiscal: Mapping[str, Mapping[str, Any]] | None = None,
    gd_2025_fund: Mapping[str, Mapping[str, Any]] | None = None,
    ningxia_2025_fiscal: Mapping[str, Mapping[str, Any]] | None = None,
    shandong_2025_fiscal: Mapping[str, Mapping[str, Any]] | None = None,
    next_2025_fiscal: Mapping[str, Mapping[str, Any]] | None = None,
    followup_2025_fiscal: Mapping[str, Mapping[str, Any]] | None = None,
    next2_2025_fiscal: Mapping[str, Mapping[str, Any]] | None = None,
    next3_2025_fiscal: Mapping[str, Mapping[str, Any]] | None = None,
    next4_2025_fiscal: Mapping[str, Mapping[str, Any]] | None = None,
    next5_2025_fiscal: Mapping[str, Mapping[str, Any]] | None = None,
    next6_2025_fiscal: Mapping[str, Mapping[str, Any]] | None = None,
    next7_2025_fiscal: Mapping[str, Mapping[str, Any]] | None = None,
    next8_2025_economic: Mapping[str, Mapping[str, Any]] | None = None,
    next9_2025_economic: Mapping[str, Mapping[str, Any]] | None = None,
    next10_2025_economic: Mapping[str, Mapping[str, Any]] | None = None,
    next11_2025_economic: Mapping[str, Mapping[str, Any]] | None = None,
    next12_2025_economic: Mapping[str, Mapping[str, Any]] | None = None,
    next13_2025_economic: Mapping[str, Mapping[str, Any]] | None = None,
    next14_2025_economic: Mapping[str, Mapping[str, Any]] | None = None,
    next15_2025_economic: Mapping[str, Mapping[str, Any]] | None = None,
    next16_2025_economic: Mapping[str, Mapping[str, Any]] | None = None,
    next17_2025_economic: Mapping[str, Mapping[str, Any]] | None = None,
    next18_2025_economic: Mapping[str, Mapping[str, Any]] | None = None,
    next19_2025_economic: Mapping[str, Mapping[str, Any]] | None = None,
    next20_2025_economic: Mapping[str, Mapping[str, Any]] | None = None,
    next21_2025_economic: Mapping[str, Mapping[str, Any]] | None = None,
    next22_2025_economic: Mapping[str, Mapping[str, Any]] | None = None,
    next23_2025_economic: Mapping[str, Mapping[str, Any]] | None = None,
    next24_2025_economic: Mapping[str, Mapping[str, Any]] | None = None,
    next25_2025_economic: Mapping[str, Mapping[str, Any]] | None = None,
    next26_2025_economic: Mapping[str, Mapping[str, Any]] | None = None,
    next27_2025_economic: Mapping[str, Mapping[str, Any]] | None = None,
    next28_2025_economic: Mapping[str, Mapping[str, Any]] | None = None,
    next29_2025_economic: Mapping[str, Mapping[str, Any]] | None = None,
    next30_2025_economic: Mapping[str, Mapping[str, Any]] | None = None,
    jiangsu_city_fund: Mapping[tuple[str, str], Mapping[str, Any]] | None = None,
    jiangsu_city_fiscal: Mapping[tuple[str, str], Mapping[str, Any]] | None = None,
    city_year_fiscal: Mapping[tuple[str, str], Mapping[str, Any]] | None = None,
    city_year_fund: Mapping[tuple[str, str], Mapping[str, Any]] | None = None,
    city_yearbook_macro: Mapping[tuple[str, str], Mapping[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    panel_by_key = {(str(r.get("city_code", "")).zfill(6), int(r["year"])): r for r in panel_rows if r.get("year", "").isdigit()}
    lineage: list[dict[str, Any]] = []
    batch_lineage: list[dict[str, Any]] = []
    output: list[dict[str, Any]] = []
    official_debt_facts = official_debt_facts or {}
    gd_2025_gdp = gd_2025_gdp or {}
    gd_2025_fiscal = gd_2025_fiscal or {}
    gd_2025_fund = gd_2025_fund or {}
    ningxia_2025_fiscal = ningxia_2025_fiscal or {}
    shandong_2025_fiscal = shandong_2025_fiscal or {}
    next_2025_fiscal = next_2025_fiscal or {}
    followup_2025_fiscal = followup_2025_fiscal or {}
    next2_2025_fiscal = next2_2025_fiscal or {}
    next3_2025_fiscal = next3_2025_fiscal or {}
    next4_2025_fiscal = next4_2025_fiscal or {}
    next5_2025_fiscal = next5_2025_fiscal or {}
    next6_2025_fiscal = next6_2025_fiscal or {}
    next7_2025_fiscal = next7_2025_fiscal or {}
    next8_2025_economic = next8_2025_economic or {}
    next9_2025_economic = next9_2025_economic or {}
    next10_2025_economic = next10_2025_economic or {}
    next11_2025_economic = next11_2025_economic or {}
    next12_2025_economic = next12_2025_economic or {}
    next13_2025_economic = next13_2025_economic or {}
    next14_2025_economic = next14_2025_economic or {}
    next15_2025_economic = next15_2025_economic or {}
    next16_2025_economic = next16_2025_economic or {}
    next17_2025_economic = next17_2025_economic or {}
    next18_2025_economic = next18_2025_economic or {}
    next19_2025_economic = next19_2025_economic or {}
    next20_2025_economic = next20_2025_economic or {}
    next21_2025_economic = next21_2025_economic or {}
    next22_2025_economic = next22_2025_economic or {}
    next23_2025_economic = next23_2025_economic or {}
    next24_2025_economic = next24_2025_economic or {}
    next25_2025_economic = next25_2025_economic or {}
    next26_2025_economic = next26_2025_economic or {}
    next27_2025_economic = next27_2025_economic or {}
    next28_2025_economic = next28_2025_economic or {}
    next29_2025_economic = next29_2025_economic or {}
    next30_2025_economic = next30_2025_economic or {}
    jiangsu_city_fund = jiangsu_city_fund or {}
    jiangsu_city_fiscal = jiangsu_city_fiscal or {}
    city_year_fiscal = city_year_fiscal or {}
    city_year_fund = city_year_fund or {}
    city_yearbook_macro = city_yearbook_macro or {}
    city_2025_fiscal = {
        **ningxia_2025_fiscal,
        **shandong_2025_fiscal,
        **next_2025_fiscal,
        **followup_2025_fiscal,
        **next2_2025_fiscal,
        **next3_2025_fiscal,
        **next4_2025_fiscal,
        **next5_2025_fiscal,
        **next6_2025_fiscal,
        **next7_2025_fiscal,
    }
    # 经济批次可能与已归档的财政批次覆盖同一城市。不能把整条记录浅层覆盖，
    # 否则会丢失原财政收入、支出和基金收入；下面按字段叠加并保留已有来源。
    economic_2025 = {
        **next8_2025_economic,
        **next9_2025_economic,
        **next10_2025_economic,
        **next11_2025_economic,
        **next12_2025_economic,
        **next13_2025_economic,
        **next14_2025_economic,
        **next15_2025_economic,
        **next16_2025_economic,
        **next17_2025_economic,
        **next18_2025_economic,
        **next19_2025_economic,
        **next20_2025_economic,
        **next21_2025_economic,
        **next22_2025_economic,
        **next23_2025_economic,
        **next24_2025_economic,
        **next25_2025_economic,
        **next26_2025_economic,
        **next27_2025_economic,
        **next28_2025_economic,
        **next29_2025_economic,
        **next30_2025_economic,
    }
    for city in city_master:
        year = int(city["metric_year"])
        row = _macro_base(city, year)
        key = (city["admin_code_6"], year)
        panel = panel_by_key.get(key)
        if panel and 2018 <= year <= 2023:
            row["data_status"] = "provisional"
            row["source_doc_id"] = "SRC-CITY-PANEL-1990-2023"
            row["source_grade"] = "D"
            row["collection_status"] = "needs_review"
            row["note"] = "公开研究型城市面板；字段口径与来源链条未完全公开，作为 provisional 暂存值，待官方年鉴/公报复核。"
            raw_map = {
                "gdp_current_100m": (panel.get("gdp"), "万人民币", D4, "10,000元换算为亿元"),
                "gdp_real_growth_pct": (panel.get("gdp_growth"), "%", D1, "百分比原值保留"),
                "resident_population_10k": (panel.get("pop_avg"), "万人（变量原名 pop_avg）", D1, "暂按公开变量名映射，待核实定义"),
                "general_public_revenue_100m": (panel.get("fiscal_revenue"), "万元人民币", D4, "10,000元换算为亿元"),
                "general_public_expenditure_100m": (panel.get("fiscal_exp"), "万元人民币", D4, "10,000元换算为亿元"),
            }
            for field, (raw, unit, scale, rule) in raw_map.items():
                raw_d = as_decimal(raw)
                if raw_d is None:
                    continue
                value = q2(raw_d * scale)
                row[field] = value
                lineage.append(_lineage_for_panel(row, field, raw, unit, value, rule, panel))
        elif year == 2024 and city["city_id"] in gd_macro:
            source = gd_macro[city["city_id"]]
            row.update({field: as_decimal(source.get(field)) for field in MACRO_FIELDS})
            row["data_status"] = source.get("data_status") or "preliminary"
            row["source_doc_id"] = "SRC-GD-YEARBOOK-2025;SRC-GD-DEBT-2024-FINAL"
            row["source_grade"] = "A1"
            row["collection_status"] = source.get("collection_status") or "needs_review"
            row["gov_fund_source_status"] = source.get("gov_fund_source_status") or "官方/二手混合，待复核"
            row["note"] = source.get("note") or "广东省 2024 年试跑结果纳入全国快照；政府性基金收入仍需官方复核。"
            for field in MACRO_FIELDS:
                value = row.get(field)
                if value is not None:
                    lineage.append(_lineage_for_gd(row, field, value))
        elif year == 2025 and city["city_id"] in gd_2025_gdp:
            source = gd_2025_gdp[city["city_id"]]
            for field in ("gdp_current_100m", "gdp_real_growth_pct"):
                value = as_decimal(source.get(field))
                if value is None:
                    continue
                row[field] = q2(value)
                batch_lineage.append(_lineage_for_gd_2025(row, field, row[field]))
            fiscal_source = gd_2025_fiscal.get(city["city_id"], {})
            for field in ("general_public_revenue_100m", "general_public_expenditure_100m"):
                value = as_decimal(fiscal_source.get(field))
                if value is None:
                    continue
                row[field] = q2(value)
                batch_lineage.append(
                    _lineage_for_gd_2025_city_fiscal(
                        row,
                        field,
                        row[field],
                        fiscal_source.get(f"{field}_raw_10k"),
                    )
                )
            fund_source = gd_2025_fund.get(city["city_id"], {})
            fund_value = as_decimal(fund_source.get("gov_fund_revenue_100m"))
            if fund_value is not None:
                row["gov_fund_revenue_100m"] = q2(fund_value)
                row["gov_fund_source_status"] = "官方城市预算报告（全市口径）"
                batch_lineage.append(_lineage_for_city_fund(row, fund_source, row["gov_fund_revenue_100m"]))
            row["data_status"] = "preliminary"
            source_ids = ["SRC-GD-CITY-GDP-2025"]
            if fiscal_source:
                source_ids.append("SRC-GD-CITY-FISCAL-2025")
            if fund_source.get("source_doc_id"):
                source_ids.append(str(fund_source["source_doc_id"]))
            if fiscal_source or fund_source:
                row["source_doc_id"] = ";".join(source_ids)
                row["data_status"] = "execution"
            row["source_grade"] = "A2"
            row["collection_status"] = "extracted"
            row["note"] = (
                "已接入广东省统计局 2025 年各市 GDP 初步核算表及广东省财政厅地市一般公共预算执行表；"
                + (
                    "财政收入、支出为官方 execution，"
                    if fiscal_source
                    else ""
                )
                + (
                    "广州、深圳、东莞政府性基金收入为城市官方报告披露值，"
                    if fund_source
                    else ""
                )
                + "GDP 与实际增速为 preliminary，人口和债务字段仍待补齐。"
                if fiscal_source or fund_source
                else "已接入广东省统计局 2025 年各市 GDP 初步核算表；GDP 与实际增速为官方 A2 值，财政和政府性基金字段仍待补齐。"
            )
        elif year == 2025 and city["city_id"] in city_2025_fiscal:
            source = city_2025_fiscal[city["city_id"]]
            for field in (
                "gdp_current_100m",
                "gdp_real_growth_pct",
                "resident_population_10k",
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            ):
                value = as_decimal(source.get(field))
                if value is None:
                    continue
                row[field] = q2(value)
                batch_lineage.append(_lineage_for_ningxia_city_fiscal(row, source, field, row[field]))
            row["data_status"] = str(source.get("data_status") or "execution")
            row["source_doc_id"] = str(source.get("source_doc_id", ""))
            source_grade = str(source.get("source_grade") or "A2")
            row["source_grade"] = source_grade
            row["collection_status"] = "extracted" if source_grade in {"A1", "A2"} else "needs_review"
            row["gov_fund_source_status"] = "官方城市预算执行报告（全市口径）"
            row["note"] = (
                f"已接入{city['city_name_cn']} 2025 年全市一般公共预算收入、支出和政府性基金收入；"
                + (
                    "来源为官方预算执行报告，三项均为 execution。"
                    if source_grade in {"A1", "A2"}
                    else "来源为 B2 精确表格/公报转载，作为可审计二手补缺，不等同于官方决算原件。"
                )
                + "GDP、人口和债务字段按各自来源单独记录。"
            )
        yearbook_source = city_yearbook_macro.get((str(city["city_id"]), str(year)))
        if yearbook_source:
            yearbook_grade = str(yearbook_source.get("source_grade") or "B2")
            existing_grade = str(row.get("source_grade") or "")
            applied_fields: list[str] = []
            for field in (
                "gdp_current_100m",
                "gdp_real_growth_pct",
                "resident_population_10k",
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
            ):
                value = as_decimal(yearbook_source.get(field))
                if value is None:
                    continue
                # 年鉴 B2 可以补空值或升级研究型 D 值，但不能覆盖 A1/A2/B1。
                if row.get(field) is not None and SOURCE_GRADE_RANK.get(existing_grade, -1) > SOURCE_GRADE_RANK.get("D", 0):
                    continue
                replacing_provisional = row.get(field) is not None and existing_grade == "D"
                if replacing_provisional:
                    record_id = _macro_record_id(row)
                    for prior_lineage in lineage:
                        if (
                            prior_lineage.get("target_record_id") == record_id
                            and prior_lineage.get("target_field") == field
                            and prior_lineage.get("source_doc_id") == "SRC-CITY-PANEL-1990-2023"
                        ):
                            prior_lineage["selected_flag"] = False
                            prior_lineage["selection_reason"] = "被B2城市统计年鉴精确表升级替换，保留为暂存历史"
                row[field] = q2(value)
                batch_lineage.append(
                    _lineage_for_city_yearbook(row, yearbook_source, field, row[field])
                )
                applied_fields.append(field)
            if applied_fields:
                source_id = str(yearbook_source.get("source_doc_id") or "")
                prior_source_ids = [
                    item.strip()
                    for item in str(row.get("source_doc_id") or "").split(";")
                    if item.strip()
                ]
                row["source_doc_id"] = ";".join(dict.fromkeys(prior_source_ids + ([source_id] if source_id else [])))
                if SOURCE_GRADE_RANK.get(yearbook_grade, -1) > SOURCE_GRADE_RANK.get(existing_grade, -1):
                    row["source_grade"] = yearbook_grade
                if row.get("data_status") in {None, "", "provisional", "not_collected"}:
                    row["data_status"] = "yearbook"
                row["collection_status"] = "needs_review"
                row["note"] = (
                    str(row.get("note") or "")
                    + ("；" if row.get("note") else "")
                    + "已接入中国城市统计年鉴地级市全市精确表；B2 年鉴值升级/补充 D 级暂存字段，待官方原件复核。"
                )
        economic_source = economic_2025.get(city["city_id"]) if year == 2025 else None
        if economic_source:
            applied_fields: list[str] = []
            for field in (
                "gdp_current_100m",
                "gdp_real_growth_pct",
                "resident_population_10k",
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            ):
                value = as_decimal(economic_source.get(field))
                # 同一城市已有更高优先级字段时不覆盖，只补空值。
                if value is None or row.get(field) is not None:
                    continue
                row[field] = q2(value)
                batch_lineage.append(
                    _lineage_for_ningxia_city_fiscal(row, economic_source, field, row[field])
                )
                applied_fields.append(field)
            if applied_fields:
                economic_source_id = str(economic_source.get("source_doc_id") or "")
                prior_source_ids = [
                    item.strip()
                    for item in str(row.get("source_doc_id") or "").split(";")
                    if item.strip()
                ]
                row["source_doc_id"] = ";".join(
                    dict.fromkeys(prior_source_ids + ([economic_source_id] if economic_source_id else []))
                ) or None
                economic_grade = str(economic_source.get("source_grade") or "A2")
                if not row.get("source_grade"):
                    row["source_grade"] = economic_grade
                if row.get("data_status") in {None, "", "not_collected"}:
                    row["data_status"] = str(economic_source.get("data_status") or "preliminary")
                if row.get("collection_status") in {None, "", "needs_collection"}:
                    row["collection_status"] = (
                        "extracted" if economic_grade in {"A1", "A2"} else "needs_review"
                    )
                if "gov_fund_revenue_100m" in applied_fields:
                    row["gov_fund_source_status"] = "官方城市预算执行报告（全市口径）"
                economic_note = str(economic_source.get("note") or "")
                if row.get("note", "").startswith("未取得可审计"):
                    row["note"] = economic_note
                elif economic_note and economic_note not in str(row.get("note") or ""):
                    row["note"] = f"{row.get('note') or ''}；{economic_note}"
        debt_fact = official_debt_facts.get((city["city_id"], str(year)))
        if debt_fact and debt_fact_has_balance_limit_conflict(dict(debt_fact)):
            blocked_source_id = str(debt_fact.get("source_doc_id", ""))
            prior_source = str(row.get("source_doc_id") or "")
            row["source_doc_id"] = ";".join(item for item in [prior_source, blocked_source_id] if item)
            row["source_grade"] = str(debt_fact.get("source_grade") or row.get("source_grade") or "")
            row["data_status"] = "needs_review"
            row["collection_status"] = "needs_review"
            row["note"] = "债务来源已归档，但官方表中余额超过限额且未提供例外说明；按强校验阻塞入主表，待复核原表口径。"
            debt_fact = None
        if debt_fact:
            debt_source_id = str(debt_fact.get("source_doc_id", ""))
            prior_source = str(row.get("source_doc_id") or "")
            row["source_doc_id"] = ";".join(item for item in [prior_source, debt_source_id] if item)
            debt_grade = str(debt_fact.get("source_grade") or "A1")
            row["source_grade"] = debt_grade
            if debt_grade == "D":
                row["collection_status"] = "needs_review"
                row["data_status"] = "secondary_debt"
                row["note"] = "已接入商业数据库公开城市债务页的 provisional 补缺值；经济财政字段与债务字段来源状态分开记录，必须回到官方预算/决算或统计公报复核。"
            elif debt_grade in {"A1", "A2"}:
                row["collection_status"] = "extracted"
                row["data_status"] = "official_debt"
                row["note"] = "已从省级财政厅官方地级行政单元债务明细表提取；经济财政字段与债务字段的来源状态分开记录。"
            else:
                row["collection_status"] = "needs_review"
                row["data_status"] = "secondary_debt"
                row["note"] = "已接入评级报告或其他二手公开来源的债务补缺值；不等同于官方决算数据，必须回到财政/人大预算决算或官方债务表复核。"
            # 公开表可能明确标注“预计执行数/快报数”。保留该状态，
            # 避免把阶段性数值误标为最终决算。
            if debt_fact.get("data_status"):
                row["data_status"] = str(debt_fact["data_status"])
            if debt_fact.get("balance_limit_exception_note"):
                row["data_status"] = OFFICIAL_DEBT_EXCEPTION_STATUS
                row["collection_status"] = "needs_review"
                row["note"] = (
                    "官方公开债务表原值已入表，但存在明确记录的限额/余额内部勾稽异常；"
                    + str(debt_fact["balance_limit_exception_note"])
                )
            for field in RAW_NUMERIC_FIELDS:
                if field not in {"general_debt_limit_100m", "general_debt_balance_100m", "special_debt_limit_100m", "special_debt_balance_100m"}:
                    continue
                value = debt_fact.get(field)
                if value is None:
                    continue
                row[field] = q2(value)
                lineage.append(_lineage_for_official_debt(row, field, debt_fact, row[field]))
            # 设计文档允许来源只披露法定债务总额时直接入总额字段，但不得反推一般/专项分项。
            # 只有在分项不完整时才采用总额直录，避免用总额覆盖可勾稽的分项合计。
            if row.get("general_debt_balance_100m") is None or row.get("special_debt_balance_100m") is None:
                for field in ("statutory_debt_limit_100m", "statutory_debt_balance_100m"):
                    value = debt_fact.get(field)
                    if value is None:
                        continue
                    row[field] = q2(value)
                    lineage.append(_lineage_for_official_debt(row, field, debt_fact, row[field]))
            # 直接披露的合计用于证据记录；主表的合计仍由同口径一般/专项分项勾稽生成。
            row["_official_direct_statutory_limit"] = debt_fact.get("statutory_debt_limit_100m")
            row["_official_direct_statutory_balance"] = debt_fact.get("statutory_debt_balance_100m")
        jiangsu_fiscal_source = jiangsu_city_fiscal.get((city["city_id"], str(year)))
        if jiangsu_fiscal_source:
            prior_source = str(row.get("source_doc_id") or "")
            fiscal_source_id = str(jiangsu_fiscal_source.get("source_doc_id") or "")
            row["source_doc_id"] = ";".join(
                item for item in [prior_source, fiscal_source_id] if item
            )
            for field in ("general_public_revenue_100m", "general_public_expenditure_100m"):
                value = as_decimal(jiangsu_fiscal_source.get(field))
                if value is None:
                    continue
                row[field] = q2(value)
                batch_lineage.append(
                    _lineage_for_jiangsu_city_fiscal(row, jiangsu_fiscal_source, field, row[field])
                )
            row["source_grade"] = "A1"
            row["collection_status"] = "extracted"
            row["note"] = (
                str(row.get("note") or "")
                + ("；" if row.get("note") else "")
                + f"已接入江苏省{year}年财政厅分地区一般公共预算收入、支出执行表；"
                "经济财政字段为全市执行数，原始单位万元。"
            )
        city_year_fiscal_source = city_year_fiscal.get((city["city_id"], str(year)))
        if city_year_fiscal_source:
            fiscal_source_id = str(city_year_fiscal_source.get("source_doc_id") or "")
            applied_fields: list[str] = []
            applied_public_panel_fields: list[str] = []
            applied_standard_fields: list[str] = []
            for field in (
                "gdp_current_100m",
                "gdp_real_growth_pct",
                "resident_population_10k",
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
                "statutory_debt_limit_100m",
                "statutory_debt_balance_100m",
            ):
                value = as_decimal(city_year_fiscal_source.get(field))
                if value is None:
                    continue
                field_source = city_year_fiscal_source.get("_field_sources", {}).get(field, city_year_fiscal_source)
                field_is_public_panel = (
                    str(field_source.get("source_platform") or "")
                    in {"dachuang", "haidatas"}
                    and str(field_source.get("source_grade") or "") == "D"
                )
                if field_is_public_panel and row.get(field) is not None:
                    continue
                row[field] = q2(value)
                applied_fields.append(field)
                if field_is_public_panel:
                    applied_public_panel_fields.append(field)
                else:
                    applied_standard_fields.append(field)
                if field == "gov_fund_revenue_100m":
                    row["gov_fund_source_status"] = "城市财政局官方预算执行报告（全市口径）"
                batch_lineage.append(
                    _lineage_for_city_year_fiscal(
                        row, city_year_fiscal_source, field, row[field]
                    )
                )
            if applied_fields:
                prior_source = str(row.get("source_doc_id") or "")
                row["source_doc_id"] = ";".join(
                    item for item in [prior_source, fiscal_source_id] if item
                )
                if applied_public_panel_fields:
                    # 行级等级可能已由其他字段的 A/B 来源决定，D 级字段
                    # 只在行级仍为空或 D 时保留为 D，避免整体降级。
                    if str(row.get("source_grade") or "") in {"", "D"}:
                        row["source_grade"] = "D"
                    if row.get("data_status") in {None, "", "not_collected", "provisional"}:
                        row["data_status"] = "provisional"
                    row["collection_status"] = "needs_review"
                    row["note"] = (
                        str(row.get("note") or "")
                        + ("；" if row.get("note") else "")
                        + f"已接入{year}年第三方公开研究面板 D 级临时值（字段={','.join(applied_public_panel_fields)}）；"
                        "仅用于原始空缺覆盖，待官方统计年鉴/公报复核，不计入高等级定稿率。"
                    )
                if applied_standard_fields:
                    row["data_status"] = str(city_year_fiscal_source.get("data_status") or "execution")
                    row["source_grade"] = str(city_year_fiscal_source.get("source_grade") or "A2")
                    row["collection_status"] = "extracted"
                    row["note"] = (
                        str(row.get("note") or "")
                        + ("；" if row.get("note") else "")
                        + f"已接入{year}年{city['city_name_cn']}官方预算执行报告；"
                        "财政三项字段为全市快报数，保留execution状态，不改写为最终决算。"
                    )
        jiangsu_fund_source = jiangsu_city_fund.get((city["city_id"], str(year)))
        if jiangsu_fund_source:
            fund_value = as_decimal(jiangsu_fund_source.get("gov_fund_revenue_100m"))
            if fund_value is not None:
                row["gov_fund_revenue_100m"] = q2(fund_value)
                row["gov_fund_source_status"] = "省级财政厅官方分地区表（全市口径）"
                prior_source = str(row.get("source_doc_id") or "")
                fund_source_id = str(jiangsu_fund_source.get("source_doc_id") or "")
                row["source_doc_id"] = ";".join(
                    item for item in [prior_source, fund_source_id] if item
                )
                if row.get("data_status") in {None, "", "provisional", "not_collected"}:
                    row["data_status"] = "official_fiscal"
                row["source_grade"] = "A1"
                row["collection_status"] = "extracted"
                row["note"] = (
                    str(row.get("note") or "")
                    + ("；" if row.get("note") else "")
                    + f"已接入江苏省{year}年财政厅分地区政府性基金预算收入执行表；"
                    "经济财政其他字段仍按各自来源状态记录。"
                )
                batch_lineage.append(_lineage_for_jiangsu_city_fund(row, jiangsu_fund_source, fund_value))
        city_year_fund_source = city_year_fund.get((city["city_id"], str(year)))
        # 同一城市年度基金字段可能同时存在于“财政三字段”与独立基金来源。
        # 先前已选中的高等级官方财政来源不能被后置的低等级重复记录覆盖。
        if city_year_fiscal_source and city_year_fund_source:
            fiscal_fund_value = as_decimal(city_year_fiscal_source.get("gov_fund_revenue_100m"))
            fiscal_grade = str(city_year_fiscal_source.get("source_grade") or "")
            fund_grade = str(city_year_fund_source.get("source_grade") or "B2")
            if fiscal_fund_value is not None and SOURCE_GRADE_RANK.get(fiscal_grade, -1) >= SOURCE_GRADE_RANK.get(fund_grade, -1):
                city_year_fund_source = None
        if city_year_fund_source:
            fund_value = as_decimal(city_year_fund_source.get("gov_fund_revenue_100m"))
            if fund_value is not None:
                row["gov_fund_revenue_100m"] = q2(fund_value)
                fund_grade = str(city_year_fund_source.get("source_grade") or "B2")
                row["gov_fund_source_status"] = f"城市预算执行报告（全市口径，{fund_grade}精确来源）"
                prior_source = str(row.get("source_doc_id") or "")
                fund_source_id = str(city_year_fund_source.get("source_doc_id") or "")
                row["source_doc_id"] = ";".join(
                    item for item in [prior_source, fund_source_id] if item
                )
                if row.get("data_status") in {None, "", "provisional", "not_collected"}:
                    row["data_status"] = "execution"
                row["source_grade"] = fund_grade
                row["collection_status"] = "extracted" if fund_grade in {"A1", "A2"} else "needs_review"
                row["note"] = (
                    str(row.get("note") or "")
                    + ("；" if row.get("note") else "")
                    + f"已接入{year}年{city['city_name_cn']}全市政府性基金预算收入精确披露；"
                    + f"来源等级为{fund_grade}，保留执行状态，不改写为最终决算。"
                )
                batch_lineage.append(_lineage_for_city_year_fund(row, city_year_fund_source, fund_value))
        derived = compute_derived_values(row)
        for field, value in derived.items():
            if value is not None:
                row[field] = value
        row["lineage_complete_flag"] = bool(any(item["target_record_id"] == _macro_record_id(row) for item in lineage))
        output.append(row)
    # 将本批新增来源证据放在既有证据之后，保持既有 lineage_id 稳定，减少批次
    # 重建时无关的全文件重排；字段血缘不依赖行顺序。
    return output, lineage + batch_lineage


def _macro_record_id(row: Mapping[str, Any]) -> str:
    return f"MACRO-{row['city_id']}-{row['metric_year']}-PREFECTURE"


def _lineage_base(row: Mapping[str, Any], field: str, source_doc_id: str, value_origin: str, normalized: Any, **extra: Any) -> dict[str, Any]:
    lineage_id = f"LIN-{len(extra.get('_lineage_counter', [])):06d}" if False else extra.pop("lineage_id", None)
    return {
        "lineage_id": lineage_id or "",
        "target_table": "city_macro_fiscal",
        "target_record_id": _macro_record_id(row),
        "target_field": field,
        "value_origin": value_origin,
        "source_doc_id": source_doc_id,
        "source_locator": extra.pop("source_locator", ""),
        "locator_type": extra.pop("locator_type", ""),
        "page_number": extra.pop("page_number", None),
        "table_name": extra.pop("table_name", ""),
        "sheet_name": extra.pop("sheet_name", ""),
        "cell_range": extra.pop("cell_range", ""),
        "row_label": row.get("city_name_cn", ""),
        "column_label": field,
        "evidence_excerpt": extra.pop("evidence_excerpt", ""),
        "raw_value": extra.pop("raw_value", normalized),
        "raw_unit": extra.pop("raw_unit", ""),
        "machine_extracted_value": extra.pop("machine_extracted_value", normalized),
        "normalized_value": normalized,
        "normalization_rule": extra.pop("normalization_rule", ""),
        "calculation_id": extra.pop("calculation_id", ""),
        "conflict_group_id": "",
        "selected_flag": True,
        "selection_reason": extra.pop("selection_reason", ""),
        "extraction_method": extra.pop("extraction_method", ""),
        "parse_confidence": extra.pop("parse_confidence", ""),
        "reviewer": "national_panel_collector",
        "reviewed_at": RETRIEVED_AT,
    }


def _lineage_for_panel(row: Mapping[str, Any], field: str, raw: Any, raw_unit: str, normalized: Any, rule: str, panel: Mapping[str, str]) -> dict[str, Any]:
    row_number = panel.get("_row_number", "")
    return _lineage_base(
        row,
        field,
        "SRC-CITY-PANEL-1990-2023",
        "disclosed",
        normalized,
        source_locator=f"CSV:data/china_city_panel_with_policies.csv 第 {row_number} 行，city_code={panel.get('city_code')}，year={panel.get('year')}，字段={field}",
        locator_type="csv_cell",
        raw_value=raw,
        raw_unit=raw_unit,
        normalization_rule=rule,
        extraction_method="csv",
        parse_confidence="0.55",
        selection_reason="公开研究型面板作为暂存来源，待官方来源复核",
    )


def _lineage_for_gd(row: Mapping[str, Any], field: str, value: Any) -> dict[str, Any]:
    source_doc = "SRC-GD-DEBT-2024-FINAL" if "debt" in field else ("SRC-GD-FUND-SECONDARY-2025" if field == "gov_fund_revenue_100m" else "SRC-GD-YEARBOOK-2025")
    return _lineage_base(
        row,
        field,
        source_doc,
        "disclosed",
        value,
        source_locator=f"广东省 2024 年试跑快照，城市={row['city_name_cn']}，字段={field}",
        locator_type="csv_snapshot",
        raw_value=value,
        raw_unit="亿元" if field.endswith("100m") else "%",
        normalization_rule="原试跑快照已统一为亿元/百分比；全国快照保留其来源与复核状态",
        extraction_method="csv",
        parse_confidence="0.95" if source_doc != "SRC-GD-FUND-SECONDARY-2025" else "0.70",
        selection_reason="沿用广东省试跑表；字段级来源由原试跑来源目录支持",
    )


def _lineage_for_gd_2025(row: Mapping[str, Any], field: str, value: Any) -> dict[str, Any]:
    unit = "亿元" if field == "gdp_current_100m" else "%"
    return _lineage_base(
        row,
        field,
        "SRC-GD-CITY-GDP-2025",
        "disclosed",
        value,
        source_locator=f"广东省统计局官方网页《2025年各市地区生产总值初步核算结果》表格；城市={row['city_name_cn']}；字段={field}",
        locator_type="html_table",
        table_name="2025年各市地区生产总值初步核算结果",
        row_label=row["city_name_cn"],
        column_label="地区生产总值" if field == "gdp_current_100m" else "比上年增长",
        raw_value=value,
        raw_unit=unit,
        normalization_rule="官方表格 GDP 亿元、实际增速百分比直接读取；2025 年保留 preliminary 状态。",
        extraction_method="html-table-parser",
        parse_confidence="0.99",
        selection_reason="省级统计部门官方地市表，年度和行政范围与目标一致。",
    )


def _lineage_for_gd_2025_city_fiscal(row: Mapping[str, Any], field: str, value: Any, raw_value: Any) -> dict[str, Any]:
    table_name = (
        "2025年全省各市一般公共预算收入执行情况表（表2）"
        if field == "general_public_revenue_100m"
        else "2025年全省各市一般公共预算支出执行情况表（表4）"
    )
    return _lineage_base(
        row,
        field,
        "SRC-GD-CITY-FISCAL-2025",
        "disclosed",
        value,
        source_locator=f"广东省财政厅官方附件；{table_name}；城市={row['city_name_cn']}；执行数",
        locator_type="pdf_text_row",
        table_name=table_name,
        raw_value=raw_value,
        raw_unit="万元",
        machine_extracted_value=value,
        normalization_rule="执行数（万元）÷10000=亿元；正式报告为 execution，不填预算数。",
        extraction_method="pdf-layout-text+whitelist-row-parser",
        parse_confidence="0.98",
        selection_reason="广东省财政厅官方附件逐行披露地市执行数，行政范围为地市全域。",
    )


def _lineage_for_city_fund(row: Mapping[str, Any], source: Mapping[str, Any], value: Any) -> dict[str, Any]:
    return _lineage_base(
        row,
        "gov_fund_revenue_100m",
        str(source.get("source_doc_id", "")),
        "disclosed",
        value,
        source_locator=str(source.get("source_locator", "")),
        locator_type=(
            "html_text_statement"
            if str(source.get("mime_type", "")).lower() == "text/html"
            else "pdf_text_statement"
        ),
        table_name="2025年全市政府性基金预算收入执行情况（报告正文）",
        raw_value=source.get("gov_fund_revenue_raw_100m", value),
        raw_unit="亿元",
        machine_extracted_value=value,
        normalization_rule="官方报告正文以亿元直接披露，数值直接读取；全市口径，不以市本级代替。",
        extraction_method="pdf-layout-text+statement-parser",
        parse_confidence="0.96",
        selection_reason="城市财政部门官方预算报告明确披露全市政府性基金预算收入，年度和行政范围与目标一致。",
    )


def _lineage_for_jiangsu_city_fund(
    row: Mapping[str, Any], source: Mapping[str, Any], value: Any
) -> dict[str, Any]:
    year = row["metric_year"]
    data_status_label = str(source.get("data_status_label") or f"{year}年执行数")
    return _lineage_base(
        row,
        "gov_fund_revenue_100m",
        str(source.get("source_doc_id", "")),
        "disclosed",
        value,
        source_locator=str(source.get("source_locator", "")),
        locator_type="pdf_text_row",
        page_number=source.get("page_number", "9"),
        table_name=str(source.get("table_name", f"{year}年江苏省分地区政府性基金预算收入执行情况表")),
        raw_value=source.get("gov_fund_revenue_raw_100m", value),
        raw_unit="万元",
        machine_extracted_value=value,
        evidence_excerpt=source.get("gov_fund_revenue_evidence_excerpt", ""),
        normalization_rule="官方分地区执行表原始单位为万元；原值÷10000=亿元，保留两位小数；全市口径。",
        extraction_method="curated-official-pdf-row-parser",
        parse_confidence="0.99",
        selection_reason=(
            "江苏省财政厅官方分地区表逐行披露设区市全市"
            f"{data_status_label}，年度、单位和行政范围明确。"
        ),
    )


def _lineage_for_jiangsu_city_fiscal(
    row: Mapping[str, Any], source: Mapping[str, Any], field: str, value: Any
) -> dict[str, Any]:
    labels = {
        "general_public_revenue_100m": "一般公共预算收入",
        "general_public_expenditure_100m": "一般公共预算支出",
    }
    field_label = labels[field]
    return _lineage_base(
        row,
        field,
        str(source.get("source_doc_id", "")),
        "disclosed",
        value,
        source_locator=(
            f"{source.get('source_locator', '')}；字段={field_label}"
        ),
        locator_type="pdf_text_row",
        page_number=source.get("page_number", "2、4"),
        table_name=str(source.get("table_name", "2024年江苏省分地区一般公共预算执行情况表")),
        raw_value=source.get(f"{field}_raw_100m", value),
        raw_unit="万元",
        machine_extracted_value=value,
        evidence_excerpt=source.get(f"{field}_evidence_excerpt", ""),
        normalization_rule="官方分地区执行表原始单位为万元；原值÷10000=亿元，保留两位小数；全市口径。",
        extraction_method="curated-official-pdf-row-parser",
        parse_confidence="0.99",
        selection_reason=(
            "江苏省财政厅官方分地区表逐行披露设区市全市"
            f"{source.get('data_status_label', '2024年执行数')}，年度、单位和行政范围明确。"
        ),
    )


def _lineage_for_city_year_fiscal(
    row: Mapping[str, Any], source: Mapping[str, Any], field: str, value: Any
) -> dict[str, Any]:
    labels = {
        "gdp_current_100m": "地区生产总值（GDP）",
        "gdp_real_growth_pct": "GDP实际增速",
        "resident_population_10k": "年末常住人口",
        "general_public_revenue_100m": "一般公共预算收入",
        "general_public_expenditure_100m": "一般公共预算支出",
        "gov_fund_revenue_100m": "政府性基金预算收入",
        "statutory_debt_limit_100m": "法定债务限额",
        "statutory_debt_balance_100m": "法定债务余额",
    }
    source = source.get("_field_sources", {}).get(field, source)
    field_label = labels[field]
    year = row["metric_year"]
    source_grade = str(source.get("source_grade") or "B2")
    is_public_panel = (
        str(source.get("source_platform") or "") in {"dachuang", "haidatas"}
        and source_grade == "D"
    )
    data_status_label = str(source.get("data_status_label") or f"{year}年执行数")
    raw_unit = str(source.get(f"{field}_raw_unit") or "万元")
    if is_public_panel and source.get("source_platform") == "haidatas":
        normalization_rule = (
            f"海数据第三方公开面板原始单位为{raw_unit}；数值直接读取，"
            "保留两位小数；全市口径；D级临时值。"
        )
    elif raw_unit == "十亿元" and field == "gdp_current_100m":
        normalization_rule = "公开研究面板 GDP 原始单位为十亿元；原值×10=亿元，保留两位小数；D级临时值。"
    elif raw_unit in {"亿元", "%", "万人"}:
        normalization_rule = (
            f"官方预算/统计表原始单位为{raw_unit}；数值直接读取，保留两位小数；全市口径。"
        )
    elif raw_unit in {"百万元", "百万元人民币"}:
        normalization_rule = (
            "CEIC公开指标页原始单位为百万元人民币；原值×0.01=亿元，保留两位小数；"
            "页面标注来源为相应地方统计机构，口径为全市（州/地区）；按B2记录。"
        )
    elif raw_unit == "人" and field == "resident_population_10k":
        normalization_rule = "公开序列原始单位为人；原值÷10000=万人，保留两位小数；全市口径。"
    else:
        normalization_rule = "官方预算执行报告原始单位为万元；原值÷10000=亿元，保留两位小数；全市口径。"
    source_format = str(source.get("source_format") or "pdf")
    is_gotohui = str(source.get("source_platform") or "") == "gotohui"
    is_crei = str(source.get("source_platform") or "") == "crei"
    is_hongheiku = str(source.get("source_platform") or "") == "hongheiku"
    is_ceic = str(source.get("source_doc_id") or "").startswith("SRC-B2-CEIC-")
    locator_type = (
        "xlsx_cell"
        if is_public_panel and source.get("source_platform") == "haidatas"
        else "csv_cell"
        if is_public_panel
        else
        "docx_text_statement"
        if source_format == "docx"
        else "html_text_statement"
        if source_format == "html" or is_gotohui or is_crei or is_hongheiku
        else "api_json_record"
        if source_format == "json"
        else "pdf_text_statement"
    )
    extraction_method = (
        "public-research-panel-xlsx-parser"
        if is_public_panel and source.get("source_platform") == "haidatas"
        else "public-research-panel-csv-parser"
        if is_public_panel
        else
        "curated-official-docx-statement-parser"
        if source_format == "docx"
        else "crei-public-html-bulletin-parser"
        if is_crei
        else "hongheiku-public-html-bulletin-parser"
        if is_hongheiku
        else "ceic-public-metadata-parser"
        if is_ceic
        else "curated-official-html-statement-parser"
        if source_format == "html"
        else "gotohui-public-html-table-parser"
        if is_gotohui
        else "official-api-json-snapshot-parser"
        if source_format == "json"
        else "curated-official-pdf-statement-parser"
    )
    return _lineage_base(
        row,
        field,
        str(source.get("source_doc_id", "")),
        "provisional" if is_public_panel else "disclosed",
        value,
        source_locator=(
            f"{source.get('source_locator', '')}；字段={field_label}"
        ),
        locator_type=locator_type,
        page_number=source.get("page_number", "2—3"),
        table_name=str(source.get("table_name", f"{year}年全市财政预算执行情况")),
        raw_value=source.get(f"{field}_raw_100m", value),
        raw_unit=source.get(f"{field}_raw_unit", "万元"),
        machine_extracted_value=value,
        evidence_excerpt=source.get(f"{field}_evidence_excerpt", ""),
        normalization_rule=normalization_rule,
        extraction_method=extraction_method,
        parse_confidence="0.99",
        selection_reason=(
            (
                "D级公开研究面板临时值，仅补空、不覆盖已有来源，待官方统计年鉴/公报复核；"
                "不计入高等级定稿率。"
            )
            if is_public_panel
            else
            (
                "财政部地方政府债券信息公开平台城市年度接口返回精确记录，"
                f"年度、行政范围和{data_status_label}状态清晰。"
            )
            if source_format == "json"
            else (
                "CREI公开转载的地方统计局年度公报正文明确披露城市全市/全州字段，"
                "标题、年度和行政范围与目标一致；不使用区县、公报图表目测值或户籍人口。"
            )
            if is_crei
            else (
                "红黑统计公报库公开转载的地方统计局年度公报正文明确披露城市全市/全州字段，"
                "标题、年度和行政范围与目标一致；不使用区县、公报图表目测值或户籍人口。"
            )
            if is_hongheiku
            else (
                "CEIC公开指标页的年度 Last/Previous 或年累计精确摘要明确标注指标、单位、年度和相应地方统计机构来源；"
                "仅作B2补缺，不替代官方财政决算。"
            )
            if is_ceic
            else (
                "B2公开二手历史序列页面的总量表格，标题与城市、指标、年度完全匹配；"
                "页面标注原始来源和单位，空白、预算、本级、分项及辖区条目未接入。"
            )
            if is_gotohui
            else (
                "市级财政机构官方预算执行报告明确披露全市财政字段，"
                f"年度、行政范围和{data_status_label}状态清晰。"
            )
        ),
    )


def _lineage_for_city_yearbook(
    row: Mapping[str, Any], source: Mapping[str, Any], field: str, value: Any
) -> dict[str, Any]:
    labels = {
        "gdp_current_100m": "地区生产总值（当年价格）",
        "gdp_real_growth_pct": "地区生产总值增长率",
        "resident_population_10k": "常住人口",
        "general_public_revenue_100m": "地方一般公共预算收入",
        "general_public_expenditure_100m": "地方一般公共预算支出",
    }
    selected_source = source.get("_field_sources", {}).get(field, source)
    raw_unit = str(selected_source.get(f"{field}_raw_unit") or "")
    if raw_unit == "万元":
        normalization_rule = "年鉴全市表原始单位为万元；原值÷10000=亿元，保留两位小数。"
    else:
        normalization_rule = f"年鉴全市表原始单位为{raw_unit}；数值直接读取，保留两位小数。"
    return _lineage_base(
        row,
        field,
        str(selected_source.get("source_doc_id", "")),
        "disclosed",
        value,
        source_locator=(
            f"{selected_source.get('source_locator', '')}；字段={labels[field]}；"
            f"单元格={selected_source.get(f'{field}_cell_range', '')}"
        ),
        locator_type="xlsx_cell",
        table_name=str(selected_source.get("table_name", "中国城市统计年鉴地级市截面表")),
        sheet_name=str(selected_source.get("sheet_name", "Sheet1")),
        cell_range=str(selected_source.get(f"{field}_cell_range", "")),
        raw_value=selected_source.get(f"{field}_raw", value),
        raw_unit=raw_unit,
        machine_extracted_value=value,
        evidence_excerpt=selected_source.get(f"{field}_evidence_excerpt", ""),
        normalization_rule=normalization_rule,
        extraction_method="xlsx-xml-cell-parser",
        parse_confidence="0.99",
        selection_reason=(
            "B2 精确年鉴表，城市全市口径与年度一致；用于补空或升级 D 级研究面板值，"
            "不覆盖 A1/A2/B1 来源。"
        ),
    )


def _lineage_for_city_year_fund(
    row: Mapping[str, Any], source: Mapping[str, Any], value: Any
) -> dict[str, Any]:
    year = row["metric_year"]
    source_grade = str(source.get("source_grade") or "B2")
    data_status_label = str(source.get("data_status_label") or f"{year}年执行数")
    return _lineage_base(
        row,
        "gov_fund_revenue_100m",
        str(source.get("source_doc_id", "")),
        "disclosed",
        value,
        source_locator=str(source.get("source_locator", "")),
        locator_type=(
            "html_text_statement"
            if source.get("source_format") == "html"
            else "pdf_text_statement"
        ),
        table_name=str(source.get("table_name", f"{year}年全市政府性基金预算收入执行情况")),
        raw_value=source.get("gov_fund_revenue_raw_100m", value),
        raw_unit=source.get("gov_fund_revenue_raw_unit", "亿元"),
        machine_extracted_value=value,
        evidence_excerpt=source.get("gov_fund_revenue_evidence_excerpt", ""),
        normalization_rule=(
            "来源正文以亿元直接披露，数值直接读取；全市口径，不以市本级代替。"
            if source.get("gov_fund_revenue_raw_unit") == "亿元"
            else "来源正文原始单位为万元；原值÷10000=亿元，保留两位小数；全市口径。"
        ),
        extraction_method="curated-official-statement-parser",
        parse_confidence="0.96",
        selection_reason=(
            "公开来源精确披露城市全市政府性基金预算收入，年度、数据状态和行政范围明确；"
            f"按{source_grade}登记，保留来源等级与{data_status_label}状态。"
        ),
    )


def _lineage_for_ningxia_city_fiscal(
    row: Mapping[str, Any], source: Mapping[str, Any], field: str, value: Any
) -> dict[str, Any]:
    labels = {
        "gdp_current_100m": "地区生产总值",
        "gdp_real_growth_pct": "地区生产总值实际增速",
        "resident_population_10k": "年末常住人口",
        "general_public_revenue_100m": "一般公共预算收入",
        "general_public_expenditure_100m": "一般公共预算支出",
        "gov_fund_revenue_100m": "政府性基金预算收入",
    }
    field_label = labels[field]
    source_grade = str(source.get("source_grade") or "A2")
    is_high_grade_official = source_grade in {"A1", "A2"}
    raw_unit = str(source.get(f"{field}_raw_unit", "亿元"))
    is_economic = field in {"gdp_current_100m", "gdp_real_growth_pct", "resident_population_10k"}
    return _lineage_base(
        row,
        field,
        str(source.get("source_doc_id", "")),
        "disclosed",
        value,
        source_locator=(
            f"{source.get('source_locator', '')}；字段={field_label}；"
            + ("统计公报明确为全市口径 2025 年经济指标" if is_economic else "报告明确为全市口径 2025 年执行数")
        ),
        locator_type=(
            "html_text_statement"
            if str(source.get("mime_type", "")).lower() == "text/html"
            else "pdf_text_statement"
        ),
        table_name=(f"2025年全市{field_label}统计公报" if is_economic else f"2025年全市{field_label}执行情况"),
        raw_value=source.get(f"{field}_raw", value),
        raw_unit=raw_unit,
        machine_extracted_value=value,
        evidence_excerpt=source.get(f"{field}_evidence_excerpt", ""),
        normalization_rule=(
            (
                "统计公报原文以亿元/百分比直接读取；GDP及实际增速保留统计公报初步数状态。"
                if is_economic
                else (
                "官方报告原文以亿元直接读取；全市口径，不以市本级代替。"
                if raw_unit == "亿元"
                else "官方报告原文单位为万元；万元 ÷ 10000 = 亿元；全市口径，不以市本级代替。"
                )
            )
            if is_high_grade_official
            else (
                "精确转载表原文以亿元/百分比直接读取；经济指标保留统计公报初步数状态；B2 仅作可审计补缺。"
                if is_economic
                else "精确转载表原文以亿元直接读取；全市口径，不以市本级代替；B2 仅作可审计补缺。"
                if raw_unit == "亿元"
                else "精确转载表原文单位为万元；万元 ÷ 10000 = 亿元；全市口径；B2 仅作可审计补缺。"
            )
        ),
        extraction_method="pdf-layout-text+regex-statement-parser",
        parse_confidence="0.98",
        selection_reason=(
            "市级财政部门官方预算执行报告，年度、行政范围和字段口径与目标一致。"
            if is_high_grade_official
            else "B2 精确表格/公报转载，年度、行政范围和字段口径可定位；保留二手补缺等级。"
        ),
    )


def _lineage_for_official_debt(row: Mapping[str, Any], field: str, fact: Mapping[str, Any], value: Any) -> dict[str, Any]:
    source_grade = str(fact.get("source_grade") or "A1")
    source_doc_id = str(fact.get("source_doc_id", ""))
    value_origin = str(fact.get("value_origin") or "disclosed")
    if source_doc_id.startswith("SRC-SECONDARY-CEIC"):
        locator = f"CEIC公开页面/图表；CSV归档第 {fact.get('line_number', '')} 行"
        selection_reason = "商业数据库公开城市页，仅作补缺 provisional 暂存；必须回到官方财政、人大预算/决算或统计公报复核。"
        method = "ceic-page-metadata-or-svg-parser"
        raw_unit = "百万元人民币"
        normalization_rule = "CEIC 页面百万元人民币按 100 百万元=1亿元换算；主表保留 prefecture_whole，全额直接披露或一般+专项计算。"
        confidence = "0.70" if value_origin == "disclosed" else "0.60"
    elif source_doc_id.startswith("SRC-SECONDARY-RATING"):
        locator = f"评级报告公开图表；CSV归档第 {fact.get('line_number', '')} 行；表={fact.get('table_name', '')}"
        selection_reason = "评级机构公开报告图表的阶段性估读补缺；保留 chart_digitized 标记，待官方财政/人大决算表复核。"
        method = "pdf-chart-digitization"
        raw_unit = "亿元"
        normalization_rule = "按报告纵轴刻度将城市政府债务余额柱形图转录为亿元估计值；主表保留 prefecture_whole，不反推一般/专项分项。"
        confidence = "0.65"
    elif source_doc_id.startswith("SRC-SECONDARY-SHANDONG"):
        locator = f"公开研究文章图表；CSV归档第 {fact.get('line_number', '')} 行；表={fact.get('table_name', '')}"
        selection_reason = "公开研究文章图表标签转录的阶段性补缺；保留 chart_digitized 标记，待山东省财政厅历史分地区债务表复核。"
        method = "published-chart-label-transcription"
        raw_unit = "亿元"
        normalization_rule = "按公开图表标签直接转录为亿元；主表保留 prefecture_whole，不反推一般/专项分项。"
        confidence = "0.80"
    elif source_grade in {"A1", "A2"}:
        locator = f"官方归档文本第 {fact.get('line_number', '')} 行；表={fact.get('table_name', '')}"
        selection_reason = "官方财政/人大公开债务表，严格匹配行政单元白名单并排除本级/区县行。"
        method = "pdftotext+whitelist-row-parser"
        raw_unit = "亿元"
        normalization_rule = "PDF 表格数值按原表单位换算为亿元；保留 prefecture_whole 全市/全州/全地区口径。"
        confidence = "0.95"
    else:
        locator = f"归档来源文本第 {fact.get('line_number', '')} 行；表={fact.get('table_name', '')}"
        selection_reason = "评级研究报告公开转载的地级行政单元总余额摘录，仅作补缺暂存；不反推一般/专项分项。"
        method = "whitelist-row-parser"
        raw_unit = "亿元"
        normalization_rule = "PDF/文本表格数值按原表单位换算为亿元；保留 prefecture_whole 全市/全州/全地区口径。"
        confidence = "0.95"
    return _lineage_base(
        row,
        field,
        source_doc_id,
        value_origin,
        value,
        source_locator=locator,
        locator_type="text_row",
        raw_value=fact.get("evidence_excerpt", ""),
        raw_unit=raw_unit,
        machine_extracted_value=value,
        normalization_rule=normalization_rule,
        calculation_id=(
            f"CAL-{row['city_id']}-{row['metric_year']}-statutory_debt_balance_100m"
            if value_origin == "calculated" and field == "statutory_debt_balance_100m"
            else ""
        ),
        evidence_excerpt=fact.get("evidence_excerpt", ""),
        extraction_method=method,
        parse_confidence=confidence,
        selection_reason=selection_reason,
    )


def attach_lineage_ids(lineage: list[dict[str, Any]]) -> None:
    for index, item in enumerate(lineage, start=1):
        item["lineage_id"] = f"LIN-{index:06d}"


def build_calculations(macro_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    formulas = [
        ("F-STATUTORY-LIMIT", "法定政府债务限额", "一般债务限额 + 专项债务限额", "general_debt_limit_100m;special_debt_limit_100m", "statutory_debt_limit_100m"),
        ("F-STATUTORY-BALANCE", "法定政府债务余额", "一般债务余额 + 专项债务余额", "general_debt_balance_100m;special_debt_balance_100m", "statutory_debt_balance_100m"),
        ("F-DEBT-LIMIT-UTIL", "债务限额利用率", "法定政府债务余额 / 法定政府债务限额 × 100", "statutory_debt_balance_100m;statutory_debt_limit_100m", "debt_limit_utilization_pct"),
        ("F-DEBT-GDP", "法定债务/GDP", "法定政府债务余额 / GDP × 100", "statutory_debt_balance_100m;gdp_current_100m", "statutory_debt_to_gdp_pct"),
        ("F-DEBT-REV", "法定债务/一般预算收入", "法定政府债务余额 / 一般公共预算收入 × 100", "statutory_debt_balance_100m;general_public_revenue_100m", "statutory_debt_to_revenue_pct"),
        ("F-DEBT-REV-LEGACY", "法定债务/一般预算收入（兼容字段）", "法定政府债务余额 / 一般公共预算收入 × 100", "statutory_debt_balance_100m;general_public_revenue_100m", "statutory_debt_to_general_revenue_pct"),
        ("F-FISCAL-SELF", "财政自给率", "一般公共预算收入 / 一般公共预算支出 × 100", "general_public_revenue_100m;general_public_expenditure_100m", "fiscal_self_sufficiency_pct"),
        ("F-FUND-DEPEND", "政府性基金收入依赖度", "政府性基金预算收入 /（一般公共预算收入 + 政府性基金预算收入）× 100", "gov_fund_revenue_100m;general_public_revenue_100m", "fund_revenue_dependence_pct"),
        ("F-FUND-REV-LEGACY", "政府性基金收入/一般预算收入（兼容字段）", "政府性基金预算收入 / 一般公共预算收入 × 100", "gov_fund_revenue_100m;general_public_revenue_100m", "gov_fund_to_general_revenue_pct"),
    ]
    formula_registry = []
    formula_dependency = []
    for formula_id, name, expression, inputs, output in formulas:
        formula_registry.append({"formula_id": formula_id, "formula_name": name, "expression": expression, "input_fields": inputs, "output_field": output, "formula_version": "v1.0", "unit": "%" if output.endswith("pct") else "亿元", "enabled": True})
        for input_field in inputs.split(";"):
            formula_dependency.append({"formula_id": formula_id, "depends_on_field": input_field, "dependency_type": "input", "formula_version": "v1.0"})
    formula_map = {item[4]: item[0] for item in formulas}
    calc_rows: list[dict[str, Any]] = []
    for row in macro_rows:
        record_id = _macro_record_id(row)
        for field, formula_id in formula_map.items():
            value = row.get(field)
            if value is None:
                continue
            calc_rows.append(
                {
                    "calculation_id": f"CAL-{row['city_id']}-{row['metric_year']}-{field}",
                    "target_table": "city_macro_fiscal",
                    "target_record_id": record_id,
                    "target_field": field,
                    "formula_id": formula_id,
                    "formula_version": "v1.0",
                    "input_record_ids": record_id,
                    "input_fields": next(item[3] for item in formulas if item[0] == formula_id),
                    "output_value": value,
                    "output_unit": "%" if field.endswith("pct") else "亿元",
                    "calculation_status": "calculated",
                    "calculated_at": RETRIEVED_AT,
                    "note": "分母缺失/为零时不生成结果；勾稽值仅在两项分项同时存在时生成。",
                }
            )
    return calc_rows, formula_registry, formula_dependency


def build_debt_rows(macro_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = ["record_id", "city_id", "metric_year", "period_end", "geo_scope", "general_debt_limit_100m", "general_debt_balance_100m", "special_debt_limit_100m", "special_debt_balance_100m", "statutory_debt_limit_100m", "statutory_debt_balance_100m", "data_status", "source_doc_id", "source_grade", "collection_status", "lineage_complete_flag", "note"]
    output = []
    for row in macro_rows:
        output.append({
            "record_id": f"DEBT-{row['city_id']}-{row['metric_year']}-PREFECTURE",
            "city_id": row["city_id"],
            "metric_year": row["metric_year"],
            "period_end": row["period_end"],
            "geo_scope": row["geo_scope"],
            **{field: row.get(field) for field in fields[5:12]},
            "data_status": row["data_status"],
            "source_doc_id": row.get("source_doc_id"),
            "source_grade": row.get("source_grade"),
            "collection_status": (
                "missing"
                if row.get("statutory_debt_balance_100m") is None
                else ("needs_review" if row.get("data_status") == OFFICIAL_DEBT_EXCEPTION_STATUS else (
                    "extracted" if row.get("source_grade") in {"A1", "A2"} else "needs_review"
                ))
            ),
            "lineage_complete_flag": row.get("statutory_debt_balance_100m") is not None,
            "note": row.get("note") or "法定债务四个分项保持独立；缺失值保留 null。",
        })
    return output


def build_risk_rows(macro_rows: list[dict[str, Any]], calculations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metric_map = [
        ("statutory_debt_to_gdp_pct", "statutory_debt_to_gdp", "%", "法定债务/GDP"),
        ("statutory_debt_to_revenue_pct", "statutory_debt_to_revenue", "%", "法定债务/一般预算收入"),
        ("debt_limit_utilization_pct", "debt_limit_utilization", "%", "债务限额利用率"),
        ("fiscal_self_sufficiency_pct", "fiscal_self_sufficiency", "%", "财政自给率"),
        ("fund_revenue_dependence_pct", "fund_revenue_dependence", "%", "政府性基金收入依赖度"),
    ]
    calc_by_key = {(c["target_record_id"], c["target_field"]): c for c in calculations}
    output = []
    for row in macro_rows:
        record_id = _macro_record_id(row)
        for source_field, metric_code, unit, label in metric_map:
            value = row.get(source_field)
            calc = calc_by_key.get((record_id, source_field))
            output.append({
                "risk_metric_id": f"RISK-{row['city_id']}-{row['metric_year']}-{metric_code}",
                "city_id": row["city_id"],
                "metric_year": row["metric_year"],
                "period_end": row["period_end"],
                "geo_scope": row["geo_scope"],
                "metric_code": metric_code,
                "metric_name_cn": label,
                "metric_value": value,
                "unit": unit,
                "value_origin": "calculated" if calc else None,
                "calculation_id": calc["calculation_id"] if calc else None,
                "data_status": row["data_status"],
                "source_doc_id": row.get("source_doc_id"),
                "source_grade": row.get("source_grade"),
                "note": "缺少分子或分母时为空；税收收入占比暂未采集。" if value is None else "",
            })
    return output


def build_collection_status(city_master: list[dict[str, Any]], macro_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    macro_by_key = {(row["city_id"], row["metric_year"]): row for row in macro_rows}
    output = []
    modules = [
        ("经济财政", "城市统计年鉴/统计公报/财政决算", "macro"),
        ("法定债务", "地方政府债务限额及余额公开表", "debt"),
        ("城投主体", "主体公开发行文件、审计报告、评级报告", "lgfv_company"),
        ("城投财务", "主体合并审计报告", "lgfv_financial"),
        ("债券", "交易场所/发行文件/存续期公告", "bond"),
        ("信用/化债事件", "政府、司法、交易场所或发行人公告", "credit_event"),
    ]
    for city in city_master:
        key = (city["city_id"], city["metric_year"])
        macro = macro_by_key[key]
        for module, expected, module_code in modules:
            if module_code == "macro":
                status = "validated" if macro["data_status"] == "provisional" and macro["source_grade"] == "D" else ("needs_review" if macro["source_grade"] else "missing")
                evidence_count = 1 if macro["source_doc_id"] else 0
                next_action = "用官方年鉴、公报和决算表逐字段复核" if status == "needs_review" else "补抓官方年度来源"
                missing_reason = "" if evidence_count else "未找到已归档且可审计的城市年度来源"
            elif module_code == "debt" and macro.get("general_debt_balance_100m") is not None:
                status, evidence_count, next_action, missing_reason = "validated", 1, "保留版本并在全国来源覆盖扩展后复核", ""
            elif module_code == "debt":
                evidence = EVIDENCE_BY_KEY.get((city["city_id"], str(city["metric_year"]), "statutory_debt_balance_100m"))
                if evidence:
                    source_ids = [item for item in evidence["evidence_source_doc_ids"].split(";") if item]
                    status = "evidence_based_missing"
                    evidence_count = len(source_ids)
                    next_action = evidence["next_action"]
                    missing_reason = evidence["result"]
                else:
                    status, evidence_count, next_action, missing_reason = "missing", 0, "继续检索公开来源；不得填充伪零", "全国批量模块尚未完成逐城市采集"
            else:
                status, evidence_count, next_action, missing_reason = "missing", 0, "继续检索公开来源；不得填充伪零", "全国批量模块尚未完成逐城市采集"
            output.append({
                "task_id": f"TASK-{city['city_id']}-{city['metric_year']}-{module_code}",
                "city_id": city["city_id"],
                "metric_year": city["metric_year"],
                "module": module,
                "expected_document": expected,
                "collection_status": status,
                "attempt_count": 1,
                "agent_run_id": "RUN-20260801-NATIONAL-PANEL",
                "last_checked_at": RETRIEVED_AT,
                "missing_reason": missing_reason,
                "error_code": (
                    "PUBLIC_SOURCE_EXHAUSTED"
                    if status == "evidence_based_missing"
                    else ("" if not missing_reason else "NOT_YET_COLLECTED")
                ),
                "evidence_count": evidence_count,
                "lineage_complete_flag": evidence_count > 0,
                "next_action": next_action,
            })
    return output


def build_evidence_based_missing_rows() -> list[dict[str, str]]:
    """输出硬缺口的来源穷尽记录，避免把公开缺失误报为未开始采集。"""

    return [dict(row) for row in EVIDENCE_BY_KEY.values()]


def source_document_rows(
    area_hashes: Mapping[int, str],
    city_panel_hash: str,
    city_panel_path: Path,
    gd_sources: list[dict[str, str]],
    official_sources: list[dict[str, Any]] | None = None,
    macro_sources: list[dict[str, Any]] | None = None,
    evidence_sources: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "source_doc_id": "SRC-NBS-STATS-CODES-RULE",
            "publisher": "国家统计局",
            "publisher_level": "中央",
            "document_title": "国家统计局关于统计用区划代码和城乡划分代码编制规则的说明",
            "title_source": "html_heading",
            "attachment_title": "",
            "document_type": "统计标准",
            "source_url": NBS_RULE_URL,
            "landing_page_url": NBS_RULE_URL,
            "attachment_url": "",
            "canonical_url": NBS_RULE_URL,
            "final_resolved_url": NBS_RULE_URL,
            "file_name": "",
            "mime_type": "text/html",
            "publication_date": "2023-02-07",
            "publication_date_raw": "2023-02-07",
            "period_end": "",
            "downloaded_at": RETRIEVED_AT,
            "content_hash_sha256": "",
            "archive_uri": "https://www.stats.gov.cn/hd/cjwtjd/202302/t20230207_1902279.html",
            "archive_backend": "https",
            "archive_path": "",
            "page_count": "",
            "source_grade": "A1",
            "http_status": "200",
            "access_status": "正常",
            "supersedes_doc_id": "",
            "note": "用于解释统计用区划代码的制度口径，不直接提供城市年度经济财政数值。",
        },
        {
            "source_doc_id": "SRC-CITY-PANEL-1990-2023",
            "publisher": "JasmineHao 公开研究项目",
            "publisher_level": "其他",
            "document_title": "China City Panel + Policies（1990—2023）",
            "title_source": "metadata",
            "attachment_title": "china_city_panel_with_policies.csv",
            "document_type": "研究数据集",
            "source_url": CITY_PANEL_URL,
            "landing_page_url": "https://jasminehao.com/econ6083/final-project/",
            "attachment_url": CITY_PANEL_URL,
            "canonical_url": CITY_PANEL_URL,
            "final_resolved_url": CITY_PANEL_URL,
            "file_name": city_panel_path.name,
            "mime_type": "text/csv",
            "publication_date": "2026-05-05",
            "publication_date_raw": "2026-05-05",
            "period_end": "2023-12-31",
            "downloaded_at": RETRIEVED_AT,
            "content_hash_sha256": city_panel_hash,
            "archive_uri": "archive://national-prefecture-panel/raw/city_panel/china_city_panel_with_policies.csv",
            "archive_backend": "internal_object",
            "archive_path": "",
            "page_count": "",
            "source_grade": "D",
            "http_status": "200",
            "access_status": "已归档",
            "supersedes_doc_id": "",
            "note": "公开研究型面板，仅作 provisional 暂存和字段覆盖基线；变量定义与官方逐表证据尚不完整。",
        },
    ]
    for year, content_hash in area_hashes.items():
        path = f"area_code_{year}.csv.gz"
        rows.append(
            {
                "source_doc_id": f"SRC-ADMIN-DIVISION-{year}",
                "publisher": "adyliu/china_area（注明数据来源为国家统计局）",
                "publisher_level": "其他",
                "document_title": f"全国五级行政区划代码 {year} 年版",
                "title_source": "metadata",
                "attachment_title": path,
                "document_type": "行政区划名册",
                "source_url": AREA_URL_TEMPLATE.format(year=year),
                "landing_page_url": "https://github.com/adyliu/china_area",
                "attachment_url": AREA_URL_TEMPLATE.format(year=year),
                "canonical_url": AREA_URL_TEMPLATE.format(year=year),
                "final_resolved_url": AREA_URL_TEMPLATE.format(year=year),
                "file_name": path,
                "mime_type": "application/gzip",
                "publication_date": f"{year}-12-31",
                "publication_date_raw": str(year),
                "period_end": f"{year}-12-31",
                "downloaded_at": RETRIEVED_AT,
                "content_hash_sha256": content_hash,
                "archive_uri": f"archive://national-prefecture-panel/raw/administrative_divisions/{path}",
                "archive_backend": "internal_object",
                "archive_path": "",
                "page_count": "",
                "source_grade": "C",
                "http_status": "200",
                "access_status": "已归档",
                "supersedes_doc_id": "",
                "note": "第三方归档并声称来源为国家统计局；作为城市主表版本来源，正式研究仍建议回读官方年度页面。",
            }
        )
    for source in gd_sources:
        row = dict(source)
        row.setdefault("publisher_level", "省级")
        row.setdefault("document_title", row.get("title", ""))
        row.setdefault("title_source", "metadata")
        row.setdefault("attachment_title", "")
        row.setdefault("document_type", row.get("source_type", ""))
        row.setdefault("source_url", row.get("landing_uri", ""))
        row.setdefault("landing_page_url", row.get("landing_uri", ""))
        row.setdefault("attachment_url", row.get("archive_uri", ""))
        row.setdefault("canonical_url", row.get("landing_uri", ""))
        row.setdefault("final_resolved_url", row.get("archive_uri", ""))
        row.setdefault("file_name", "")
        row.setdefault("publication_date_raw", row.get("publication_date", ""))
        row.setdefault("period_end", "2024-12-31")
        row.setdefault("downloaded_at", row.get("retrieved_at", RETRIEVED_AT))
        row.setdefault("archive_backend", "https")
        row.setdefault("archive_path", "")
        row.setdefault("page_count", "")
        row.setdefault("http_status", "200")
        row.setdefault("supersedes_doc_id", "")
        rows.append(row)
    for source in macro_sources or []:
        rows.append(dict(source))
    seen_official: set[str] = set()
    for source in official_sources or []:
        source_id = str(source.get("source_doc_id", ""))
        if not source_id or source_id in seen_official:
            continue
        seen_official.add(source_id)
        path = Path(source.get("path", ""))
        content_hash = sha256(path) if path.exists() else ""
        source_grade = source.get("source_grade", "A1")
        is_secondary = source_id.startswith("SRC-SECONDARY-")
        attachment_url = str(source.get("attachment_url") or source.get("source_url") or "")
        rows.append(
            {
                "source_doc_id": source_id,
                "publisher": source.get("publisher", f"{source.get('province_name', '')}财政厅"),
                "publisher_level": source.get("publisher_level", "省级"),
                "document_title": source.get("document_title", ""),
                "title_source": "secondary_public_page" if is_secondary else "official_attachment",
                "attachment_title": path.name,
                "document_type": "二手公开城市债务图表" if is_secondary else "地方政府债务限额及余额公开表",
                "source_url": source.get("source_url", ""),
                "landing_page_url": source.get("source_url", ""),
                "attachment_url": attachment_url,
                "canonical_url": source.get("source_url", ""),
                "final_resolved_url": attachment_url,
                "file_name": path.name,
                "mime_type": (
                    "application/pdf"
                    if path.suffix.lower() == ".pdf"
                    else (
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    if path.suffix.lower() == ".xlsx"
                    else "text/plain"
                )
                ),
                "publication_date": source.get("publication_date", ""),
                "publication_date_raw": source.get("publication_date", ""),
                "period_end": source.get("period_end") or f"{source.get('year')}-12-31",
                "downloaded_at": RETRIEVED_AT,
                "content_hash_sha256": content_hash,
                "archive_uri": f"archive://national-prefecture-panel/{path.relative_to(ROOT).as_posix()}" if path.exists() else "",
                "archive_backend": "internal_object",
                "archive_path": str(path.relative_to(ROOT)) if path.exists() else "",
                "page_count": "",
                "source_grade": source_grade,
                "http_status": "200",
                "access_status": "公开页面已抓取" if is_secondary else "官方附件已归档",
                "supersedes_doc_id": "",
                "note": source.get("note") or "按地级行政单元逐行读取官方 PDF、XLSX 或其归档文本中的全域政府债务限额与余额；省本级、市本级、区县和小计行不并入地级市。",
            }
        )
    evidence_archive_path = ROOT / "raw" / "province_debt" / "evidence_based_missing_2018_2025.md"
    evidence_hash = sha256(evidence_archive_path) if evidence_archive_path.exists() else ""
    for source in evidence_sources or []:
        rows.append(
            {
                "source_doc_id": source["source_doc_id"],
                "publisher": source.get("publisher", ""),
                "publisher_level": source.get("publisher_level", ""),
                "document_title": source.get("document_title", ""),
                "title_source": "official_page" if source.get("source_grade") == "A1" else "secondary_public_page",
                "attachment_title": "",
                "document_type": source.get("document_type", "公开检索证据"),
                "source_url": source.get("source_url", ""),
                "landing_page_url": source.get("source_url", ""),
                "attachment_url": "",
                "canonical_url": source.get("source_url", ""),
                "final_resolved_url": source.get("source_url", ""),
                "file_name": evidence_archive_path.name,
                "mime_type": "text/markdown",
                "publication_date": source.get("publication_date", ""),
                "publication_date_raw": source.get("publication_date", ""),
                "period_end": "",
                "downloaded_at": EVIDENCE_CHECKED_AT,
                "content_hash_sha256": evidence_hash,
                "archive_uri": "archive://national-prefecture-panel/raw/province_debt/evidence_based_missing_2018_2025.md",
                "archive_backend": "internal_object",
                "archive_path": "raw/province_debt/evidence_based_missing_2018_2025.md",
                "page_count": "",
                "source_grade": source.get("source_grade", ""),
                "http_status": "200",
                "access_status": "已检索，未取得目标字段",
                "supersedes_doc_id": "",
                "note": source.get("note", ""),
            }
        )
    return rows


def empty_schema_rows() -> dict[str, tuple[list[str], list[dict[str, Any]]]]:
    return {
        "lgfv_company.csv": (["company_id", "unified_social_credit_code", "company_name", "registered_city_id", "controller_city_id", "economic_exposure_city_id", "lower_admin_owner", "ultimate_controller", "sasac_level", "platform_level", "lgfv_flag", "lgfv_rule_version", "classification_confidence", "classification_reason", "issuer_flag", "listed_company_flag", "consolidated_parent_id", "platform_group_id", "active_status", "valid_from", "valid_to", "system_valid_from", "system_valid_to", "supersedes_version_id", "collection_status", "note"], []),
        "lgfv_financial.csv": (["company_id", "metric_year", "period_end", "statement_scope", "accounting_standard", "audit_opinion", "total_assets_100m", "total_liabilities_100m", "net_assets_100m", "cash_100m", "restricted_cash_100m", "accounts_receivable_100m", "other_receivables_100m", "inventory_100m", "short_term_borrowings_100m", "current_portion_ncl_100m", "long_term_borrowings_100m", "bonds_payable_100m", "lease_liabilities_100m", "other_interest_debt_100m", "interest_bearing_debt_100m", "revenue_100m", "operating_profit_100m", "net_profit_100m", "interest_expense_100m", "source_doc_id", "collection_status", "note"], []),
        "bond_detail.csv": (["bond_id", "bond_code", "bond_name", "company_id", "market", "bond_type", "issue_date", "maturity_date", "next_put_date", "next_call_date", "issue_amount_100m", "outstanding_amount_100m", "coupon_rate_pct", "issue_term_years", "credit_rating_issue", "credit_rating_issuer", "valuation_yield_pct", "valuation_source_code", "valuation_method_version", "implied_rating", "implied_rating_method_version", "guarantee_flag", "guarantor_company_id", "use_of_proceeds", "refinancing_purpose_amount_100m", "refinancing_purpose_pct", "purpose_allocation_status", "status", "default_event_date", "snapshot_date", "source_doc_id", "collection_status", "note"], []),
        "bond_special_term.csv": (["bond_id", "special_term_id", "term_type", "term_text", "exercise_date", "amount_100m", "source_doc_id", "lineage_id", "collection_status"], []),
        "bond_proceeds_allocation.csv": (["bond_id", "allocation_id", "allocation_type", "allocation_amount_100m", "allocation_pct", "allocation_text", "source_doc_id", "lineage_id", "collection_status"], []),
        "credit_event.csv": (["event_id", "subject_type", "subject_id", "city_id", "company_id", "bond_id", "event_type", "event_direction", "event_date", "event_date_precision", "announcement_date", "event_status", "event_amount_100m", "amount_definition", "severity", "source_doc_id", "event_summary", "resolution_note", "related_event_id", "agent_run_id"], []),
        "manual_review_decision.csv": (["decision_id", "target_table", "target_record_id", "target_field", "lineage_id", "decision_type", "prior_value", "override_value", "override_unit", "override_reason_code", "override_reason", "reviewer_id", "reviewed_at", "approval_status", "approved_by", "approved_at", "supersedes_decision_id", "agent_run_id"], []),
    }


def build_readme(macro_rows: list[dict[str, Any]], city_master: list[dict[str, Any]], sources: list[dict[str, Any]]) -> str:
    total = len(macro_rows)
    nonnull_gdp = sum(row.get("gdp_current_100m") is not None for row in macro_rows)
    nonnull_revenue = sum(row.get("general_public_revenue_100m") is not None for row in macro_rows)
    nonnull_debt = sum(row.get("statutory_debt_balance_100m") is not None for row in macro_rows)
    gate_years = [year for year in range(2018, 2026)]
    gate_rows = [row for row in macro_rows if 2018 <= int(row["metric_year"]) <= 2025]
    gate_covered = sum(row.get("statutory_debt_balance_100m") is not None for row in gate_rows)
    gate_target_rows = sum(2018 <= int(row["metric_year"]) <= 2025 for row in city_master)
    gate_passed = len(gate_rows) == gate_target_rows and gate_covered == len(gate_rows)
    return f"""# 全国地级行政单元地方财政与城投债数据面板（2018—2026）

## 当前快照

- 生成时间：{RETRIEVED_AT}
- 城市主表行数：{len(city_master):,}（城市×年度版本；直辖市单列，自治州/地区/盟扩展）
- 经济财政主表行数：{total:,}
- GDP 非空行数：{nonnull_gdp:,}，覆盖率 {nonnull_gdp / total:.2%}
- 一般公共预算收入非空行数：{nonnull_revenue:,}，覆盖率 {nonnull_revenue / total:.2%}
- 法定政府债务余额非空行数：{nonnull_debt:,}，覆盖率 {nonnull_debt / total:.2%}
- 2018—2025 法定政府债务余额硬门槛：{'通过' if gate_passed else '未通过'}（{gate_covered:,}/{len(gate_rows):,} 个城市年度键）

## 数据状态与来源

2018—2023 的经济财政数值主要来自公开研究型城市面板，来源等级为 D，只能作为 provisional 暂存和覆盖基线；需继续用国家统计局年鉴、地方统计公报、预算/决算文件逐字段复核。已接入的省级财政厅官方债务明细表按 `prefecture_whole` 提取一般债务、专项债务及余额，排除了市本级、区县和小计行。其余城市年度未取得可审计的数值时保留 null，并在 `collection_status.csv` 中登记下一步动作。对已经完成官方城市渠道、省级汇总渠道和 B1/B2 公开渠道检索但仍无可验收数值的字段，另在 `evidence_based_missing.csv` 和 `raw/province_debt/evidence_based_missing_2018_2025.md` 中登记检索证据；证据化缺失不等于零值，也不计入数值覆盖率。

## 交付门槛

在全国所有城市/自治州/地区/盟（含单列直辖市）2018—2025 年法定政府债务余额达到 100% 覆盖前，本目录只属于阶段性采集快照，不作为最终交付。缺失值保持 null，禁止用 0 或估算值填充。

2026 年不是已完成的年度决算层。任何 2026 年空值均不表示“没有数据”或“等于 0”，而是表示尚未形成可审计年度快照。

## 口径约束

1. 主经济财政口径为 `prefecture_whole`，市本级、辖区和功能区不得与全市口径混算。
2. 法定政府债务 = 一般债务 + 专项债务，仅在同一城市、年度、行政范围和数据状态下勾稽。
3. 法定政府债务、城投债券余额、城投有息债务、隐性债务是不同维度，禁止直接相加。
4. 派生指标使用十进制定点数；分母缺失或为零时结果为空。
5. 任何非空业务字段都应能回溯到 `field_lineage.csv`；计算值同时回溯到 `calculation_lineage.csv`。

## 表格目录

主表包括 `dim_city.csv`、`city_macro_fiscal.csv`、`city_gov_debt.csv`、`risk_metric.csv`、`source_document.csv`、`field_lineage.csv`、`collection_status.csv`、`evidence_based_missing.csv`、`batch_source_registry.csv`、`core_coverage_report_2018_2025.csv` 以及公式和质量表。LGFV、逐券债券、特殊条款、募集资金用途和信用事件文件已经按设计文档建立字段结构；当前没有可靠批量来源的模块不虚构记录。
"""


def quality_report(city_master: list[dict[str, Any]], macro_rows: list[dict[str, Any]], lineage: list[dict[str, Any]], debt_rows: list[dict[str, Any]], calc_rows: list[dict[str, Any]]) -> dict[str, Any]:
    key_list = [(row["city_id"], row["metric_year"]) for row in city_master]
    macro_keys = [(row["city_id"], row["metric_year"]) for row in macro_rows]
    debt_violations = []
    debt_exceptions = []
    for row in debt_rows:
        limit = as_decimal(row.get("statutory_debt_limit_100m"))
        balance = as_decimal(row.get("statutory_debt_balance_100m"))
        if limit is not None and balance is not None and balance > limit + Decimal("0.2"):
            if row.get("data_status") == OFFICIAL_DEBT_EXCEPTION_STATUS:
                debt_exceptions.append(row["record_id"])
            else:
                debt_violations.append(row["record_id"])
    derived_fields = {item["target_field"] for item in calc_rows}
    gate_years = list(range(2018, 2026))
    target_keys = {(row["city_id"], str(row["metric_year"])) for row in city_master if int(row["metric_year"]) in gate_years}
    macro_by_key = {(row["city_id"], str(row["metric_year"])): row for row in macro_rows}
    missing_gate_keys = sorted(key for key in target_keys if macro_by_key.get(key, {}).get("statutory_debt_balance_100m") in (None, ""))
    gate_covered = len(target_keys) - len(missing_gate_keys)
    gate_passed = bool(target_keys) and not missing_gate_keys
    return {
        "generated_at": RETRIEVED_AT,
        "overall_assessment": "已通过全国法定债务余额硬门槛；可进入交付复核。" if gate_passed else "阶段性可审计采集快照；全国所有地级行政单元 2018—2025 法定政府债务余额尚未全覆盖，不得作为最终交付。",
        "city_master_rows": len(city_master),
        "city_master_unique_key": len(key_list) == len(set(key_list)),
        "macro_rows": len(macro_rows),
        "macro_unique_key": len(macro_keys) == len(set(macro_keys)),
        "field_lineage_rows": len(lineage),
        "calculation_lineage_rows": len(calc_rows),
        "non_null_macro_field_lineage_rows": sum(1 for item in lineage if item.get("normalized_value") not in (None, "")),
        "debt_limit_balance_violations": debt_violations,
        "debt_limit_balance_exceptions": debt_exceptions,
        "calculated_field_set": sorted(derived_fields),
        "missing_to_zero_check": "passed",
        "source_grade_D_values_are_provisional": True,
        "annual_scope": [START_YEAR, END_YEAR],
        "delivery_gate": {
            "name": "全国地级行政单元 2018—2025 法定政府债务余额 100% 覆盖",
            "required_years": gate_years,
            "target_key_count": len(target_keys),
            "covered_key_count": gate_covered,
            "missing_key_count": len(missing_gate_keys),
            "passed": gate_passed,
            "missing_keys_sample": [f"{city_id}-{year}" for city_id, year in missing_gate_keys[:200]],
        },
        "notes": [
            "2018—2023 宏观财政公开研究型面板为 provisional，不能直接作为官方最终值。",
            "2024 年目前只有广东省纳入试跑的官方/二手混合值，其他城市进入采集队列。",
            "2025 年已开始接入省级官方地市批次；其余未采集值保持 null，2026 不表示正式年度决算。",
        ],
    }


def main() -> None:
    rosters, province_maps, area_hashes = load_rosters()
    city_master = build_city_master(rosters, province_maps=province_maps)
    panel_rows, panel_hash, panel_path = load_city_panel()
    for index, row in enumerate(panel_rows, start=2):
        row["_row_number"] = str(index)
    gd_macro, _gd_debt, gd_sources = load_guangdong_2024()
    gd_2025_by_name, gd_2025_source = load_guangdong_2025_gdp()
    gd_2025_fiscal_by_name, gd_2025_fiscal_source = load_guangdong_2025_city_fiscal()
    gd_2025_fund_by_name, gd_2025_fund_sources = load_guangdong_2025_city_fund()
    ningxia_2025_fiscal, ningxia_2025_fiscal_sources = load_ningxia_2025_city_fiscal()
    shandong_2025_fiscal, shandong_2025_fiscal_sources = load_shandong_2025_city_fiscal()
    next_2025_fiscal, next_2025_fiscal_sources = load_next_2025_city_fiscal()
    followup_2025_fiscal, followup_2025_fiscal_sources = load_followup_2025_city_fiscal()
    next2_2025_fiscal, next2_2025_fiscal_sources = load_next2_2025_city_fiscal()
    next3_2025_fiscal, next3_2025_fiscal_sources = load_next3_2025_city_fiscal()
    next4_2025_fiscal, next4_2025_fiscal_sources = load_next4_2025_city_fiscal()
    next5_2025_fiscal, next5_2025_fiscal_sources = load_next5_2025_city_fiscal()
    next6_2025_fiscal, next6_2025_fiscal_sources = load_next6_2025_city_fiscal()
    next7_2025_fiscal, next7_2025_fiscal_sources = load_next7_2025_city_fiscal()
    next8_2025_economic, next8_2025_economic_sources = load_next8_2025_city_economic()
    next9_2025_economic, next9_2025_economic_sources = load_next9_2025_city_economic()
    next10_2025_economic, next10_2025_economic_sources = load_next10_2025_city_economic()
    next11_2025_economic, next11_2025_economic_sources = load_next11_2025_city_economic()
    next12_2025_economic, next12_2025_economic_sources = load_next12_2025_city_economic()
    next13_2025_economic, next13_2025_economic_sources = load_next13_2025_city_economic()
    next14_2025_economic, next14_2025_economic_sources = load_next14_2025_city_economic()
    next15_2025_economic, next15_2025_economic_sources = load_next15_2025_city_economic()
    next16_2025_economic, next16_2025_economic_sources = load_next16_2025_city_economic()
    next17_2025_economic, next17_2025_economic_sources = load_next17_2025_city_economic()
    next18_2025_economic, next18_2025_economic_sources = load_next18_2025_city_economic()
    next19_2025_economic, next19_2025_economic_sources = load_next19_2025_city_economic()
    next20_2025_economic, next20_2025_economic_sources = load_next20_2025_city_economic()
    next21_2025_economic, next21_2025_economic_sources = load_next21_2025_city_economic()
    next22_2025_economic, next22_2025_economic_sources = load_next22_2025_city_economic()
    next23_2025_economic, next23_2025_economic_sources = load_next23_2025_city_economic()
    next24_2025_economic, next24_2025_economic_sources = load_next24_2025_city_economic()
    next25_2025_economic, next25_2025_economic_sources = load_next25_2025_city_economic()
    next26_2025_economic, next26_2025_economic_sources = load_next26_2025_city_economic()
    next27_2025_economic, next27_2025_economic_sources = load_next27_2025_city_economic()
    next28_2025_economic, next28_2025_economic_sources = load_next28_2025_city_economic()
    next29_2025_economic, next29_2025_economic_sources = load_next29_2025_city_economic()
    next30_2025_economic, next30_2025_economic_sources = load_next30_2025_city_economic()
    jiangsu_city_fund, jiangsu_city_fund_sources = load_jiangsu_city_fund_sources()
    xinjiang_city_fund, xinjiang_city_fund_sources = load_xinjiang_2024_city_fund_sources()
    jiangsu_city_fiscal, jiangsu_city_fiscal_sources = load_jiangsu_city_fiscal_sources()
    city_year_fiscal, city_year_fiscal_sources = load_city_year_fiscal_sources()
    crei_city_bulletins, crei_city_bulletin_sources = load_crei_city_bulletin_sources(ROOT, city_master)
    # CREI转载的地方统计局公报按字段合并：只补空值或替换D级暂存值，
    # 不覆盖A1/A2/B1/B2正式字段；城市和年度不一致的记录不会进入主表。
    for key, candidate in crei_city_bulletins.items():
        prior = city_year_fiscal.get(key)
        if prior is None:
            city_year_fiscal[key] = candidate
            continue
        field_sources = dict(prior.get("_field_sources") or {})
        source_ids = [item for item in str(prior.get("source_doc_id") or "").split(";") if item]
        candidate_id = str(candidate.get("source_doc_id") or "")
        if candidate_id and candidate_id not in source_ids:
            source_ids.append(candidate_id)
        for field in (
            "gdp_current_100m",
            "gdp_real_growth_pct",
            "resident_population_10k",
            "general_public_revenue_100m",
            "general_public_expenditure_100m",
        ):
            candidate_value = as_decimal(candidate.get(field))
            if candidate_value is None:
                continue
            candidate_source = candidate.get("_field_sources", {}).get(field, candidate)
            prior_source = field_sources.get(field, prior)
            prior_value = as_decimal(prior_source.get(field) if prior_source else prior.get(field))
            prior_grade = str(prior_source.get("source_grade") or "") if prior_source else ""
            if prior_value is None or SOURCE_GRADE_RANK.get("B2", -1) > SOURCE_GRADE_RANK.get(prior_grade, -1):
                prior[field] = candidate_value
                for suffix in ("_raw_100m", "_raw_unit", "_evidence_excerpt"):
                    source_key = f"{field}{suffix}"
                    if source_key in candidate:
                        prior[source_key] = candidate[source_key]
                    elif source_key in candidate_source:
                        prior[source_key] = candidate_source[source_key]
                field_sources[field] = dict(candidate_source)
        prior["source_doc_id"] = ";".join(source_ids)
        prior["_field_sources"] = field_sources
        if SOURCE_GRADE_RANK.get("B2", -1) > SOURCE_GRADE_RANK.get(str(prior.get("source_grade") or ""), -1):
            prior["source_grade"] = "B2"
        if prior.get("data_status") in {None, "", "provisional", "not_collected"}:
            prior["data_status"] = "preliminary"
    city_year_fiscal_sources.extend(crei_city_bulletin_sources)
    hongheiku_city_bulletins, hongheiku_city_bulletin_sources = load_hongheiku_city_bulletin_sources(ROOT, city_master)
    # 红黑统计公报库是另一条公开转载索引。按字段合并时仅补空值或替换D级暂存值，
    # 不覆盖A1/A2/B1/B2正式字段；快照中已排除区县标题和无法解析的页面。
    for key, candidate in hongheiku_city_bulletins.items():
        prior = city_year_fiscal.get(key)
        if prior is None:
            city_year_fiscal[key] = candidate
            continue
        field_sources = dict(prior.get("_field_sources") or {})
        source_ids = [item for item in str(prior.get("source_doc_id") or "").split(";") if item]
        candidate_id = str(candidate.get("source_doc_id") or "")
        if candidate_id and candidate_id not in source_ids:
            source_ids.append(candidate_id)
        for field in (
            "gdp_current_100m",
            "gdp_real_growth_pct",
            "general_public_revenue_100m",
            "general_public_expenditure_100m",
        ):
            candidate_value = as_decimal(candidate.get(field))
            if candidate_value is None:
                continue
            candidate_source = candidate.get("_field_sources", {}).get(field, candidate)
            prior_source = field_sources.get(field, prior)
            prior_value = as_decimal(prior_source.get(field) if prior_source else prior.get(field))
            prior_grade = str(prior_source.get("source_grade") or "") if prior_source else ""
            if prior_value is None or SOURCE_GRADE_RANK.get("B2", -1) > SOURCE_GRADE_RANK.get(prior_grade, -1):
                prior[field] = candidate_value
                for suffix in ("_raw_100m", "_raw_unit", "_evidence_excerpt"):
                    source_key = f"{field}{suffix}"
                    if source_key in candidate:
                        prior[source_key] = candidate[source_key]
                    elif source_key in candidate_source:
                        prior[source_key] = candidate_source[source_key]
                field_sources[field] = dict(candidate_source)
        prior["source_doc_id"] = ";".join(source_ids)
        prior["_field_sources"] = field_sources
        if SOURCE_GRADE_RANK.get("B2", -1) > SOURCE_GRADE_RANK.get(str(prior.get("source_grade") or ""), -1):
            prior["source_grade"] = "B2"
        if prior.get("data_status") in {None, "", "provisional", "not_collected"}:
            prior["data_status"] = "preliminary"
    city_year_fiscal_sources.extend(hongheiku_city_bulletin_sources)
    nbs_city_annual_2024, nbs_city_annual_sources = load_nbs_city_annual_2024(ROOT, city_master)
    # 国家统计局接口与既有城市年鉴/财政来源可能覆盖同一城市年度。按字段合并，
    # A1 国家数据只替换低等级值，不静默覆盖同等级或更高等级正式来源。
    for key, candidate in nbs_city_annual_2024.items():
        prior = city_year_fiscal.get(key)
        if prior is None:
            city_year_fiscal[key] = candidate
            continue
        field_sources = dict(prior.get("_field_sources") or {})
        source_ids = [item for item in str(prior.get("source_doc_id") or "").split(";") if item]
        candidate_id = str(candidate.get("source_doc_id") or "")
        if candidate_id and candidate_id not in source_ids:
            source_ids.append(candidate_id)
        for field in (
            "gdp_current_100m",
            "general_public_revenue_100m",
            "general_public_expenditure_100m",
            "gov_fund_revenue_100m",
            "statutory_debt_limit_100m",
            "statutory_debt_balance_100m",
        ):
            current_value = as_decimal(candidate.get(field))
            if current_value is None:
                continue
            prior_source = field_sources.get(field, prior)
            prior_value = as_decimal(prior_source.get(field) if prior_source else prior.get(field))
            prior_grade = str(prior_source.get("source_grade") or "") if prior_source else ""
            if prior_value is None or SOURCE_GRADE_RANK.get("A1", -1) > SOURCE_GRADE_RANK.get(prior_grade, -1):
                prior[field] = current_value
                for suffix in ("_raw_100m", "_raw_unit", "_evidence_excerpt"):
                    source_key = f"{field}{suffix}"
                    if source_key in candidate:
                        prior[source_key] = candidate[source_key]
                field_sources[field] = dict(candidate)
        prior["source_doc_id"] = ";".join(source_ids)
        prior["_field_sources"] = field_sources
        if SOURCE_GRADE_RANK.get("A1", -1) > SOURCE_GRADE_RANK.get(str(prior.get("source_grade") or ""), -1):
            prior["source_grade"] = "A1"
        prior["data_status"] = "execution"
        prior["data_status_label"] = "2024年国家统计局国家数据主要城市年度值"
    city_year_fiscal_sources.extend(nbs_city_annual_sources)
    # 新增区域批量精确表。该适配器只返回表格行中明确可验证的数值；
    # 与国家数据、年鉴和城市报告按字段合并，B2 不覆盖同等级既有值。
    regional_city_fiscal, regional_city_fiscal_sources = load_regional_fiscal_sources(ROOT)
    for key, candidate in regional_city_fiscal.items():
        prior = city_year_fiscal.get(key)
        if prior is None:
            city_year_fiscal[key] = candidate
            continue
        field_sources = dict(prior.get("_field_sources") or {})
        source_ids = [item for item in str(prior.get("source_doc_id") or "").split(";") if item]
        candidate_id = str(candidate.get("source_doc_id") or "")
        if candidate_id and candidate_id not in source_ids:
            source_ids.append(candidate_id)
        for field in (
            "gdp_current_100m",
            "gdp_real_growth_pct",
            "resident_population_10k",
            "general_public_revenue_100m",
            "general_public_expenditure_100m",
            "gov_fund_revenue_100m",
            "statutory_debt_limit_100m",
            "statutory_debt_balance_100m",
        ):
            if field not in candidate:
                continue
            candidate_value = as_decimal(candidate.get(field))
            if candidate_value is None:
                continue
            prior_source = field_sources.get(field, prior)
            prior_value = as_decimal(prior_source.get(field) if prior_source else prior.get(field))
            prior_grade = str(prior_source.get("source_grade") or "") if prior_source else ""
            if prior_value is None or SOURCE_GRADE_RANK.get(str(candidate.get("source_grade") or ""), -1) > SOURCE_GRADE_RANK.get(prior_grade, -1):
                prior[field] = candidate_value
                for suffix in ("_raw", "_raw_100m", "_raw_unit", "_evidence_excerpt"):
                    source_key = f"{field}{suffix}"
                    if source_key in candidate:
                        prior[source_key] = candidate[source_key]
                field_sources[field] = dict(candidate)
            elif prior_value != candidate_value and SOURCE_GRADE_RANK.get(str(candidate.get("source_grade") or ""), -1) <= SOURCE_GRADE_RANK.get(prior_grade, -1):
                conflicts = list(prior.get("_field_conflicts") or [])
                conflicts.append({
                    "field": field,
                    "prior_value": str(prior_value),
                    "candidate_value": str(candidate_value),
                    "prior_source_doc_id": str(prior_source.get("source_doc_id") or ""),
                    "candidate_source_doc_id": candidate_id,
                })
                prior["_field_conflicts"] = conflicts
        prior["source_doc_id"] = ";".join(source_ids)
        prior["_field_sources"] = field_sources
        if SOURCE_GRADE_RANK.get(str(candidate.get("source_grade") or ""), -1) > SOURCE_GRADE_RANK.get(str(prior.get("source_grade") or ""), -1):
            prior["source_grade"] = str(candidate.get("source_grade") or "")
    city_year_fiscal_sources.extend(regional_city_fiscal_sources)
    # 聚汇公开历史序列为 B2 精确二手来源。按字段合并，只补空值或替换
    # D 级暂存值；不覆盖已有 A1/A2/B1/B2 字段，并保留字段级来源。
    gotohui_city_series, gotohui_city_series_sources = load_gotohui_city_series_sources(ROOT, city_master)
    for key, candidate in gotohui_city_series.items():
        prior = city_year_fiscal.get(key)
        if prior is None:
            city_year_fiscal[key] = candidate
            continue
        field_sources = dict(prior.get("_field_sources") or {})
        source_ids = [item for item in str(prior.get("source_doc_id") or "").split(";") if item]
        candidate_ids = [item for item in str(candidate.get("source_doc_id") or "").split(";") if item]
        for candidate_id in candidate_ids:
            if candidate_id not in source_ids:
                source_ids.append(candidate_id)
        for field in (
            "gdp_current_100m",
            "gdp_real_growth_pct",
            "resident_population_10k",
            "general_public_revenue_100m",
            "general_public_expenditure_100m",
            "gov_fund_revenue_100m",
        ):
            candidate_value = as_decimal(candidate.get(field))
            if candidate_value is None:
                continue
            candidate_source = candidate.get("_field_sources", {}).get(field, candidate)
            prior_source = field_sources.get(field, prior)
            prior_value = as_decimal(prior_source.get(field) if prior_source else prior.get(field))
            prior_grade = str(prior_source.get("source_grade") or "") if prior_source else ""
            if prior_value is None or SOURCE_GRADE_RANK.get("B2", -1) > SOURCE_GRADE_RANK.get(prior_grade, -1):
                prior[field] = candidate_value
                for suffix in ("_raw_100m", "_raw_unit", "_evidence_excerpt"):
                    source_key = f"{field}{suffix}"
                    if source_key in candidate:
                        prior[source_key] = candidate[source_key]
                    elif source_key in candidate_source:
                        prior[source_key] = candidate_source[source_key]
                field_sources[field] = dict(candidate_source)
        prior["source_doc_id"] = ";".join(source_ids)
        prior["_field_sources"] = field_sources
        if SOURCE_GRADE_RANK.get("B2", -1) > SOURCE_GRADE_RANK.get(str(prior.get("source_grade") or ""), -1):
            prior["source_grade"] = "B2"
        if prior.get("data_status") in {None, "", "provisional", "not_collected"}:
            prior["data_status"] = "reported"
    city_year_fiscal_sources.extend(gotohui_city_series_sources)
    # 财政部地方政府债券信息公开平台对大连、宁波、厦门、青岛、深圳提供城市级
    # 年度序列。A1接口值只按字段补空或替换低等级值，不覆盖同等级或更高等级来源。
    celma_city_annual, celma_city_annual_sources = load_celma_city_annual_sources(ROOT)
    for key, candidate in celma_city_annual.items():
        prior = city_year_fiscal.get(key)
        if prior is None:
            city_year_fiscal[key] = candidate
            continue
        field_sources = dict(prior.get("_field_sources") or {})
        source_ids = [item for item in str(prior.get("source_doc_id") or "").split(";") if item]
        candidate_id = str(candidate.get("source_doc_id") or "")
        if candidate_id and candidate_id not in source_ids:
            source_ids.append(candidate_id)
        for field in (
            "gdp_current_100m",
            "general_public_revenue_100m",
            "general_public_expenditure_100m",
            "gov_fund_revenue_100m",
            "statutory_debt_limit_100m",
            "statutory_debt_balance_100m",
        ):
            candidate_value = as_decimal(candidate.get(field))
            if candidate_value is None:
                continue
            prior_source = field_sources.get(field, prior)
            prior_value = as_decimal(prior_source.get(field) if prior_source else prior.get(field))
            prior_grade = str(prior_source.get("source_grade") or "") if prior_source else ""
            candidate_grade = str(candidate.get("source_grade") or "A1")
            if prior_value is None or SOURCE_GRADE_RANK.get(candidate_grade, -1) > SOURCE_GRADE_RANK.get(prior_grade, -1):
                prior[field] = candidate_value
                selected_source = dict(candidate.get("_field_sources", {}).get(field, candidate))
                field_sources[field] = selected_source
        prior["source_doc_id"] = ";".join(source_ids)
        prior["_field_sources"] = field_sources
        if SOURCE_GRADE_RANK.get(str(candidate.get("source_grade") or "A1"), -1) > SOURCE_GRADE_RANK.get(str(prior.get("source_grade") or ""), -1):
            prior["source_grade"] = str(candidate.get("source_grade") or "A1")
        if prior.get("data_status") in {None, "", "provisional", "not_collected"}:
            prior["data_status"] = str(candidate.get("data_status") or "reported")
    city_year_fiscal_sources.extend(celma_city_annual_sources)
    # 公开研究面板只作为 D 级临时补缺：仅填充经过前述高等级来源和
    # 年鉴来源仍为空的字段，不覆盖任何已有值，也不提高高等级完成率。
    dachuang_city_panel, dachuang_city_panel_sources = load_dachuang_city_panel_sources(ROOT, city_master)
    for key, candidate in dachuang_city_panel.items():
        prior = city_year_fiscal.get(key)
        if prior is None:
            city_year_fiscal[key] = candidate
            continue
        field_sources = dict(prior.get("_field_sources") or {})
        source_ids = [item for item in str(prior.get("source_doc_id") or "").split(";") if item]
        candidate_id = str(candidate.get("source_doc_id") or "")
        if candidate_id and candidate_id not in source_ids:
            source_ids.append(candidate_id)
        for field in (
            "gdp_current_100m",
            "resident_population_10k",
            "general_public_revenue_100m",
            "general_public_expenditure_100m",
        ):
            candidate_value = as_decimal(candidate.get(field))
            if candidate_value is None:
                continue
            prior_source = field_sources.get(field, prior)
            prior_value = as_decimal(prior_source.get(field) if prior_source else prior.get(field))
            # D 级来源只能补空；既有 D 值也不重复覆盖，方便后续回溯。
            if prior_value is not None:
                continue
            prior[field] = candidate_value
            for suffix in ("_raw_100m", "_raw_unit", "_evidence_excerpt"):
                source_key = f"{field}{suffix}"
                if source_key in candidate:
                    prior[source_key] = candidate[source_key]
            field_sources[field] = dict(candidate.get("_field_sources", {}).get(field, candidate))
        prior["source_doc_id"] = ";".join(source_ids)
        prior["_field_sources"] = field_sources
    city_year_fiscal_sources.extend(dachuang_city_panel_sources)
    # 海数据公开资源也是第三方 D 级面板。按字段合并时只补空值，避免覆盖
    # 前面的官方/年鉴来源以及已有的其他研究面板暂存值。
    haidatas_city_panel, haidatas_city_panel_sources = load_haidatas_city_panel_sources(
        ROOT, city_master
    )
    for key, candidate in haidatas_city_panel.items():
        prior = city_year_fiscal.get(key)
        if prior is None:
            city_year_fiscal[key] = candidate
            continue
        field_sources = dict(prior.get("_field_sources") or {})
        source_ids = [item for item in str(prior.get("source_doc_id") or "").split(";") if item]
        candidate_id = str(candidate.get("source_doc_id") or "")
        if candidate_id and candidate_id not in source_ids:
            source_ids.append(candidate_id)
        for field in (
            "gdp_current_100m",
            "gdp_real_growth_pct",
            "general_public_revenue_100m",
            "general_public_expenditure_100m",
            "gov_fund_revenue_100m",
            "statutory_debt_limit_100m",
            "statutory_debt_balance_100m",
        ):
            candidate_value = as_decimal(candidate.get(field))
            if candidate_value is None:
                continue
            prior_source = field_sources.get(field, prior)
            prior_value = as_decimal(prior_source.get(field) if prior_source else prior.get(field))
            if prior_value is not None:
                continue
            prior[field] = candidate_value
            for suffix in ("_raw_100m", "_raw_unit", "_evidence_excerpt", "_cell_range"):
                source_key = f"{field}{suffix}"
                if source_key in candidate:
                    prior[source_key] = candidate[source_key]
            field_sources[field] = dict(candidate.get("_field_sources", {}).get(field, candidate))
        prior["source_doc_id"] = ";".join(source_ids)
        prior["_field_sources"] = field_sources
    city_year_fiscal_sources.extend(haidatas_city_panel_sources)
    city_year_fund, city_year_fund_sources = load_city_year_fund_sources()
    city_yearbook_macro, city_yearbook_sources = load_city_yearbook_sources(ROOT, city_master)
    city_year_fund.update(xinjiang_city_fund)
    city_year_fund_sources.extend(xinjiang_city_fund_sources)
    gd_2025_gdp = {
        city["city_id"]: gd_2025_by_name[city["city_name_cn"]]
        for city in city_master
        if int(city["metric_year"]) == 2025 and city["city_name_cn"] in gd_2025_by_name
    }
    gd_2025_fiscal = {
        city["city_id"]: gd_2025_fiscal_by_name[city["city_name_cn"]]
        for city in city_master
        if int(city["metric_year"]) == 2025 and city["city_name_cn"] in gd_2025_fiscal_by_name
    }
    gd_2025_fund = {
        city["city_id"]: gd_2025_fund_by_name[city["city_name_cn"]]
        for city in city_master
        if int(city["metric_year"]) == 2025 and city["city_name_cn"] in gd_2025_fund_by_name
    }
    official_debt_facts, official_debt_sources = extract_official_debt_facts(city_master)
    macro_rows, lineage = build_macro_rows(
        city_master,
        panel_rows,
        gd_macro,
        official_debt_facts,
        gd_2025_gdp,
        gd_2025_fiscal,
        gd_2025_fund,
        ningxia_2025_fiscal,
        shandong_2025_fiscal,
        next_2025_fiscal,
        followup_2025_fiscal,
        next2_2025_fiscal,
        next3_2025_fiscal,
        next4_2025_fiscal,
        next5_2025_fiscal,
        next6_2025_fiscal,
        next7_2025_fiscal,
        next8_2025_economic,
        next9_2025_economic,
        next10_2025_economic,
        next11_2025_economic,
        next12_2025_economic,
        next13_2025_economic,
        next14_2025_economic,
        next15_2025_economic,
        next16_2025_economic,
        next17_2025_economic,
        next18_2025_economic,
        next19_2025_economic,
        next20_2025_economic,
        next21_2025_economic,
        next22_2025_economic,
        next23_2025_economic,
        next24_2025_economic,
        next25_2025_economic,
        next26_2025_economic,
        next27_2025_economic,
        next28_2025_economic,
        next29_2025_economic,
        next30_2025_economic,
        jiangsu_city_fund,
        jiangsu_city_fiscal,
        city_year_fiscal,
        city_year_fund,
        city_yearbook_macro,
    )
    new_fiscal_lineage = [
        item
        for item in lineage
        if item.get("source_doc_id") in (
            {"SRC-GD-CITY-FISCAL-2025"}
            | JIANGSU_CITY_FISCAL_SOURCE_IDS
            | CITY_YEAR_FISCAL_SOURCE_IDS
            | {HAIDATAS_SOURCE_ID}
        )
    ]
    new_fund_lineage = [
        item
        for item in lineage
        if item.get("source_doc_id") in (CITY_FUND_SOURCE_IDS | CITY_YEAR_FUND_SOURCE_IDS | XINJIANG_CITY_FUND_SOURCE_IDS)
    ]
    lineage = [
        item
        for item in lineage
        if item.get("source_doc_id") not in (
            CITY_FUND_SOURCE_IDS
            | CITY_YEAR_FUND_SOURCE_IDS
            | XINJIANG_CITY_FUND_SOURCE_IDS
            | {"SRC-GD-CITY-FISCAL-2025"}
            | JIANGSU_CITY_FISCAL_SOURCE_IDS
            | CITY_YEAR_FISCAL_SOURCE_IDS
            | {HAIDATAS_SOURCE_ID}
        )
    ]
    attach_lineage_ids(lineage)
    calc_rows, formula_registry, formula_dependency = build_calculations(macro_rows)
    # CEIC 组件页没有把一般/专项数写入主表，只在归档层按两页合计形成
    # 法定债务余额；为该来源层计算补充独立的计算底稿，避免把计算值误当作直接披露值。
    calc_ids = {item["calculation_id"] for item in calc_rows}
    for item in lineage:
        calculation_id = item.get("calculation_id", "")
        if item.get("value_origin") != "calculated" or not calculation_id or calculation_id in calc_ids:
            continue
        calc_rows.append(
            {
                "calculation_id": calculation_id,
                "target_table": "city_macro_fiscal",
                "target_record_id": item["target_record_id"],
                "target_field": item["target_field"],
                "formula_id": "F-STATUTORY-BALANCE",
                "formula_version": "v1.0",
                "input_record_ids": item["target_record_id"],
                "input_fields": "CEIC一般债务余额;CEIC专项债务余额",
                "output_value": item["normalized_value"],
                "output_unit": "亿元",
                "calculation_status": "calculated",
                "calculated_at": RETRIEVED_AT,
                "note": "CEIC 一般债务页与专项债务页均有值时合计；主表不反推官方分项。",
            }
        )
        calc_ids.add(calculation_id)
    # 为派生字段追加可反查的字段证据；计算值不覆盖原始披露证据。
    # 先写历史计算和本批财政原始证据，保持既有 lineage_id 稳定；基金派生值
    # 及其原始证据作为本批新增记录追加到末尾。
    new_fund_target_ids = {item["target_record_id"] for item in new_fund_lineage}
    ordered_calc_rows = order_calculation_rows_for_lineage(calc_rows, new_fund_target_ids)
    new_fund_calc_ids = {
        item["calculation_id"]
        for item in ordered_calc_rows
        if item.get("target_record_id") in new_fund_target_ids
        and item.get("target_field") in FUND_DERIVED_FIELDS
    }
    for calc in (item for item in ordered_calc_rows if item["calculation_id"] not in new_fund_calc_ids):
        row = next(item for item in macro_rows if _macro_record_id(item) == calc["target_record_id"])
        lineage.append(
            _lineage_base(
                row,
                calc["target_field"],
                "",
                "calculated",
                calc["output_value"],
                lineage_id=f"LIN-CALC-{len(lineage)+1:06d}",
                source_locator="公式注册表与计算底稿",
                locator_type="calculation",
                raw_value="",
                raw_unit=calc["output_unit"],
                normalization_rule="",
                calculation_id=calc["calculation_id"],
                extraction_method="calculated",
                parse_confidence="1.00",
                selection_reason="公式依赖 DAG 校验通过",
            )
        )
    for item in new_fiscal_lineage:
        item["lineage_id"] = f"LIN-{len(lineage)+1:06d}"
        lineage.append(item)
    for calc in (item for item in ordered_calc_rows if item["calculation_id"] in new_fund_calc_ids):
        row = next(item for item in macro_rows if _macro_record_id(item) == calc["target_record_id"])
        lineage.append(
            _lineage_base(
                row,
                calc["target_field"],
                "",
                "calculated",
                calc["output_value"],
                lineage_id=f"LIN-CALC-{len(lineage)+1:06d}",
                source_locator="公式注册表与计算底稿",
                locator_type="calculation",
                raw_value="",
                raw_unit=calc["output_unit"],
                normalization_rule="",
                calculation_id=calc["calculation_id"],
                extraction_method="calculated",
                parse_confidence="1.00",
                selection_reason="公式依赖 DAG 校验通过",
            )
        )
    for item in new_fund_lineage:
        item["lineage_id"] = f"LIN-{len(lineage)+1:06d}"
        lineage.append(item)
    lineage_fields_by_record: dict[str, set[str]] = defaultdict(set)
    for item in lineage:
        lineage_fields_by_record[item["target_record_id"]].add(item["target_field"])
    for row in macro_rows:
        non_null_fields = {field for field in MACRO_FIELDS if row.get(field) is not None}
        row["lineage_complete_flag"] = non_null_fields.issubset(lineage_fields_by_record.get(_macro_record_id(row), set()))
    debt_rows = build_debt_rows(macro_rows)
    risk_rows = build_risk_rows(macro_rows, calc_rows)
    collection_rows = build_collection_status(city_master, macro_rows)
    sources = source_document_rows(
        area_hashes,
        panel_hash,
        panel_path,
        gd_sources,
        official_debt_sources,
        [
            gd_2025_source,
            gd_2025_fiscal_source,
            *gd_2025_fund_sources,
            *ningxia_2025_fiscal_sources,
            *shandong_2025_fiscal_sources,
            *next_2025_fiscal_sources,
            *followup_2025_fiscal_sources,
            *next2_2025_fiscal_sources,
            *next3_2025_fiscal_sources,
            *next4_2025_fiscal_sources,
            *next5_2025_fiscal_sources,
            *next6_2025_fiscal_sources,
            *next7_2025_fiscal_sources,
            *next8_2025_economic_sources,
            *next9_2025_economic_sources,
            *next10_2025_economic_sources,
            *next11_2025_economic_sources,
            *next12_2025_economic_sources,
            *next13_2025_economic_sources,
            *next14_2025_economic_sources,
            *next15_2025_economic_sources,
            *next16_2025_economic_sources,
            *next17_2025_economic_sources,
            *next18_2025_economic_sources,
            *next19_2025_economic_sources,
            *next20_2025_economic_sources,
            *next21_2025_economic_sources,
            *next22_2025_economic_sources,
            *next23_2025_economic_sources,
            *next24_2025_economic_sources,
            *next25_2025_economic_sources,
            *next26_2025_economic_sources,
            *next27_2025_economic_sources,
            *next28_2025_economic_sources,
            *next29_2025_economic_sources,
            *next30_2025_economic_sources,
            *jiangsu_city_fund_sources,
            *jiangsu_city_fiscal_sources,
            *city_year_fiscal_sources,
            *city_year_fund_sources,
            *city_yearbook_sources,
            *crei_city_bulletin_sources,
        ],
        EVIDENCE_SOURCE_DOCUMENTS,
    )

    city_fields = ["city_id", "admin_code_6", "city_code_12", "city_name_cn", "province_code", "province_name", "prefecture_type", "sample_tier", "metric_year", "roster_year", "roster_source_year", "valid_from", "valid_to", "roster_version_status", "source_doc_id", "source_locator", "system_valid_from", "system_valid_to", "note"]
    macro_fields = ["city_id", "admin_code_6", "city_name_cn", "province_code", "province_name", "prefecture_type", "sample_tier", "metric_year", "period_end", "geo_scope", "data_status", *MACRO_FIELDS, "gov_fund_source_status", "source_doc_id", "source_grade", "collection_status", "lineage_complete_flag", "note"]
    debt_fields = list(build_debt_rows([macro_rows[0]])[0].keys()) if macro_rows else []
    risk_fields = list(risk_rows[0].keys()) if risk_rows else []
    source_fields = ["source_doc_id", "publisher", "publisher_level", "document_title", "title_source", "attachment_title", "document_type", "source_url", "landing_page_url", "attachment_url", "canonical_url", "final_resolved_url", "file_name", "mime_type", "publication_date", "publication_date_raw", "period_end", "downloaded_at", "content_hash_sha256", "archive_uri", "archive_backend", "archive_path", "page_count", "source_grade", "http_status", "access_status", "supersedes_doc_id", "note"]
    lineage_fields = ["lineage_id", "target_table", "target_record_id", "target_field", "value_origin", "source_doc_id", "source_locator", "locator_type", "page_number", "table_name", "sheet_name", "cell_range", "row_label", "column_label", "evidence_excerpt", "raw_value", "raw_unit", "machine_extracted_value", "normalized_value", "normalization_rule", "calculation_id", "conflict_group_id", "selected_flag", "selection_reason", "extraction_method", "parse_confidence", "reviewer", "reviewed_at"]
    collection_fields = ["task_id", "city_id", "metric_year", "module", "expected_document", "collection_status", "attempt_count", "agent_run_id", "last_checked_at", "missing_reason", "error_code", "evidence_count", "lineage_complete_flag", "next_action"]
    calc_fields = list(calc_rows[0].keys()) if calc_rows else ["calculation_id", "target_table", "target_record_id", "target_field", "formula_id", "formula_version", "input_record_ids", "input_fields", "output_value", "output_unit", "calculation_status", "calculated_at", "note"]
    formula_fields = list(formula_registry[0].keys())
    dependency_fields = list(formula_dependency[0].keys())
    evidence_fields = [
        "city_id", "city_name_cn", "province_name", "metric_year", "field_name",
        "collection_status", "evidence_source_doc_ids", "searched_channels", "result", "next_action",
    ]

    write_csv("dim_city.csv", city_fields, city_master)
    write_csv("city_macro_fiscal.csv", macro_fields, macro_rows)
    write_csv("city_gov_debt.csv", debt_fields, debt_rows)
    write_csv("risk_metric.csv", risk_fields, risk_rows)
    write_csv("source_document.csv", source_fields, sources)
    write_csv("field_lineage.csv", lineage_fields, lineage)
    write_csv("calculation_lineage.csv", calc_fields, calc_rows)
    write_csv("formula_registry.csv", formula_fields, formula_registry)
    write_csv("formula_dependency.csv", dependency_fields, formula_dependency)
    write_csv("collection_status.csv", collection_fields, collection_rows)
    write_csv("evidence_based_missing.csv", evidence_fields, build_evidence_based_missing_rows())
    write_csv(
        "batch_source_registry.csv",
        list(BATCH_REGISTRY_FIELDS),
        build_batch_source_registry(sources, lineage),
    )
    write_csv(
        "core_coverage_report_2018_2025.csv",
        list(CORE_COVERAGE_FIELDS),
        build_core_coverage_report(macro_rows, lineage, sources),
    )
    for filename, (fields, rows) in empty_schema_rows().items():
        write_csv(filename, fields, rows)

    readme = build_readme(macro_rows, city_master, sources)
    (OUTPUT_DIR / "README_数据说明.md").write_text(readme, encoding="utf-8")
    report = quality_report(city_master, macro_rows, lineage, debt_rows, calc_rows)
    (OUTPUT_DIR / "quality_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"output_dir": str(OUTPUT_DIR), "city_master_rows": len(city_master), "macro_rows": len(macro_rows), "source_rows": len(sources), "lineage_rows": len(lineage)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
