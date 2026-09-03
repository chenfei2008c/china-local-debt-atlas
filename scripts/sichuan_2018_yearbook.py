"""四川省统计局《四川统计年鉴2019》2018年分市州核心指标批次。

年鉴目录公开了四张官方图表：地区生产总值、地区生产总值指数、一般公共预算收入和
一般公共预算支出。这里把图表逐行转录为可审计摘录，并严格按21个地级行政单元接入。
GDP指数按“上年=100”减100计算实际增速；财政表原始单位为万元，统一换算为亿元。
"""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable, Mapping


YEAR = "2018"
SOURCE_GRADE = "A2"
RAW_DIR = Path("raw/province_fiscal/2018/official")

GDP_URL = "https://tjj.sc.gov.cn/scstjj/tjnjnew/2019/zk/html/02-10.jpg"
GDP_INDEX_URL = "https://tjj.sc.gov.cn/scstjj/tjnjnew/2019/zk/html/02-11.jpg"
REVENUE_URL = "https://tjj.sc.gov.cn/scstjj/tjnjnew/2019/zk/html/08-03.jpg"
EXPENDITURE_URL = "https://tjj.sc.gov.cn/scstjj/tjnjnew/2019/zk/html/08-04.jpg"

CITY_IDS = {
    "成都市": "CN-510100",
    "自贡市": "CN-510300",
    "攀枝花市": "CN-510400",
    "泸州市": "CN-510500",
    "德阳市": "CN-510600",
    "绵阳市": "CN-510700",
    "广元市": "CN-510800",
    "遂宁市": "CN-510900",
    "内江市": "CN-511000",
    "乐山市": "CN-511100",
    "南充市": "CN-511300",
    "眉山市": "CN-511400",
    "宜宾市": "CN-511500",
    "广安市": "CN-511600",
    "达州市": "CN-511700",
    "雅安市": "CN-511800",
    "巴中市": "CN-511900",
    "资阳市": "CN-512000",
    "阿坝藏族羌族自治州": "CN-513200",
    "甘孜藏族自治州": "CN-513300",
    "凉山彝族自治州": "CN-513400",
}

# GDP现价单位为亿元；GDP指数为上年=100；财政表单位为万元。
GDP_CURRENT = {
    "成都市": "15342.77", "自贡市": "1406.71", "攀枝花市": "1173.52",
    "泸州市": "1694.97", "德阳市": "2213.87", "绵阳市": "2303.82",
    "广元市": "801.85", "遂宁市": "1221.39", "内江市": "1411.75",
    "乐山市": "1615.09", "南充市": "2006.03", "眉山市": "1256.02",
    "宜宾市": "2026.37", "广安市": "1250.24", "达州市": "1690.17",
    "雅安市": "646.10", "巴中市": "645.88", "资阳市": "1066.53",
    "阿坝藏族羌族自治州": "306.67", "甘孜藏族自治州": "291.20", "凉山彝族自治州": "1533.19",
}

GDP_INDEX = {
    "成都市": "108.0", "自贡市": "108.7", "攀枝花市": "110.7",
    "泸州市": "107.6", "德阳市": "109.0", "绵阳市": "109.0",
    "广元市": "108.4", "遂宁市": "108.8", "内江市": "107.8",
    "乐山市": "108.7", "南充市": "109.0", "眉山市": "107.5",
    "宜宾市": "109.2", "广安市": "108.0", "达州市": "108.3",
    "雅安市": "108.1", "巴中市": "108.0", "资阳市": "107.8",
    "阿坝藏族羌族自治州": "104.7", "甘孜藏族自治州": "109.3", "凉山彝族自治州": "104.0",
}

GENERAL_REVENUE = {
    "成都市": "14241550", "自贡市": "604091", "攀枝花市": "615026",
    "泸州市": "1500905", "德阳市": "1175813", "绵阳市": "1245419",
    "广元市": "476907", "遂宁市": "638447", "内江市": "616958",
    "乐山市": "1099199", "南充市": "1138963", "眉山市": "1031974",
    "宜宾市": "1608883", "广安市": "800524", "达州市": "1010246",
    "雅安市": "400289", "巴中市": "454580", "资阳市": "528490",
    "阿坝藏族羌族自治州": "246610", "甘孜藏族自治州": "300342", "凉山彝族自治州": "1462031",
}

GENERAL_EXPENDITURE = {
    "成都市": "18374238", "自贡市": "2422700", "攀枝花市": "1379392",
    "泸州市": "4121544", "德阳市": "2719508", "绵阳市": "4081641",
    "广元市": "2770144", "遂宁市": "2522120", "内江市": "2433876",
    "乐山市": "3028632", "南充市": "4952197", "眉山市": "2351578",
    "宜宾市": "4160183", "广安市": "2890322", "达州市": "4186791",
    "雅安市": "1305375", "巴中市": "3138866", "资阳市": "1917986",
    "阿坝藏族羌族自治州": "2950767", "甘孜藏族自治州": "4205713", "凉山彝族自治州": "6817064",
}

FIELD_SPECS = {
    "gdp_current_100m": ("GDP", "亿元", GDP_URL, "四川统计年鉴2019 02-10表"),
    "gdp_real_growth_pct": ("GDP指数", "", GDP_INDEX_URL, "四川统计年鉴2019 02-11表"),
    "general_public_revenue_100m": ("一般公共预算收入", "万元", REVENUE_URL, "四川统计年鉴2019 08-03表"),
    "general_public_expenditure_100m": ("一般公共预算支出", "万元", EXPENDITURE_URL, "四川统计年鉴2019 08-04表"),
}

SICHUAN_2018_SOURCE_IDS = {
    "SRC-A2-SICHUAN-YEARBOOK-2019-GDP-2018",
    "SRC-A2-SICHUAN-YEARBOOK-2019-GDP-INDEX-2018",
    "SRC-A2-SICHUAN-YEARBOOK-2019-FISCAL-REVENUE-2018",
    "SRC-A2-SICHUAN-YEARBOOK-2019-FISCAL-EXPENDITURE-2018",
}


def _decimal(value: Any) -> Decimal:
    cleaned = str(value).replace(",", "").replace("，", "").replace("%", "").strip()
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"四川2018年鉴数值无法解析：{value}") from exc


def _q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _extract(path: Path, city_name: str, label: str, unit: str) -> Decimal:
    text = re.sub(r"\s+", "", path.read_text(encoding="utf-8"))
    suffix = re.escape(unit)
    pattern = rf"城市={re.escape(city_name)}｜年度={YEAR}｜{re.escape(label)}=([0-9.,-]+){suffix}"
    match = re.search(pattern, text)
    if not match:
        raise ValueError(f"未能从四川2018年鉴摘录提取{city_name}的{label}")
    return _decimal(match.group(1))


def _source(*, source_doc_id: str, path: Path, url: str, table_name: str, page_number: str) -> dict[str, Any]:
    return {
        "source_doc_id": source_doc_id,
        "publisher": "四川省统计局",
        "publisher_level": "省级统计机构",
        "document_title": "四川统计年鉴2019（2018年分市州表）",
        "title_source": "official_yearbook_index",
        "attachment_title": path.name,
        "document_type": "省级统计年鉴分市州核心经济财政表",
        "source_url": url,
        "landing_page_url": "https://tjj.sc.gov.cn/scstjj/tjnjnew/2019/zk/left_.htm",
        "attachment_url": url,
        "canonical_url": url,
        "final_resolved_url": url,
        "file_name": path.name,
        "mime_type": "text/plain",
        "publication_date": "2019-12-31",
        "publication_date_raw": "2019年官方统计年鉴",
        "period_end": "2018-12-31",
        "content_hash_sha256": _sha256(path),
        "archive_uri": f"archive://national-prefecture-panel/{path.as_posix()}",
        "archive_backend": "internal_object",
        "archive_path": path.as_posix(),
        "page_count": "",
        "source_grade": SOURCE_GRADE,
        "http_status": "200",
        "access_status": "官方年鉴图表入口及逐行摘录已归档",
        "supersedes_doc_id": "",
        "note": f"四川省统计局官方年鉴图表：{table_name}；原始图表页为 {url}；严格采用分市州全域行。",
        "table_name": table_name,
        "page_number": page_number,
    }


def _field_source(
    *, source_doc_id: str, path: Path, url: str, table_name: str, city_name: str,
    field: str, raw_value: Decimal, normalized_value: Decimal, raw_unit: str,
    value_origin: str = "disclosed",
) -> dict[str, Any]:
    source = {
        "source_doc_id": source_doc_id,
        "source_grade": SOURCE_GRADE,
        "source_format": "txt",
        "source_url": url,
        "landing_page_url": "https://tjj.sc.gov.cn/scstjj/tjnjnew/2019/zk/left_.htm",
        "attachment_url": url,
        field: normalized_value,
        "data_status": "reported",
        "data_status_label": "2018年官方统计年鉴表值",
        "source_locator": (
            f"四川统计年鉴2019；{table_name}；摘录文件={path.as_posix()}；"
            f"地区={city_name}；年度=2018；行政范围=全市/全州"
        ),
        "table_name": table_name,
        "page_number": "四川统计年鉴2019官方图表 JPG",
        f"{field}_raw_100m": raw_value,
        f"{field}_raw_unit": raw_unit,
        f"{field}_evidence_excerpt": f"城市={city_name}｜年度=2018｜原始值={raw_value}{raw_unit}",
        "lineage_locator_type": "yearbook_image_row_transcription",
        "lineage_extraction_method": "official-sichuan-2019-yearbook-image-transcription",
        "lineage_normalization_rule": (
            "财政表原始单位为万元，除以10000换算为亿元，保留两位小数。"
            if raw_unit == "万元"
            else "GDP现价表原始单位为亿元，保留两位小数。"
            if raw_unit == "亿元"
            else "GDP指数口径为上年=100，指数减100得到实际增速，保留两位小数。"
        ),
        "lineage_selection_reason": "官方省级统计年鉴逐行披露分市州全域值，严格按21个地级行政单元匹配。",
    }
    if value_origin == "calculated":
        source.update({
            "value_origin": "calculated",
            "calculation_id": f"CAL-SICHUAN-{city_name}-2018-GDP-GROWTH",
            "calculation_formula_id": "F-SICHUAN-GDP-INDEX-TO-GROWTH",
            "calculation_input_record_ids": f"{source_doc_id}:{city_name}:2018",
            "calculation_input_fields": "gdp_index_prev_year_100_pct",
            "calculation_note": "以四川统计年鉴2019官方 GDP 指数（上年=100）减100，转换为GDP实际增速。",
        })
    else:
        source["value_origin"] = "disclosed"
    return source


def _cities_by_name(city_master: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    available = {
        str(row.get("city_name_cn") or ""): str(row.get("city_id") or "")
        for row in city_master
        if str(row.get("metric_year") or "") == YEAR
    }
    return {
        name: available.get(name, city_id)
        for name, city_id in CITY_IDS.items()
        if available.get(name, city_id) == city_id
    }


def load_sichuan_2018_yearbook_sources(
    root: Path, city_master: Iterable[Mapping[str, Any]]
) -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    """读取四川21个市州2018年官方年鉴的GDP、增速和一般预算收支。"""

    root = Path(root)
    paths = {
        "gdp_current_100m": root / RAW_DIR / "sichuan_2018_yearbook_gdp_excerpt.txt",
        "gdp_real_growth_pct": root / RAW_DIR / "sichuan_2018_yearbook_gdp_index_excerpt.txt",
        "general_public_revenue_100m": root / RAW_DIR / "sichuan_2018_yearbook_revenue_excerpt.txt",
        "general_public_expenditure_100m": root / RAW_DIR / "sichuan_2018_yearbook_expenditure_excerpt.txt",
    }
    source_ids = {
        "gdp_current_100m": "SRC-A2-SICHUAN-YEARBOOK-2019-GDP-2018",
        "gdp_real_growth_pct": "SRC-A2-SICHUAN-YEARBOOK-2019-GDP-INDEX-2018",
        "general_public_revenue_100m": "SRC-A2-SICHUAN-YEARBOOK-2019-FISCAL-REVENUE-2018",
        "general_public_expenditure_100m": "SRC-A2-SICHUAN-YEARBOOK-2019-FISCAL-EXPENDITURE-2018",
    }
    sources = [
        _source(
            source_doc_id=source_ids[field],
            path=path.relative_to(root),
            url=FIELD_SPECS[field][2],
            table_name=FIELD_SPECS[field][3],
            page_number=FIELD_SPECS[field][3],
        )
        for field, path in paths.items()
    ]
    source_by_id = {source["source_doc_id"]: source for source in sources}
    values: dict[tuple[str, str], dict[str, Any]] = {}
    for city_name, city_id in _cities_by_name(city_master).items():
        gdp = _extract(paths["gdp_current_100m"], city_name, "GDP", "亿元")
        index = _extract(paths["gdp_real_growth_pct"], city_name, "GDP指数", "")
        revenue = _extract(paths["general_public_revenue_100m"], city_name, "一般公共预算收入", "万元")
        expenditure = _extract(paths["general_public_expenditure_100m"], city_name, "一般公共预算支出", "万元")
        normalized = {
            "gdp_current_100m": _q2(gdp),
            "gdp_real_growth_pct": _q2(index - Decimal("100")),
            "general_public_revenue_100m": _q2(revenue / Decimal("10000")),
            "general_public_expenditure_100m": _q2(expenditure / Decimal("10000")),
        }
        raw_values = {
            "gdp_current_100m": (gdp, "亿元", "disclosed"),
            "gdp_real_growth_pct": (index, "指数（上年=100）", "calculated"),
            "general_public_revenue_100m": (revenue, "万元", "disclosed"),
            "general_public_expenditure_100m": (expenditure, "万元", "disclosed"),
        }
        record: dict[str, Any] = {
            **normalized,
            "source_doc_id": ";".join(source_ids[field] for field in paths),
            "source_grade": SOURCE_GRADE,
            "source_format": "txt",
            "data_status": "reported",
            "data_status_label": "2018年官方统计年鉴表值",
            "source_locator": f"四川统计年鉴2019；地区={city_name}；年度=2018；行政范围=全市/全州",
            "table_name": "四川统计年鉴2019 02-10、02-11、08-03、08-04表",
            "note": "A2四川省统计局官方统计年鉴图表逐行摘录；GDP增速由官方指数（上年=100）减100计算。",
            "_field_sources": {},
        }
        for field, (raw_value, raw_unit, origin) in raw_values.items():
            field_source = _field_source(
                source_doc_id=source_ids[field],
                path=paths[field].relative_to(root),
                url=FIELD_SPECS[field][2],
                table_name=FIELD_SPECS[field][3],
                city_name=city_name,
                field=field,
                raw_value=raw_value,
                normalized_value=normalized[field],
                raw_unit=raw_unit,
                value_origin=origin,
            )
            record["_field_sources"][field] = field_source
            for key, value in field_source.items():
                if key.startswith(f"{field}_") or key in {
                    "value_origin", "calculation_id", "calculation_formula_id",
                    "calculation_input_record_ids", "calculation_input_fields", "calculation_note",
                }:
                    record.setdefault(key, value)
        values[(city_id, YEAR)] = record
    return values, [source_by_id[source_ids[field]] for field in paths]


if __name__ == "__main__":
    print("四川2018年鉴适配器已定义")
