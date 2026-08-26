"""大创公开研究面板的 D 级临时补缺适配器。

该面板不是本项目的正式统计来源，字段级原始出处和口径不能逐值复核，
因此这里只把它作为 ``provisional`` 临时值使用：只补主表最终仍为空的字段，
不覆盖任何已有的 A1/A2/B1/B2/C/D 值，也不计入高等级定稿率。

面板中的 ``地区生产总值`` 控制变量按十亿元保存，接入时乘以 10 转为亿元；
``公共财政收入_亿``、``公共财政支出_亿`` 已是亿元；``常住人口``按万人读取。
人口列存在少数明显的十倍异常值，适配器按保守规则剔除非重庆市超过 3000 万人的记录。
"""

from __future__ import annotations

import csv
import hashlib
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping


SNAPSHOT_PATH = Path("raw/province_fiscal/dachuang/dachuang_city_panel_2015_2024.csv")
SOURCE_DOC_ID = "SRC-D-DACHUANG-CITY-PANEL-2015-2024"
SOURCE_GRADE = "D"
DOWNLOADED_AT = "2026-08-26T00:00:00+08:00"
SOURCE_URL = (
    "https://github.com/vegetarianwolf/dachuang/blob/12c314c/"
    "%E9%9D%A2%E6%9D%BF%E6%95%B0%E6%8D%AE/%E5%9C%B0%E7%BA%A7%E5%B8%82%E6%80%BB%E9%9D%A2%E6%9D%BF_2015_2024%E7%89%88.csv"
)


def _decimal(value: Any) -> Decimal | None:
    text = str(value or "").strip().replace(",", "").replace("，", "")
    if not text or text in {"-", "—", "–", "…", "...", "/", "--"}:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _name_key(value: Any) -> str:
    text = re.sub(r"\s+", "", str(value or ""))
    replacements = (
        ("恩施土家族苗族自治州", "恩施州"),
        ("黔西南布依族苗族自治州", "黔西南州"),
        ("黔东南苗族侗族自治州", "黔东南州"),
        ("黔南布依族苗族自治州", "黔南州"),
        ("延边朝鲜族自治州", "延边州"),
        ("湘西土家族苗族自治州", "湘西州"),
        ("大理白族自治州", "大理州"),
        ("楚雄彝族自治州", "楚雄州"),
        ("红河哈尼族彝族自治州", "红河州"),
        ("文山壮族苗族自治州", "文山州"),
        ("西双版纳傣族自治州", "西双版纳州"),
        ("德宏傣族景颇族自治州", "德宏州"),
        ("迪庆藏族自治州", "迪庆州"),
        ("凉山彝族自治州", "凉山州"),
        ("阿坝藏族羌族自治州", "阿坝州"),
        ("甘南藏族自治州", "甘南州"),
        ("临夏回族自治州", "临夏州"),
        ("海西蒙古族藏族自治州", "海西州"),
        ("海南藏族自治州", "海南州"),
        ("海北藏族自治州", "海北州"),
        ("黄南藏族自治州", "黄南州"),
        ("玉树藏族自治州", "玉树州"),
        ("果洛藏族自治州", "果洛州"),
        ("博尔塔拉蒙古自治州", "博尔塔拉州"),
        ("巴音郭楞蒙古自治州", "巴音郭楞州"),
        ("昌吉回族自治州", "昌吉州"),
        ("伊犁哈萨克自治州", "伊犁州"),
        ("克孜勒苏柯尔克孜自治州", "克孜勒苏州"),
    )
    for source, target in replacements:
        text = text.replace(source, target)
    return re.sub(r"(市|地区|盟|州)$", "", text)


def _source_record(content_hash: str) -> dict[str, Any]:
    return {
        "source_doc_id": SOURCE_DOC_ID,
        "publisher": "vegetarianwolf/dachuang（公开研究项目）",
        "publisher_level": "公开研究面板",
        "document_title": "地级市总面板_2015_2024版",
        "title_source": "public_research_panel",
        "attachment_title": SNAPSHOT_PATH.name,
        "document_type": "public_research_city_panel_csv",
        "source_url": SOURCE_URL,
        "landing_page_url": SOURCE_URL,
        "attachment_url": SOURCE_URL,
        "canonical_url": SOURCE_URL,
        "final_resolved_url": SOURCE_URL,
        "file_name": SNAPSHOT_PATH.name,
        "mime_type": "text/csv",
        "publication_date": "",
        "publication_date_raw": "2015—2024",
        "period_end": "2024-12-31",
        "downloaded_at": DOWNLOADED_AT,
        "content_hash_sha256": content_hash,
        "archive_uri": f"archive://national-prefecture-panel/{SNAPSHOT_PATH}",
        "archive_backend": "internal_object",
        "archive_path": str(SNAPSHOT_PATH),
        "page_count": "",
        "source_grade": SOURCE_GRADE,
        "http_status": "200",
        "access_status": "公开研究面板已归档；字段级口径待回到官方原件复核",
        "supersedes_doc_id": "",
        "note": (
            "D级临时值，仅用于降低原始数值空缺，不计入高等级定稿率；"
            "不覆盖已有来源值。GDP列按十亿元×10换算为亿元，财政收支列按面板列名读取为亿元，"
            "人口列按万人读取；非重庆市人口超过3000万的明显异常记录剔除。"
        ),
    }


def load_dachuang_city_panel_sources(
    root: Path, city_master: list[Mapping[str, Any]]
) -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    """读取大创面板，返回城市年度标准输入和一条文件级来源记录。"""

    path = root / SNAPSHOT_PATH
    if not path.exists():
        return {}, []
    content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    city_by_key: dict[str, Mapping[str, Any]] = {}
    for city in city_master:
        city_id = str(city.get("city_id") or "")
        if city_id and _name_key(city.get("city_name_cn")) not in city_by_key:
            city_by_key[_name_key(city.get("city_name_cn"))] = city

    values: dict[tuple[str, str], dict[str, Any]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            year_text = str(row.get("年份") or "").strip()
            if not year_text.isdigit() or not 2018 <= int(year_text) <= 2024:
                continue
            city = city_by_key.get(_name_key(row.get("城市")))
            if not city:
                continue
            city_id = str(city.get("city_id") or "")
            city_name = str(city.get("city_name_cn") or row.get("城市") or "")
            values_key = (city_id, year_text)
            record = values.setdefault(
                values_key,
                {
                    "source_doc_id": SOURCE_DOC_ID,
                    "source_grade": SOURCE_GRADE,
                    "source_format": "csv",
                    "source_platform": "dachuang",
                    "data_status": "provisional",
                    "data_status_label": f"{year_text}年公开研究面板临时值",
                    "city_id": city_id,
                    "city_name": city_name,
                    "year": year_text,
                    "_field_sources": {},
                },
            )
            field_specs = (
                ("地区生产总值", "gdp_current_100m", "十亿元", lambda x: x * Decimal("10")),
                ("公共财政收入_亿", "general_public_revenue_100m", "亿元", lambda x: x),
                ("公共财政支出_亿", "general_public_expenditure_100m", "亿元", lambda x: x),
                ("常住人口", "resident_population_10k", "万人", lambda x: x),
            )
            for source_column, field, raw_unit, normalize in field_specs:
                raw = _decimal(row.get(source_column))
                if raw is None or raw <= 0:
                    continue
                if field == "resident_population_10k" and raw > Decimal("3000") and city_name != "重庆市":
                    continue
                value = _q2(normalize(raw))
                field_source = {
                    "source_doc_id": SOURCE_DOC_ID,
                    "source_grade": SOURCE_GRADE,
                    "source_format": "csv",
                    "source_platform": "dachuang",
                    "data_status": "provisional",
                    "data_status_label": record["data_status_label"],
                    "source_locator": (
                        f"{SNAPSHOT_PATH}；CSV字段={source_column}；城市={city_name}；"
                        f"年份={year_text}；行政范围=城市面板口径"
                    ),
                    "table_name": "地级市总面板_2015_2024版",
                    "page_number": "CSV行",
                    f"{field}_raw_100m": raw,
                    f"{field}_raw_unit": raw_unit,
                    f"{field}_evidence_excerpt": f"{city_name}|{year_text}|{source_column}|{raw}",
                }
                record[field] = value
                record[f"{field}_raw_100m"] = raw
                record[f"{field}_raw_unit"] = raw_unit
                record[f"{field}_evidence_excerpt"] = field_source[f"{field}_evidence_excerpt"]
                record["_field_sources"][field] = field_source

    return values, [_source_record(content_hash)]


__all__ = ["load_dachuang_city_panel_sources"]
