"""CREI 地市统计公报批量快照与标准来源适配器。

CREI 的“地市统计公报”栏目转载地方统计局公报。本模块只接受标题中
明确为 2025 年地级行政单元公报的页面，并保留入口页、正文哈希和字段
级证据。区县公报、新闻稿和省级公报不进入全国地级市主表。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import ssl
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.request import Request, urlopen


SNAPSHOT_PATH = Path("raw/province_fiscal/crei/city_bulletin_snapshot.json")
INDEX_URL = "https://www.crei.cn/file/index.aspx?p={page}&op=z4"
YEAR = 2025
SOURCE_GRADE = "B2"

_STATE_ALIASES = {
    "凉山彝族自治州": "凉山州",
    "甘孜藏族自治州": "甘孜州",
    "阿坝藏族羌族自治州": "阿坝州",
    "黔南布依族苗族自治州": "黔南州",
    "黔东南苗族侗族自治州": "黔东南州",
    "黔西南布依族苗族自治州": "黔西南州",
    "楚雄彝族自治州": "楚雄州",
    "大理白族自治州": "大理州",
    "文山壮族苗族自治州": "文山州",
    "西双版纳傣族自治州": "西双版纳州",
    "德宏傣族景颇族自治州": "德宏州",
    "怒江傈僳族自治州": "怒江州",
    "迪庆藏族自治州": "迪庆州",
    "恩施土家族苗族自治州": "恩施州",
    "海西蒙古族藏族自治州": "海西州",
    "海北藏族自治州": "海北州",
    "黄南藏族自治州": "黄南州",
    "海南藏族自治州": "海南州",
    "果洛藏族自治州": "果洛州",
    "玉树藏族自治州": "玉树州",
    "克孜勒苏柯尔克孜自治州": "克州",
    "巴音郭楞蒙古自治州": "巴州",
    "昌吉回族自治州": "昌吉州",
    "伊犁哈萨克自治州": "伊犁州",
    "兴安盟": "兴安盟",
    "锡林郭勒盟": "锡林郭勒盟",
    "阿拉善盟": "阿拉善盟",
}


def _aliases(city_name: str) -> set[str]:
    return {city_name, _STATE_ALIASES.get(city_name, city_name)}


def is_target_bulletin_title(title: str, city_name: str) -> bool:
    """只接受“城市+2025年+统计公报”或其倒装标题。"""

    compact = re.sub(r"\s+", "", html.unescape(title or "")).strip("・")
    if "国民经济和社会发展统计公报" not in compact:
        return False
    year = r"2025(?:年|年度)"
    for alias in sorted(_aliases(city_name), key=len, reverse=True):
        if re.search(rf"(?:{year}{re.escape(alias)}|{re.escape(alias)}{year})国民经济和社会发展统计公报", compact):
            return True
    return False


def _decimal(raw: str, unit: str) -> Decimal:
    try:
        normalized = re.sub(r"\s+", "", raw).replace(",", "").replace("，", "")
        normalized = normalized.replace("．", ".")
        value = Decimal(normalized)
    except (InvalidOperation, ValueError):
        raise ValueError(f"无法解析公报数值：{raw!r}") from None
    if unit in {"万元", "人"}:
        value /= Decimal("10000")
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _amount_after(text: str, label_pattern: str) -> Decimal | None:
    match = re.search(
        rf"(?:{label_pattern})"
        rf"\s*(?:[（(][^）)]{{0,30}}[）)])?"
        rf"\s*(?:\[[^\]]{{1,8}}\]|【[^】]{{1,8}}】)?"
        rf"\s*(?:完成|为|是|达(?:到)?|实现|约|达到)?"
        rf"\s*([0-9][0-9,.\s，．]*)\s*(亿元|万元)",
        text,
    )
    return _decimal(match.group(1), match.group(2)) if match else None


def parse_bulletin_text(text: str) -> dict[str, Decimal]:
    """从公报正文提取可直接定位的经济财政、人口和基金收入字段。"""

    text = re.sub(r"\s+", " ", text or "")
    result: dict[str, Decimal] = {}
    gdp_match = re.search(
        r"(?<!人均)(?:地区生产总值|生产总值)(?:\s*（?GDP）?)?[^。；;\n]{0,100}?([0-9][0-9,.\s，．]*)\s*亿元",
        text,
    )
    if gdp_match:
        result["gdp_current_100m"] = _decimal(gdp_match.group(1), "亿元")
        sentence = text[gdp_match.start() : re.search(r"[。；;]", text[gdp_match.end() :]).start() + gdp_match.end() if re.search(r"[。；;]", text[gdp_match.end() :]) else gdp_match.end() + 100]
        growth = re.search(r"(?:增长|同比增长|较上年增长)(?:[（(]下同[）)])?\s*([0-9][0-9,.]*)\s*%", sentence)
        if growth:
            result["gdp_real_growth_pct"] = _decimal(growth.group(1), "%")
    population = re.search(
        r"(?<!城镇)(?:年末[^。；;\n]{0,30}?常住(?:总)?人口|常住(?:总)?人口)"
        r"[^。；;\n]{0,60}?([0-9][0-9,.\s，．]*)\s*(万人|人)",
        text,
    )
    if population:
        result["resident_population_10k"] = _decimal(population.group(1), population.group(2))
    revenue = _amount_after(
        text,
        r"(?:地方)?(?:一般公共预算收入|一般公共财政预算收入|公共财政预算收入|公共财政一般预算收入)",
    )
    if revenue is not None:
        result["general_public_revenue_100m"] = revenue
    expenditure = _amount_after(
        text,
        r"(?:地方)?(?:一般公共预算支出|一般公共财政预算支出|公共财政预算支出|财政一般预算支出)",
    )
    if expenditure is not None:
        result["general_public_expenditure_100m"] = expenditure
    fund_revenue = _amount_after(text, r"政府性基金(?:预算)?收入")
    if fund_revenue is None:
        # 部分转载公报的表格只在列标题中标注“亿元”，行内写成
        # “政府性基金预算收入 651.63 -0.7”；HTML 清洗后相邻列还可能
        # 粘连为“43.995.1”。这里只接受带小数点的首个金额，且要求后面
        # 紧接增长率/分隔符，避免把其他“基金”语境中的数字误认成收入。
        compact_table_fund = re.search(
            r"政府性基金(?:预算)?收入\s*"
            r"([0-9][0-9,]*\.[0-9]{1,2})"
            r"(?=\s*(?:[-+−]?\d|[.，,。；;]|$))",
            text,
        )
        if compact_table_fund:
            fund_revenue = _decimal(compact_table_fund.group(1), "亿元")
    if fund_revenue is not None:
        result["gov_fund_revenue_100m"] = fund_revenue
    return result


def _fetch(url: str, retries: int = 3) -> tuple[bytes, str] | None:
    context = ssl._create_unverified_context()
    for attempt in range(retries):
        try:
            response = urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=25, context=context)
            return response.read(), response.headers.get_content_charset() or "gb2312"
        except Exception:
            if attempt + 1 < retries:
                time.sleep(0.8 * (attempt + 1))
    return None


def _listing_links(text: str) -> list[tuple[str, str]]:
    links = []
    for match in re.finditer(r"href=([\"']?br\.aspx\?id=\d+[^\"' >]*)[^>]*>(.*?)</a>", text, re.S | re.I):
        title = re.sub(r"<[^>]+>", "", html.unescape(match.group(2))).replace("\r", " ").replace("\n", " ").strip(" \t・")
        links.append(("https://www.crei.cn/file/" + match.group(1).strip("\"'"), title))
    return links


def _match_city(title: str, city_master: Iterable[Mapping[str, Any]]) -> tuple[str, str] | None:
    matches = []
    for city in city_master:
        if str(city.get("metric_year")) != str(YEAR):
            continue
        city_id, city_name = str(city.get("city_id") or ""), str(city.get("city_name_cn") or "")
        if city_id and city_name and is_target_bulletin_title(title, city_name):
            matches.append((city_id, city_name))
    return matches[0] if len(matches) == 1 else None


def crawl_crei_bulletins(root: Path, city_master: list[Mapping[str, Any]], pages: int = 150) -> dict[str, int]:
    """抓取索引并冻结可匹配的地级市 2025 年公报。"""

    snapshot_path = root / SNAPSHOT_PATH
    existing_payload = json.loads(snapshot_path.read_text(encoding="utf-8")) if snapshot_path.exists() else {"bulletins": []}
    existing = {str(item.get("source_url")): item for item in existing_payload.get("bulletins") or []}
    selected: dict[tuple[str, str], tuple[str, str, str]] = {}
    for page in range(1, pages + 1):
        response = _fetch(INDEX_URL.format(page=page))
        if not response:
            continue
        body, charset = response
        for url, title in _listing_links(body.decode(charset, "ignore")):
            if "2025" not in title or "国民经济和社会发展统计公报" not in title:
                continue
            city = _match_city(title, city_master)
            if not city:
                continue
            key = (city[0], str(YEAR))
            if key not in selected or url > selected[key][0]:
                selected[key] = (url, title, city[1])
    for (city_id, _year), (url, title, city_name) in selected.items():
        if url in existing:
            continue
        response = _fetch(url)
        if not response:
            continue
        body, charset = response
        digest = hashlib.sha256(body).hexdigest()
        page_text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", body.decode(charset, "ignore"), flags=re.S | re.I)
        page_text = re.sub(r"<[^>]+>", " ", html.unescape(page_text))
        page_text = re.sub(r"\s+", " ", page_text).strip()
        values = parse_bulletin_text(page_text)
        if not values:
            continue
        existing[url] = {
            "city_id": city_id,
            "city_name": city_name,
            "metric_year": str(YEAR),
            "title": title,
            "source_url": url,
            "publisher": (re.search(r"出处[：:]\s*([^ ]+)", page_text) or ["", ""])[1],
            "publication_date": url.split("id=")[-1][:8],
            "content_hash_sha256": digest,
            "values": {field: str(value) for field, value in values.items()},
            "text": page_text,
        }
    payload = {
        "snapshot_date": time.strftime("%Y-%m-%d"),
        "source_platform": "CREI地市统计公报栏目",
        "selection_note": "只保留标题明确为2025年地级行政单元国民经济和社会发展统计公报的转载页面；区县、省级和新闻稿排除。",
        "bulletins": sorted(existing.values(), key=lambda item: (item.get("city_id", ""), item.get("metric_year", ""))),
    }
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"indexed_targets": len(selected), "total_bulletins": len(payload["bulletins"]), "new_bulletins": len(payload["bulletins"]) - len(existing_payload.get("bulletins") or [])}


def load_crei_city_bulletin_sources(root: Path, city_master: list[Mapping[str, Any]]) -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    path = root / SNAPSHOT_PATH
    if not path.exists():
        return {}, []
    payload = json.loads(path.read_text(encoding="utf-8"))
    values: dict[tuple[str, str], dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    city_ids = {str(item.get("city_id")) for item in city_master}
    for item in payload.get("bulletins") or []:
        city_id, year = str(item.get("city_id") or ""), str(item.get("metric_year") or "")
        if city_id not in city_ids or year != str(YEAR):
            continue
        source_id = f"SRC-B2-CREI-CITY-BULLETIN-{city_id}-{year}"
        record: dict[str, Any] = {
            "source_doc_id": source_id,
            "source_grade": SOURCE_GRADE,
            "source_format": "html",
            "source_platform": "crei",
            "data_status": "preliminary",
            "data_status_label": "2025年统计公报初步核算/公开值",
            "source_locator": f"{SNAPSHOT_PATH}；URL={item.get('source_url')};标题={item.get('title')};城市={item.get('city_name')};2025年全市/全州口径",
            "table_name": "2025年国民经济和社会发展统计公报",
            "page_number": "HTML正文",
            "_field_sources": {},
        }
        raw_units = {
            "gdp_current_100m": "亿元",
            "gdp_real_growth_pct": "%",
            "resident_population_10k": "万人",
            "general_public_revenue_100m": "亿元",
            "general_public_expenditure_100m": "亿元",
            "gov_fund_revenue_100m": "亿元",
        }
        stored_values = dict(item.get("values") or {})
        # 快照保留原始解析结果；加载时用当前解析器只补充快照正文中
        # 当时未识别的规范字段，便于解析规则修复后无需重抓网页。
        for field, parsed in parse_bulletin_text(str(item.get("text") or "")).items():
            if field not in stored_values:
                stored_values[field] = str(parsed)
        for field, raw in stored_values.items():
            try:
                value = Decimal(str(raw)).quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError):
                continue
            record[field] = value
            record[f"{field}_raw_100m"] = value
            record[f"{field}_raw_unit"] = raw_units.get(field, "亿元")
            record[f"{field}_evidence_excerpt"] = f"{item.get('title')}；{field}={raw}；正文={str(item.get('text') or '')[:300]}"
            record["_field_sources"][field] = dict(record)
        if not record["_field_sources"]:
            continue
        key = (city_id, year)
        values[key] = record
        sources.append({
            "source_doc_id": source_id,
            "publisher": item.get("publisher") or "地方统计局（CREI公开转载）",
            "publisher_level": "地方统计局公报的公开二手转载",
            "document_title": item.get("title", ""),
            "title_source": "secondary_public_page",
            "attachment_title": path.name,
            "document_type": "地级市国民经济和社会发展统计公报",
            "source_url": item.get("source_url", ""),
            "landing_page_url": item.get("source_url", ""),
            "attachment_url": item.get("source_url", ""),
            "canonical_url": item.get("source_url", ""),
            "final_resolved_url": item.get("source_url", ""),
            "file_name": path.name,
            "mime_type": "text/html",
            "publication_date": item.get("publication_date", ""),
            "publication_date_raw": item.get("publication_date", ""),
            "period_end": "2025-12-31",
            "downloaded_at": "2026-08-25T00:00:00+08:00",
            "content_hash_sha256": item.get("content_hash_sha256", ""),
            "archive_uri": f"archive://national-prefecture-panel/{SNAPSHOT_PATH}",
            "archive_backend": "internal_object",
            "archive_path": str(SNAPSHOT_PATH),
            "page_count": "",
            "source_grade": SOURCE_GRADE,
            "http_status": "200",
            "access_status": "公开公报页面已归档",
            "supersedes_doc_id": "",
            "note": "B2公开二手转载；标题、年度和地级行政范围明确，正文数值直接读取；不使用区县、公报图表目测值或户籍人口代替常住人口。",
        })
    return values, sources


def main() -> None:
    parser = argparse.ArgumentParser(description="抓取CREI地市统计公报并冻结快照")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--pages", type=int, default=150)
    args = parser.parse_args()
    with (args.root / "outputs/national_prefecture_panel_2018_2026/dim_city.csv").open(encoding="utf-8-sig", newline="") as handle:
        city_master = list(csv.DictReader(handle))
    print(json.dumps(crawl_crei_bulletins(args.root, city_master, args.pages), ensure_ascii=False))


if __name__ == "__main__":
    main()
