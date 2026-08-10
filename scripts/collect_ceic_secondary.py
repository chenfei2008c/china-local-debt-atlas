#!/usr/bin/env python3
"""抓取 CEIC 城市级地方政府债务余额，作为可追溯的次级补缺层。

CEIC 页面公开展示城市全域地方政府债务余额（单位：百万元人民币）。本脚本只
抓取页面明确展示的数值：2018—2024 年来自 SVG 图表，2025 年来自页面元数据。
来源等级固定为 D，不能替代财政厅、人大预算/决算或官方统计公报；但可作为
缺口清单、官方检索线索和暂存值。未返回城市页的请求不会被当成 0。
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "raw" / "province_debt" / "secondary" / "ceic_city_debt_2018_2025.csv"
DEFAULT_PROBE_OUTPUT = ROOT / "raw" / "province_debt" / "secondary" / "ceic_city_page_hits.json"
BASE_PAGE = "https://www.ceicdata.com/zh-hans/china/local-government-debt-prefecture-level-city-outstanding/cn-local-government-debt-outstanding-"
BASE_CHART = "https://www.ceicdata.com/datapage/charts/o_china_cn-local-government-debt-outstanding-"

# 只列入当前全国快照中法定债务余额缺口的地级行政单元。直辖县级占位行没有
# 可安全映射的“全域城市页”，留待海南、湖北、新疆官方合计表处理。
CITY_SLUGS: dict[str, tuple[str, str]] = {
    "CN-130300": ("秦皇岛市", "hebei-qinhuangdao"),
    "CN-130600": ("保定市", "hebei-baoding"),
    "CN-130800": ("承德市", "hebei-chengde"),
    "CN-130900": ("沧州市", "hebei-cangzhou"),
    "CN-131100": ("衡水市", "hebei-hengshui"),
    "CN-140100": ("太原市", "shanxi-taiyuan"),
    "CN-140300": ("阳泉市", "shanxi-yangquan"),
    "CN-140600": ("朔州市", "shanxi-shuozhou"),
    "CN-140800": ("运城市", "shanxi-yuncheng"),
    "CN-140900": ("忻州市", "shanxi-xinzhou"),
    "CN-141000": ("临汾市", "shanxi-linfen"),
    "CN-150200": ("包头市", "inner-mongolia-baotou"),
    "CN-150300": ("乌海市", "inner-mongolia-wuhai"),
    "CN-150500": ("通辽市", "inner-mongolia-tongliao"),
    "CN-150600": ("鄂尔多斯市", "inner-mongolia-ordos"),
    "CN-150700": ("呼伦贝尔市", "inner-mongolia-hulunbuir"),
    "CN-150800": ("巴彦淖尔市", "inner-mongolia-bayannur"),
    "CN-150900": ("乌兰察布市", "inner-mongolia-ulanqab"),
    "CN-152200": ("兴安盟", "inner-mongolia-xinganmeng"),
    "CN-152500": ("锡林郭勒盟", "inner-mongolia-xilingol"),
    "CN-152900": ("阿拉善盟", "inner-mongolia-alxa"),
    "CN-320700": ("连云港市", "jiangsu-lianyungang"),
    "CN-321100": ("镇江市", "jiangsu-zhenjiang"),
    "CN-331100": ("丽水市", "zhejiang-lishui"),
    "CN-360500": ("新余市", "jiangxi-xinyu"),
    "CN-360900": ("宜春市", "jiangxi-yichun"),
    "CN-420900": ("孝感市", "hubei-xiaogan"),
    "CN-421100": ("黄冈市", "hubei-huanggang"),
    "CN-421300": ("随州市", "hubei-suizhou"),
    "CN-422800": ("恩施土家族苗族自治州", "hubei-enshi"),
    "CN-450300": ("桂林市", "guangxi-guilin"),
    "CN-450500": ("北海市", "guangxi-beihai"),
    "CN-451100": ("贺州市", "guangxi-hezhou"),
    "CN-451200": ("河池市", "guangxi-hechi"),
    "CN-451300": ("来宾市", "guangxi-laibin"),
    "CN-460300": ("三沙市", "hainan-sansha"),
    "CN-460400": ("儋州市", "hainan-danzhou"),
    "CN-530600": ("昭通市", "yunnan-zhaotong"),
    "CN-530700": ("丽江市", "yunnan-lijiang"),
    "CN-530800": ("普洱市", "yunnan-puer"),
    "CN-532300": ("楚雄彝族自治州", "yunnan-chuxiong"),
    "CN-532600": ("文山壮族苗族自治州", "yunnan-wenshan"),
    "CN-532800": ("西双版纳傣族自治州", "yunnan-xishuangbanna"),
    "CN-533100": ("德宏傣族景颇族自治州", "yunnan-dehong"),
    "CN-533300": ("怒江傈僳族自治州", "yunnan-nujiang"),
    "CN-620100": ("兰州市", "gansu-lanzhou"),
    "CN-620200": ("嘉峪关市", "gansu-jiayuguan"),
    "CN-620300": ("金昌市", "gansu-jinchang"),
    "CN-620600": ("武威市", "gansu-wuwei"),
    "CN-620800": ("平凉市", "gansu-pingliang"),
    "CN-620900": ("酒泉市", "gansu-jiuquan"),
    "CN-621000": ("庆阳市", "gansu-qingyang"),
    "CN-621100": ("定西市", "gansu-dingxi"),
    "CN-621200": ("陇南市", "gansu-longnan"),
    "CN-622900": ("临夏回族自治州", "gansu-linxia"),
    "CN-623000": ("甘南藏族自治州", "gansu-gannan"),
}

PROVINCE_SLUGS = {
    "北京市": "beijing",
    "天津市": "tianjin",
    "河北省": "hebei",
    "山西省": "shanxi",
    "内蒙古自治区": "inner-mongolia",
    "辽宁省": "liaoning",
    "吉林省": "jilin",
    "黑龙江省": "heilongjiang",
    "上海市": "shanghai",
    "江苏省": "jiangsu",
    "浙江省": "zhejiang",
    "安徽省": "anhui",
    "福建省": "fujian",
    "江西省": "jiangxi",
    "山东省": "shandong",
    "河南省": "henan",
    "湖北省": "hubei",
    "湖南省": "hunan",
    "广东省": "guangdong",
    "广西壮族自治区": "guangxi",
    "海南省": "hainan",
    "重庆市": "chongqing",
    "四川省": "sichuan",
    "贵州省": "guizhou",
    "云南省": "yunnan",
    "西藏自治区": "tibet",
    "陕西省": "shaanxi",
    "甘肃省": "gansu",
    "青海省": "qinghai",
    "宁夏回族自治区": "ningxia",
    "新疆维吾尔自治区": "xinjiang",
}

ETHNIC_TOKENS = (
    "柯尔克孜族", "哈萨克族", "土家族", "苗族", "彝族", "壮族", "傣族", "景颇族",
    "傈僳族", "藏族", "回族", "侗族", "布依族", "白族", "哈尼族", "拉祜族", "佤族",
    "羌族", "朝鲜族", "蒙古族", "瑶族", "水族", "仡佬族", "毛南族", "京族",
    "柯尔克孜", "哈萨克",
)

# 由 CEIC 分页索引填充；全量索引模式下只请求明确存在的指标页面，避免
# 对不存在的 total/general/special 页面逐一等待超时。
INDEXED_COMPONENTS: dict[str, set[str]] = {}


def _pinyin_city_slug(city_name: str) -> str:
    """将中文地级行政单元名转换为 CEIC 常用的英文 slug。"""
    try:
        from pypinyin import lazy_pinyin
    except ImportError as exc:  # pragma: no cover - only used for --all-cities
        raise RuntimeError("--all-cities 需要 pypinyin；请先安装 pypinyin") from exc
    name = city_name
    if name.endswith("自治州"):
        name = name[: -len("自治州")]
        for token in ETHNIC_TOKENS:
            name = name.replace(token, "")
    elif name.endswith("自治州"):
        name = name[: -len("自治州")]
    for suffix in ("地区", "市", "盟", "林区"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    # CEIC 对三个盟使用约定俗成的英文名称，而不是汉字直译。
    special = {"阿拉善": "alxa", "兴安": "xinganmeng", "锡林郭勒": "xilingol"}
    if name in special:
        return special[name]
    return "-".join(lazy_pinyin(name, errors="ignore"))


def _all_city_slugs(city_master_path: Path) -> dict[str, tuple[str, str]]:
    """从城市主表生成全国候选 CEIC slug；已有人工核验 slug 优先。"""
    cities: dict[str, tuple[str, str]] = dict(CITY_SLUGS)
    seen: set[str] = set()
    with city_master_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            city_id = row.get("city_id", "")
            province = row.get("province_name", "")
            city_name = row.get("city_name_cn", "")
            if not city_id or city_id in seen or province not in PROVINCE_SLUGS:
                continue
            seen.add(city_id)
            # 省直辖县级行政区划没有可安全映射的地级市全域页。
            if city_id.endswith("9000") or "直辖县级" in city_name:
                continue
            if city_id not in cities:
                city_slug = _pinyin_city_slug(city_name)
                if city_slug:
                    cities[city_id] = (city_name, f"{PROVINCE_SLUGS[province]}-{city_slug}")
    return cities


def _ceic_city_name_key(name: str) -> str:
    """将 CEIC 标题中的城市名归一化为城市主表可匹配的名称。"""
    value = re.sub(r"\s+", "", name or "")
    for suffix in ("市", "地区", "盟", "自治州", "林区"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
            break
    return value


def _discover_index_city_slugs(city_master_path: Path, pages: int = 8) -> dict[str, tuple[str, str]]:
    """从 CEIC 地级市数据集的分页索引读取真实 slug，避免仅依赖拼音猜测。"""
    province_display = {
        "北京市": "北京", "天津市": "天津", "河北省": "河北", "山西省": "山西",
        "内蒙古自治区": "内蒙古", "辽宁省": "辽宁", "吉林省": "吉林", "黑龙江省": "黑龙江",
        "上海市": "上海", "江苏省": "江苏", "浙江省": "浙江", "安徽省": "安徽",
        "福建省": "福建", "江西省": "江西", "山东省": "山东", "河南省": "河南",
        "湖北省": "湖北", "湖南省": "湖南", "广东省": "广东", "广西壮族自治区": "广西",
        "海南省": "海南", "重庆市": "重庆", "四川省": "四川", "贵州省": "贵州",
        "云南省": "云南", "西藏自治区": "西藏", "陕西省": "陕西", "甘肃省": "甘肃",
        "青海省": "青海", "宁夏回族自治区": "宁夏", "新疆维吾尔自治区": "新疆",
    }
    lookup: dict[tuple[str, str], tuple[str, str]] = {}
    with city_master_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            city_id = row.get("city_id", "")
            province = row.get("province_name", "")
            city_name = row.get("city_name_cn", "")
            if not city_id or province not in province_display or not city_name:
                continue
            if city_id.endswith("9000") or "直辖县级" in city_name:
                continue
            lookup[(province_display[province], _ceic_city_name_key(city_name))] = (city_id, city_name)

    discovered: dict[str, tuple[str, str]] = {}
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Accept-Language": "zh-CN,zh;q=0.9"})
    base = "https://www.ceicdata.com/datapage/zh-hans/orphans_for_orphan_group/china/local-government-debt-prefecture-level-city-outstanding"
    for page_number in range(1, pages + 1):
        try:
            response = session.get(
                f"{base}?page={page_number}",
                headers={"Referer": "https://www.ceicdata.com/zh-hans/china/local-government-debt-prefecture-level-city-outstanding"},
                timeout=30,
            )
            payload = response.json()
        except (requests.RequestException, ValueError):
            break
        if response.status_code != 200 or payload.get("status") != "success" or not payload.get("html"):
            break
        soup = BeautifulSoup(payload["html"], "html.parser")
        for item in soup.select(".orphan-group-item"):
            anchor = item.select_one("h3 a[href]")
            if not anchor:
                continue
            title = anchor.get_text(" ", strip=True)
            parts = [part for part in title.split(":") if part]
            if len(parts) < 3:
                continue
            province_display_name = parts[-2]
            city_key = _ceic_city_name_key(parts[-1])
            match = lookup.get((province_display_name, city_key))
            if not match:
                continue
            city_id, city_name = match
            slug_match = re.search(r"cn-local-government-debt-outstanding-(?:general-|special-)?(.+)$", anchor["href"])
            if not slug_match:
                continue
            discovered[city_id] = (city_name, slug_match.group(1))
            if len(parts) == 3:
                component = "total"
            elif parts[1] == "一般":
                component = "general"
            elif parts[1] == "专项":
                component = "special"
            else:
                continue
            INDEXED_COMPONENTS.setdefault(city_id, set()).add(component)
        if not soup.select_one(".orphan-group-item"):
            break
    return discovered


def _numeric(text: str) -> Decimal | None:
    match = re.search(r"\d[\d\s,]*\.\d+", text or "")
    if not match:
        return None
    return Decimal(match.group(0).replace(" ", "").replace(",", ""))


def _description(page: str) -> str:
    match = re.search(r'<meta\s+name="description"\s+content="([^"]+)', page, re.I)
    return html.unescape(match.group(1)) if match else ""


def _page_url(slug: str, component: str | None = None) -> str:
    prefix = f"{component}-" if component else ""
    return f"{BASE_PAGE}{prefix}{slug}"


def _fetch_page(session: requests.Session, slug: str, component: str | None = None) -> tuple[str, str, str] | None:
    url = _page_url(slug, component)
    try:
        response = session.get(url, timeout=10)
    except requests.RequestException:
        return None
    marker = f"cn-local-government-debt-outstanding-{('' if component is None else component + '-')}{slug}"
    if response.status_code != 200 or marker not in response.url or len(response.content) > 800_000:
        return None
    return url, response.url, response.text


def _chart_values(session: requests.Session, page_url: str, slug: str, component: str | None, page: str) -> dict[int, Decimal]:
    marker = f"{('' if component is None else component + '-')}{slug}"
    chart_base = f"{BASE_CHART}{('' if component is None else component + '-')}{slug}/"
    image_match = re.search(r'"image"\s*:\s*"([^"]+)', page)
    if image_match and "datapage/charts" in image_match.group(1):
        # 页面已经根据该城市实际可用区间生成了图表 URL；必须保留原始
        # from/to，部分城市只接受 2017—2025 或 2015—2024 的固定区间。
        chart_url = html.unescape(image_match.group(1))
    else:
        query = urlencode({"type": "area", "from": "2015-12-01", "to": "2024-12-01", "lang": "zh-hans"})
        chart_url = f"{chart_base}?{query}"
    chart_session = requests.Session()
    chart_session.headers.update({"User-Agent": "Mozilla/5.0", "Accept-Language": "zh-CN,zh;q=0.9"})
    try:
        # CloudFront 偶尔会把页面和图表分配到不同的后端；先在独立会话
        # 建立页面 cookie，再请求 SVG，稳定性明显高于复用三张指标页的会话。
        chart_session.get(page_url, timeout=10)
        response = chart_session.get(
            chart_url,
            headers={"Referer": page_url, "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"},
            timeout=10,
        )
        if response.status_code != 200:
            response = session.get(chart_url, headers={"Referer": page_url}, timeout=10)
    except requests.RequestException:
        return {}
    if response.status_code != 200 or "<svg" not in response.text[:1000]:
        return {}
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError:
        return {}
    years: list[int] = []
    labels: list[str] = []
    for element in root.iter():
        cls = element.attrib.get("class", "")
        if "highcharts-xaxis-labels" in cls:
            # SVG 文本标签之间通常没有分隔符，会拼成“201520162017…”。
            years.extend(int(x) for x in re.findall(r"20\d{2}", "".join(element.itertext())))
        if "highcharts-data-label" in cls.split():
            labels.append("".join(element.itertext()))
    values = [_numeric(label) for label in labels]
    return {year: value for year, value in zip(years, values) if value is not None}


def _latest_2025(desc: str) -> Decimal | None:
    match = re.search(r"12-01-2025达([\d,.]+)百万人民币", desc)
    return Decimal(match.group(1).replace(",", "")) if match else None


def _previous_2024(desc: str) -> Decimal | None:
    """从 CEIC 2025 年摘要中的同比基准句提取 2024 年值。

    部分城市页的图表接口已不再返回 SVG，但页面元数据仍保留“相较于
    12-01-2024 的 X 百万人民币”这一可审计摘要。该值只能作为 CEIC
    次级补缺值，不能覆盖更高等级的官方来源。
    """
    patterns = (
        r"相较于12-01-2024的([\d,.]+)百万人民币",
        r"相较于\s*12-01-2024\s*的\s*([\d,.]+)百万人民币",
    )
    for pattern in patterns:
        match = re.search(pattern, desc)
        if match:
            return Decimal(match.group(1).replace(",", ""))
    return None


def _fetch_city(city_id: str, item: tuple[str, str]) -> dict[str, Any]:
    city_name, slug = item
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Accept-Language": "zh-CN,zh;q=0.9"})
    pages: dict[str, tuple[str, str, str]] = {}
    components = INDEXED_COMPONENTS.get(city_id)
    if components:
        component_order = [None, "general", "special"]
        requested_components = [component for component in component_order if ("total" if component is None else component) in components]
    else:
        # 对已确认命中的城市页先请求总额页；只有总额页不存在时才探测一般/专项页，
        # 避免对全国快照中的大批组件页重复发起慢请求。
        requested_components = [None]
    for component in requested_components:
        page = _fetch_page(session, slug, component)
        if page:
            pages["total" if component is None else component] = page
    if not pages and not components:
        for component in ("general", "special"):
            page = _fetch_page(session, slug, component)
            if page:
                pages[component] = page
    if not pages:
        return {"city_id": city_id, "city_name_cn": city_name, "slug": slug, "rows": [], "status": "no_city_pages"}

    metric_values: dict[str, dict[int, Decimal]] = {}
    sources: dict[str, str] = {}
    evidence: dict[tuple[str, int], str] = {}
    for metric, page_info in pages.items():
        page_url, _, page = page_info
        metric_values[metric] = _chart_values(session, page_url, slug, None if metric == "total" else metric, page)
        sources[metric] = page_url
        for year, value in metric_values[metric].items():
            evidence[(metric, year)] = f"CEIC图表：{year}年={value}百万人民币"
        latest = _latest_2025(_description(page))
        if latest is not None:
            metric_values[metric][2025] = latest
            evidence[(metric, 2025)] = f"CEIC页面元数据：2025年={latest}百万人民币"
        previous = _previous_2024(_description(page))
        if previous is not None:
            metric_values[metric][2024] = previous
            evidence[(metric, 2024)] = f"CEIC页面元数据同比基准：2024年={previous}百万人民币"

    rows: list[dict[str, Any]] = []
    all_years = sorted(set().union(*(set(values) for values in metric_values.values())))
    for year in all_years:
        if year < 2018 or year > 2025:
            continue
        origin = "disclosed"
        if metric_values.get("total", {}).get(year) is not None:
            value = metric_values["total"][year]
            source_url = sources["total"]
            excerpt = evidence[("total", year)]
        elif metric_values.get("general", {}).get(year) is not None and metric_values.get("special", {}).get(year) is not None:
            value = metric_values["general"][year] + metric_values["special"][year]
            source_url = f"{sources['general']};{sources['special']}"
            excerpt = f"CEIC一般+专项分项：一般={metric_values['general'][year]}，专项={metric_values['special'][year]}百万人民币；合计为计算值"
            origin = "calculated"
        else:
            continue
        rows.append(
            {
                "city_id": city_id,
                "city_name_cn": city_name,
                "metric_year": year,
                "statutory_debt_balance_100m": value * Decimal("0.01"),
                "raw_value_million_rmb": value,
                "value_origin": origin,
                "source_doc_id": f"SRC-SECONDARY-CEIC-{city_id}",
                "source_url": source_url,
                "evidence_excerpt": excerpt,
                "source_grade": "D",
            }
        )
    status = "total_page" if "total" in pages else "components_only"
    return {"city_id": city_id, "city_name_cn": city_name, "slug": slug, "rows": rows, "status": status, "sources": sources}


def _probe_city(city_id: str, item: tuple[str, str], timeout: tuple[float, float]) -> dict[str, Any]:
    """短超时探测城市页，避免不存在的候选 slug 拖慢全量扫描。"""
    city_name, slug = item
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Accept-Language": "zh-CN,zh;q=0.9"})
    hits: dict[str, str] = {}
    for component in (None, "general", "special"):
        url = _page_url(slug, component)
        marker = f"cn-local-government-debt-outstanding-{('' if component is None else component + '-')}{slug}"
        try:
            response = session.get(url, timeout=timeout, allow_redirects=True)
        except requests.RequestException:
            continue
        if response.status_code == 200 and marker in response.url and len(response.content) <= 800_000:
            hits["total" if component is None else component] = url
    return {"city_id": city_id, "city_name_cn": city_name, "slug": slug, "hits": hits}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--all-cities",
        action="store_true",
        help="从全国城市主表生成候选 CEIC slug，扫描所有地级行政单元而非仅扫描当前缺口",
    )
    parser.add_argument(
        "--city-master",
        type=Path,
        default=ROOT / "outputs" / "national_prefecture_panel_2018_2026" / "dim_city.csv",
    )
    parser.add_argument(
        "--city-slugs-json",
        type=Path,
        help="只抓取 JSON 中的城市 slug 映射（格式为 {city_id: [中文名, slug]}）",
    )
    parser.add_argument(
        "--ceic-index",
        action="store_true",
        help="从 CEIC 地级市数据集的分页索引读取真实城市 slug；比拼音猜测更完整",
    )
    parser.add_argument(
        "--ceic-index-pages",
        type=int,
        default=8,
        help="CEIC 索引最多扫描页数（默认 8，当前公开索引通常少于此数）",
    )
    parser.add_argument(
        "--probe-only",
        action="store_true",
        help="仅用短超时探测城市页是否存在，并输出命中城市清单",
    )
    parser.add_argument("--probe-output", type=Path, default=DEFAULT_PROBE_OUTPUT)
    parser.add_argument("--probe-connect-timeout", type=float, default=3.0)
    parser.add_argument("--probe-read-timeout", type=float, default=7.0)
    args = parser.parse_args()
    if args.city_slugs_json:
        city_slugs = {
            city_id: (str(item[0]), str(item[1]))
            for city_id, item in json.loads(args.city_slugs_json.read_text(encoding="utf-8")).items()
        }
    else:
        city_slugs = _all_city_slugs(args.city_master) if args.all_cities else dict(CITY_SLUGS)
    if args.ceic_index:
        indexed_slugs = _discover_index_city_slugs(args.city_master, pages=max(1, args.ceic_index_pages))
        city_slugs.update(indexed_slugs)
        print(f"CEIC 索引识别城市：{len(indexed_slugs)}")
    if args.probe_only:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            futures = [
                executor.submit(
                    _probe_city,
                    city_id,
                    item,
                    (args.probe_connect_timeout, args.probe_read_timeout),
                )
                for city_id, item in city_slugs.items()
            ]
            probe_results = [future.result() for future in as_completed(futures)]
        probe_results.sort(key=lambda item: item["city_id"])
        hit_slugs = {
            item["city_id"]: (item["city_name_cn"], item["slug"])
            for item in probe_results
            if item["hits"]
        }
        args.probe_output.parent.mkdir(parents=True, exist_ok=True)
        args.probe_output.write_text(
            __import__("json").dumps(hit_slugs, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"城市页命中：{len(hit_slugs)}/{len(city_slugs)}")
        print(f"探测结果：{args.probe_output}")
        return 0
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [executor.submit(_fetch_city, city_id, item) for city_id, item in city_slugs.items()]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: item["city_id"])
    fields = [
        "city_id", "city_name_cn", "metric_year", "statutory_debt_balance_100m",
        "raw_value_million_rmb", "value_origin", "source_doc_id", "source_url",
        "evidence_excerpt", "source_grade",
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            writer.writerows(result["rows"])
    print(f"城市页状态：{sum(result['status'] != 'no_city_pages' for result in results)}/{len(results)}")
    print(f"抓取记录：{sum(len(result['rows']) for result in results)}")
    print(f"输出：{args.output}")
    for result in results:
        if result["status"] != "no_city_pages":
            print(result["city_id"], result["city_name_cn"], result["status"], len(result["rows"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
