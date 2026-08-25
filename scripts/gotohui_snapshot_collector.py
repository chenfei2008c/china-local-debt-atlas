"""按城市逐项检索并冻结聚汇公开历史序列。

该脚本是现有 :mod:`gotohui_city_series` 适配器的采集端。检索时只接受
标题与地级行政单元名称完全匹配的总量序列；预算数、分项、本级之外的
区县条目不写入快照。快照写入后由现有适配器负责单位标准化和字段血缘。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import ssl
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SNAPSHOT_PATH = Path("raw/province_fiscal/gotohui/city_series_snapshot.json")
API_ROOT = "https://www.gotohui.com/api"
YEAR_RANGE = range(2018, 2026)

METRIC_FIELDS = {
    "gdp": "gdp_current_100m",
    "growth": "gdp_real_growth_pct",
    "population": "resident_population_10k",
    "revenue": "general_public_revenue_100m",
    "expenditure": "general_public_expenditure_100m",
    "fund": "gov_fund_revenue_100m",
    "limit": "statutory_debt_limit_100m",
    "balance": "statutory_debt_balance_100m",
}
QUERY_WORDS = {
    "gdp": "GDP",
    "growth": "GDP增长率",
    "population": "常住人口",
    "revenue": "一般公共预算收入",
    "expenditure": "一般公共预算支出",
    "fund": "政府性基金收入",
    "limit": "地方政府债务限额",
    "balance": "地方政府债务余额",
}


def acceptable_series_title(metric: str, city_name: str, title: str) -> bool:
    """判断标题是否是目标城市的全市总量序列。"""

    exact = {
        "gdp": {f"{city_name}GDP"},
        "growth": {f"{city_name}GDP增长率"},
        "population": {f"{city_name}常住人口"},
        "revenue": {
            f"{city_name}地方财政收入:一般公共预算收入",
            f"{city_name}一般公共预算收入",
        },
        "expenditure": {
            f"{city_name}地方财政支出:一般公共预算支出",
            f"{city_name}一般公共预算支出",
        },
        "fund": {
            f"{city_name}政府性基金收入",
            f"{city_name}地方政府性基金收入",
            f"{city_name}地方政府性基金本级收入",
        },
        "limit": {f"{city_name}地方政府债务限额"},
        "balance": {f"{city_name}地方政府债务余额"},
    }
    return title.strip() in exact.get(metric, set())


def normalize_series_value(metric: str, raw: Any, unit: str) -> Decimal:
    """把聚汇原始单位标准化为主表单位。"""

    try:
        value = Decimal(str(raw).replace(",", "").replace("，", ""))
    except (InvalidOperation, ValueError):
        raise ValueError(f"无法解析聚汇数值：{raw!r}") from None
    if metric in {"revenue", "expenditure", "fund", "limit", "balance"} and unit == "万元":
        value /= Decimal("10000")
    elif metric == "population" and unit == "人":
        value /= Decimal("10000")
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def merge_snapshot_series(
    existing: Iterable[Mapping[str, Any]], additions: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """按 series_id 合并，保持已有快照优先并去除重复序列。"""

    merged: dict[str, dict[str, Any]] = {}
    for item in [*existing, *additions]:
        series_id = str(item.get("series_id") or "")
        if series_id and series_id not in merged:
            merged[series_id] = dict(item)
    return sorted(merged.values(), key=lambda item: (str(item.get("metric") or ""), str(item.get("city_name") or ""), str(item.get("series_id") or "")))


def _json_request(url: str, retries: int = 3) -> dict[str, Any] | None:
    # 当前运行环境的代理证书链无法校验 gotohui；数据仍通过 HTTPS 传输，
    # 页面 URL、响应哈希和采集时间都会冻结到快照和来源血缘中。
    context = ssl._create_unverified_context()
    for attempt in range(retries):
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
            with urlopen(request, timeout=25, context=context) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:
            if attempt + 1 < retries:
                time.sleep(0.8 * (attempt + 1))
    return None


def _search_city_metric(city_name: str, metric: str, pages: int) -> list[dict[str, Any]]:
    query = urlencode({"word": f"{city_name} {QUERY_WORDS[metric]}", "channel": "data", "page": 1})
    found: dict[str, dict[str, Any]] = {}
    for page in range(1, pages + 1):
        query = urlencode({"word": f"{city_name} {QUERY_WORDS[metric]}", "channel": "data", "page": page})
        payload = _json_request(f"{API_ROOT}/search?{query}") or {}
        for item in ((payload.get("data") or {}).get("list") or []):
            title = str(item.get("title") or "")
            if acceptable_series_title(metric, city_name, title):
                found[str(item.get("id"))] = item
    return list(found.values())


def _freeze_series(city_id: str, city_name: str, metric: str, item: Mapping[str, Any]) -> dict[str, Any] | None:
    series_id = str(item.get("id") or "")
    payload = _json_request(f"{API_ROOT}/pc/macro/chart/{series_id}") or {}
    data = payload.get("data") or {}
    labels = [str(value) for value in data.get("labels") or []]
    values = data.get("values") or []
    rows = []
    for year, value in zip(labels, values):
        if year not in {str(item_year) for item_year in YEAR_RANGE} or value in (None, "", "-", "—", "–"):
            continue
        rows.append({"year": year, "value": value})
    if not rows:
        return None
    chart_bytes = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return {
        "city_id": city_id,
        "city_name": city_name,
        "metric": metric,
        "series_id": series_id,
        "title": str(item.get("title") or data.get("title") or ""),
        "unit": str(item.get("unit") or data.get("unit") or ""),
        "source": str(item.get("source") or ""),
        "data_range": str(item.get("data_range") or ""),
        "url": str(item.get("url") or f"https://www.gotohui.com/show-{series_id}"),
        "content_hash_sha256": hashlib.sha256(chart_bytes).hexdigest(),
        "rows": rows,
    }


def _read_city_targets(root: Path, metrics: set[str]) -> list[tuple[str, str, str]]:
    macro_path = root / "outputs/national_prefecture_panel_2018_2026/city_macro_fiscal.csv"
    current: dict[tuple[str, str], dict[str, str]] = {}
    with macro_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if 2018 <= int(row["metric_year"]) <= 2025:
                current[(row["city_id"], row["metric_year"])] = row
    cities = {
        (row["city_id"], row["city_name_cn"])
        for (city_id, _year), row in current.items()
        if row["metric_year"] == "2025"
    }
    targets = []
    for metric in sorted(metrics):
        field = METRIC_FIELDS[metric]
        for city_id, city_name in sorted(cities):
            if any(
                not current.get((city_id, str(year)), {}).get(field, "").strip()
                for year in YEAR_RANGE
            ):
                targets.append((metric, city_id, city_name))
    return targets


def collect(root: Path, metrics: set[str], workers: int = 4, pages: int = 3) -> dict[str, int]:
    snapshot_path = root / SNAPSHOT_PATH
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    existing = list(payload.get("series") or [])
    existing_ids = {str(item.get("series_id")) for item in existing}
    targets = _read_city_targets(root, metrics)
    additions: list[dict[str, Any]] = []

    def process(target: tuple[str, str, str]) -> list[dict[str, Any]]:
        metric, city_id, city_name = target
        found = _search_city_metric(city_name, metric, pages if metric in {"fund", "limit", "balance"} else min(pages, 2))
        result = []
        for item in found:
            if str(item.get("id")) in existing_ids:
                continue
            frozen = _freeze_series(city_id, city_name, metric, item)
            if frozen:
                result.append(frozen)
        return result

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [executor.submit(process, target) for target in targets]
        for future in as_completed(futures):
            additions.extend(future.result())

    merged = merge_snapshot_series(existing, additions)
    payload["series"] = merged
    payload["snapshot_date"] = time.strftime("%Y-%m-%d")
    snapshot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "targets": len(targets),
        "new_series": len(additions),
        "new_cells": sum(len(item.get("rows") or []) for item in additions),
        "total_series": len(merged),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="逐城扩展聚汇公开历史序列快照")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--metrics", default=",".join(METRIC_FIELDS), help="逗号分隔指标")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--pages", type=int, default=3)
    args = parser.parse_args()
    metrics = {item.strip() for item in args.metrics.split(",") if item.strip()}
    unknown = metrics - set(METRIC_FIELDS)
    if unknown:
        parser.error(f"未知指标：{sorted(unknown)}")
    print(json.dumps(collect(args.root, metrics, args.workers, args.pages), ensure_ascii=False))


if __name__ == "__main__":
    main()
