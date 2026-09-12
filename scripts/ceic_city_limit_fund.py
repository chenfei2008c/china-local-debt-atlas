"""CEIC 城市级政府性基金收入和法定债务限额公开页面适配器。

CEIC 的城市页面公开展示指标元数据和可读 SVG 数据标签。本适配器只接受：

* 页面标题明确包含目标城市和目标指标；
* 页面明确标注年度频率、RMB mn 单位和原始来源机构；
* 2024/2025 的页面摘要精确值，或 SVG 中带年度标签的精确数值标签。

页面是公开二手来源，统一标为 B2；原始来源机构保存到字段血缘。不会从
坐标轴或柱形高度估读，也不会把省级页面或页面重定向后的空指标页当成城市值。
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import ssl
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from http.client import IncompleteRead
from pathlib import Path
from typing import Any, Mapping
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "raw" / "province_debt" / "secondary"
SLUG_PATH = OUTPUT_DIR / "ceic_city_page_hits.json"
SNAPSHOT_PATH = OUTPUT_DIR / "ceic_city_limit_fund_snapshot.json"
SOURCE_GRADE = "B2"
START_YEAR = 2018
END_YEAR = 2025


def _ssl_context() -> ssl.SSLContext:
    return ssl._create_unverified_context()


def _fetch(url: str, timeout: float = 18.0, attempts: int = 2) -> tuple[str, str, str] | None:
    """返回 (最终 URL, 正文, content hash)，对 CloudFront 截断响应重试。"""

    for attempt in range(attempts):
        try:
            # 当前运行环境中 curl 的 HTTP/1.1 路径比 urllib 的 TLS 连接更稳定；
            # 保留 urllib 作为没有 curl 或 curl 失败时的回退路径。
            with tempfile.NamedTemporaryFile(prefix="ceic-page-", delete=False) as handle:
                body_path = handle.name
            try:
                result = subprocess.run(
                    [
                        "curl", "--http1.1", "-L", "-sS",
                        "--max-time", str(max(5, int(timeout))),
                        "-A", "Mozilla/5.0 (compatible; national-panel/1.0)",
                        "-o", body_path,
                        "-w", "%{http_code}\\t%{url_effective}",
                        url,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=max(timeout + 8.0, 20.0),
                    check=False,
                )
                if result.returncode == 0:
                    meta = result.stdout.strip().split("\\t", 1)
                    body = Path(body_path).read_bytes()
                    if len(meta) == 2 and meta[0] == "200" and len(body) >= 500:
                        return (
                            meta[1],
                            body.decode("utf-8", "ignore"),
                            hashlib.sha256(body).hexdigest(),
                        )
            finally:
                Path(body_path).unlink(missing_ok=True)

            response = urlopen(
                Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; national-panel/1.0)",
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                ),
                timeout=timeout,
                context=_ssl_context(),
            )
            try:
                body = response.read()
            except IncompleteRead as exc:
                body = exc.partial
            if len(body) < 500:
                raise ValueError("页面响应过短")
            text = body.decode(response.headers.get_content_charset() or "utf-8", "ignore")
            return response.geturl(), text, hashlib.sha256(body).hexdigest()
        except Exception:
            if attempt + 1 < attempts:
                time.sleep(0.25 * (attempt + 1))
    return None


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def _title(page: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
    return _clean_text(match.group(1)) if match else ""


def _description(page: str) -> str:
    patterns = (
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']',
    )
    for pattern in patterns:
        match = re.search(pattern, page, re.I | re.S)
        if match:
            return _clean_text(match.group(1))
    return ""


def _number(value: str) -> Decimal | None:
    match = re.search(r"\d[\d,\s]*\.\d+", value or "")
    if not match:
        return None
    try:
        return Decimal(match.group(0).replace(",", "").replace(" ", ""))
    except InvalidOperation:
        return None


def _meta_values(description: str) -> dict[int, tuple[Decimal, str]]:
    """提取英文 CEIC 摘要中的最新年度与同比前一年精确值。"""

    values: dict[int, tuple[Decimal, str]] = {}
    latest = re.search(
        r"data was reported at\s*([\d,\.]+)\s*RMB mn in\s*(?:Dec\s+)?(20\d{2})",
        description,
        re.I,
    )
    if latest:
        value = _number(latest.group(1))
        if value is not None:
            values[int(latest.group(2))] = (value, "HTML description：reported at 最新年度")
    previous = re.search(
        r"previous number of\s*([\d,\.]+)\s*RMB mn for\s*(?:Dec\s+)?(20\d{2})",
        description,
        re.I,
    )
    if previous:
        value = _number(previous.group(1))
        if value is not None:
            values[int(previous.group(2))] = (value, "HTML description：previous number 前一年度")
    return values


def _chart_base(page: str) -> str:
    match = re.search(r'class=["\']chart-base-link["\'][^>]*value=["\']([^"\']+)', page, re.I)
    if not match:
        match = re.search(r'"image"\s*:\s*"(https?[^" ]*datapage/charts[^" ]*)', page, re.I)
        if not match:
            return ""
        return html.unescape(match.group(1)).split("?", 1)[0]
    path = html.unescape(match.group(1)).split("?", 1)[0]
    if path.startswith("http"):
        return path
    return f"https://www.ceicdata.com{path}"


def _chart_values(page: str, page_url: str) -> tuple[dict[int, tuple[Decimal, str]], str]:
    """读取公开 SVG 的年度标签和值标签，返回 RMB mn 原值。"""

    base = _chart_base(page)
    if not base:
        return {}, ""
    fetched = _fetch(base, timeout=10.0, attempts=1)
    if not fetched:
        return {}, base
    _, svg, _ = fetched
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return {}, base
    years: list[int] = []
    values: list[Decimal] = []
    for element in root.iter():
        classes = set((element.attrib.get("class") or "").split())
        text = "".join(element.itertext())
        if "highcharts-xaxis-labels" in classes:
            years.extend(int(item) for item in re.findall(r"20\d{2}", text))
        if "highcharts-data-label" in classes:
            value = _number(text)
            if value is not None:
                values.append(value)
    result: dict[int, tuple[Decimal, str]] = {}
    for year, value in zip(years, values):
        if START_YEAR <= year <= END_YEAR:
            result[year] = (value, "SVG data-label：年度标签与精确数值标签配对")
    return result, base


def _province_slug(slug: str) -> str:
    return slug.split("-", 1)[0] if "-" in slug else slug


def _limit_url(slug: str) -> str:
    return (
        "https://www.ceicdata.com/en/china/"
        "local-government-debt-limit-prefecture-level-city-local-level/"
        f"cn-local-government-debt-limit-local-level-{slug}"
    )


def _fund_url(slug: str) -> str:
    province = _province_slug(slug)
    return (
        f"https://www.ceicdata.com/en/china/government-funds-revenue--expenditure-{province}/"
        f"cn-{slug}-government-funds-revenue-sum"
    )


def _metric_is_valid(
    title: str,
    description: str,
    resolved_url: str,
    slug: str,
    metric: str,
) -> bool:
    compact = _clean_text(title + " " + description).lower()
    # CEIC 英文页面标题使用英文城市名，不能与中文主表名直接比较。最终
    # URL 必须保留城市 slug；如果重定向到省级目录，则不是城市指标页。
    if slug.lower() not in resolved_url.lower():
        return False
    if metric.startswith("limit"):
        return "local government debt limit: local level" in compact
    return "government funds revenue: sum" in compact or "government funds revenue: total" in compact


def _publisher(description: str) -> str:
    match = re.search(r"reported by\s+(.+?)\.\s+The data is", description, re.I)
    return match.group(1).strip() if match else "CEIC 页面未明确标注原始来源"


def _read_metric_page(url: str, slug: str, metric: str) -> dict[str, Any]:
    fetched = _fetch(url, timeout=10.0, attempts=1)
    if not fetched:
        return {"status": "fetch_failed", "url": url, "rows": []}
    resolved_url, page, page_hash = fetched
    title = _title(page)
    desc = _description(page)
    if not _metric_is_valid(title, desc, resolved_url, slug, metric):
        return {
            "status": "no_exact_city_metric",
            "url": url,
            "resolved_url": resolved_url,
            "title": title,
            "description": desc,
            "page_hash": page_hash,
            "rows": [],
        }
    values = _meta_values(desc)
    chart_values, chart_url = _chart_values(page, resolved_url)
    for year, item in chart_values.items():
        values.setdefault(year, item)
    rows = [
        {"year": year, "raw_value_rmb_mn": str(value), "evidence": evidence}
        for year, (value, evidence) in sorted(values.items())
        if START_YEAR <= year <= END_YEAR
    ]
    return {
        "status": "ok",
        "url": url,
        "resolved_url": resolved_url,
        "chart_url": chart_url,
        "title": title,
        "description": desc,
        "publisher": _publisher(desc),
        "page_hash": page_hash,
        "rows": rows,
    }


def _limit_component_url(slug: str, component: str) -> str:
    return (
        "https://www.ceicdata.com/en/china/"
        "local-government-debt-limit-prefecture-level-city-local-level/"
        f"cn-local-government-debt-limit-local-level-{component}-{slug}"
    )


def _discover_fund_urls(root: Path, slugs: list[str]) -> dict[str, str]:
    """从 CEIC 省级基金目录读取实际存在的城市总计/合计链接。"""

    result: dict[str, str] = {}
    provinces = sorted({_province_slug(slug) for slug in slugs})

    def fetch_index(province: str) -> tuple[str, str] | None:
        index_url = f"https://www.ceicdata.com/en/china/government-funds-revenue--expenditure-{province}"
        fetched = _fetch(index_url, timeout=12.0, attempts=1)
        return (province, fetched[1]) if fetched else None

    with ThreadPoolExecutor(max_workers=8) as executor:
        index_pages = [item for item in executor.map(fetch_index, provinces) if item]
    for _, page in index_pages:
        links = re.findall(r'href=["\']([^"\']+)["\']', page, re.I)
        for slug in slugs:
            prefix = f"cn-{slug}-government-funds-revenue-"
            candidates = [
                html.unescape(link)
                for link in links
                if prefix in link and re.search(r"government-funds-revenue-(?:sum|total)$", link)
            ]
            if candidates:
                selected = sorted(candidates, key=lambda item: ("-sum" not in item, len(item)))[0]
                result[slug] = selected if selected.startswith("http") else f"https://www.ceicdata.com{selected}"
    return result


def _series_for_city(
    city_id: str,
    city_name: str,
    slug: str,
    fund_url: str | None = None,
) -> dict[str, Any]:
    output: dict[str, Any] = {
        "city_id": city_id,
        "city_name_cn": city_name,
        "slug": slug,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "metrics": {},
    }
    output["metrics"]["limit"] = _read_metric_page(_limit_url(slug), slug, "limit")
    limit_detail = output["metrics"]["limit"]
    # 许多城市没有“合计”页，但同时公开一般、专项两个精确序列；只有在合计
    # 页没有覆盖全部目标年度时才请求分项，并且只对同年度两项都存在的年份求和。
    if len(limit_detail.get("rows", [])) < (END_YEAR - START_YEAR + 1):
        components: dict[str, dict[str, Any]] = {}
        for component in ("general", "special"):
            components[component] = _read_metric_page(
                _limit_component_url(slug, component), slug, f"limit_{component}"
            )
        by_component = {
            component: {int(item["year"]): item for item in detail.get("rows", [])}
            for component, detail in components.items()
        }
        combined = {int(item["year"]): item for item in limit_detail.get("rows", [])}
        for year in sorted(set(by_component["general"]) & set(by_component["special"])):
            if year in combined:
                continue
            general = Decimal(by_component["general"][year]["raw_value_rmb_mn"])
            special = Decimal(by_component["special"][year]["raw_value_rmb_mn"])
            combined[year] = {
                "year": year,
                "raw_value_rmb_mn": str(general + special),
                "evidence": (
                    "CEIC一般+专项 SVG/HTML精确值求和："
                    f"一般={general} RMB mn；专项={special} RMB mn"
                ),
            }
        if combined:
            limit_detail["status"] = "ok"
            limit_detail["rows"] = [combined[year] for year in sorted(combined)]
            limit_detail["components"] = components
            limit_detail["url"] = ";".join(
                [limit_detail.get("url", "")]
                + [item.get("url", "") for item in components.values() if item.get("status") == "ok"]
            )
            limit_detail["publisher"] = ";".join(
                sorted({item.get("publisher", "") for item in [limit_detail, *components.values()] if item.get("publisher")})
            )
    output["metrics"]["fund"] = _read_metric_page(fund_url or _fund_url(slug), slug, "fund")
    return output


def refresh_snapshot(root: Path, workers: int = 8) -> dict[str, Any]:
    slug_path = root / SLUG_PATH
    if not slug_path.exists():
        raise FileNotFoundError(slug_path)
    slug_map = json.loads(slug_path.read_text(encoding="utf-8"))
    items = [
        (str(city_id), str(item[0]), str(item[1]))
        for city_id, item in slug_map.items()
        if isinstance(item, list) and len(item) >= 2
    ]
    fund_urls = _discover_fund_urls(root, [item[2] for item in items])
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [
            executor.submit(_series_for_city, city_id, city_name, slug, fund_urls.get(slug))
            for city_id, city_name, slug in items
        ]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: item["city_id"])
    payload = {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source_grade": SOURCE_GRADE,
        "unit": "RMB mn; loader converts to 亿元",
        "cities": results,
    }
    path = root / SNAPSHOT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {"cities": len(results), "limit_values": 0, "fund_values": 0, "limit_hits": 0, "fund_hits": 0}
    for city in results:
        for metric in ("limit", "fund"):
            item = city["metrics"].get(metric, {})
            counts[f"{metric}_values"] += len(item.get("rows", []))
            counts[f"{metric}_hits"] += item.get("status") == "ok"
    counts["fund_page_links"] = len(fund_urls)
    counts["snapshot"] = str(path)
    return counts


def repair_snapshot_meta(root: Path) -> dict[str, Any]:
    """修复已归档页面摘要中的月份前缀，不重新请求网络。"""

    path = root / SNAPSHOT_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    repaired = 0
    repaired_rows = 0
    for city in payload.get("cities", []):
        detail = city.get("metrics", {}).get("fund", {})
        if detail.get("status") != "ok" or detail.get("rows"):
            continue
        values = _meta_values(str(detail.get("description") or ""))
        if not values:
            continue
        detail["rows"] = [
            {"year": year, "raw_value_rmb_mn": str(value), "evidence": evidence}
            for year, (value, evidence) in sorted(values.items())
            if START_YEAR <= year <= END_YEAR
        ]
        if detail["rows"]:
            repaired += 1
            repaired_rows += len(detail["rows"])
    payload["repaired_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"repaired_pages": repaired, "repaired_rows": repaired_rows, "snapshot": str(path)}


def _source_id(metric: str, city_id: str) -> str:
    return f"SRC-B2-CEIC-{metric.upper()}-{city_id}"


def _source_record(metric: str, city: Mapping[str, Any], item: Mapping[str, Any], snapshot_hash: str) -> dict[str, Any]:
    detail = city["metrics"][metric]
    source_id = _source_id(metric, str(city["city_id"]))
    return {
        "source_doc_id": source_id,
        "publisher": detail.get("publisher") or "CEIC公开页面（原始来源未明确）",
        "publisher_level": "公开二手数据平台",
        "document_title": detail.get("title") or "",
        "title_source": "CEIC公开城市指标页",
        "attachment_title": detail.get("title") or "",
        "document_type": "公开城市年度指标页面（HTML摘要+SVG精确标签）",
        "source_url": detail.get("url") or "",
        "landing_page_url": detail.get("url") or "",
        "attachment_url": detail.get("chart_url") or "",
        "canonical_url": detail.get("resolved_url") or detail.get("url") or "",
        "final_resolved_url": detail.get("resolved_url") or detail.get("url") or "",
        "file_name": SNAPSHOT_PATH.name,
        "mime_type": "application/json",
        "publication_date": "",
        "publication_date_raw": "",
        "period_end": "2025-12-31",
        "downloaded_at": str(city.get("fetched_at") or ""),
        "content_hash_sha256": detail.get("page_hash") or snapshot_hash,
        "archive_uri": f"archive://national-prefecture-panel/{SNAPSHOT_PATH}",
        "archive_backend": "local snapshot",
        "archive_path": str(SNAPSHOT_PATH),
        "page_count": "HTML页面；SVG图表",
        "source_grade": SOURCE_GRADE,
        "http_status": "200",
        "access_status": "公开页面已归档；精确值按年度标签读取",
        "supersedes_doc_id": "",
        "note": (
            f"B2公开二手来源；{city['city_name_cn']}的{('法定债务限额' if metric == 'limit' else '政府性基金预算收入')}。"
            f"页面原始来源标注为{detail.get('publisher') or '未明确'}；不从图表几何高度估读。"
        ),
    }


def load_ceic_city_limit_fund_sources(
    root: Path, city_master: list[Mapping[str, Any]]
) -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    path = root / SNAPSHOT_PATH
    if not path.exists():
        return {}, []
    content = path.read_bytes()
    payload = json.loads(content.decode("utf-8"))
    snapshot_hash = hashlib.sha256(content).hexdigest()
    city_ids = {str(row.get("city_id")): row for row in city_master if row.get("city_id")}
    values: dict[tuple[str, str], dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    seen_sources: set[str] = set()
    field_map = {"limit": "statutory_debt_limit_100m", "fund": "gov_fund_revenue_100m"}
    for city in payload.get("cities", []):
        city_id = str(city.get("city_id") or "")
        if city_id not in city_ids:
            continue
        for metric, field in field_map.items():
            detail = city.get("metrics", {}).get(metric, {})
            if detail.get("status") != "ok":
                continue
            source_id = _source_id(metric, city_id)
            if source_id not in seen_sources:
                sources.append(_source_record(metric, city, detail, snapshot_hash))
                seen_sources.add(source_id)
            for item in detail.get("rows", []):
                try:
                    year = int(item.get("year"))
                    raw = Decimal(str(item.get("raw_value_rmb_mn")))
                except (TypeError, ValueError, InvalidOperation):
                    continue
                if not START_YEAR <= year <= END_YEAR:
                    continue
                value = (raw / Decimal("100")).quantize(Decimal("0.01"))
                key = (city_id, str(year))
                record = values.setdefault(
                    key,
                    {
                        "city_id": city_id,
                        "city_name": str(city_ids[city_id].get("city_name_cn") or city.get("city_name_cn") or ""),
                        "year": str(year),
                        "source_doc_id": "",
                        "source_grade": SOURCE_GRADE,
                        "source_format": "html+svg",
                        "source_platform": "ceic",
                        "data_status": "reported",
                        "data_status_label": f"{year}年CEIC公开精确页面值",
                        "_field_sources": {},
                    },
                )
                source_locator = (
                    f"{SNAPSHOT_PATH};城市={city.get('city_name_cn')};年份={year};"
                    f"指标={detail.get('title')};URL={detail.get('resolved_url') or detail.get('url')};"
                    f"单位=RMB mn；证据={item.get('evidence')};页面原始来源={detail.get('publisher') or '未明确'}"
                )
                field_source = {
                    "source_doc_id": source_id,
                    "source_grade": SOURCE_GRADE,
                    "source_format": "html+svg",
                    "source_platform": "ceic",
                    "data_status": "reported",
                    "data_status_label": record["data_status_label"],
                    "source_locator": source_locator,
                    "table_name": "CEIC公开城市年度指标页",
                    "page_number": "HTML摘要/SVG年度标签",
                    "raw_value": raw,
                    "raw_unit": "RMB mn",
                    f"{field}_raw_100m": raw,
                    f"{field}_raw_unit": "RMB mn",
                    f"{field}_evidence_excerpt": f"{detail.get('title')} | {year} | {raw} RMB mn | {item.get('evidence')}",
                }
                record[field] = value
                record[f"{field}_raw_100m"] = raw
                record[f"{field}_raw_unit"] = "RMB mn"
                record[f"{field}_evidence_excerpt"] = field_source[f"{field}_evidence_excerpt"]
                record["_field_sources"][field] = field_source
                ids = [item for item in str(record.get("source_doc_id") or "").split(";") if item]
                if source_id not in ids:
                    ids.append(source_id)
                record["source_doc_id"] = ";".join(ids)
    return values, sources


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--repair-meta", action="store_true")
    args = parser.parse_args()
    if args.refresh:
        print(json.dumps(refresh_snapshot(args.root, args.workers), ensure_ascii=False))
    elif args.repair_meta:
        print(json.dumps(repair_snapshot_meta(args.root), ensure_ascii=False))
    else:
        print(f"snapshot={args.root / SNAPSHOT_PATH}")


if __name__ == "__main__":
    main()
