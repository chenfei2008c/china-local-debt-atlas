"""湖北省直管县级行政区划的官方统计年鉴批量来源。

湖北省统计年鉴把仙桃、潜江、天门和神农架林区作为单独行列示。
本适配器仅将四个直管单元在同一年度、同一套省级表中的现价 GDP、
一般公共预算收入和支出加总到全国主表的 ``CN-429000`` 占位行。
GDP 实际增速不做当前价加权推算；省年鉴只披露四个单元各自的 GDP 指数，
没有可直接引用的“湖北省直管县级行政区划”合计增速，因此保持缺失。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_BASE = ROOT / "raw" / "province_fiscal" / "hubei_yearbook"

_OFFICIAL_ARCHIVES = {
    2018: "https://tjj.hubei.gov.cn/tjsj/sjkscx/tjnj/qstjnj/201912/P020240903632511602780.rar",
    2019: "https://tjj.hubei.gov.cn/tjsj/sjkscx/tjnj/qstjnj/202010/P020240903631788119195.rar",
    2020: "https://tjj.hubei.gov.cn/tjsj/sjkscx/tjnj/qstjnj/202110/P020240903631312749096.rar",
    2021: "https://tjj.hubei.gov.cn/tjsj/sjkscx/tjnj/qstjnj/202211/P020240903630403969067.rar",
    2022: "https://tjj.hubei.gov.cn/tjsj/sjkscx/tjnj/qstjnj/202402/P020240815365664897419.rar",
    2023: "https://tjj.hubei.gov.cn/tjsj/sjkscx/tjnj/qstjnj/202501/P020250114330164457869.zip",
    2024: "https://tjj.hubei.gov.cn/tjsj/sjkscx/tjnj/qstjnj/202601/P020260114553839802144.zip",
}

# 统计年鉴目录公布日期；数据年度为年鉴出版年度的前一年。
_PUBLICATION_DATES = {
    2018: "2019-12-10",
    2019: "2020-10-20",
    2020: "2021-10-13",
    2021: "2022-11-21",
    2022: "2023-12-29",
    2023: "2024-12-31",
    2024: "2026-01-14",
}


def _source(metric_year: int, gdp: str, revenue: str, expenditure: str) -> dict[str, object]:
    publication_year = metric_year + 1
    year_dir = RAW_BASE / str(metric_year)
    text_path = year_dir / f"hubei_{publication_year}_429000_excerpt.txt"
    return {
        "year": metric_year,
        "city_name": "湖北省直辖县级行政区划",
        "city_id": "CN-429000",
        "source_doc_id": f"SRC-A2-HUBEI-YEARBOOK-{publication_year}-429000-CORE",
        "url": _OFFICIAL_ARCHIVES[metric_year],
        "path": year_dir / f"hubei_{publication_year}_0115_gdp.xls",
        "text_path": text_path,
        "document_title": f"{publication_year}年湖北统计年鉴（{metric_year}年市州统计表）",
        "publisher": "湖北省统计局",
        "publisher_level": "省级统计机构",
        "publication_date": _PUBLICATION_DATES[metric_year],
        "source_grade": "A2",
        "source_format": "xls",
        "raw_unit": "亿元",
        "data_status": "yearbook",
        "data_status_label": f"{metric_year}年官方统计年鉴值",
        "document_type": "省级统计年鉴官方XLS表（直管单元汇总）",
        "page_number": "表0115、表0704、表0705；Excel行=仙桃/潜江/天门/神农架",
        "patterns": {
            "gdp_current_100m": r"GDP=([0-9.]+)",
            "general_public_revenue_100m": r"收入=([0-9.]+)",
            "general_public_expenditure_100m": r"支出=([0-9.]+)",
        },
        "note": (
            "A2湖北省统计局官方统计年鉴；表0115列示四个直管市/林区的地区生产总值，"
            "表0704和0705列示同四地的一般公共预算收入、支出；本批按同年度、同一行政范围"
            "将仙桃、潜江、天门、神农架林区四行逐项加总，原始单位亿元并保留两位小数。"
            "表0116仅列四地各自GDP指数，没有直管单元合计实际增速，故不以当前价权重推算。"
            + ("2024年财政表注明为财政收支月报数，保留年鉴值状态，不改写为最终决算。" if metric_year == 2024 else "")
        ),
        "_expected": {
            "gdp_current_100m": gdp,
            "general_public_revenue_100m": revenue,
            "general_public_expenditure_100m": expenditure,
        },
    }


HUBEI_DIRECT_ADMIN_YEARBOOK_SOURCES = (
    _source(2018, "2175.65", "84.69", "260.25"),
    _source(2019, "2364.78", "88.71", "282.60"),
    _source(2020, "2241.36", "71.35", "302.44"),
    _source(2021, "2536.77", "90.62", "272.68"),
    _source(2022, "2665.45", "88.80", "273.91"),
    _source(2023, "2672.22", "102.14", "318.19"),
    _source(2024, "2911.13", "111.89", "338.32"),
)
