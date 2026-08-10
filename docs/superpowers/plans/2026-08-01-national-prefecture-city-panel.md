# 全国地级市地方财政与城投债数据面板（2018—2026）实施计划

## 目标

按 `prefecture-city-lgfv-data-collection-schema.md` 的字段、粒度、来源、状态和血缘约束，构建可审计的全国地级行政单元年度数据包，覆盖 2018—2026 年，并生成 CSV 明细表与一个可筛选的 XLSX 工作簿。

本次交付采用“可公开来源可证数值 + 明确缺失状态”的策略：2018—2025 的法定债务余额必须逐个目标地级行政单元、逐年取得可留存来源证据的值，作为交付硬门槛；2026 只保留滚动、初步或待采集状态。不得绕过反爬、登录或付费墙，不把第三方商业数据标成官方值，不把缺失值填成 0，不对隐性债务做伪精确估计。

## 范围与口径

1. 以年度行政区划版本生成 `dim_city`，不硬编码固定城市数量。
2. `prefecture_type=地级市` 为主分析样本；自治州、地区、盟进入扩展样本；直辖市单列观察，不与普通地级市直接排名。
3. 主经济财政面板默认 `geo_scope=prefecture_whole`。市本级、辖区、功能区和未知口径不混入主比率。
4. 法定债务、城投债券余额、城投有息债务、隐性债务分开保存，禁止相加。首版优先落地经济财政、法定债务、风险指标和来源血缘；城投主体、逐券债券、信用事件先建立结构与采集状态，只有取得可审计来源才填正式值。
5. 金额统一为亿元（`100m CNY`），正式计算用 Python `Decimal`，导出的数值列保持数值类型；比率以百分比点保存。
6. 2025、2026 不表示“完整年度决算”。2026 年若无正式披露，业务值为空，`data_status` 和 `collection_status` 明确记录为滚动/待采集。

## 工作分解

### 1. 固化计划、配置与测试骨架

- 在 `docs/superpowers/plans/2026-08-01-national-prefecture-city-panel.md` 保存本计划。
- 建立 `config/source_registry.yml`、`config/schema.yml` 和 `tests/`。
- 测试先覆盖：城市年度主键唯一性、城市代码/名称非空、2018—2026 年度范围、缺失不等于 0、债务分项勾稽、限额不低于余额、计算公式依赖无环、每个非空业务字段有 `field_lineage`。

### 2. 取得并归档城市主表来源

- 下载年度行政区划代码原始文件（可取得的 2018—2024 版本），保存到 `raw/administrative_divisions/`，记录 URL、抓取时间、SHA-256 和 `archive_uri`。
- 从年度文件中抽取地级行政单元，赋予稳定 `city_id`，保存年度版本、历史名称、行政层级、样本层级和有效期。
- 2025—2026 使用最近可用行政区划版本仅作前向占位，写明 `roster_version_status=carry_forward`，不声称为官方当年版本。

### 3. 建立来源目录并抓取可公开原始证据

- 先保存国家统计、财政部、省级财政部门、城市统计公报、预算/决算公开和债务公开页面及附件元数据。
- 原始优先级：HTML/XLSX/CSV，其次可搜索 PDF，最后 OCR；所有失败链接、附件缺失、验证码或口径不明情况写入 `collection_status`。
- 非官方公开面板只能作为暂存/交叉线索，来源等级标记为 `C` 或 `D`，不得伪装成官方最终值；不能验证原始口径的值不进入正式主表。

### 4. 抽取并标准化经济财政与法定债务

- 生成 2018—2026 年×年度行政单元的采集矩阵。
- 采集 GDP、常住人口、一般公共预算收入、一般公共预算支出、政府性基金预算收入，以及一般/专项债务限额和余额。
- 保留 `raw_value`、原始单位、报告期、行政范围、原文位置、来源状态和标准化值；不静默覆盖旧版本。
- 直接披露值标记 `disclosed`，分项加总标记 `calculated`，无法可靠取得的值为 `null` 并记录缺失原因。

### 5. 生成派生指标和血缘

- 注册并校验公式 DAG：法定债务余额/限额、一般+专项勾稽、法定债务/GDP、法定债务/一般预算收入、财政自给率、政府性基金收入依赖度、限额利用率等。
- 每个计算值写入 `calculation_lineage`，记录公式版本、输入记录、单位转换、容差和计算时间。
- 不在跨行政范围、跨期、跨状态或未知分母之间计算比率；分母为零或缺失时结果为 `null`。

### 6. 输出设计文档要求的表格

在 `outputs/national_prefecture_panel_2018_2026/` 生成：

- `dim_city.csv`
- `city_macro_fiscal.csv`
- `city_gov_debt.csv`
- `lgfv_company.csv`
- `lgfv_financial.csv`
- `bond_detail.csv`
- `bond_special_term.csv`
- `bond_proceeds_allocation.csv`
- `credit_event.csv`
- `source_document.csv`
- `field_lineage.csv`
- `manual_review_decision.csv`
- `calculation_lineage.csv`
- `formula_registry.csv`
- `formula_dependency.csv`
- `risk_metric.csv`
- `collection_status.csv`
- `README_数据说明.md`
- `quality_report.json`

LGFV、债券和信用事件没有可靠值时保留设计文档定义的字段表和采集状态，不创建虚构记录；正式字段与阶段状态必须能区分。

### 7. 用 artifact-tool 生成 XLSX

- 使用 `@oai/artifact-tool`，通过工作区依赖加载器运行 `scripts/build_workbook.mjs`，不使用替代的 XLSX 库。
- 工作簿包含：`说明`、`城市主表`、`经济财政`、`法定债务`、`风险指标`、`来源目录`、`字段血缘`、`采集状态`、`质量检查`，以及结构化的 LGFV/债券/事件工作表。
- 说明页写清年度范围、样本边界、数据状态、来源等级、缺失规则和四类债务不可相加规则；表头冻结、金额和百分比格式统一、长文本可读、超宽字段不挤压主表。
- 对每个面向用户的工作表至少渲染一次，检查关键区域、公式错误和导出文件可读取性。

### 8. 质量检查与验收

- 检查城市年度主键、行数、重复值、字段类型、单位、缺失率、来源完整性、行政范围一致性、债务勾稽和公式重算。
- 对主城市主表、GDP/一般预算收入、债务分项分别报告覆盖率；不能达到设计文档阈值时明确列出缺失原因，不隐瞒。
- 交付硬门槛：`2018—2025 × 全部目标地级行政单元` 的 `statutory_debt_balance_100m` 均非空，且每个非空值均有 `field_lineage` 和可回溯来源证据；硬门槛未满足时不得宣称完成或交付全国面板。
- 用独立校验脚本重读所有 CSV 和 XLSX 关键范围，扫描公式错误；保存 `quality_report.json` 和质量结论。
- 最终交付前再次核对：正式值均有来源/字段血缘，计算值均有计算血缘，2026 不被写成完成年度，所有文档和用户可读说明均为中文。

## 实际执行命令

```bash
python3 -m pytest -q
python3 scripts/collect_national_panel.py --start-year 2018 --end-year 2026
python3 scripts/validate_national_panel.py --input-dir outputs/national_prefecture_panel_2018_2026
node scripts/build_workbook.mjs
python3 scripts/validate_national_panel.py --input-dir outputs/national_prefecture_panel_2018_2026 --check-xlsx
```

若工作区当前无法加载官方表格运行时，保留 CSV、质量报告和阻塞说明，不改用未批准的替代库。
