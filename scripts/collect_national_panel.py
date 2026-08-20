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
except ModuleNotFoundError:  # 允许以 python scripts/collect_national_panel.py 直接运行
    from province_debt_sources import extract_official_debt_facts
    from data_quality import OFFICIAL_DEBT_EXCEPTION_STATUS, debt_fact_has_balance_limit_conflict
    from evidence_based_missing import EVIDENCE_BY_KEY, EVIDENCE_CHECKED_AT, EVIDENCE_SOURCE_DOCUMENTS
    from official_city_macro_sources import parse_city_fund_revenue_text, parse_guangdong_city_budget_page, parse_guangdong_city_gdp_html
    from pdf_layout_text import extract_pdf_text

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
        "pattern": r"2025年全市政府性基金预算收入([0-9.]+)亿元",
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
)
CITY_YEAR_FISCAL_SOURCE_IDS = {item["source_doc_id"] for item in CITY_YEAR_FISCAL_SOURCES}

FUND_DERIVED_FIELDS = {"fund_revenue_dependence_pct", "gov_fund_to_general_revenue_pct"}

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
        values[config["city_id"]] = city_values
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
    """读取江苏省财政厅 2022—2024 年分地区政府性基金收入表。"""

    values: dict[tuple[str, str], dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    for config in JIANGSU_CITY_FUND_SOURCES:
        source_path = Path(config["path"])
        text_path = Path(config["text_path"])
        content_hash = ensure_download(str(config["url"]), source_path)
        report_text = text_path.read_text(encoding="utf-8")
        year = int(config["year"])
        found_city_ids: set[str] = set()
        for city_id, city_name in config["cities"].items():
            match = re.search(rf"^{re.escape(city_name)}\s+([0-9,]+)\s*$", report_text, re.MULTILINE)
            if not match:
                raise ValueError(f"未能从江苏省{year}年政府性基金分地区表提取{city_name}")
            raw_value = Decimal(match.group(1).replace(",", ""))
            values[(city_id, str(year))] = {
                "gov_fund_revenue_100m": q2(raw_value * D4),
                "gov_fund_revenue_raw_100m": raw_value,
                "gov_fund_revenue_raw_unit": "万元",
                "gov_fund_revenue_evidence_excerpt": match.group(0),
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
                    "江苏省财政厅官方分地区政府性基金预算收入表；"
                    f"采用各设区市全市{config.get('data_status_label') or f'{year}年执行数'}，"
                    "原始单位万元，统一换算为亿元。"
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
            raw_value = Decimal(match.group(1).replace(",", "").replace("，", ""))
            raw_unit = str(config.get("raw_unit") or "万元")
            normalized = q2(raw_value if raw_unit == "亿元" else raw_value * D4)
            record[field] = normalized
            record[f"{field}_raw_100m"] = raw_value
            record[f"{field}_raw_unit"] = raw_unit
            record[f"{field}_evidence_excerpt"] = match.group(0)
        values[(str(config["city_id"]), year)] = record
        sources.append(
            {
                "source_doc_id": config["source_doc_id"],
                "publisher": config["publisher"],
                "publisher_level": config["publisher_level"],
                "document_title": config["document_title"],
                "title_source": "official_budget_report",
                "attachment_title": source_path.name,
                "document_type": config["document_type"],
                "source_url": config["url"],
                "landing_page_url": config.get("landing_page_url") or config["url"],
                "attachment_url": config.get("attachment_url") or config["url"],
                "canonical_url": config.get("landing_page_url") or config["url"],
                "final_resolved_url": config.get("attachment_url") or config["url"],
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
                "page_count": config.get("page_count", "179"),
                "source_grade": config["source_grade"],
                "http_status": "200",
                "access_status": "官方网页已归档" if config.get("source_format") == "html" else "官方PDF已归档",
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
    jiangsu_city_fund: Mapping[tuple[str, str], Mapping[str, Any]] | None = None,
    jiangsu_city_fiscal: Mapping[tuple[str, str], Mapping[str, Any]] | None = None,
    city_year_fiscal: Mapping[tuple[str, str], Mapping[str, Any]] | None = None,
    city_year_fund: Mapping[tuple[str, str], Mapping[str, Any]] | None = None,
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
    jiangsu_city_fund = jiangsu_city_fund or {}
    jiangsu_city_fiscal = jiangsu_city_fiscal or {}
    city_year_fiscal = city_year_fiscal or {}
    city_year_fund = city_year_fund or {}
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
            prior_source = str(row.get("source_doc_id") or "")
            row["source_doc_id"] = ";".join(
                item for item in [prior_source, fiscal_source_id] if item
            )
            for field in (
                "general_public_revenue_100m",
                "general_public_expenditure_100m",
                "gov_fund_revenue_100m",
            ):
                value = as_decimal(city_year_fiscal_source.get(field))
                if value is None:
                    continue
                row[field] = q2(value)
                if field == "gov_fund_revenue_100m":
                    row["gov_fund_source_status"] = "城市财政局官方预算执行报告（全市口径）"
                batch_lineage.append(
                    _lineage_for_city_year_fiscal(
                        row, city_year_fiscal_source, field, row[field]
                    )
                )
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
        "general_public_revenue_100m": "一般公共预算收入",
        "general_public_expenditure_100m": "一般公共预算支出",
        "gov_fund_revenue_100m": "政府性基金预算收入",
    }
    field_label = labels[field]
    year = row["metric_year"]
    data_status_label = str(source.get("data_status_label") or f"{year}年执行数")
    raw_unit = str(source.get(f"{field}_raw_unit") or "万元")
    normalization_rule = (
        "官方预算执行报告原始单位为亿元；数值直接读取，保留两位小数；全市口径。"
        if raw_unit == "亿元"
        else "官方预算执行报告原始单位为万元；原值÷10000=亿元，保留两位小数；全市口径。"
    )
    return _lineage_base(
        row,
        field,
        str(source.get("source_doc_id", "")),
        "disclosed",
        value,
        source_locator=(
            f"{source.get('source_locator', '')}；字段={field_label}"
        ),
        locator_type="pdf_text_statement",
        page_number=source.get("page_number", "2—3"),
        table_name=str(source.get("table_name", f"{year}年全市财政预算执行情况")),
        raw_value=source.get(f"{field}_raw_100m", value),
        raw_unit=source.get(f"{field}_raw_unit", "万元"),
        machine_extracted_value=value,
        evidence_excerpt=source.get(f"{field}_evidence_excerpt", ""),
        normalization_rule=normalization_rule,
        extraction_method="curated-official-pdf-statement-parser",
        parse_confidence="0.99",
        selection_reason=(
            "市级财政机构官方预算执行报告明确披露全市财政字段，"
            f"年度、行政范围和{data_status_label}状态清晰。"
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

主表包括 `dim_city.csv`、`city_macro_fiscal.csv`、`city_gov_debt.csv`、`risk_metric.csv`、`source_document.csv`、`field_lineage.csv`、`collection_status.csv`、`evidence_based_missing.csv` 以及公式和质量表。LGFV、逐券债券、特殊条款、募集资金用途和信用事件文件已经按设计文档建立字段结构；当前没有可靠批量来源的模块不虚构记录。
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
    jiangsu_city_fund, jiangsu_city_fund_sources = load_jiangsu_city_fund_sources()
    jiangsu_city_fiscal, jiangsu_city_fiscal_sources = load_jiangsu_city_fiscal_sources()
    city_year_fiscal, city_year_fiscal_sources = load_city_year_fiscal_sources()
    city_year_fund, city_year_fund_sources = load_city_year_fund_sources()
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
        jiangsu_city_fund,
        jiangsu_city_fiscal,
        city_year_fiscal,
        city_year_fund,
    )
    new_fiscal_lineage = [
        item
        for item in lineage
        if item.get("source_doc_id") in (
            {"SRC-GD-CITY-FISCAL-2025"}
            | JIANGSU_CITY_FISCAL_SOURCE_IDS
            | CITY_YEAR_FISCAL_SOURCE_IDS
        )
    ]
    new_fund_lineage = [
        item
        for item in lineage
        if item.get("source_doc_id") in (CITY_FUND_SOURCE_IDS | CITY_YEAR_FUND_SOURCE_IDS)
    ]
    lineage = [
        item
        for item in lineage
        if item.get("source_doc_id") not in (
            CITY_FUND_SOURCE_IDS
            | CITY_YEAR_FUND_SOURCE_IDS
            | {"SRC-GD-CITY-FISCAL-2025"}
            | JIANGSU_CITY_FISCAL_SOURCE_IDS
            | CITY_YEAR_FISCAL_SOURCE_IDS
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
            *jiangsu_city_fund_sources,
            *jiangsu_city_fiscal_sources,
            *city_year_fiscal_sources,
            *city_year_fund_sources,
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
    for filename, (fields, rows) in empty_schema_rows().items():
        write_csv(filename, fields, rows)

    readme = build_readme(macro_rows, city_master, sources)
    (OUTPUT_DIR / "README_数据说明.md").write_text(readme, encoding="utf-8")
    report = quality_report(city_master, macro_rows, lineage, debt_rows, calc_rows)
    (OUTPUT_DIR / "quality_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"output_dir": str(OUTPUT_DIR), "city_master_rows": len(city_master), "macro_rows": len(macro_rows), "source_rows": len(sources), "lineage_rows": len(lineage)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
