"""生成全国地级行政单元面板的缺口清单和字段完整度汇总。"""

from __future__ import annotations

import csv
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs" / "national_prefecture_panel_2018_2026"
INPUT_PATH = OUTPUT_DIR / "city_macro_fiscal.csv"

TARGET_START = 2018
TARGET_END = 2025
PROJECT_END = 2026

FIELD_LABELS = {
    "gdp_current_100m": "地区生产总值（现价，亿元）",
    "gdp_real_growth_pct": "地区生产总值实际增速（%）",
    "resident_population_10k": "年末常住人口（万人）",
    "general_public_revenue_100m": "一般公共预算收入（亿元）",
    "general_public_expenditure_100m": "一般公共预算支出（亿元）",
    "gov_fund_revenue_100m": "政府性基金预算收入（亿元）",
    "general_debt_limit_100m": "一般债务限额（亿元）",
    "general_debt_balance_100m": "一般债务余额（亿元）",
    "special_debt_limit_100m": "专项债务限额（亿元）",
    "special_debt_balance_100m": "专项债务余额（亿元）",
    "statutory_debt_limit_100m": "法定债务限额（亿元）",
    "statutory_debt_balance_100m": "法定债务余额（亿元）",
    "debt_limit_utilization_pct": "债务限额使用率（%）",
    "statutory_debt_to_gdp_pct": "法定债务/GDP（%）",
    "statutory_debt_to_revenue_pct": "法定债务/一般预算收入（%）",
    "fiscal_self_sufficiency_pct": "财政自给率（%）",
    "fund_revenue_dependence_pct": "政府性基金收入依赖度（%）",
}


def is_missing(value: str | None) -> bool:
    return value is None or not str(value).strip() or str(value).strip().lower() in {"null", "none", "nan"}


def pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "0.00"
    return str((Decimal(numerator) * Decimal("100") / Decimal(denominator)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    with INPUT_PATH.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    gate_rows = [
        row
        for row in rows
        if TARGET_START <= int(row["metric_year"]) <= TARGET_END
        and is_missing(row.get("statutory_debt_balance_100m"))
    ]
    write_csv(
        OUTPUT_DIR / "missing_statutory_debt_2018_2025.csv",
        ["city_id", "city_name_cn", "province_name", "metric_year", "sample_tier", "data_status", "source_doc_id", "source_grade", "collection_status", "note"],
        [
            {
                key: row.get(key, "")
                for key in ["city_id", "city_name_cn", "province_name", "metric_year", "sample_tier", "data_status", "source_doc_id", "source_grade", "collection_status", "note"]
            }
            for row in sorted(gate_rows, key=lambda item: (int(item["metric_year"]), item["province_name"], item["city_id"]))
        ],
    )

    field_detail_rows: list[dict[str, object]] = []
    for row in rows:
        year = int(row["metric_year"])
        for field, label in FIELD_LABELS.items():
            if is_missing(row.get(field)):
                field_detail_rows.append(
                    {
                        "city_id": row["city_id"],
                        "city_name_cn": row["city_name_cn"],
                        "province_name": row["province_name"],
                        "metric_year": year,
                        "field_name": field,
                        "field_label_cn": label,
                        "sample_tier": row["sample_tier"],
                        "data_status": row["data_status"],
                        "source_doc_id": row.get("source_doc_id", ""),
                        "source_grade": row.get("source_grade", ""),
                        "collection_status": row.get("collection_status", ""),
                        "note": row.get("note", ""),
                    }
                )
    write_csv(
        OUTPUT_DIR / "missing_data_detail_2018_2026.csv",
        ["city_id", "city_name_cn", "province_name", "metric_year", "field_name", "field_label_cn", "sample_tier", "data_status", "source_doc_id", "source_grade", "collection_status", "note"],
        sorted(field_detail_rows, key=lambda item: (item["metric_year"], item["province_name"], item["city_id"], item["field_name"])),
    )

    summary_rows: list[dict[str, object]] = []
    for year_start, year_end, period_label in [(TARGET_START, TARGET_END, "2018—2025"), (PROJECT_END, PROJECT_END, "2026")]:
        period_rows = [row for row in rows if year_start <= int(row["metric_year"]) <= year_end]
        for field, label in FIELD_LABELS.items():
            missing_count = sum(is_missing(row.get(field)) for row in period_rows)
            total_count = len(period_rows)
            summary_rows.append(
                {
                    "period": period_label,
                    "field_name": field,
                    "field_label_cn": label,
                    "total_city_year_rows": total_count,
                    "missing_rows": missing_count,
                    "covered_rows": total_count - missing_count,
                    "coverage_pct": pct(total_count - missing_count, total_count),
                }
            )
    write_csv(
        OUTPUT_DIR / "missing_data_summary.csv",
        ["period", "field_name", "field_label_cn", "total_city_year_rows", "missing_rows", "covered_rows", "coverage_pct"],
        summary_rows,
    )

    province_year_counter = Counter((row["province_name"], int(row["metric_year"])) for row in gate_rows)
    write_csv(
        OUTPUT_DIR / "missing_statutory_debt_by_province_year.csv",
        ["province_name", "metric_year", "missing_city_year_rows"],
        [
            {"province_name": province, "metric_year": year, "missing_city_year_rows": count}
            for (province, year), count in sorted(province_year_counter.items(), key=lambda item: (item[0][0], item[0][1]))
        ],
    )

    print({
        "all_city_year_rows": len(rows),
        "gate_target_rows": sum(TARGET_START <= int(row["metric_year"]) <= TARGET_END for row in rows),
        "missing_statutory_debt_2018_2025": len(gate_rows),
        "missing_field_cells_2018_2026": len(field_detail_rows),
    })


if __name__ == "__main__":
    main()
