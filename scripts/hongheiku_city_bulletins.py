"""红黑统计公报库地级市 2019—2025 年公报批量适配器。

红黑统计公报库是公开的统计公报转载索引。本适配器只接受标题明确指向
地级行政单元本身的 2019—2025 年公报，并把页面正文作为 B2 精确二手来源：
不读取区县页面，不从图表估读，也不把转载页标为官方 A2 来源。

与 CREI 快照适配器分开保存，避免混淆两个转载入口；两者最终都通过
``_field_sources`` 进入全国主表的字段级血缘。
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import html
import json
import re
import ssl
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

try:
    from scripts.crei_city_bulletins import parse_bulletin_text
except ModuleNotFoundError:  # 允许以 python scripts/hongheiku_city_bulletins.py 直接运行
    from crei_city_bulletins import parse_bulletin_text


SNAPSHOT_PATH = Path("raw/province_fiscal/hongheiku/city_bulletin_snapshot.json")
SITEMAP_URL = "https://tjgb.hongheiku.com/wp-sitemap-posts-post-10.xml"
WP_API_POSTS_URL = "https://tjgb.hongheiku.com/wp-json/wp/v2/posts"
WP_PREFECTURE_CATEGORY_ID = 2
SUPPORTED_YEARS = {"2019", "2020", "2021", "2022", "2023", "2024", "2025"}
SOURCE_GRADE = "B2"
TARGET_FIELDS = (
    "gdp_current_100m",
    "gdp_real_growth_pct",
    "resident_population_10k",
    "general_public_revenue_100m",
    "general_public_expenditure_100m",
    "gov_fund_revenue_100m",
)
XML_NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
SHORT_ALIASES = {
    "巴音郭楞蒙古自治州": "巴州",
    "昌吉回族自治州": "昌吉州",
    "克孜勒苏柯尔克孜自治州": "克州",
    "伊犁哈萨克自治州": "伊犁州",
    "恩施土家族苗族自治州": "恩施州",
    "海西蒙古族藏族自治州": "海西州",
    "海北藏族自治州": "海北州",
    "黄南藏族自治州": "黄南州",
    "海南藏族自治州": "海南州",
    "果洛藏族自治州": "果洛州",
    "玉树藏族自治州": "玉树州",
    "楚雄彝族自治州": "楚雄州",
    "大理白族自治州": "大理州",
    "红河哈尼族彝族自治州": "红河州",
    "西双版纳傣族自治州": "西双版纳州",
    "德宏傣族景颇族自治州": "德宏州",
    "怒江傈僳族自治州": "怒江州",
    "迪庆藏族自治州": "迪庆州",
    "甘南藏族自治州": "甘南州",
    "临夏回族自治州": "临夏州",
    "延边朝鲜族自治州": "延边州",
    "甘孜藏族自治州": "甘孜州",
}


def _compact(value: Any) -> str:
    return re.sub(r"\s+", "", html.unescape(str(value or "")))


def is_target_bulletin_title(title: str, city_name: str, year: str = "2025") -> bool:
    """匹配地级市本身的指定年度公报标题，排除该市下辖区县公报。"""

    compact = _compact(title).strip("・")
    # 部分区县/开发区标题会以“(地级市)2024年...”开头，导致仅按城市别名和
    # 年份匹配时误归入地级市。开发区、园区和县级公报均不属于本适配器的
    # 地级行政单元范围；“新区”不在排除列表中，因为雄安新区本身是主表单元。
    excluded_scope_markers = (
        "县级统计公报",
        "县级公报",
        "开发区",
        "高新区",
        "高新技术产业开发区",
        "经济技术开发区",
        "经开区",
        "工业园区",
        "管理区",
        "示范区",
    )
    if any(marker in compact for marker in excluded_scope_markers):
        return False
    if year not in SUPPORTED_YEARS:
        return False
    years = {
        "2019": ("2019年", "2019年度", "二〇一九年", "二○一九年", "二Ｏ一九年"),
        "2020": ("2020年", "2020年度", "二〇二〇年", "二○二〇年", "二Ｏ二〇年"),
        "2021": ("2021年", "2021年度", "二〇二一年", "二○二一年", "二Ｏ二一年"),
        "2022": ("2022年", "2022年度", "二〇二二年", "二○二二年", "二Ｏ二二年"),
        "2023": ("2023年", "2023年度", "二〇二三年", "二○二三年", "二Ｏ二三年"),
        "2024": ("2024年", "2024年度", "二〇二四年", "二○二四年"),
        "2025": ("2025年", "2025年度", "二〇二五年", "二○二五年"),
    }[year]
    city = _compact(city_name)
    aliases = {city}
    if city.endswith("市"):
        aliases.add(city[:-1])
    if "自治州" in city:
        aliases.add(city.replace("自治州", "州"))
        short = SHORT_ALIASES.get(city)
        if short:
            aliases.add(short)
    if "地区" in city:
        aliases.add(city.replace("地区", "地区"))
    for alias in sorted(aliases, key=len, reverse=True):
        for year in years:
            # 两种常见顺序：2025年城市公报、城市2025年公报。
            if re.search(rf"(?:^|[）)]){re.escape(alias)}{re.escape(year)}.*统计(?:数据)?公报", compact):
                return True
            if re.search(rf"{re.escape(year)}{re.escape(alias)}.*统计(?:数据)?公报", compact):
                return True
    return False


def _page_text(body: bytes) -> str:
    text = body.decode("utf-8", "ignore")
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", html.unescape(text))
    text = text.replace("％", "%").replace("－", "-").replace("—", "-")
    # 部分转载页的 PDF/OCR 正文把年份和小数拆成数字+空格；只合并数字之间的空格。
    text = re.sub(r"(?<=\d)\s+(?=\d)", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _published_date(text: str, url: str) -> str:
    match = re.search(r"发布于\s*(\d{4}-\d{2}-\d{2})", text)
    if match:
        return match.group(1)
    match = re.search(r"id=(\d{8})", url)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d").date().isoformat()
        except ValueError:
            pass
    return ""


def _publisher(text: str) -> str:
    match = re.search(r"来源[：:]\s*([^ ]{2,40})", text)
    if not match:
        return "地方统计局（红黑统计公报库转载）"
    value = re.split(r"发布于|分类|选择区域", match.group(1), maxsplit=1)[0].strip("，,；;")
    return value or "地方统计局（红黑统计公报库转载）"


def _is_prefecture_bulletin_text(text: str) -> bool:
    """按转载页正文分类再次确认地级市口径，排除县区公报误匹配。"""

    compact = _compact(text)
    # 站点公共导航同时包含“县级统计公报”和“地级市统计公报”，不能只按
    # 页面全文查找；只检查正文开头的面包屑/分类元信息。
    header = compact[:1600]
    if re.search(r"当前位置：[^。]{0,120}>(?:县级|区县)统计公报", header):
        return False
    if re.search(r"分类：(?:县级|区县)统计公报", header):
        return False
    return True


def _fetch(url: str) -> tuple[bytes, str] | None:
    try:
        response = urlopen(
            Request(url, headers={"User-Agent": "Mozilla/5.0"}),
            timeout=6,
            context=ssl._create_unverified_context(),
        )
        return response.read(), response.headers.get_content_charset() or "utf-8"
    except Exception:
        return None


def _fetch_wp_api(params: Iterable[tuple[str, Any]]) -> tuple[list[dict[str, Any]], Mapping[str, str]] | None:
    """读取 WordPress REST API，保留响应头中的分页信息。"""

    query = urlencode(list(params), doseq=True)
    url = f"{WP_API_POSTS_URL}?{query}"
    try:
        response = urlopen(
            Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}),
            timeout=20,
            context=ssl._create_unverified_context(),
        )
        payload = json.loads(response.read().decode(response.headers.get_content_charset() or "utf-8"))
        if not isinstance(payload, list):
            return None
        return payload, dict(response.headers.items())
    except Exception:
        return None


def _wp_title(post: Mapping[str, Any]) -> str:
    rendered = (post.get("title") or {}).get("rendered", "")
    return _compact(re.sub(r"<[^>]+>", "", html.unescape(str(rendered))))


def _wp_post_candidate(
    post: Mapping[str, Any],
    city_lookup: Mapping[str, Mapping[str, list[tuple[str, str, str]]]],
) -> dict[str, Any] | None:
    """将 WordPress 结构化帖子转换为现有快照格式。"""

    title = _wp_title(post)
    city = _match_city(title, city_lookup)
    if not city:
        return None
    content = (post.get("content") or {}).get("rendered", "")
    text = _page_text(str(content).encode("utf-8"))
    values = {field: value for field, value in parse_bulletin_text(text).items() if field in TARGET_FIELDS}
    if not values:
        return None
    city_id, city_name, year = city
    source_url = str(post.get("link") or "")
    post_date = str(post.get("date") or "")[:10]
    return {
        "city_id": city_id,
        "city_name": city_name,
        "metric_year": year,
        "title": title,
        "source_url": source_url,
        "publisher": _publisher(text),
        "publication_date": _published_date(text, source_url) or post_date,
        "content_hash_sha256": hashlib.sha256(str(content).encode("utf-8")).hexdigest(),
        "values": {field: str(value) for field, value in values.items()},
        "text": text,
    }


def crawl_hongheiku_wp_api(
    root: Path,
    city_master: list[Mapping[str, Any]],
    batch_size: int = 100,
) -> dict[str, int]:
    """通过地级市分类的 REST API 批量获取尚未归档的帖子正文。"""

    snapshot_path = root / SNAPSHOT_PATH
    if snapshot_path.exists():
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    else:
        payload = {"bulletins": []}
    existing = {str(item.get("source_url")): item for item in payload.get("bulletins") or []}
    city_lookup = _build_city_lookup(city_master)
    first = _fetch_wp_api(
        (
            ("categories", WP_PREFECTURE_CATEGORY_ID),
            ("per_page", 100),
            ("page", 1),
            ("_fields", "id,link,title,date"),
        )
    )
    if not first:
        return {"api_pages": 0, "candidate_posts": 0, "total_bulletins": len(existing), "new_bulletins": 0}
    metadata, headers = first
    total_pages = int(headers.get("X-WP-TotalPages", "1"))
    metadata_pages = [metadata]
    for page in range(2, total_pages + 1):
        result = _fetch_wp_api(
            (
                ("categories", WP_PREFECTURE_CATEGORY_ID),
                ("per_page", 100),
                ("page", page),
                ("_fields", "id,link,title,date"),
            )
        )
        if result:
            metadata_pages.append(result[0])
    candidates = []
    for page in metadata_pages:
        for post in page:
            source_url = str(post.get("link") or "")
            if source_url in existing:
                continue
            if _match_city(_wp_title(post), city_lookup):
                candidates.append(post)

    additions: list[dict[str, Any]] = []
    for start in range(0, len(candidates), batch_size):
        ids = [int(post["id"]) for post in candidates[start : start + batch_size] if post.get("id")]
        if not ids:
            continue
        params: list[tuple[str, Any]] = [("categories", WP_PREFECTURE_CATEGORY_ID)]
        params.extend(("include[]", post_id) for post_id in ids)
        params.extend((("per_page", 100), ("_fields", "id,link,title,date,content")))
        result = _fetch_wp_api(params)
        if not result:
            continue
        for post in result[0]:
            source_url = str(post.get("link") or "")
            if source_url in existing:
                continue
            item = _wp_post_candidate(post, city_lookup)
            if item:
                additions.append(item)
                existing[source_url] = item
        _write_snapshot(snapshot_path, existing.values())
    _write_snapshot(snapshot_path, existing.values())
    return {
        "api_pages": len(metadata_pages),
        "candidate_posts": len(candidates),
        "total_bulletins": len(existing),
        "new_bulletins": len(additions),
    }


def _sitemap_urls(sitemap_url: str = SITEMAP_URL) -> list[str]:
    fetched = _fetch(sitemap_url)
    if not fetched:
        return []
    body, charset = fetched
    try:
        root = ET.fromstring(body.decode(charset, "ignore"))
    except ET.ParseError:
        return []
    return [item.findtext("s:loc", namespaces=XML_NS) for item in root.findall("s:url", XML_NS) if item.findtext("s:loc", namespaces=XML_NS)]


def _filter_sitemap_urls(urls: Iterable[str], path_prefixes: Iterable[str] = ()) -> list[str]:
    """按 URL 路径前缀筛选站点地图，减少明显无关页面的请求。"""

    prefixes = tuple(
        "/" + str(prefix).strip().strip("/")
        for prefix in path_prefixes
        if str(prefix).strip().strip("/")
    )
    if not prefixes:
        return list(urls)
    return [
        url
        for url in urls
        if any(urlparse(url).path.startswith(prefix + "/") or urlparse(url).path == prefix for prefix in prefixes)
    ]


def _unfetched_urls(urls: Iterable[str], existing: Mapping[str, Any]) -> list[str]:
    """只返回快照中尚未归档的页面，避免重复请求已完成的批次。"""

    return [url for url in urls if url not in existing]


def _city_aliases(city_name: str) -> set[str]:
    city = _compact(city_name)
    aliases = {city}
    if city.endswith("市"):
        aliases.add(city[:-1])
    if "自治州" in city:
        aliases.add(city.replace("自治州", "州"))
        short = SHORT_ALIASES.get(city)
        if short:
            aliases.add(short)
    return {alias for alias in aliases if alias}


def _build_city_lookup(city_master: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, list[tuple[str, str, str]]]]:
    lookup: dict[str, dict[str, list[tuple[str, str, str]]]] = {}
    for city in city_master:
        year = str(city.get("metric_year") or "")
        city_id = str(city.get("city_id") or "")
        city_name = str(city.get("city_name_cn") or "")
        if year not in SUPPORTED_YEARS or not city_id or not city_name:
            continue
        year_aliases = lookup.setdefault(year, {})
        for alias in _city_aliases(city_name):
            year_aliases.setdefault(alias, []).append((city_id, city_name, year))
    return lookup


def _match_city(
    title: str,
    city_lookup: Mapping[str, Mapping[str, list[tuple[str, str, str]]]] | Iterable[Mapping[str, Any]],
) -> tuple[str, str, str] | None:
    compact = _compact(title)
    year_match = re.search(r"20(?:19|20|21|22|23|24|25)", compact)
    title_year = year_match.group(0) if year_match else ""
    if isinstance(city_lookup, Mapping):
        matches = []
        for alias, cities in city_lookup.get(title_year, {}).items():
            if f"{alias}{title_year}" not in compact and f"{title_year}{alias}" not in compact:
                continue
            for city_id, city_name, year in cities:
                if is_target_bulletin_title(title, city_name, year):
                    matches.append((city_id, city_name, year))
    else:
        matches = []
        for city in city_lookup:
            year = str(city.get("metric_year") or "")
            if title_year and year != title_year:
                continue
            if year not in SUPPORTED_YEARS:
                continue
            city_id = str(city.get("city_id") or "")
            city_name = str(city.get("city_name_cn") or "")
            if city_id and city_name and is_target_bulletin_title(title, city_name, year):
                matches.append((city_id, city_name, year))
    return matches[0] if len(matches) == 1 else None


def _fetch_candidate(
    url: str,
    city_lookup: Mapping[str, Mapping[str, list[tuple[str, str, str]]]],
) -> dict[str, Any] | None:
    fetched = _fetch(url)
    if not fetched:
        return None
    body, charset = fetched
    decoded = body.decode(charset, "ignore")
    title_match = re.search(r"<title[^>]*>(.*?)</title>", decoded, flags=re.S | re.I)
    title = re.sub(r"<[^>]+>", "", html.unescape(title_match.group(1) if title_match else ""))
    city = _match_city(title, city_lookup)
    if not city:
        return None
    text = _page_text(body)
    if not _is_prefecture_bulletin_text(text):
        return None
    values = parse_bulletin_text(text)
    values = {field: value for field, value in values.items() if field in TARGET_FIELDS}
    if not values:
        return None
    city_id, city_name, year = city
    return {
        "city_id": city_id,
        "city_name": city_name,
        "metric_year": year,
        "title": _compact(title),
        "source_url": url,
        "publisher": _publisher(text),
        "publication_date": _published_date(text, url),
        "content_hash_sha256": hashlib.sha256(body).hexdigest(),
        "values": {field: str(value) for field, value in values.items()},
        "text": text,
    }


def crawl_hongheiku_bulletins(
    root: Path,
    city_master: list[Mapping[str, Any]],
    workers: int = 16,
    sitemap_urls: Iterable[str] | None = None,
    url_path_prefixes: Iterable[str] = (),
) -> dict[str, int]:
    """批量抓取指定 sitemap 中可匹配的地级市公报。"""

    snapshot_path = root / SNAPSHOT_PATH
    if snapshot_path.exists():
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    else:
        payload = {"bulletins": []}
    existing = {str(item.get("source_url")): item for item in payload.get("bulletins") or []}
    city_lookup = _build_city_lookup(city_master)
    sitemap_list = list(sitemap_urls or (SITEMAP_URL,))
    urls: list[str] = []
    for sitemap_url in sitemap_list:
        urls.extend(_sitemap_urls(sitemap_url))
    urls = _filter_sitemap_urls(dict.fromkeys(urls), url_path_prefixes)
    urls = _unfetched_urls(urls, existing)
    additions: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_fetch_candidate, url, city_lookup) for url in urls]
        for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            try:
                item = future.result()
            except Exception:
                item = None
            if item and item["source_url"] not in existing:
                additions.append(item)
                existing[item["source_url"]] = item
            # 允许长批次中断后从已完成的页面继续，不丢失前面的可用证据。
            if index % 100 == 0:
                _write_snapshot(snapshot_path, existing.values())
    all_items = sorted(existing.values(), key=lambda item: (item.get("city_id", ""), item.get("metric_year", ""), item.get("source_url", "")))
    _write_snapshot(snapshot_path, all_items)
    return {"sitemap_urls": len(urls), "total_bulletins": len(all_items), "new_bulletins": len(additions)}


def _write_snapshot(snapshot_path: Path, items: Iterable[Mapping[str, Any]]) -> None:
    output = {
        "snapshot_date": time.strftime("%Y-%m-%d"),
        "source_platform": "红黑统计公报库（地方统计公报公开转载）",
        "selection_note": "只保留标题明确为2019—2025年地级行政单元本身的统计公报；区县公报、图表估读和无法解析的页面排除。数值以页面正文直接读取，来源等级为B2。",
        "bulletins": sorted(items, key=lambda item: (item.get("city_id", ""), item.get("metric_year", ""), item.get("source_url", ""))),
    }
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_hongheiku_city_bulletin_sources(
    root: Path,
    city_master: list[Mapping[str, Any]],
) -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    path = root / SNAPSHOT_PATH
    if not path.exists():
        return {}, []
    payload = json.loads(path.read_text(encoding="utf-8"))
    city_ids = {str(item.get("city_id")) for item in city_master}
    values: dict[tuple[str, str], dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    for item in payload.get("bulletins") or []:
        city_id = str(item.get("city_id") or "")
        year = str(item.get("metric_year") or "")
        if city_id not in city_ids or year not in SUPPORTED_YEARS:
            continue
        # 快照可能来自旧版匹配器；加载时再次按标题校验，避免历史上已经
        # 错归到地级市的区县/开发区记录继续进入主表。
        if not is_target_bulletin_title(str(item.get("title") or ""), str(item.get("city_name") or ""), year):
            continue
        source_id = f"SRC-B2-HONGHEIKU-CITY-BULLETIN-{city_id}-{year}"
        record: dict[str, Any] = {
            "source_doc_id": source_id,
            "source_grade": SOURCE_GRADE,
            "source_format": "html",
            "source_platform": "hongheiku",
            "data_status": "preliminary",
            "data_status_label": f"{year}年统计公报公开值（转载）",
            "source_locator": f"{SNAPSHOT_PATH}；URL={item.get('source_url')};标题={item.get('title')};城市={item.get('city_name')};{year}年全市/全州口径",
            "table_name": f"{year}年国民经济和社会发展统计公报",
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
        bulletin_text = str(item.get("text") or "")
        if not _is_prefecture_bulletin_text(bulletin_text):
            continue
        # 快照保留原始解析结果；加载时用当前解析器只补充快照正文中
        # 当时未识别的规范字段，便于解析规则修复后无需重抓网页。
        for field, parsed in parse_bulletin_text(bulletin_text).items():
            if field in TARGET_FIELDS and field not in stored_values:
                stored_values[field] = str(parsed)
        for field, raw in stored_values.items():
            try:
                value = Decimal(str(raw)).quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError):
                continue
            record[field] = value
            record[f"{field}_raw_100m"] = value
            record[f"{field}_raw_unit"] = raw_units[field]
            record[f"{field}_evidence_excerpt"] = f"{item.get('title')}；{field}={raw}；正文={bulletin_text[:500]}"
            record["_field_sources"][field] = dict(record)
        if not record["_field_sources"]:
            continue
        values[(city_id, year)] = record
        source_url = str(item.get("source_url") or "")
        sources.append({
            "source_doc_id": source_id,
            "publisher": item.get("publisher") or "地方统计局（红黑统计公报库转载）",
            "publisher_level": "地方统计局公报的公开二手转载",
            "document_title": item.get("title", ""),
            "title_source": "secondary_public_page",
            "attachment_title": path.name,
            "document_type": "地级市国民经济和社会发展统计公报",
            "source_url": source_url,
            "landing_page_url": source_url,
            "attachment_url": source_url,
            "canonical_url": source_url,
            "final_resolved_url": source_url,
            "file_name": path.name,
            "mime_type": "text/html",
            "publication_date": item.get("publication_date", ""),
            "publication_date_raw": item.get("publication_date", ""),
            "period_end": f"{year}-12-31",
            "downloaded_at": "2026-08-27T00:00:00+08:00",
            "content_hash_sha256": item.get("content_hash_sha256", ""),
            "archive_uri": f"archive://national-prefecture-panel/{SNAPSHOT_PATH}",
            "archive_backend": "internal_object",
            "archive_path": str(SNAPSHOT_PATH),
            "page_count": "",
            "source_grade": SOURCE_GRADE,
            "http_status": "200",
            "access_status": "公开转载页面已归档",
            "supersedes_doc_id": "",
            "note": "B2公开二手转载；标题、年度和地级行政范围明确，数值从正文直接读取；不使用区县、公报图表目测值或户籍人口代替常住人口。",
        })
    return values, sources


def main() -> None:
    parser = argparse.ArgumentParser(description="抓取红黑统计公报库地级市2019—2025年公报")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--sitemap-url", action="append", default=None, help="要抓取的 WordPress 站点地图，可重复指定")
    parser.add_argument("--url-path-prefix", action="append", default=None, help="只抓取指定 URL 路径前缀，可重复指定，例如 djs/")
    args = parser.parse_args()
    with (args.root / "outputs/national_prefecture_panel_2018_2026/dim_city.csv").open(encoding="utf-8-sig", newline="") as handle:
        city_master = list(csv.DictReader(handle))
    print(
        json.dumps(
            crawl_hongheiku_bulletins(
                args.root,
                city_master,
                args.workers,
                args.sitemap_url,
                args.url_path_prefix or (),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()


__all__ = [
    "crawl_hongheiku_bulletins",
    "crawl_hongheiku_wp_api",
    "is_target_bulletin_title",
    "load_hongheiku_city_bulletin_sources",
]
