"""已穷尽公开渠道但仍无可验收数值的字段证据登记。"""

from __future__ import annotations


EVIDENCE_CHECKED_AT = "2026-09-02"

CORE_GAP_FIELDS = (
    "gdp_current_100m",
    "gdp_real_growth_pct",
    "general_public_revenue_100m",
    "general_public_expenditure_100m",
)


def _sansha_rows() -> tuple[dict[str, str], ...]:
    rows = []
    for year in range(2018, 2026):
        rows.append(
            {
                "city_id": "CN-460300",
                "city_name_cn": "三沙市",
                "province_name": "海南省",
                "metric_year": str(year),
                "field_name": "statutory_debt_balance_100m",
                "collection_status": "evidence_based_missing",
                "evidence_source_doc_ids": (
                    f"SRC-OFFICIAL-DEBT-HAINAN-DIRECT-COUNTY-{year};"
                    "SRC-EVIDENCE-MISSING-SANSHA-PUBLICATION-STATUS"
                ),
                "searched_channels": "海南省财政厅预决算公开；海南省财政厅债务公开附件；中国地方政府债务管理协会归档页面",
                "result": "官方债务表逐行公开海口、三亚、儋州及省直辖县级行政单位，但未列示三沙市；海南省财政厅公开年报明确三沙市整体涉密、不予公开。未找到可审计的三沙市年末法定债务余额。",
                "next_action": "若取得依法可公开的三沙市专项财政或债务披露，再补录并复核；在此之前保持 null。",
            }
        )
    return tuple(rows)


def _core_row(
    *,
    city_id: str,
    city_name_cn: str,
    province_name: str,
    metric_year: int,
    field_name: str,
    evidence_source_doc_ids: str,
    searched_channels: str,
    result: str,
    next_action: str,
) -> dict[str, str]:
    return {
        "city_id": city_id,
        "city_name_cn": city_name_cn,
        "province_name": province_name,
        "metric_year": str(metric_year),
        "field_name": field_name,
        "collection_status": "evidence_based_missing",
        "evidence_source_doc_ids": evidence_source_doc_ids,
        "searched_channels": searched_channels,
        "result": result,
        "next_action": next_action,
    }


def _core_rows() -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []

    sansha_sources = (
        "SRC-EVIDENCE-MISSING-SANSHA-SEARCH-2026;"
        "SRC-EVIDENCE-MISSING-SANSHA-PUBLICATION-STATUS;"
        "SRC-EVIDENCE-MISSING-SANSHA-RATING-2024"
    )
    sansha_channels = "三沙市政府门户网站站内检索；海南省财政厅政府信息公开和财政公开页面；评级报告及债务公开附件"
    sansha_result = (
        "三沙市官网按年度公报、地区生产总值、一般公共预算、财政决算和政府性基金预算等关键词检索，"
        "结果主要为预算会议、审计动员和阶段性执行信息，未取得可直接入表的年度全市数值；海南省财政厅公开年报"
        "明确三沙市整体涉密不予公开；评级资料亦说明近年缺少三沙市经济财政数据。不能用海南省合计、其他市县"
        "合计、预算数或上半年数反推。"
    )
    sansha_next = "若未来公开可依法使用的三沙市年度统计公报或全市财政决算表，按同口径补录并复核；当前保持 null。"
    for year in range(2018, 2026):
        fields = ["gdp_real_growth_pct", "general_public_revenue_100m", "general_public_expenditure_100m"]
        if year in (2022, 2025):
            fields.insert(0, "gdp_current_100m")
        for field in fields:
            rows.append(_core_row(
                city_id="CN-460300", city_name_cn="三沙市", province_name="海南省",
                metric_year=year, field_name=field,
                evidence_source_doc_ids=sansha_sources,
                searched_channels=sansha_channels, result=sansha_result, next_action=sansha_next,
            ))

    for year, field, result, next_action, source_ids in (
        (
            2020,
            "gdp_real_growth_pct",
            "官方阿里地区2020年信息公开页面只披露2020年GDP总量70.7亿元，没有按不变价格计算的实际增速；"
            "阿里地区官方统计数据目录当前可见的年度经济条目仅到2017年，后续主要是2023年前三季度等阶段信息；"
            "未找到同年度官方公报或年鉴的实际增速。",
            "若取得阿里地区2020年官方统计公报/年鉴实际增速，再按全地区口径补录；不得由相邻年度总量计算。",
            "SRC-EVIDENCE-MISSING-ALI-GROWTH-2020;SRC-EVIDENCE-MISSING-ALI-STATISTICS-INDEX-2026",
        ),
        (
            2022,
            "gdp_real_growth_pct",
            "B2评级报告表格列出阿里地区2022年GDP及0.50%的增速，但脚注明确该增速由GDP绝对值计算，"
            "不是公开披露的实际增速；阿里地区官方统计数据目录也未提供2022年按不变价格计算的实际增速，"
            "按本项目口径不作为定稿值。",
            "若取得阿里地区2022年官方按不变价格计算的实际增速，替换当前空值；不得采用评级报告推算值。",
            "SRC-EVIDENCE-MISSING-ALI-GROWTH-2022;SRC-EVIDENCE-MISSING-ALI-STATISTICS-INDEX-2026",
        ),
    ):
        rows.append(_core_row(
            city_id="CN-542500", city_name_cn="阿里地区", province_name="西藏自治区",
            metric_year=year, field_name=field, evidence_source_doc_ids=source_ids,
            searched_channels="阿里地区行政公署官方经济信息；西藏自治区统计/财政公开渠道；B2地方政府风险评级报告",
            result=result, next_action=next_action,
        ))

    for year, fields in (
        (2021, ("general_public_expenditure_100m",)),
        (2022, ("general_public_revenue_100m", "general_public_expenditure_100m")),
        (2023, ("general_public_revenue_100m", "general_public_expenditure_100m")),
        (2024, CORE_GAP_FIELDS),
        (2025, CORE_GAP_FIELDS),
    ):
        for field in fields:
            is_gdp = field in {"gdp_current_100m", "gdp_real_growth_pct"}
            rows.append(_core_row(
                city_id="CN-659000", city_name_cn="自治区直辖县级行政区划", province_name="新疆生产建设兵团",
                metric_year=year, field_name=field,
                evidence_source_doc_ids=(
                    "SRC-EVIDENCE-MISSING-XPCC-GDP-2024-2025;SRC-EVIDENCE-MISSING-XPCC-GDP-REPORT-2025;"
                    "SRC-EVIDENCE-MISSING-XPCC-GDP-INDEX-2026;SRC-EVIDENCE-MISSING-XPCC-FISCAL-POST-2021"
                    if is_gdp else
                    "SRC-EVIDENCE-MISSING-XPCC-FINANCE-INDEX;SRC-EVIDENCE-MISSING-XPCC-FISCAL-POST-2021"
                ),
                searched_channels=(
                    "兵团统计局统计公报和统计资料库；兵团官方新闻门户；交易所公开评级报告"
                    if is_gdp else
                    "兵团财政局预决算公开和信息公开目录；兵团统计局/财政局官方页面；交易所公开评级报告"
                ),
                result=(
                    "兵团统计局公报目录及交易所公开评级材料仅取得2024年前三季度、2025年上半年/前三季度等阶段性GDP"
                    "数据；评级材料明确未披露2024全年度经济数据，亦未取得2025全年GDP总量/实际增速。阶段性数据不能代替年度值。"
                    if is_gdp else
                    "兵团财政局公开目录和官方评级资料显示，2021年后未继续公开可定位的全兵团年度财政信息；"
                    "2022年上半年收入、预算数或自治区代编的兵团债务收支不能代替全年度全兵团一般预算收支。"
                ),
                next_action=(
                    "若取得兵团统计局正式年度公报或年鉴，再补录全年值；当前保持 null。"
                    if is_gdp else
                    "若取得兵团财政局正式年度决算或预算执行表，再补录全兵团值；当前保持 null。"
                ),
            ))

    for year, fields in ((2024, ("gdp_current_100m", "gdp_real_growth_pct")), (2025, ("gdp_current_100m", "gdp_real_growth_pct"))):
        for field in fields:
            rows.append(_core_row(
                city_id="CN-133100", city_name_cn="雄安新区", province_name="河北省",
                metric_year=year, field_name=field,
                evidence_source_doc_ids=(
                    "SRC-EVIDENCE-MISSING-XIONGAN-GDP-STATUS;SRC-EVIDENCE-MISSING-XIONGAN-STATISTICS-INDEX-2026;"
                    "SRC-EVIDENCE-MISSING-XIONGAN-DECISION"
                ),
                searched_channels="中国雄安官网统计信息和站内检索；雄安新区财政预决算公开专栏；河北省及新区公开报告",
                result=(
                    "中国雄安官网统计信息目录及公开材料可核验到‘十四五’期间GDP年均增长17.1%、固定资产投资和外贸等"
                    "指标，但未找到该年度新区全域GDP总量或按不变价格计算的实际增速；财政决算公开专栏不产生GDP数值。"
                    "网络文章按河北省市级合计差额推算的数值不具备全域官方表格血缘，不能入表。"
                ),
                next_action="若公开新区年度统计公报或全域GDP正式表格，再补录并复核；当前保持 null。",
            ))

    rows.append(_core_row(
        city_id="CN-371200", city_name_cn="莱芜市", province_name="山东省", metric_year=2019,
        field_name="gdp_real_growth_pct",
        evidence_source_doc_ids="SRC-EVIDENCE-MISSING-LAIWU-YEARBOOK;SRC-EVIDENCE-MISSING-LAIWU-2018-REPORT;SRC-EVIDENCE-MISSING-LAIWU-YEARBOOK-2019-EDITION",
        searched_channels="济南市统计局官方年鉴页面及2020年年鉴附件；济南市政府官方2019年工作/计划报告；中国城市统计年鉴2019版公开表格",
        result=(
            "济南市2020年官方年鉴附件确认2019年莱芜全域GDP为871.60亿元，但该分地区表未列全域实际增速；"
            "中国城市统计年鉴2019版公开表格中的7.20%与1005.65亿元对应2018年，官方报告可定位到的7.2%也是原莱芜市2018年增速，"
            "不是2019年。合并后的莱芜区/钢城区增速不能直接代表"
            "原地级莱芜市全域，故不作口径推算。"
        ),
        next_action="若取得2019年原莱芜全域按不变价格计算的官方实际增速，再补录；当前保持 null。",
    ))
    return tuple(rows)


EVIDENCE_BASED_MISSING: tuple[dict[str, str], ...] = _sansha_rows() + _core_rows() + (
    {
        "city_id": "CN-540600",
        "city_name_cn": "那曲市",
        "province_name": "西藏自治区",
        "metric_year": "2019",
        "field_name": "statutory_debt_balance_100m",
        "collection_status": "evidence_based_missing",
        "evidence_source_doc_ids": "SRC-EVIDENCE-MISSING-NAQU-2019-AUDIT;SRC-EVIDENCE-MISSING-NAQU-2019-BUDGET;SRC-EVIDENCE-MISSING-NAQU-2019-RATING",
        "searched_channels": "西藏自治区财政预算执行报告；那曲市2019年度财政决算审计公告；西藏自治区政府债务公开表；B2评级报告精确表格/注释",
        "result": "自治区报告只披露全区2019年债务限额和余额；那曲市审计公告披露财政收支及基金收支但未披露债务余额；公开评级报告明确注明未取得2019年那曲市政府债务余额。未找到全市年末可审计数值。",
        "next_action": "继续等待或申请那曲市/西藏自治区财政部门公开2019年地市债务决算表；不得用2018、2020或图表估读值推算。",
    },
    {
        "city_id": "CN-620900",
        "city_name_cn": "酒泉市",
        "province_name": "甘肃省",
        "metric_year": "2025",
        "field_name": "statutory_debt_balance_100m",
        "collection_status": "evidence_based_missing",
        "evidence_source_doc_ids": "SRC-EVIDENCE-MISSING-JIUQUAN-2025-BUDGET;SRC-EVIDENCE-MISSING-JIUQUAN-2025-EXECUTION;SRC-EVIDENCE-MISSING-JIUQUAN-2025-DEBT-BRIEF",
        "searched_channels": "酒泉市财政局2025年市级预算公开；酒泉市财政局2025年度财政预算执行情况；酒泉市财政局2025年债务简报；甘肃省财政厅2025年债务汇总表",
        "result": "酒泉市官方年度预算和执行页面公开一般预算、政府性基金及市级债务预算资料，但未公开2025年末全市（含县市区）法定债务余额；2025年债务简报截至10月，亦非年末决算口径；甘肃省级汇总表只到全省及市县合计。",
        "next_action": "等待酒泉市2025年度决算及全市债务限额余额表公开；不得以市本级预算或2024年末余额代填全市2025年末值。",
    },
)


EVIDENCE_SOURCE_DOCUMENTS: tuple[dict[str, str], ...] = (
    {
        "source_doc_id": "SRC-EVIDENCE-MISSING-SANSHA-PUBLICATION-STATUS",
        "publisher": "海南省财政厅",
        "publisher_level": "省级财政部门",
        "document_title": "2020年海南省财政厅政府信息公开工作年度报告",
        "source_url": "https://mof.hainan.gov.cn/sczt/0204/202101/63544335246a433d82446428cc6e33d0.shtml?ddtab=true",
        "publication_date": "2021-01-19",
        "source_grade": "A1",
        "document_type": "政府信息公开年度报告",
        "note": "官方年报明确记载：2020年海南省预算公开中三沙市整体涉密不予公开；本来源仅作为公开渠道缺失的证据，不产生业务数值。",
    },
    {
        "source_doc_id": "SRC-EVIDENCE-MISSING-SANSHA-SEARCH-2026",
        "publisher": "三沙市人民政府",
        "publisher_level": "市级政府",
        "document_title": "三沙市政府门户网站站内检索结果（年度GDP及财政关键词）",
        "source_url": "https://www.sansha.gov.cn/search5/html/searchResult.html",
        "publication_date": "2026-09-01",
        "source_grade": "A1",
        "document_type": "政府门户网站检索记录",
        "note": "按2018—2025年度公报、地区生产总值、一般公共预算、财政决算、政府性基金预算等关键词检索；结果未取得可直接入表的年度全市数值，本来源仅登记检索结果。",
    },
    {
        "source_doc_id": "SRC-EVIDENCE-MISSING-SANSHA-RATING-2024",
        "publisher": "上海新世纪资信评估投资服务有限公司",
        "publisher_level": "评级机构",
        "document_title": "海南省及下辖市县地方政府与城投企业债务风险研究报告",
        "source_url": "https://pdf.dfcfw.com/pdf/H3_AP202412181641343322_1.pdf?1734528397000.pdf=",
        "publication_date": "2024-12-18",
        "source_grade": "B2",
        "document_type": "评级研究报告",
        "note": "报告对三沙市近年经济财政数据缺失作出说明；仅用于确认公开渠道状态，不转录推算值。",
    },
    {
        "source_doc_id": "SRC-EVIDENCE-MISSING-ALI-GROWTH-2020",
        "publisher": "阿里地区行政公署",
        "publisher_level": "地级行政公署",
        "document_title": "阿里地区2020年经济社会发展再上新台阶",
        "source_url": "https://www.al.gov.cn/info/1035/39331.htm",
        "publication_date": "2021-07-20",
        "source_grade": "A1",
        "document_type": "官方经济信息",
        "note": "官方页面披露2020年GDP总量70.7亿元，但未披露按不变价格计算的实际增速；本来源不产生增速值。",
    },
    {
        "source_doc_id": "SRC-EVIDENCE-MISSING-ALI-GROWTH-2022",
        "publisher": "联合资信评估股份有限公司",
        "publisher_level": "评级机构",
        "document_title": "地方政府与城投企业债务风险研究报告——西藏自治区篇",
        "source_url": "https://www.lhratings.com/file/f732353344d.pdf",
        "publication_date": "2024-11-25",
        "source_grade": "B2",
        "document_type": "评级研究报告",
        "note": "报告表格脚注说明阿里地区2022年GDP增速由绝对值计算；由于不是公开披露的实际增速，按严格口径不写入主表。",
    },
    {
        "source_doc_id": "SRC-EVIDENCE-MISSING-ALI-STATISTICS-INDEX-2026",
        "publisher": "阿里地区行政公署",
        "publisher_level": "地级行政公署",
        "document_title": "阿里地区统计数据公开目录（截至2026年9月2日复核）",
        "source_url": "https://www.al.gov.cn/gk/xxgkml1/tjsj/1.htm",
        "publication_date": "2026-09-02",
        "source_grade": "A1",
        "document_type": "政府统计信息公开目录",
        "note": "官方目录当前可见年度经济条目包括2017年GDP信息，近年主要为2023年前三季度等阶段性信息；未见2020或2022年阿里地区按不变价格计算的全年GDP实际增速表格。本来源用于登记已检索公开渠道，不产生增速值。",
    },
    {
        "source_doc_id": "SRC-EVIDENCE-MISSING-XPCC-FINANCE-INDEX",
        "publisher": "新疆生产建设兵团财政局",
        "publisher_level": "兵团财政部门",
        "document_title": "预决算公开和兵团政府性基金、行政事业性收费目录清单",
        "source_url": "https://cwj.xjbt.gov.cn/xxgk/yjsgkhbtzfxjjxz/",
        "publication_date": "2026-09-01",
        "source_grade": "A1",
        "document_type": "财政信息公开目录",
        "note": "已检查兵团财政局预决算公开目录及信息公开索引，未找到可定位的2021年后全兵团年度一般预算收支表。",
    },
    {
        "source_doc_id": "SRC-EVIDENCE-MISSING-XPCC-FISCAL-POST-2021",
        "publisher": "上海证券交易所公开披露平台",
        "publisher_level": "交易所公开披露平台",
        "document_title": "新疆生产建设兵团政府债券相关评级报告（2025）",
        "source_url": "https://static.sse.com.cn/disclosure/bond/announcement/local/c/new/2025-09-10/0000_20250910_I5Z5.pdf",
        "publication_date": "2025-09-10",
        "source_grade": "B2",
        "document_type": "政府债券评级报告",
        "note": "报告明确说明自2021年起受政策调整等因素影响，兵团未再披露后续年度财政信息；不把上半年或自治区汇总数据当作全兵团年度值。",
    },
    {
        "source_doc_id": "SRC-EVIDENCE-MISSING-XPCC-GDP-2024-2025",
        "publisher": "新疆生产建设兵团商务局、兵团官方新闻门户",
        "publisher_level": "兵团政府部门",
        "document_title": "二〇二四年兵团经济发展述评及2025年阶段性经济信息",
        "source_url": "https://swj.xjbt.gov.cn/c/2025-01-08/8377374.shtml",
        "publication_date": "2025-01-08",
        "source_grade": "A1",
        "document_type": "官方经济运行信息",
        "note": "公开信息描述2024年经济运行但未给出全年GDP总量或实际增速；相关评级资料仅有2024年前三季度和2025年上半年数值。",
    },
    {
        "source_doc_id": "SRC-EVIDENCE-MISSING-XPCC-GDP-REPORT-2025",
        "publisher": "联合资信评估股份有限公司、上海证券交易所公开披露平台",
        "publisher_level": "全国性政府债券评级机构/交易所公开披露平台",
        "document_title": "2025年新疆维吾尔自治区（新疆生产建设兵团）地方政府债券信用评级报告",
        "source_url": "https://static.sse.com.cn/disclosure/bond/announcement/local/c/new/2025-09-10/0000_20250910_I5Z5.pdf",
        "publication_date": "2025-09-10",
        "source_grade": "B2",
        "document_type": "政府债券评级报告",
        "note": "报告列示2023年全年GDP及2024年前三季度、2025年上半年阶段数据，并明确未取得2024全年度经济数据；不能据阶段值年化或外推2025全年值。",
    },
    {
        "source_doc_id": "SRC-EVIDENCE-MISSING-XPCC-GDP-INDEX-2026",
        "publisher": "新疆生产建设兵团统计局",
        "publisher_level": "兵团统计机构",
        "document_title": "兵团统计局统计公报目录（截至2026年9月2日复核）",
        "source_url": "https://tjj.xjbt.gov.cn/sjzx/tjgb/",
        "publication_date": "2026-09-02",
        "source_grade": "A1",
        "document_type": "统计公报公开目录",
        "note": "复核兵团统计局统计公报入口及公开索引，当前未找到2024或2025年全年兵团国民经济和社会发展统计公报；仅有已公开的2023年全年及阶段性经济信息。",
    },
    {
        "source_doc_id": "SRC-EVIDENCE-MISSING-XIONGAN-GDP-STATUS",
        "publisher": "中国雄安官网",
        "publisher_level": "新区政府门户网站",
        "document_title": "‘十四五’雄安答卷专题发布会信息",
        "source_url": "https://www.xiongan.gov.cn/20251226/2b31d8cd97fd4776a2ffedb99e812b04/c.html",
        "publication_date": "2025-12-26",
        "source_grade": "A1",
        "document_type": "官方新闻发布信息",
        "note": "只披露‘十四五’GDP年均增长17.1%，不披露2024或2025年度GDP总量/实际增速；不以平均增速代替年度值。",
    },
    {
        "source_doc_id": "SRC-EVIDENCE-MISSING-XIONGAN-DECISION",
        "publisher": "中国雄安官网",
        "publisher_level": "新区政府门户网站",
        "document_title": "政府决算公开专栏",
        "source_url": "https://www.xiongan.gov.cn/zwgk/czyjsgkzl/zfjs/index.html",
        "publication_date": "2026-09-01",
        "source_grade": "A1",
        "document_type": "政府决算公开目录",
        "note": "已核验2024、2025年全区财政决算公开入口；该专栏用于财政数值，不产生GDP数值。",
    },
    {
        "source_doc_id": "SRC-EVIDENCE-MISSING-XIONGAN-STATISTICS-INDEX-2026",
        "publisher": "中国雄安官网",
        "publisher_level": "新区政府门户网站",
        "document_title": "雄安新区统计信息公开目录（截至2026年9月2日复核）",
        "source_url": "https://www.xiongan.gov.cn/zwgk/zfxxgk/fdgknr/tjxx.html",
        "publication_date": "2026-09-02",
        "source_grade": "A1",
        "document_type": "统计信息公开目录",
        "note": "复核新区统计信息目录，当前可见内容包括投资、外贸及阶段性区域信息，未找到2024或2025年新区全域GDP总量及实际增速表格。",
    },
    {
        "source_doc_id": "SRC-EVIDENCE-MISSING-LAIWU-YEARBOOK",
        "publisher": "济南市统计局",
        "publisher_level": "市级统计部门",
        "document_title": "济南统计年鉴2020及分地区生产总值表",
        "source_url": "https://jntj.jinan.gov.cn/col27523/art/2020/art_27523_4002510.html",
        "publication_date": "2020-12-31",
        "source_grade": "A1",
        "document_type": "官方统计年鉴附件",
        "note": "2019年莱芜全域GDP可定位为871.60亿元，但分地区表未列全域实际增速；不能用莱芜区、钢城区增速相加或加权推算。",
    },
    {
        "source_doc_id": "SRC-EVIDENCE-MISSING-LAIWU-2018-REPORT",
        "publisher": "济南市人民政府",
        "publisher_level": "市级政府",
        "document_title": "济南市2019年国民经济和社会发展计划",
        "source_url": "https://www.jinan.gov.cn/col2612/art/2019/art_2612_2911096.html",
        "publication_date": "2019-03-01",
        "source_grade": "A1",
        "document_type": "政府工作/计划报告",
        "note": "该报告中的原莱芜市GDP 1005.7亿元、增速7.2%对应2018年，不是2019年；本来源用于排除年度错配。",
    },
    {
        "source_doc_id": "SRC-EVIDENCE-MISSING-LAIWU-YEARBOOK-2019-EDITION",
        "publisher": "中国城市统计年鉴公开表格镜像",
        "publisher_level": "公开统计年鉴表格镜像",
        "document_title": "2019中国城市统计年鉴表2-9地区生产总值（莱芜市行）",
        "source_url": "https://www.chinautc.com/upload/fckeditor/20192-9.pdf",
        "publication_date": "2019",
        "source_grade": "B2",
        "document_type": "统计年鉴表格镜像（年度错配排除证据）",
        "note": "该版年鉴表格的莱芜市行列示GDP 10056500（万元）及实际增速7.20%，与官方2018年原莱芜市GDP 1005.65亿元、增速7.2%一致；它是2018年度数据，不能用于填补2019年原莱芜市全域实际增速。本来源仅用于排除将年鉴版次误当数据年度。",
    },
    {
        "source_doc_id": "SRC-EVIDENCE-MISSING-NAQU-2019-AUDIT",
        "publisher": "西藏自治区审计厅",
        "publisher_level": "省级审计部门",
        "document_title": "2021年第7号公告：那曲市2019年度财政决算和其他财政收支情况审计结果公告",
        "source_url": "https://sjt.xizang.gov.cn/xwzx/gsgg/202104/t20210401_198078.html",
        "publication_date": "2021-04-01",
        "source_grade": "A1",
        "document_type": "审计公告",
        "note": "官方公告披露2019年那曲市一般公共预算和政府性基金预算，但未披露全市法定债务余额；本来源仅作为已检索证据。",
    },
    {
        "source_doc_id": "SRC-EVIDENCE-MISSING-NAQU-2019-BUDGET",
        "publisher": "西藏自治区人民政府",
        "publisher_level": "省级政府",
        "document_title": "关于西藏自治区2019年预算执行情况和2020年预算草案的报告",
        "source_url": "https://www.xizang.gov.cn/zwgk/zdxxlygk/czyjsgk/202001/t20200126_131048.html",
        "publication_date": "2020-01-26",
        "source_grade": "A1",
        "document_type": "预算执行报告",
        "note": "官方报告披露2019年全区政府法定债务限额及余额，但未拆分到那曲市；本来源不用于反推地市数值。",
    },
    {
        "source_doc_id": "SRC-EVIDENCE-MISSING-NAQU-2019-RATING",
        "publisher": "联合资信评估股份有限公司",
        "publisher_level": "评级机构",
        "document_title": "地方政府与城投企业债务风险研究报告——西藏自治区篇",
        "source_url": "https://www.lhratings.com/file/f292d56c60f.pdf",
        "publication_date": "2023-05-10",
        "source_grade": "B2",
        "document_type": "评级研究报告",
        "note": "报告图表注释明确指出未获取2019年那曲市政府债务余额；仅用于证明二手公开渠道也无该值，不转录图表估读。",
    },
    {
        "source_doc_id": "SRC-EVIDENCE-MISSING-JIUQUAN-2025-BUDGET",
        "publisher": "酒泉市财政局",
        "publisher_level": "市级财政部门",
        "document_title": "2025年酒泉市市级政府预算公开",
        "source_url": "https://czj.jiuquan.gov.cn/czj/c105196/202501/f4f8551abf904585975f50c90289da84.shtml",
        "publication_date": "2025-01-24",
        "source_grade": "A1",
        "document_type": "市级预算公开",
        "note": "官方页面及附件含2025年市级债务预算说明，不等同于2025年末全市决算余额；本来源仅作为已检索证据。",
    },
    {
        "source_doc_id": "SRC-EVIDENCE-MISSING-JIUQUAN-2025-EXECUTION",
        "publisher": "酒泉市财政局",
        "publisher_level": "市级财政部门",
        "document_title": "酒泉市2025年度财政预算执行情况",
        "source_url": "https://czj.jiuquan.gov.cn/czj/c105207/202601/ccf1159a8e644b57ab2f69169fa0de75.shtml",
        "publication_date": "2026-01-29",
        "source_grade": "A1",
        "document_type": "年度财政执行情况",
        "note": "官方页面公开2025年度全市一般预算和政府性基金执行数据，未披露2025年末全市法定债务余额。",
    },
    {
        "source_doc_id": "SRC-EVIDENCE-MISSING-JIUQUAN-2025-DEBT-BRIEF",
        "publisher": "酒泉市财政局",
        "publisher_level": "市级财政部门",
        "document_title": "酒泉市2025年10月债务简报",
        "source_url": "https://czj.jiuquan.gov.cn/czj/c105201/202511/242032e1d8f945c59c374522d856596b.shtml",
        "publication_date": "2025-11-20",
        "source_grade": "A1",
        "document_type": "债务简报",
        "note": "官方简报截至2025年10月，非年末决算；不将阶段性偿还数据换算为年末债务余额。",
    },
)


EVIDENCE_BY_KEY = {
    (row["city_id"], row["metric_year"], row["field_name"]): row
    for row in EVIDENCE_BASED_MISSING
}
