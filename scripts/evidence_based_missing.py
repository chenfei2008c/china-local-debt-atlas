"""已穷尽公开渠道但仍无可验收数值的字段证据登记。"""

from __future__ import annotations


EVIDENCE_CHECKED_AT = "2026-08-19"


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


EVIDENCE_BASED_MISSING: tuple[dict[str, str], ...] = _sansha_rows() + (
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

