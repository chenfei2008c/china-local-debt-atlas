"""济源省直辖县级行政区划 2018—2023 年官方历史来源。

统计公报和财政执行报告均明确使用全市/示范区口径。2020 年 GDP 采用济源官方
经济运行回顾页披露的最终核实值，财政收支采用官方财政预算执行报告，避免把
2020 年公报中的初步 GDP 和财政初步执行数写入定稿值。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://fgw.jiyuan.gov.cn/14186/17304/20647"


def _source(
    *,
    year: int,
    url: str,
    path: str,
    text_path: str,
    source_doc_id: str,
    document_title: str,
    publisher: str,
    publication_date: str,
    source_format: str,
    data_status: str,
    data_status_label: str,
    document_type: str,
    page_number: str,
    patterns: dict[str, str],
    note: str,
    attachment_url: str | None = None,
) -> dict[str, object]:
    return {
        "year": year,
        "city_name": "省直辖县级行政区划",
        "city_id": "CN-419000",
        "source_doc_id": source_doc_id,
        "url": url,
        "attachment_url": attachment_url or url,
        "download_url": attachment_url or url,
        "path": ROOT / path,
        "text_path": ROOT / text_path,
        "text_is_curated": True,
        "document_title": document_title,
        "publisher": publisher,
        "publisher_level": "地市统计/财政机构",
        "publication_date": publication_date,
        "source_grade": "A2",
        "source_format": source_format,
        "raw_unit": "亿元",
        "data_status": data_status,
        "data_status_label": data_status_label,
        "document_type": document_type,
        "title_source": "official_bulletin",
        "page_number": page_number,
        "page_count": "1" if source_format == "html" else "14",
        "patterns": patterns,
        "note": note,
    }


JIYUAN_HISTORICAL_SOURCES = (
    _source(
        year=2018,
        url=f"{BASE_URL}/t675056.html",
        attachment_url=f"{BASE_URL}/P020200528400726252957.doc",
        path="raw/province_fiscal/2018/official/jiyuan_2018_statistical_bulletin.doc",
        text_path="raw/province_fiscal/2018/official/jiyuan_2018_419000_core_excerpt.txt",
        source_doc_id="SRC-A2-JIYUAN-2018-STATISTICAL-BULLETIN-CORE",
        document_title="2018年济源市国民经济和社会发展统计公报",
        publisher="济源产城融合示范区发展改革和统计局",
        publication_date="2019-04-04",
        source_format="doc",
        data_status="bulletin",
        data_status_label="2018年官方统计公报值（初步统计）",
        document_type="地市官方国民经济和社会发展统计公报DOC附件",
        page_number="Word附件第1页及财政金融段；全市",
        patterns={
            "gdp_current_100m": r"GDP=([0-9.]+)",
            "gdp_real_growth_pct": r"增速=([0-9.]+)",
            "general_public_revenue_100m": r"收入=([0-9.]+)",
            "general_public_expenditure_100m": r"支出=([0-9.]+)",
        },
        note=(
            "A2济源官方统计公报附件，明确披露全市生产总值641.84亿元、增长8.3%、"
            "地方一般公共财政预算收入50.1亿元和支出69.0亿元；原始附件为官方DOC。"
        ),
    ),
    _source(
        year=2019,
        url=f"{BASE_URL}/t675058.html",
        path="raw/province_fiscal/2019/official/jiyuan_2019_statistical_bulletin.html",
        text_path="raw/province_fiscal/2019/official/jiyuan_2019_419000_core_excerpt.txt",
        source_doc_id="SRC-A2-JIYUAN-2019-STATISTICAL-BULLETIN-CORE",
        document_title="2019年济源示范区国民经济和社会发展统计公报",
        publisher="济源产城融合示范区发展改革和统计局",
        publication_date="2020-04-10",
        source_format="html",
        data_status="bulletin",
        data_status_label="2019年官方统计公报值（初步统计）",
        document_type="地市官方国民经济和社会发展统计公报",
        page_number="网页正文：综合、财政金融；全市",
        patterns={
            "gdp_current_100m": r"GDP=([0-9.]+)",
            "gdp_real_growth_pct": r"增速=([0-9.]+)",
            "general_public_revenue_100m": r"收入=([0-9.]+)",
            "general_public_expenditure_100m": r"支出=([0-9.]+)",
        },
        note=(
            "A2济源官方统计公报，明确披露示范区生产总值686.96亿元、增长7.8%、"
            "地方一般公共财政预算收入57.1亿元和支出77.5亿元；全部为全市口径。"
        ),
    ),
    _source(
        year=2020,
        url="https://www.jiyuan.gov.cn/zwgk/zdlyxxgk/czzj/yjxgkpt/zfyjx/zfyx/t716535.html",
        path="raw/province_fiscal/2020/official/jiyuan_2020_budget_execution_report.html",
        text_path="raw/province_fiscal/2020/official/jiyuan_2020_419000_fiscal_excerpt.txt",
        source_doc_id="SRC-A2-JIYUAN-2020-BUDGET-EXECUTION-CORE",
        document_title="关于济源市2020年财政预算执行情况和2021年财政预算草案的报告",
        publisher="济源产城融合示范区财政金融局",
        publication_date="2021-03-08",
        source_format="html",
        data_status="execution",
        data_status_label="2020年全市一般公共预算执行数",
        document_type="地市官方财政预算执行报告",
        page_number="网页正文：一般公共预算执行情况；全市",
        patterns={
            "general_public_revenue_100m": r"收入=([0-9.]+)",
            "general_public_expenditure_100m": r"支出=([0-9.]+)",
        },
        note=(
            "A2济源官方财政预算执行报告，明确列示2020年全市一般公共预算收入58.4亿元、"
            "支出81.3亿元；本来源只接入财政字段，GDP另采用官方最终核实披露。"
        ),
    ),
    _source(
        year=2020,
        url="https://fgw.jiyuan.gov.cn/14186/17304/17307/17332/t770147.html",
        path="raw/province_fiscal/2021/official/jiyuan_2021_economic_review.html",
        text_path="raw/province_fiscal/2021/official/jiyuan_2020_419000_gdp_revision_excerpt.txt",
        source_doc_id="SRC-A2-JIYUAN-2020-GDP-FINAL-REVIEW",
        document_title="2021年济源经济持续稳定恢复（2020年GDP最终核实披露）",
        publisher="济源产城融合示范区发展改革和统计局",
        publication_date="2022-01-27",
        source_format="html",
        data_status="revised",
        data_status_label="2020年GDP最终核实值",
        document_type="地市官方经济运行回顾页历史修订披露",
        page_number="网页正文注释；2020年GDP最终核实",
        patterns={
            "gdp_current_100m": r"GDP修订=([0-9.]+)",
            "gdp_real_growth_pct": r"增速修订=([0-9.]+)",
        },
        note=(
            "A2济源官方经济运行回顾页明确：经最终核实，2020年地区生产总值现价总量为"
            "691.35亿元，按不变价格计算比上年增长3.3%；以最终核实值替代2020年统计公报初步值。"
        ),
    ),
    _source(
        year=2021,
        url=f"{BASE_URL}/t829953.html",
        path="raw/province_fiscal/2021/official/jiyuan_2021_statistical_bulletin.html",
        text_path="raw/province_fiscal/2021/official/jiyuan_2021_419000_core_excerpt.txt",
        source_doc_id="SRC-A2-JIYUAN-2021-STATISTICAL-BULLETIN-CORE",
        document_title="2021年济源国民经济和社会发展统计公报",
        publisher="济源产城融合示范区发展改革和统计局",
        publication_date="2022-03-29",
        source_format="html",
        data_status="bulletin",
        data_status_label="2021年官方统计公报值（初步统计）",
        document_type="地市官方国民经济和社会发展统计公报",
        page_number="网页正文：综合、财政金融；全市",
        patterns={
            "gdp_current_100m": r"GDP=([0-9.]+)",
            "gdp_real_growth_pct": r"增速=([0-9.]+)",
            "general_public_revenue_100m": r"收入=([0-9.]+)",
            "general_public_expenditure_100m": r"支出=([0-9.]+)",
        },
        note=(
            "A2济源官方统计公报，明确披露全市生产总值762.23亿元、增长6.1%、"
            "地方一般公共预算收入59.1亿元和支出81.59亿元。"
        ),
    ),
    _source(
        year=2022,
        url=f"{BASE_URL}/t886202.html",
        path="raw/province_fiscal/2022/official/jiyuan_2022_statistical_bulletin.html",
        text_path="raw/province_fiscal/2022/official/jiyuan_2022_419000_core_excerpt.txt",
        source_doc_id="SRC-A2-JIYUAN-2022-STATISTICAL-BULLETIN-CORE",
        document_title="2022年济源国民经济和社会发展统计公报",
        publisher="济源产城融合示范区发展改革和统计局",
        publication_date="2023-03-28",
        source_format="html",
        data_status="bulletin",
        data_status_label="2022年官方统计公报值（初步统计）",
        document_type="地市官方国民经济和社会发展统计公报",
        page_number="网页正文：综合、财政金融；全市",
        patterns={
            "gdp_current_100m": r"GDP=([0-9.]+)",
            "gdp_real_growth_pct": r"增速=([0-9.]+)",
            "general_public_revenue_100m": r"收入=([0-9.]+)",
            "general_public_expenditure_100m": r"支出=([0-9.]+)",
        },
        note=(
            "A2济源官方统计公报，明确披露全市生产总值806.22亿元、增长4.4%、"
            "地方一般公共预算收入66.8亿元和支出84.2亿元。"
        ),
    ),
    _source(
        year=2023,
        url=f"{BASE_URL}/t940646.html",
        path="raw/province_fiscal/2023/official/jiyuan_2023_statistical_bulletin.html",
        text_path="raw/province_fiscal/2023/official/jiyuan_2023_419000_core_excerpt.txt",
        source_doc_id="SRC-A2-JIYUAN-2023-STATISTICAL-BULLETIN-CORE",
        document_title="2023年济源国民经济和社会发展统计公报",
        publisher="济源产城融合示范区发展改革和统计局",
        publication_date="2024-04-29",
        source_format="html",
        data_status="bulletin",
        data_status_label="2023年官方统计公报值（初步统计）",
        document_type="地市官方国民经济和社会发展统计公报",
        page_number="网页正文：综合、财政金融；全市",
        patterns={
            "gdp_current_100m": r"GDP=([0-9.]+)",
            "gdp_real_growth_pct": r"增速=([0-9.]+)",
            "general_public_revenue_100m": r"收入=([0-9.]+)",
            "general_public_expenditure_100m": r"支出=([0-9.]+)",
        },
        note=(
            "A2济源官方统计公报，明确披露全市地区生产总值788.61亿元、增长5.4%、"
            "地方一般公共预算收入60亿元和支出75.5亿元。"
        ),
    ),
)
