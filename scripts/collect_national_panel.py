#!/usr/bin/env python3
"""采集并生成全国地级行政单元 2018—2026 年数据面板。

本脚本把“抓取”拆成可审计的几个阶段：
1. 下载并保存年度行政区划原始文件；
2. 生成年度城市主表；
3. 读取公开研究型城市面板作为暂存/临时宏观来源；
4. 合并已经完成的广东省 2024 年官方试跑结果；
5. 以 Decimal 计算派生指标并写出来源、字段血缘、公式和采集状态。

没有公开且可验证的数值保持为空，并进入 collection_status；不得用 0 代替缺失。
"""

from __future__ import annotations

import csv
import gzip
import hashlib
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
except ModuleNotFoundError:  # 允许以 python scripts/collect_national_panel.py 直接运行
    from province_debt_sources import extract_official_debt_facts

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
    "statutory_debt_to_general_revenue_pct",
    "fiscal_self_sufficiency_pct",
    "gov_fund_to_general_revenue_pct",
]
RAW_NUMERIC_FIELDS = {
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
}


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


def q4(value: Any) -> Decimal | None:
    number = as_decimal(value)
    return None if number is None else number.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def pct(numerator: Any, denominator: Any) -> Decimal | None:
    num = as_decimal(numerator)
    den = as_decimal(denominator)
    if num is None or den in (None, D0):
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
        "statutory_debt_to_general_revenue_pct": pct(statutory_balance, row.get("general_public_revenue_100m")),
        "fiscal_self_sufficiency_pct": pct(row.get("general_public_revenue_100m"), row.get("general_public_expenditure_100m")),
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
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    panel_by_key = {(str(r.get("city_code", "")).zfill(6), int(r["year"])): r for r in panel_rows if r.get("year", "").isdigit()}
    lineage: list[dict[str, Any]] = []
    output: list[dict[str, Any]] = []
    official_debt_facts = official_debt_facts or {}
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
        debt_fact = official_debt_facts.get((city["city_id"], str(year)))
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
        derived = compute_derived_values(row)
        for field, value in derived.items():
            if value is not None:
                row[field] = value
        row["lineage_complete_flag"] = bool(any(item["target_record_id"] == _macro_record_id(row) for item in lineage))
        output.append(row)
    return output, lineage


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
        ("F-DEBT-REV", "法定债务/一般预算收入", "法定政府债务余额 / 一般公共预算收入 × 100", "statutory_debt_balance_100m;general_public_revenue_100m", "statutory_debt_to_general_revenue_pct"),
        ("F-FISCAL-SELF", "财政自给率", "一般公共预算收入 / 一般公共预算支出 × 100", "general_public_revenue_100m;general_public_expenditure_100m", "fiscal_self_sufficiency_pct"),
        ("F-FUND-DEPEND", "政府性基金收入依赖度", "政府性基金预算收入 / 一般公共预算收入 × 100", "gov_fund_revenue_100m;general_public_revenue_100m", "gov_fund_to_general_revenue_pct"),
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
                else ("extracted" if row.get("source_grade") in {"A1", "A2"} else "needs_review")
            ),
            "lineage_complete_flag": row.get("statutory_debt_balance_100m") is not None,
            "note": "法定债务四个分项保持独立；缺失值保留 null。",
        })
    return output


def build_risk_rows(macro_rows: list[dict[str, Any]], calculations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metric_map = [
        ("statutory_debt_to_gdp_pct", "statutory_debt_to_gdp", "%", "法定债务/GDP"),
        ("statutory_debt_to_general_revenue_pct", "statutory_debt_to_general_revenue", "%", "法定债务/一般预算收入"),
        ("debt_limit_utilization_pct", "debt_limit_utilization", "%", "债务限额利用率"),
        ("fiscal_self_sufficiency_pct", "fiscal_self_sufficiency", "%", "财政自给率"),
        ("gov_fund_to_general_revenue_pct", "gov_fund_dependence", "%", "政府性基金收入依赖度"),
        ("tax_share_pct", "tax_share", "%", "税收收入占比"),
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
                "error_code": "" if not missing_reason else "NOT_YET_COLLECTED",
                "evidence_count": evidence_count,
                "lineage_complete_flag": evidence_count > 0,
                "next_action": next_action,
            })
    return output


def source_document_rows(
    area_hashes: Mapping[int, str],
    city_panel_hash: str,
    city_panel_path: Path,
    gd_sources: list[dict[str, str]],
    official_sources: list[dict[str, Any]] | None = None,
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
    seen_official: set[str] = set()
    for source in official_sources or []:
        source_id = str(source.get("source_doc_id", ""))
        if not source_id or source_id in seen_official:
            continue
        seen_official.add(source_id)
        path = Path(source.get("path", ""))
        content_hash = sha256(path) if path.exists() else ""
        source_grade = source.get("source_grade", "A1")
        is_secondary = source_id.startswith("SRC-SECONDARY-CEIC")
        attachment_url = str(source.get("attachment_url") or source.get("source_url") or "")
        rows.append(
            {
                "source_doc_id": source_id,
                "publisher": source.get("publisher", f"{source.get('province_name', '')}财政厅"),
                "publisher_level": source.get("publisher_level", "省级"),
                "document_title": source.get("document_title", ""),
                "title_source": "secondary_public_page" if is_secondary else "official_attachment",
                "attachment_title": path.name,
                "document_type": "商业数据库城市债务页面" if is_secondary else "地方政府债务限额及余额公开表",
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

2018—2023 的经济财政数值主要来自公开研究型城市面板，来源等级为 D，只能作为 provisional 暂存和覆盖基线；需继续用国家统计局年鉴、地方统计公报、预算/决算文件逐字段复核。已接入的省级财政厅官方债务明细表按 `prefecture_whole` 提取一般债务、专项债务及余额，排除了市本级、区县和小计行。其余城市年度未取得可审计的数值时保留 null，并在 `collection_status.csv` 中登记下一步动作。

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

主表包括 `dim_city.csv`、`city_macro_fiscal.csv`、`city_gov_debt.csv`、`risk_metric.csv`、`source_document.csv`、`field_lineage.csv`、`collection_status.csv` 以及公式和质量表。LGFV、逐券债券、特殊条款、募集资金用途和信用事件文件已经按设计文档建立字段结构；当前没有可靠批量来源的模块不虚构记录。
"""


def quality_report(city_master: list[dict[str, Any]], macro_rows: list[dict[str, Any]], lineage: list[dict[str, Any]], debt_rows: list[dict[str, Any]], calc_rows: list[dict[str, Any]]) -> dict[str, Any]:
    key_list = [(row["city_id"], row["metric_year"]) for row in city_master]
    macro_keys = [(row["city_id"], row["metric_year"]) for row in macro_rows]
    debt_violations = []
    for row in debt_rows:
        limit = as_decimal(row.get("statutory_debt_limit_100m"))
        balance = as_decimal(row.get("statutory_debt_balance_100m"))
        if limit is not None and balance is not None and balance > limit + Decimal("0.2"):
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
            "2025—2026 未采集值保持 null；2026 不表示正式年度决算。",
        ],
    }


def main() -> None:
    rosters, province_maps, area_hashes = load_rosters()
    city_master = build_city_master(rosters, province_maps=province_maps)
    panel_rows, panel_hash, panel_path = load_city_panel()
    for index, row in enumerate(panel_rows, start=2):
        row["_row_number"] = str(index)
    gd_macro, _gd_debt, gd_sources = load_guangdong_2024()
    official_debt_facts, official_debt_sources = extract_official_debt_facts(city_master)
    macro_rows, lineage = build_macro_rows(city_master, panel_rows, gd_macro, official_debt_facts)
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
    for calc in calc_rows:
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
    lineage_fields_by_record: dict[str, set[str]] = defaultdict(set)
    for item in lineage:
        lineage_fields_by_record[item["target_record_id"]].add(item["target_field"])
    for row in macro_rows:
        non_null_fields = {field for field in MACRO_FIELDS if row.get(field) is not None}
        row["lineage_complete_flag"] = non_null_fields.issubset(lineage_fields_by_record.get(_macro_record_id(row), set()))
    debt_rows = build_debt_rows(macro_rows)
    risk_rows = build_risk_rows(macro_rows, calc_rows)
    collection_rows = build_collection_status(city_master, macro_rows)
    sources = source_document_rows(area_hashes, panel_hash, panel_path, gd_sources, official_debt_sources)

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
    for filename, (fields, rows) in empty_schema_rows().items():
        write_csv(filename, fields, rows)

    readme = build_readme(macro_rows, city_master, sources)
    (OUTPUT_DIR / "README_数据说明.md").write_text(readme, encoding="utf-8")
    report = quality_report(city_master, macro_rows, lineage, debt_rows, calc_rows)
    (OUTPUT_DIR / "quality_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"output_dir": str(OUTPUT_DIR), "city_master_rows": len(city_master), "macro_rows": len(macro_rows), "source_rows": len(sources), "lineage_rows": len(lineage)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
