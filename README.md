# 中国地方债 Atlas 数据采集项目

本仓库保存中国地级行政单元 2018—2026 年地方财政、法定政府债务及相关数据的采集脚本、原始证据、结构化输出和质量校验结果。

## 目录

- `docs/`：数据采集设计文档和执行计划
- `scripts/`：采集、解析、缺口报告和质量校验脚本
- `raw/`：按年份和来源等级归档的原始资料
- `outputs/`：全国城市年度面板、来源血缘和缺口报告
- `tests/`：解析器与面板构建回归测试

## 常用命令

```bash
python3 -m unittest discover -s tests -v
python3 scripts/collect_national_panel.py --start-year 2018 --end-year 2026
python3 scripts/report_missing_data.py
python3 scripts/validate_national_panel.py \
  --input-dir outputs/national_prefecture_panel_2018_2026 \
  --require-statutory-debt-2018-2025
```

## 数据质量说明

来源等级 A1/A2 表示官方财政、预算或决算资料；B1/B2 表示公开评级或二手研究资料；C/D 表示更低等级的公开或研究型来源。不同等级不得在分析中混为同一可信度，具体口径以 `docs/prefecture-city-lgfv-data-collection-schema.md` 为准。

当前输出保留缺失值为 null，不用零值填充；未明确披露一般债务和专项债务分项时，不根据总额进行反推。
