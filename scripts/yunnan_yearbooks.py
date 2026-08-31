"""云南省统计局官方统计年鉴 2018—2020 年各州市核心经济财政批次。

2019、2020、2021 年《云南统计年鉴》分别提供 2018、2019、2020 年的各州市
地区生产总值表；2021 年年鉴财政章节的表 18-8、18-10 连续提供 2018—2020
年各州市地方一般公共预算收入、支出。这里按州（市）全域行接入，不把县区
行相加后冒充州（市）值，也不把省级合计分摊到州市。

由于一个指标批次和财政批次来自不同年鉴附件，配置按字段来源拆成两组，
供统一的城市年度财政来源加载器合并，并保留字段级血缘。
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw" / "province_fiscal" / "yunnan" / "yearbook"


PREFECTURES = (
    ("昆明市", "CN-530100", "Kunming"),
    ("曲靖市", "CN-530300", "Qujing"),
    ("玉溪市", "CN-530400", "Yuxi"),
    ("保山市", "CN-530500", "Baoshan"),
    ("昭通市", "CN-530600", "Zhaotong"),
    ("丽江市", "CN-530700", "Lijiang"),
    ("普洱市", "CN-530800", "Pu'er"),
    ("临沧市", "CN-530900", "Lincang"),
    ("楚雄彝族自治州", "CN-532300", "Chuxiong"),
    ("红河哈尼族彝族自治州", "CN-532500", "Honghe"),
    ("文山壮族苗族自治州", "CN-532600", "Wenshan"),
    ("西双版纳傣族自治州", "CN-532800", "Xishuangbanna"),
    ("大理白族自治州", "CN-532900", "Dali"),
    ("德宏傣族景颇族自治州", "CN-533100", "Dehong"),
    ("怒江傈僳族自治州", "CN-533300", "Nujiang"),
    ("迪庆藏族自治州", "CN-533400", "Diqing"),
)


YEARBOOKS = {
    2018: {
        "publication_year": 2019,
        "document_title": "2019年云南统计年鉴",
        "gdp_table": "表2-4“各州市生产总值（2018年）”",
        "landing_page_url": "https://stats.yn.gov.cn/zwgk/zfxxgk/fdzdgknr/tjsj/tjnj/201912/t20191205_1202426.html",
        "attachment_url": "https://stats.yn.gov.cn/zwgk/zfxxgk/fdzdgknr/tjsj/tjnj/201912/P020260724580562673182.gz",
        "path_name": "yunnan_2018_core_excerpt.txt",
    },
    2019: {
        "publication_year": 2020,
        "document_title": "2020年云南统计年鉴",
        "gdp_table": "表2-4“各州市生产总值（2019年）”",
        "landing_page_url": "https://stats.yn.gov.cn/zwgk/zfxxgk/fdzdgknr/tjsj/tjnj/202105/t20210520_1202513.html",
        "attachment_url": "https://stats.yn.gov.cn/zwgk/zfxxgk/fdzdgknr/tjsj/tjnj/202105/P020251011359143959343.zip",
        "path_name": "yunnan_2019_core_excerpt.txt",
    },
    2020: {
        "publication_year": 2021,
        "document_title": "2021年云南统计年鉴",
        "gdp_table": "表2-6“各州市生产总值（2020年）”",
        "landing_page_url": "https://stats.yn.gov.cn/zwgk/zfxxgk/fdzdgknr/tjsj/tjnj/202607/t20260716_3205139.html",
        "attachment_url": "https://stats.yn.gov.cn/zwgk/zfxxgk/fdzdgknr/tjsj/tjnj/202607/P020260722556553747180.gz",
        "path_name": "yunnan_2020_core_excerpt.txt",
    },
}


FISCAL_YEARBOOK = {
    "publication_year": 2021,
    "document_title": "2021年云南统计年鉴",
    "fiscal_tables": (
        "表18-8“各州市县地方一般公共预算收入（2012—2020年）”",
        "表18-10“各州市县地方一般公共预算支出（2012—2020年）”",
    ),
    "landing_page_url": "https://stats.yn.gov.cn/zwgk/zfxxgk/fdzdgknr/tjsj/tjnj/202607/t20260716_3205139.html",
    "attachment_url": "https://stats.yn.gov.cn/zwgk/zfxxgk/fdzdgknr/tjsj/tjnj/202607/P020260722556553747180.gz",
}


def _pattern(city_name: str, year: int, label: str) -> str:
    return (
        rf"城市={re.escape(city_name)}｜年度={year}｜"
        rf"(?:(?!城市=).)*?{re.escape(label)}=([0-9.,-]+)亿元"
    )


def _base_source(
    *,
    year: int,
    city_name: str,
    city_id: str,
    source_doc_id: str,
    document_title: str,
    landing_page_url: str,
    attachment_url: str,
    path: Path,
    publication_year: int,
    table_name: str,
    fields: tuple[str, ...],
    note: str,
) -> dict:
    labels = {
        "gdp_current_100m": "GDP",
        "general_public_revenue_100m": "一般公共预算收入",
        "general_public_expenditure_100m": "一般公共预算支出",
    }
    return {
        "year": year,
        "city_name": city_name,
        "city_id": city_id,
        "source_doc_id": source_doc_id,
        "url": landing_page_url,
        "landing_page_url": landing_page_url,
        "attachment_url": attachment_url,
        "path": path,
        "text_path": path,
        "text_is_curated": True,
        "document_title": document_title,
        "publisher": "云南省统计局",
        "publisher_level": "省级统计机构",
        "publication_date": f"{publication_year}-12-31",
        "source_grade": "A2",
        "source_format": "txt",
        "data_status": "yearbook",
        "data_status_label": f"{year}年官方统计年鉴表",
        "document_type": "省级统计年鉴各州市核心经济财政表",
        "page_number": f"官方附件Excel；{table_name}；城市={city_name}全域行",
        "title_source": "official_statistical_yearbook",
        "access_status": "云南省统计局官方年鉴附件及精确摘录已归档",
        "raw_unit": "亿元",
        "raw_units": {field: "亿元" for field in fields},
        "table_name": table_name,
        "source_locator": (
            f"{path.relative_to(ROOT)}；{table_name}；城市={city_name}；"
            f"年度={year}；行政范围=各州市全域行"
        ),
        "patterns": {field: _pattern(city_name, year, labels[field]) for field in fields},
        "note": note,
    }


def _gdp_source(year: int, city_name: str, city_id: str) -> dict:
    book = YEARBOOKS[year]
    path = RAW_DIR / book["path_name"]
    return _base_source(
        year=year,
        city_name=city_name,
        city_id=city_id,
        source_doc_id=(
            f"SRC-A2-YUNNAN-YEARBOOK-{book['publication_year']}-GDP-"
            f"{year}-{city_id}"
        ),
        document_title=f"{book['document_title']}（{book['gdp_table']}）",
        landing_page_url=book["landing_page_url"],
        attachment_url=book["attachment_url"],
        path=path,
        publication_year=book["publication_year"],
        table_name=book["gdp_table"],
        fields=("gdp_current_100m",),
        note=(
            f"A2云南省统计局官方{book['document_title']}附件精确摘录；{book['gdp_table']}"
            f"逐行披露{city_name}全域地区生产总值，原始单位为亿元，GDP绝对数按当年价格；"
            "不使用省级合计、县区行或县区加总值。"
        ),
    )


def _fiscal_source(year: int, city_name: str, city_id: str) -> dict:
    book = FISCAL_YEARBOOK
    path = RAW_DIR / YEARBOOKS[year]["path_name"]
    tables = "、".join(book["fiscal_tables"])
    return _base_source(
        year=year,
        city_name=city_name,
        city_id=city_id,
        source_doc_id=f"SRC-A2-YUNNAN-YEARBOOK-2021-FISCAL-{year}-{city_id}",
        document_title=f"{book['document_title']}（{tables}）",
        landing_page_url=book["landing_page_url"],
        attachment_url=book["attachment_url"],
        path=path,
        publication_year=book["publication_year"],
        table_name=tables,
        fields=("general_public_revenue_100m", "general_public_expenditure_100m"),
        note=(
            f"A2云南省统计局官方{book['document_title']}附件精确摘录；表18-8和表18-10的年度列"
            f"逐行披露{city_name}全域地方一般公共预算收入、支出，原始单位为亿元；"
            "不使用省级合计、县区行、州/市本级行或县区加总值。"
        ),
    )


YUNNAN_YEARBOOK_SOURCES = tuple(
    source
    for year in (2018, 2019, 2020)
    for city_name, city_id, _english_name in PREFECTURES
    for source in (_gdp_source(year, city_name, city_id), _fiscal_source(year, city_name, city_id))
)
