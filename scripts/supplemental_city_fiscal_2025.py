"""尚未接入主表的 2025 年城市财政/经济摘录适配器。

本模块只登记仓库中已经归档、并且明确标注全市（全州/全地区）口径的
文本摘录。数值由 ``collect_national_panel.load_city_year_fiscal_sources``
统一解析、换算和登记血缘；本文件不生成估算值。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw" / "province_fiscal" / "2025"

N = r"[0-9][0-9,]*(?:\.[0-9]+)?"
N_WIDE_DOT = r"[0-9][0-9,]*(?:[\.．][0-9]+)?"


def _spec(
    *,
    file_name: str,
    city_name: str,
    city_id: str,
    fields: dict[str, tuple[str, str]],
    grade: str,
    publisher: str,
    document_title: str,
    note: str,
    secondary: bool = False,
) -> dict[str, Any]:
    path = RAW / ("secondary" if secondary else "official") / file_name
    return {
        "year": 2025,
        "city_name": city_name,
        "city_id": city_id,
        "source_doc_id": f"SRC-SUPPLEMENTAL-CITY-FISCAL-2025-{city_id.replace('-', '')}-{file_name.split('_2025', 1)[0].upper()}",
        "url": "",
        "path": path,
        "text_path": path,
        "text_is_curated": True,
        "document_title": document_title,
        "publisher": publisher,
        "publisher_level": "评级机构公开披露" if secondary else "市级/州级官方公开资料",
        "publication_date": "",
        "source_grade": grade,
        "source_format": "txt",
        "data_status": "execution",
        "data_status_label": "2025年执行数",
        "document_type": "城市财政/统计公报精确摘录",
        "patterns": {field: spec[0] for field, spec in fields.items()},
        "raw_units": {field: spec[1] for field, spec in fields.items()},
        "note": note,
    }


FUND_100M = {
    "gov_fund_revenue_100m": (
        rf"政府性基金(?:预算)?收入(?:合计|实际完成|完成|为)?({N})(?:亿元)",
        "亿元",
    )
}
FUND_10K = {
    "gov_fund_revenue_100m": (
        rf"政府性基金(?:预算)?收入(?:合计|实际完成|完成|为)?({N})(?:万元)",
        "万元",
    )
}


SUPPLEMENTAL_CITY_FISCAL_SOURCES: list[dict[str, Any]] = [
    _spec(
        file_name="fangchenggang_2025_budget_report_excerpt.txt",
        city_name="防城港市", city_id="CN-450600", fields=FUND_10K,
        grade="A2", publisher="防城港市财政局",
        document_title="防城港市2025年预算执行情况和2026年预算草案报告",
        note="官方预算报告摘录明确为全市政府性基金预算收入合计，原始单位万元；不使用市本级调整数。",
    ),
    _spec(
        file_name="guyuan_2025_budget_report_excerpt.txt",
        city_name="固原市", city_id="CN-640400", fields=FUND_10K,
        grade="A2", publisher="固原市财政局",
        document_title="固原市2025年全市及市本级财政预算执行情况和2026年预算草案报告",
        note="官方预算报告明确为全市政府性基金收入完成数，原始单位万元。",
    ),
    _spec(
        file_name="hotan_2025_economic_fiscal_excerpt.txt",
        city_name="和田地区", city_id="CN-653200",
        fields={
            "general_public_revenue_100m": (rf"一般公共预算收入决算表：本年收入合计({N})(?:万元)", "万元"),
            "general_public_expenditure_100m": (rf"一般公共预算支出决算表：本年支出合计({N})(?:万元)", "万元"),
            "gov_fund_revenue_100m": (rf"政府性基金预算收入决算表：政府性基金收入({N})(?:万元)", "万元"),
        },
        grade="A2", publisher="和田地区财政局",
        document_title="2025年度和田地区政府决算公开摘录",
        note="官方决算表摘录明确为和田地区全地区决算数，原始单位万元；不使用地区本级口径。",
    ),
    _spec(
        file_name="jiaozuo_2025_budget_report_excerpt.txt",
        city_name="焦作市", city_id="CN-410800", fields={"gov_fund_revenue_100m": (rf"实际完成({N})亿元；支出", "亿元")},
        grade="A2", publisher="焦作市财政局",
        document_title="焦作市2025年预算执行情况和2026年预算草案报告",
        note="官方预算执行报告明确为全市快报执行数，保留 execution 状态。",
    ),
    _spec(
        file_name="kaifeng_2025_fund_excerpt.txt",
        city_name="开封市", city_id="CN-410200", fields=FUND_100M,
        grade="B2", publisher="中国货币网公开披露的评级报告",
        document_title="开封市主要经济财政指标（评级报告表2）",
        note="B2 精确表格明确列示开封市全市 2025 年政府性基金收入，不使用市本级预算数。",
    ),
    _spec(
        file_name="putian_2025_budget_report_excerpt.txt",
        city_name="莆田市", city_id="CN-350300", fields=FUND_100M,
        grade="A2", publisher="莆田市财政局",
        document_title="莆田市2025年预算执行公开信息",
        note="官方预算执行公开信息明确为全市政府性基金收入，单位亿元。",
    ),
    _spec(
        file_name="qujing_2025_budget_execution_report_excerpt.txt",
        city_name="曲靖市", city_id="CN-530300", fields=FUND_100M,
        grade="A2", publisher="曲靖市财政局",
        document_title="曲靖市2025年地方财政预算执行情况和2026年预算草案报告",
        note="官方预算执行报告明确为曲靖市全市政府性基金预算收入，不使用市级收入。",
    ),
    _spec(
        file_name="sanming_2025_budget_report_excerpt.txt",
        city_name="三明市", city_id="CN-350400", fields=FUND_10K,
        grade="A2", publisher="三明市人民政府",
        document_title="三明市2025年预算执行情况和2026年预算草案报告",
        note="官方预算报告明确为全市政府性基金预算收入，原始单位万元。",
    ),
    _spec(
        file_name="shanwei_2025_budget_execution_report_excerpt.txt",
        city_name="汕尾市", city_id="CN-441500", fields=FUND_100M,
        grade="A2", publisher="汕尾市财政局",
        document_title="汕尾市2025年预算执行情况和2026年预算草案报告",
        note="官方预算执行报告明确为汕尾市全市政府性基金预算收入，不使用市级数。",
    ),
    _spec(
        file_name="suzhou_anhui_2025_budget_report_excerpt.txt",
        city_name="宿州市", city_id="CN-341300", fields=FUND_100M,
        grade="A2", publisher="宿州市人民政府",
        document_title="宿州市2025年预算执行情况和2026年预算草案报告摘要",
        note="官方预算报告摘要明确为宿州市全市政府性基金预算收入。",
    ),
    _spec(
        file_name="wuhan_2025_budget_tables_excerpt.txt",
        city_name="武汉市", city_id="CN-420100", fields={
            "general_public_revenue_100m": (rf"一般公共预算收入执行情况表：一般公共预算收入({N})(?:万元)", "万元"),
            "general_public_expenditure_100m": (rf"一般公共预算支出执行情况表：一般公共预算支出({N})(?:万元)", "万元"),
            "gov_fund_revenue_100m": (rf"政府性基金收入执行情况表：政府性基金收入({N})(?:万元)", "万元"),
        },
        grade="A2", publisher="武汉市财政局",
        document_title="武汉市2025年全市预算执行表摘录",
        note="官方预算执行表摘录明确为全市口径，原始单位万元。",
    ),
    _spec(
        file_name="xinxiang_2025_budget_report_excerpt.txt",
        city_name="新乡市", city_id="CN-410700", fields={"gov_fund_revenue_100m": (rf"政府性基金收入预算({N})亿元，实际完成({N})亿元", "亿元")},
        grade="A2", publisher="新乡市财政局/公开报告",
        document_title="新乡市2025年预算执行情况和2026年预算草案报告摘要",
        note="公开预算报告摘要明确为全市政府性基金收入实际完成数，不使用市级预算安排数。",
    ),
    _spec(
        file_name="yunfu_2025_budget_report_excerpt.txt",
        city_name="云浮市", city_id="CN-445300", fields=FUND_10K,
        grade="A2", publisher="云浮市人民政府",
        document_title="2026年云浮市本级政府预算公开（2025年全市基金执行摘录）",
        note="官方预算公开附件明确为全市政府性基金预算收入，原始单位万元。",
    ),
    _spec(
        file_name="yuxi_2025_budget_execution_report_excerpt.txt",
        city_name="玉溪市", city_id="CN-530400", fields=FUND_100M,
        grade="A2", publisher="玉溪市财政局",
        document_title="玉溪市2025年地方财政预算执行情况和2026年预算草案报告",
        note="官方预算执行报告明确为玉溪市全市政府性基金预算收入，不使用市本级收入。",
    ),
    _spec(
        file_name="zhoukou_2025_budget_report_excerpt.txt",
        city_name="周口市", city_id="CN-411600", fields={"gov_fund_revenue_100m": (rf"政府性基金预算。全市收入完成({N})亿元", "亿元")},
        grade="A2", publisher="周口市人民政府门户",
        document_title="周口市2025年预算执行情况和2026年预算草案报告解读",
        note="公开预算报告解读明确为全市政府性基金收入完成数，不使用市级预算数。",
    ),
    _spec(
        file_name="anqing_2025_rating_report_excerpt.txt",
        city_name="安庆市", city_id="CN-340800", fields=FUND_100M,
        grade="B2", publisher="东方金诚国际信用评估有限公司",
        document_title="安庆市主要经济及财政指标（评级报告图表15）",
        note="B2 精确表格列示安庆市全市 2025 年政府性基金收入。",
        secondary=True,
    ),
    _spec(
        file_name="baoji_2025_statistical_bulletin_excerpt.txt",
        city_name="宝鸡市", city_id="CN-610300", fields=FUND_100M,
        grade="B2", publisher="宝鸡市人民政府、宝鸡市统计局",
        document_title="2025年宝鸡市国民经济和社会发展统计公报",
        note="公开统计公报财政段落明确为宝鸡市全市政府性基金收入完成数。",
        secondary=True,
    ),
    _spec(
        file_name="chengdu_2025_fund_execution_excerpt.txt",
        city_name="成都市", city_id="CN-510100", fields={"gov_fund_revenue_100m": (rf"政府性基金预算收入合计，快报执行数({N})万元", "万元")},
        grade="B2", publisher="成都市财政局",
        document_title="2025年成都市政府性基金预算收入执行情况表",
        note="财政局官方执行表摘录明确为成都市全市快报执行数，原始单位万元。",
        secondary=True,
    ),
    _spec(
        file_name="datong_2025_budget_report_excerpt.txt",
        city_name="大同市", city_id="CN-140200", fields={"gov_fund_revenue_100m": (rf"政府性基金预算收入完成({N_WIDE_DOT})亿元", "亿元")},
        grade="B2", publisher="大同市人民政府",
        document_title="大同市2025年全市和市本级预算执行报告",
        note="公开预算执行报告明确为大同市全市政府性基金预算收入执行数。",
        secondary=True,
    ),
    _spec(
        file_name="foshan_2025_fiscal_rating_excerpt.txt",
        city_name="佛山市", city_id="CN-440600", fields={
            "general_public_revenue_100m": (r"一般公共预算收入(?:\|[0-9]+\.[0-9]+){2}\|([0-9]+\.[0-9]+)", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出(?:\|[0-9]+\.[0-9]+){2}\|([0-9]+\.[0-9]+)", "亿元"),
            "gov_fund_revenue_100m": (r"政府性基金预算收入(?:\|[0-9]+\.[0-9]+){2}\|([0-9]+\.[0-9]+)", "亿元"),
        },
        grade="B2", publisher="联合资信评估股份有限公司",
        document_title="佛山市主要财政数据（评级报告表5）",
        note="B2 精确表格明确使用佛山市全市财政数据，取 2025 年列。",
        secondary=True,
    ),
    _spec(
        file_name="longyan_2025_rating_report_excerpt.txt",
        city_name="龙岩市", city_id="CN-350800", fields=FUND_100M,
        grade="B2", publisher="东方金诚国际信用评估有限公司",
        document_title="龙岩市地方政府再融资债券相关评级报告财政表",
        note="B2 精确表格明确为龙岩市全市政府性基金收入。",
        secondary=True,
    ),
    _spec(
        file_name="lvliang_2025_budget_report_excerpt.txt",
        city_name="吕梁市", city_id="CN-141100", fields=FUND_100M,
        grade="B2", publisher="吕梁市人民政府",
        document_title="吕梁市2025年全市和市本级预算执行报告",
        note="公开预算执行报告明确为吕梁市全市政府性基金收入执行数。",
        secondary=True,
    ),
    _spec(
        file_name="nanping_2025_rating_report_excerpt.txt",
        city_name="南平市", city_id="CN-350700", fields=FUND_100M,
        grade="B2", publisher="联合资信评估股份有限公司",
        document_title="南平市地方经济财政实力评级表",
        note="B2 精确表格明确为南平市全市政府性基金收入。",
        secondary=True,
    ),
    _spec(
        file_name="ningde_2025_rating_report_excerpt.txt",
        city_name="宁德市", city_id="CN-350900", fields=FUND_100M,
        grade="B2", publisher="中诚信国际信用评级有限责任公司",
        document_title="宁德市地方经济财政实力评级表",
        note="B2 精确表格明确为宁德市全市年度快报执行数。",
        secondary=True,
    ),
    _spec(
        file_name="pingdingshan_2025_budget_report_excerpt.txt",
        city_name="平顶山市", city_id="CN-410400", fields={"gov_fund_revenue_100m": (rf"实际完成({N})万元", "万元")},
        grade="B2", publisher="平顶山市人民政府",
        document_title="平顶山市2025年预算执行情况和2026年预算草案报告",
        note="公开预算执行报告明确为全市政府性基金收入实际完成数，原始单位万元。",
        secondary=True,
    ),
    _spec(
        file_name="shandong_2025_city_fiscal_rating_report_excerpt.txt",
        city_name="潍坊市", city_id="CN-370700", fields={"gov_fund_revenue_100m": (r"潍坊市政府性基金收入({N})亿元".format(N=N), "亿元")},
        grade="B2", publisher="中证鹏元资信评估股份有限公司",
        document_title="2025山东省部分地级行政区经济财政指标情况",
        note="B2 精确表格列示潍坊市全市政府性基金收入。", secondary=True,
    ),
    _spec(
        file_name="shandong_2025_city_fiscal_rating_report_excerpt.txt",
        city_name="淄博市", city_id="CN-370300", fields={"gov_fund_revenue_100m": (r"淄博市政府性基金收入({N})亿元".format(N=N), "亿元")},
        grade="B2", publisher="中证鹏元资信评估股份有限公司",
        document_title="2025山东省部分地级行政区经济财政指标情况",
        note="B2 精确表格列示淄博市全市政府性基金收入。", secondary=True,
    ),
    _spec(
        file_name="shandong_2025_city_fiscal_rating_report_excerpt.txt",
        city_name="泰安市", city_id="CN-370900", fields={"gov_fund_revenue_100m": (r"泰安市政府性基金收入({N})亿元".format(N=N), "亿元")},
        grade="B2", publisher="中证鹏元资信评估股份有限公司",
        document_title="2025山东省部分地级行政区经济财政指标情况",
        note="B2 精确表格列示泰安市全市政府性基金收入。", secondary=True,
    ),
    _spec(
        file_name="shandong_2025_city_fiscal_rating_report_excerpt.txt",
        city_name="滨州市", city_id="CN-371600", fields={"gov_fund_revenue_100m": (r"滨州市政府性基金收入({N})亿元".format(N=N), "亿元")},
        grade="B2", publisher="中证鹏元资信评估股份有限公司",
        document_title="2025山东省部分地级行政区经济财政指标情况",
        note="B2 精确表格列示滨州市全市政府性基金收入。", secondary=True,
    ),
    _spec(
        file_name="shandong_2025_city_fiscal_rating_report_excerpt.txt",
        city_name="日照市", city_id="CN-371100", fields={"gov_fund_revenue_100m": (r"日照市政府性基金收入({N})亿元".format(N=N), "亿元")},
        grade="B2", publisher="中证鹏元资信评估股份有限公司",
        document_title="2025山东省部分地级行政区经济财政指标情况",
        note="B2 精确表格列示日照市全市政府性基金收入。", secondary=True,
    ),
    _spec(
        file_name="shandong_2025_city_fiscal_rating_report_excerpt.txt",
        city_name="枣庄市", city_id="CN-370400", fields={"gov_fund_revenue_100m": (r"枣庄市政府性基金收入({N})亿元".format(N=N), "亿元")},
        grade="B2", publisher="中证鹏元资信评估股份有限公司",
        document_title="2025山东省部分地级行政区经济财政指标情况",
        note="B2 精确表格列示枣庄市全市政府性基金收入。", secondary=True,
    ),
    _spec(
        file_name="taizhou_2025_finance_rating_excerpt.txt",
        city_name="泰州市", city_id="CN-321200", fields={
            "general_public_revenue_100m": (r"一般公共预算收入（亿元）(?:[0-9]+\.[0-9]+){2}([0-9]+\.[0-9]+)", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出（亿元）(?:[0-9]+\.[0-9]+){2}([0-9]+\.[0-9]+)", "亿元"),
            "gov_fund_revenue_100m": (r"政府性基金预算收入（亿元）(?:[0-9]+\.[0-9]+){2}([0-9]+\.[0-9]+)", "亿元"),
        },
        grade="B2", publisher="评级机构公开披露",
        document_title="泰州市主要财政数据精确表格",
        note="B2 精确表格列示泰州市全市 2025 年财政收入、支出和政府性基金收入。",
        secondary=True,
    ),
    _spec(
        file_name="xiamen_2025_budget_report_excerpt.txt",
        city_name="厦门市", city_id="CN-350200", fields={"gov_fund_revenue_100m": (rf"政府性基金收入合计为({N})亿元", "亿元")},
        grade="B2", publisher="联合资信评估股份有限公司",
        document_title="厦门市2025年地方政府再融资信用报告财政表",
        note="B2 精确表格引用厦门市预算执行报告附表，明确为全市政府性基金收入。",
        secondary=True,
    ),
    _spec(
        file_name="xuancheng_2025_budget_report_excerpt.txt",
        city_name="宣城市", city_id="CN-341800", fields=FUND_100M,
        grade="B2", publisher="宣城市人民政府",
        document_title="宣城市2025年预算执行情况和2026年预算草案报告",
        note="公开预算执行报告明确为宣城市全市政府性基金预算收入执行数。",
        secondary=True,
    ),
    _spec(
        file_name="xuzhou_2025_finance_rating_excerpt.txt",
        city_name="徐州市", city_id="CN-320300", fields={
            "general_public_revenue_100m": (r"一般公共预算收入（亿元）(?:[0-9]+\.[0-9]+)([0-9]+\.[0-9]+)", "亿元"),
            "general_public_expenditure_100m": (r"一般公共预算支出（亿元）(?:[0-9]+\.[0-9]+)([0-9]+\.[0-9]+)", "亿元"),
            "gov_fund_revenue_100m": (r"政府性基金收入（亿元）(?:[0-9]+\.[0-9]+)([0-9]+\.[0-9]+)", "亿元"),
        },
        grade="B2", publisher="联合资信评估股份有限公司",
        document_title="徐州市主要财力指标精确表格",
        note="B2 精确表格列示徐州市全市 2025 年财政收入、支出和政府性基金收入。",
        secondary=True,
    ),
    _spec(
        file_name="yangjiang_2025_budget_report_excerpt.txt",
        city_name="阳江市", city_id="CN-441700", fields=FUND_100M,
        grade="B2", publisher="阳江日报公开转载",
        document_title="阳江市2025年预算执行情况和2026年预算草案财政执行段落",
        note="B2 精确转载明确为阳江市全市政府性基金预算收入。",
        secondary=True,
    ),
    _spec(
        file_name="zhengzhou_2025_budget_report_excerpt.txt",
        city_name="郑州市", city_id="CN-410100", fields=FUND_100M,
        grade="B2", publisher="郑州市财政局",
        document_title="郑州市财政局2025年工作总结",
        note="市财政局公开工作总结明确为郑州市全市政府性基金收入执行数。",
        secondary=True,
    ),
    _spec(
        file_name="zhuhai_2025_fiscal_rating_excerpt.txt",
        city_name="珠海市", city_id="CN-440400", fields=FUND_100M,
        grade="B2", publisher="联合资信评估股份有限公司",
        document_title="珠海市主要财政指标评级表",
        note="B2 精确表格明确使用珠海市全市财政指标，取 2025 年政府性基金收入。",
        secondary=True,
    ),
]


ECONOMIC_FIELDS = {
    "gdp_current_100m": (rf"(?:地区生产总值|生产总值)(?:（GDP）)?({N})亿元", "亿元"),
    "gdp_real_growth_pct": (rf"(?:地区生产总值|生产总值).*?增长({N})%", "%"),
    "resident_population_10k": (rf"年末.*?常住人口({N})万人", "万人"),
    "general_public_revenue_100m": (rf"(?:地方)?一般公共预算收入(?:完成|实现)?({N})亿元", "亿元"),
    "general_public_expenditure_100m": (rf"一般公共预算支出(?:完成|实现)?({N})亿元", "亿元"),
}

for file_name, city_name, city_id in (
    ("kizilsu_2025_economic_fiscal_excerpt.txt", "克孜勒苏柯尔克孜自治州", "CN-653000"),
    ("nanyang_2025_statistical_bulletin_excerpt.txt", "南阳市", "CN-411300"),
    ("xinyang_2025_statistical_bulletin_excerpt.txt", "信阳市", "CN-411500"),
    ("xuchang_2025_statistical_bulletin_excerpt.txt", "许昌市", "CN-411000"),
    ("anyang_2025_statistical_bulletin_excerpt.txt", "安阳市", "CN-410500"),
    ("hebi_2025_statistical_bulletin_excerpt.txt", "鹤壁市", "CN-410600"),
    ("kaifeng_2025_statistical_bulletin_excerpt.txt", "开封市", "CN-410200"),
    ("shangqiu_2025_statistical_bulletin_excerpt.txt", "商丘市", "CN-411400"),
    ("zhoukou_2025_statistical_bulletin_excerpt.txt", "周口市", "CN-411600"),
):
    SUPPLEMENTAL_CITY_FISCAL_SOURCES.append(
        _spec(
            file_name=file_name, city_name=city_name, city_id=city_id,
            fields=ECONOMIC_FIELDS, grade="A2", publisher="地方统计机构官方统计公报",
            document_title=f"{city_name}2025年国民经济和社会发展统计公报",
            note="官方统计公报明确披露全市经济、财政和人口字段；政府性基金未在本来源中代填。",
            secondary=file_name.split("_2025", 1)[0] in {"anyang", "hebi", "kaifeng", "shangqiu", "zhoukou"},
        )
    )

SUPPLEMENTAL_CITY_FISCAL_SOURCES.append(
    _spec(
        file_name="urumqi_2025_statistical_bulletin_excerpt.txt",
        city_name="乌鲁木齐市", city_id="CN-650100",
        fields={
            **ECONOMIC_FIELDS,
            "gov_fund_revenue_100m": (rf"政府性基金预算收入({N})亿元", "亿元"),
        },
        grade="A2", publisher="乌鲁木齐市统计局",
        document_title="乌鲁木齐市2025年国民经济和社会发展统计公报",
        note="官方统计公报明确披露乌鲁木齐市全市经济、财政和人口字段，单位亿元/万人。",
    )
)


# 浙江省和山东省的二手精确表均为一个多城市文件。拆成字段级来源，
# 这样同一文件可以对每个城市写入独立的城市年度血缘。
for city_name, city_id, value in (
    ("杭州市", "CN-330100", "1717.13"), ("宁波市", "CN-330200", "535.34"),
    ("温州市", "CN-330300", "884.27"), ("嘉兴市", "CN-330400", "414.43"),
    ("湖州市", "CN-330500", "345.94"), ("绍兴市", "CN-330600", "407.19"),
    ("金华市", "CN-330700", "541.78"), ("衢州市", "CN-330800", "170.15"),
    ("舟山市", "CN-330900", "89.39"), ("台州市", "CN-331000", "463.06"),
    ("丽水市", "CN-331100", "234.13"),
):
    SUPPLEMENTAL_CITY_FISCAL_SOURCES.append(
        _spec(
            file_name="zhejiang_2025_city_fiscal_rating_report_excerpt.txt",
            city_name=city_name, city_id=city_id,
            fields={"gov_fund_revenue_100m": (rf"{city_name}\|政府性基金收入\|({N})亿元", "亿元")},
            grade="B2", publisher="中证鹏元资信评估股份有限公司",
            document_title="2025年浙江省部分地级市经济财政指标情况",
            note="B2 精确表格按全市地级行政区列示政府性基金收入；不使用市本级、区县或预算安排数。",
            secondary=True,
        )
    )


__all__ = ["SUPPLEMENTAL_CITY_FISCAL_SOURCES"]
