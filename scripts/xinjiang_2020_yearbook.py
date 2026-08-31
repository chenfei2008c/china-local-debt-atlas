"""新疆统计局 2021 年统计年鉴中的 2020 年地州级核心字段批次。

三张官方 HTML 表分别提供 GDP 总量、GDP 指数和一般公共预算收支。
表格同时列示县级行，因此本适配器只接受新疆 14 个地级行政单元全域行，
不把市本级、区县或分项行混入主表。
"""

from __future__ import annotations

import csv
import hashlib
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from scripts.official_city_macro_sources import _TableParser
except ModuleNotFoundError:  # 允许以 python scripts/xinjiang_2020_yearbook.py 直接运行
    from official_city_macro_sources import _TableParser


YEAR = "2020"
YEARBOOK_YEAR = "2021"
SOURCE_GRADE = "A1"
GDP_TOTAL_PATH = Path("raw/province_fiscal/2020/official/xinjiang_2020_gdp_total.html")
GDP_INDEX_PATH = Path("raw/province_fiscal/2020/official/xinjiang_2020_gdp_index.html")
FISCAL_PATH = Path("raw/province_fiscal/2020/official/xinjiang_2020_fiscal.html")

GDP_TOTAL_URL = "https://tjj.xinjiang.gov.cn/tjj/gmjjsm/202203/89d4cb95c3154532a9a14f31f020e1e6.shtml"
GDP_INDEX_URL = "https://tjj.xinjiang.gov.cn/tjj/gmjjsm/202203/71b3f5a53d164535900b8565b859a995.shtml"
FISCAL_URL = "https://tjj.xinjiang.gov.cn/tjj/czzrs/202203/94bcca4549634997b6c16bde0922ca1e.shtml"

TARGET_CITY_NAMES = {
    "乌鲁木齐市": "CN-650100",
    "克拉玛依市": "CN-650200",
    "吐鲁番市": "CN-650400",
    "哈密市": "CN-650500",
    "昌吉回族自治州": "CN-652300",
    "博尔塔拉蒙古自治州": "CN-652700",
    "巴音郭楞蒙古自治州": "CN-652800",
    "阿克苏地区": "CN-652900",
    "克孜勒苏柯尔克孜自治州": "CN-653000",
    "喀什地区": "CN-653100",
    "和田地区": "CN-653200",
    "伊犁哈萨克自治州": "CN-654000",
    "塔城地区": "CN-654200",
    "阿勒泰地区": "CN-654300",
}

FIELD_NAMES = (
    "gdp_current_100m",
    "gdp_real_growth_pct",
    "general_public_revenue_100m",
    "general_public_expenditure_100m",
)

XINJIANG_GDP_INDEX_FORMULA_REGISTRY = {
    "formula_id": "F-XINJIANG-GDP-INDEX-TO-GROWTH",
    "formula_name": "新疆统计年鉴 GDP 指数转实际增速",
    "expression": "GDP指数（上年=100）- 100",
    "input_fields": "gdp_index_prev_year_100_pct",
    "output_field": "gdp_real_growth_pct",
    "formula_version": "v1.0",
    "unit": "%",
    "enabled": True,
}
XINJIANG_GDP_INDEX_FORMULA_DEPENDENCY = ({
    "formula_id": "F-XINJIANG-GDP-INDEX-TO-GROWTH",
    "depends_on_field": "gdp_index_prev_year_100_pct",
    "dependency_type": "input",
    "formula_version": "v1.0",
},)
XINJIANG_2020_SOURCE_IDS = {
    "SRC-A1-XINJIANG-YEARBOOK-2021-GDP-2020",
    "SRC-A1-XINJIANG-YEARBOOK-2021-GDP-INDEX-2020",
    "SRC-A1-XINJIANG-YEARBOOK-2021-FISCAL-2020",
}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").replace("\u3000", "").replace("\u2002", ""))


def _decimal(value: Any) -> Decimal | None:
    cleaned = _clean(value).replace(",", "").replace("，", "").replace("%", "")
    if not cleaned or cleaned in {"—", "–", "-", "\u2014", "\u2013"}:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _q2(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _row_map(path: Path) -> dict[str, tuple[int, list[str]]]:
    parser = _TableParser()
    parser.feed(path.read_text(encoding="utf-8"))
    result: dict[str, tuple[int, list[str]]] = {}
    for row_number, cells in enumerate(parser.rows, start=1):
        if not cells:
            continue
        name = _clean(cells[0])
        if name in TARGET_CITY_NAMES:
            result[name] = (row_number, cells)
    return result


def _cities_by_name(city_master: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    available = {
        str(row.get("city_name_cn") or ""): str(row.get("city_id") or "")
        for row in city_master
        if str(row.get("metric_year") or "") == YEAR
    }
    return {
        name: available.get(name, city_id)
        for name, city_id in TARGET_CITY_NAMES.items()
        if available.get(name, city_id) == city_id
    }


def _source(
    *,
    source_doc_id: str,
    path: Path,
    url: str,
    document_title: str,
    table_name: str,
    note: str,
) -> dict[str, Any]:
    return {
        "source_doc_id": source_doc_id,
        "publisher": "新疆维吾尔自治区统计局",
        "publisher_level": "省级统计机构",
        "document_title": document_title,
        "table_name": table_name,
        "title_source": "official_html_heading",
        "attachment_title": path.name,
        "document_type": "新疆统计年鉴地州分地区表",
        "source_url": url,
        "landing_page_url": url,
        "attachment_url": url,
        "canonical_url": url,
        "final_resolved_url": url,
        "file_name": path.name,
        "mime_type": "text/html",
        "publication_date": "2022-03-01",
        "publication_date_raw": "2022年公开页面（2021年统计年鉴）",
        "period_end": "2020-12-31",
        "content_hash_sha256": _file_hash(path),
        "archive_uri": f"archive://national-prefecture-panel/{path.as_posix()}",
        "archive_backend": "internal_object",
        "archive_path": path.as_posix(),
        "page_count": "",
        "source_grade": SOURCE_GRADE,
        "http_status": "200",
        "access_status": "新疆统计局官方 HTML 表已归档",
        "supersedes_doc_id": "",
        "note": note,
    }


def _field_source(
    *,
    source_doc_id: str,
    path: Path,
    url: str,
    table_name: str,
    row_number: int,
    city_name: str,
    field: str,
    raw_value: Any,
    normalized_value: str,
    value_origin: str = "disclosed",
) -> dict[str, Any]:
    row_locator = (
        f"{path.as_posix()}；官方页面={url}；统计年鉴表={table_name}；"
        f"HTML表格行={row_number}；地区={city_name}；年度={YEAR}；行政范围=全州/全市/全地区"
    )
    source: dict[str, Any] = {
        "source_doc_id": source_doc_id,
        "source_grade": SOURCE_GRADE,
        "source_format": "html",
        "data_status": "reported",
        "data_status_label": "2020年统计年鉴表值",
        "source_locator": row_locator,
        "table_name": table_name,
        "page_number": "官方 HTML 表格",
        f"{field}_raw_100m": raw_value,
        f"{field}_raw_unit": "万元" if field != "gdp_real_growth_pct" else "指数（上年=100）",
        f"{field}_evidence_excerpt": f"{city_name}｜{raw_value}",
        "lineage_locator_type": "html_table_row",
        "lineage_extraction_method": "official-xinjiang-yearbook-html-table-parser",
        "lineage_normalization_rule": (
            "新疆统计局官方表原始单位为万元；原值÷10000=亿元，保留两位小数；"
            "严格取地州全域行，不取本级、区县或分项。"
            if field != "gdp_real_growth_pct"
            else "新疆统计局官方 GDP 指数表口径为上年=100；指数减100得到实际增速，保留两位小数；全地州口径。"
        ),
        "lineage_selection_reason": (
            "新疆统计局 2021 年统计年鉴分地区表逐行披露 2020 年地州全域值；"
            "严格按地级行政单元白名单筛选，来源等级 A1。"
        ),
    }
    if value_origin == "calculated":
        source.update({
            "value_origin": "calculated",
            "calculation_id": f"CAL-XINJIANG-{city_name}-{YEAR}-GDP-GROWTH",
            "calculation_formula_id": "F-XINJIANG-GDP-INDEX-TO-GROWTH",
            "calculation_input_record_ids": f"{source_doc_id}:{city_name}:{YEAR}",
            "calculation_input_fields": "gdp_index_prev_year_100_pct",
            "calculation_note": "以新疆统计局官方表中 GDP 指数（上年=100）减100，转换为 GDP 实际增速。",
        })
    return source


def load_xinjiang_2020_yearbook_sources(
    root: Path, city_master: Iterable[Mapping[str, Any]]
) -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    """读取新疆 2020 年地州级 GDP、增速和一般预算收支。"""

    root = Path(root)
    total_path = root / GDP_TOTAL_PATH
    index_path = root / GDP_INDEX_PATH
    fiscal_path = root / FISCAL_PATH
    total_rows = _row_map(total_path)
    index_rows = _row_map(index_path)
    fiscal_rows = _row_map(fiscal_path)
    city_ids = _cities_by_name(city_master)
    values: dict[tuple[str, str], dict[str, Any]] = {}
    total_source_id = "SRC-A1-XINJIANG-YEARBOOK-2021-GDP-2020"
    index_source_id = "SRC-A1-XINJIANG-YEARBOOK-2021-GDP-INDEX-2020"
    fiscal_source_id = "SRC-A1-XINJIANG-YEARBOOK-2021-FISCAL-2020"
    total_source = _source(
        source_doc_id=total_source_id,
        path=GDP_TOTAL_PATH,
        url=GDP_TOTAL_URL,
        document_title="2-6 各地、州、市、县(市)地区生产总值",
        table_name="2-6 各地、州、市、县(市)地区生产总值",
        note="官方统计年鉴 GDP 总量表；只接入地州全域行，单位为万元。",
    )
    index_source = _source(
        source_doc_id=index_source_id,
        path=GDP_INDEX_PATH,
        url=GDP_INDEX_URL,
        document_title="2-8 各地、州、市、县(市)地区生产总值指数",
        table_name="2-8 各地、州、市、县(市)地区生产总值指数",
        note="官方统计年鉴 GDP 指数表；指数口径为上年=100，按指数减100计算实际增速。",
    )
    fiscal_source = _source(
        source_doc_id=fiscal_source_id,
        path=FISCAL_PATH,
        url=FISCAL_URL,
        document_title="8-4 各地、州、市、县(市)一般公共预算收支",
        table_name="8-4 各地、州、市、县(市)一般公共预算收支",
        note="官方统计年鉴一般公共预算收支表；收入、支出原始单位为万元，只接入地州全域行。",
    )
    for city_name, city_id in city_ids.items():
        if city_name not in total_rows or city_name not in index_rows or city_name not in fiscal_rows:
            continue
        total_row_number, total_cells = total_rows[city_name]
        index_row_number, index_cells = index_rows[city_name]
        fiscal_row_number, fiscal_cells = fiscal_rows[city_name]
        gdp_raw = _decimal(total_cells[1] if len(total_cells) > 1 else None)
        index_raw = _decimal(index_cells[1] if len(index_cells) > 1 else None)
        revenue_raw = _decimal(fiscal_cells[1] if len(fiscal_cells) > 1 else None)
        expenditure_raw = _decimal(fiscal_cells[2] if len(fiscal_cells) > 2 else None)
        if None in {gdp_raw, index_raw, revenue_raw, expenditure_raw}:
            continue
        gdp = _q2(gdp_raw / Decimal("10000"))
        growth = _q2(index_raw - Decimal("100"))
        revenue = _q2(revenue_raw / Decimal("10000"))
        expenditure = _q2(expenditure_raw / Decimal("10000"))
        fields = {
            "gdp_current_100m": (gdp, total_source_id, GDP_TOTAL_PATH, GDP_TOTAL_URL, total_source["table_name"], total_row_number, gdp_raw),
            "gdp_real_growth_pct": (growth, index_source_id, GDP_INDEX_PATH, GDP_INDEX_URL, index_source["table_name"], index_row_number, index_raw),
            "general_public_revenue_100m": (revenue, fiscal_source_id, FISCAL_PATH, FISCAL_URL, fiscal_source["table_name"], fiscal_row_number, revenue_raw),
            "general_public_expenditure_100m": (expenditure, fiscal_source_id, FISCAL_PATH, FISCAL_URL, fiscal_source["table_name"], fiscal_row_number, expenditure_raw),
        }
        record: dict[str, Any] = {
            field: value for field, (value, *_metadata) in fields.items()
        }
        record.update({
            "source_doc_id": ";".join((total_source_id, index_source_id, fiscal_source_id)),
            "source_grade": SOURCE_GRADE,
            "source_format": "html",
            "data_status": "reported",
            "data_status_label": "2020年统计年鉴表值",
            "source_locator": f"新疆统计局2021年统计年鉴；地区={city_name}；年度={YEAR}；行政范围=地州全域",
            "table_name": "新疆统计局2021年统计年鉴 2-6、2-8、8-4",
            "note": "A1 官方统计年鉴分地区表，严格取地州全域行；GDP 实际增速由官方 GDP 指数（上年=100）减100计算。",
            "gdp_real_growth_pct_value_origin": "calculated",
            "gdp_real_growth_pct_calculation_formula_id": "F-XINJIANG-GDP-INDEX-TO-GROWTH",
            "_field_sources": {},
        })
        for field, (value, source_id, path, url, table_name, row_number, raw) in fields.items():
            field_source = _field_source(
                source_doc_id=source_id,
                path=path,
                url=url,
                table_name=table_name,
                row_number=row_number,
                city_name=city_name,
                field=field,
                raw_value=raw,
                normalized_value=value,
                value_origin="calculated" if field == "gdp_real_growth_pct" else "disclosed",
            )
            record["_field_sources"][field] = field_source
            for key, field_value in field_source.items():
                if key.startswith(f"{field}_") or key in {
                    "value_origin", "calculation_id", "calculation_formula_id",
                    "calculation_input_record_ids", "calculation_input_fields", "calculation_note",
                }:
                    record.setdefault(key, field_value)
        values[(city_id, YEAR)] = record
    return values, [total_source, index_source, fiscal_source]


if __name__ == "__main__":
    import json

    root = Path(__file__).resolve().parents[1]
    city_master = list(csv.DictReader((root / "outputs/national_prefecture_panel_2018_2026/dim_city.csv").open(encoding="utf-8-sig", newline="")))
    values, sources = load_xinjiang_2020_yearbook_sources(root, city_master)
    print(json.dumps({"values": len(values), "sources": [item["source_doc_id"] for item in sources]}, ensure_ascii=False))
