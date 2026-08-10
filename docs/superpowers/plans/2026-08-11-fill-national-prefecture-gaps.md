# 全国地级行政单元数据缺口回填实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 在不牺牲来源可审计性和行政范围口径的前提下，尽可能补齐 2018—2025 年全国地级行政单元的法定债务余额及核心经济财政字段，并重新生成缺口清单。

**架构：** 先以现有输出建立缺口基线，再扫描 `raw/province_debt/` 中已归档但未接入的官方或半官方来源；高优先级来源通过 `province_debt_sources.py` 的配置进入现有解析链，保留原始文本、来源元数据、字段血缘和状态。无法取得可审计数值的键继续保留为空，不用估算值或零值填充。

**技术栈：** Python 3、标准库 CSV/Decimal、现有债务解析器、pytest、独立校验器。

## 全局约束

- 2018—2025 法定债务余额必须逐城市、逐年度保存可回溯来源；硬门槛未达成时不得宣称完成。
- 官方财政厅/财政局/预算决算附件优先；CELMA 等公开聚合页面只作为可审计的次级来源，并明确来源等级。
- 法定债务余额优先使用直接披露值；只有一般债务余额和专项债务余额均明确时才计算合计。
- 不把隐性债务、城投有息债务和法定政府债务混加，不把缺失值写成 0。
- 2026 年保留为未完结年度占位，不把尚未发生的全年数据当作采集失败。
- 生成的用户可读说明和报告字段使用中文；所有新增数值必须附带来源和字段血缘。

---

### 任务 1：建立缺口回填基线

**文件：**
- 读取：`outputs/national_prefecture_panel_2018_2026/city_macro_fiscal.csv`
- 读取：`outputs/national_prefecture_panel_2018_2026/city_gov_debt.csv`
- 使用：`scripts/report_missing_data.py`

- [ ] **步骤 1：** 运行缺口报告脚本，记录 2018—2025 各年度、各省份和各字段的缺失键数量。
- [ ] **步骤 2：** 导出当前缺口键与 `raw/province_debt/` 下文件名进行标准化城市名匹配，形成可复用的候选来源列表；候选来源必须能定位到具体年度和城市。
- [ ] **步骤 3：** 将候选来源按“官方分地区表 > 官方预算/决算附件 > 官方城市财政公开 > 可留存的公开聚合页面”排序，只对已有原始文件或可稳定下载的页面进入下一任务。

### 任务 2：接入已归档且尚未注册的来源

**文件：**
- 修改：`scripts/province_debt_sources.py`
- 可能新增：`raw/province_debt/multi_year_official/*.txt`
- 测试：`tests/test_province_debt_parser.py`

- [ ] **步骤 1：** 用配置路径与实际原始文件清单做双向核对，列出“文件存在但没有来源配置”和“来源配置缺少原始文件”的差异。
- [ ] **步骤 2：** 对每个可解析的候选文件补充最小来源配置：`source_doc_id`、省份、年度、原始路径、来源 URL、来源等级、单位、表名、文本边界和口径说明。
- [ ] **步骤 3：** 为至少一个新增来源增加解析测试，断言城市代码、年度、一般/专项余额或直接法定余额、单位换算和来源等级均正确。
- [ ] **步骤 4：** 运行债务解析器测试；解析失败的文件移出正式来源配置，并在缺口报告中保留 `needs_review` 或 `needs_collection` 状态。

### 任务 3：优先回填法定债务余额硬门槛

**文件：**
- 使用：`scripts/collect_national_panel.py`
- 使用：`scripts/validate_national_panel.py`
- 使用：`scripts/report_missing_data.py`
- 输出：`outputs/national_prefecture_panel_2018_2026/`

- [ ] **步骤 1：** 运行完整采集器，确认新增来源进入 `source_document.csv`、`field_lineage.csv` 和 `collection_status.csv`。
- [ ] **步骤 2：** 运行独立校验器，确认没有重复年度主键、断裂血缘、非法数值或新的限额—余额矛盾。
- [ ] **步骤 3：** 重新生成逐字段缺口清单，并比较硬门槛覆盖率、按年度缺口和按省份缺口的变化。
- [ ] **步骤 4：** 对余额已填但 `statutory_debt_balance_100m > statutory_debt_limit_100m` 的记录建立复核清单；不因追求覆盖率自动覆盖冲突值。

### 任务 4：在不改变口径的前提下补充宏观财政字段

**文件：**
- 可能修改：`scripts/collect_national_panel.py`
- 新增或读取：`raw/city_panel/`、`raw/province_debt/` 下的可审计宏观资料
- 输出：`missing_data_summary.csv`、`missing_data_detail_2018_2026.csv`

- [ ] **步骤 1：** 仅使用能确认城市范围、报告期和单位的来源补充 GDP、一般公共预算收入、一般公共预算支出和常住人口。
- [ ] **步骤 2：** 对政府性基金预算收入、债务限额等稀疏字段先保留缺失状态，除非找到逐城市官方分地区表；不得由省级总额按比例拆分。
- [ ] **步骤 3：** 重新计算派生比率，并确认分母缺失时比率仍为空、计算血缘完整。

### 任务 5：验证并给出后续建议

**文件：**
- 生成：`outputs/national_prefecture_panel_2018_2026/README_数据说明.md`
- 生成：`outputs/national_prefecture_panel_2018_2026/quality_report.json`

- [ ] **步骤 1：** 运行全部单元测试、采集器、独立校验器和缺口报告。
- [ ] **步骤 2：** 汇总新增覆盖键、剩余缺口、来源等级和质量异常，区分“已填官方值”“已填次级值”“待复核”“仍未采集”。
- [ ] **步骤 3：** 输出下一轮建议：优先省份、优先年份、来源获取方式、口径核对规则和可自动化的质量测试。

