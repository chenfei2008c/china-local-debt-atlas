"""可审计的区域经济财政批量表适配器（2022—2024）。

本批只接入报告中可以定位到表格行、且明确为全市/全州口径的值。
报告中的图表、估算值和市本级值不在这里录入；字段合并仍由主采集器
按字段和来源等级执行，避免低等级或同等级冲突值覆盖既有值。
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path
from typing import Any


SOURCE_GRADE = "B2"
GRADE_RANK = {"A1": 5, "A2": 4, "B1": 3, "B2": 2, "C": 1, "D": 0}


CITY_IDS = {
    # 甘肃
    "兰州市": "CN-620100", "嘉峪关市": "CN-620200", "金昌市": "CN-620300",
    "白银市": "CN-620400", "天水市": "CN-620500", "武威市": "CN-620600",
    "张掖市": "CN-620700", "平凉市": "CN-620800", "酒泉市": "CN-620900",
    "庆阳市": "CN-621000", "定西市": "CN-621100", "陇南市": "CN-621200",
    "临夏回族自治州": "CN-622900", "甘南藏族自治州": "CN-623000",
    # 青海
    "西宁市": "CN-630100", "海东市": "CN-630200",
    "海北藏族自治州": "CN-632200", "黄南藏族自治州": "CN-632300",
    "海南藏族自治州": "CN-632500", "果洛藏族自治州": "CN-632600",
    "玉树藏族自治州": "CN-632700", "海西蒙古族藏族自治州": "CN-632800",
    # 湖南
    "长沙市": "CN-430100", "株洲市": "CN-430200", "湘潭市": "CN-430300",
    "衡阳市": "CN-430400", "邵阳市": "CN-430500", "岳阳市": "CN-430600",
    "常德市": "CN-430700", "张家界市": "CN-430800", "益阳市": "CN-430900",
    "郴州市": "CN-431000", "永州市": "CN-431100", "娄底市": "CN-431300",
    "湘西土家族苗族自治州": "CN-433100",
    # 浙江
    "杭州市": "CN-330100", "宁波市": "CN-330200", "温州市": "CN-330300",
    "嘉兴市": "CN-330400", "湖州市": "CN-330500", "绍兴市": "CN-330600",
    "金华市": "CN-330700", "衢州市": "CN-330800", "舟山市": "CN-330900",
    "台州市": "CN-331000", "丽水市": "CN-331100",
    # 四川
    "成都市": "CN-510100", "泸州市": "CN-510500", "绵阳市": "CN-510700",
    "广元市": "CN-510800", "乐山市": "CN-511100", "眉山市": "CN-511400",
    "宜宾市": "CN-511500", "凉山彝族自治州": "CN-513400",
    # 吉林
    "长春市": "CN-220100", "吉林市": "CN-220200", "四平市": "CN-220300",
    "辽源市": "CN-220400", "通化市": "CN-220500", "白山市": "CN-220600",
    "松原市": "CN-220700", "白城市": "CN-220800", "延边朝鲜族自治州": "CN-222400",
    # 云南
    "昆明市": "CN-530100", "昭通市": "CN-530600", "丽江市": "CN-530700",
    "普洱市": "CN-530800", "临沧市": "CN-530900", "保山市": "CN-530500",
    "曲靖市": "CN-530300", "玉溪市": "CN-530400", "红河哈尼族彝族自治州": "CN-532500",
    "文山壮族苗族自治州": "CN-532600", "西双版纳傣族自治州": "CN-532800",
    "楚雄彝族自治州": "CN-532300", "大理白族自治州": "CN-532900",
    "德宏傣族景颇族自治州": "CN-533100", "怒江傈僳族自治州": "CN-533300",
    "迪庆藏族自治州": "CN-533400",
    # 广西
    "南宁市": "CN-450100", "柳州市": "CN-450200", "桂林市": "CN-450300",
    "梧州市": "CN-450400", "北海市": "CN-450500", "防城港市": "CN-450600",
    "钦州市": "CN-450700", "贵港市": "CN-450800", "玉林市": "CN-450900",
    "百色市": "CN-451000", "贺州市": "CN-451100", "河池市": "CN-451200",
    "来宾市": "CN-451300", "崇左市": "CN-451400",
    # 宁夏
    "银川市": "CN-640100", "石嘴山市": "CN-640200", "吴忠市": "CN-640300",
    "固原市": "CN-640400", "中卫市": "CN-640500",
    # 西藏
    "拉萨市": "CN-540100", "日喀则市": "CN-540200", "昌都市": "CN-540300",
    "林芝市": "CN-540400", "山南市": "CN-540500", "那曲市": "CN-540600",
    "阿里地区": "CN-542500",
    # 辽宁
    "沈阳市": "CN-210100", "大连市": "CN-210200", "鞍山市": "CN-210300",
    "抚顺市": "CN-210400", "本溪市": "CN-210500", "丹东市": "CN-210600",
    "锦州市": "CN-210700", "营口市": "CN-210800", "阜新市": "CN-210900",
    "辽阳市": "CN-211000", "盘锦市": "CN-211100", "铁岭市": "CN-211200",
    "朝阳市": "CN-211300", "葫芦岛市": "CN-211400",
    # 内蒙古
    "呼和浩特市": "CN-150100", "包头市": "CN-150200", "乌海市": "CN-150300",
    "赤峰市": "CN-150400", "通辽市": "CN-150500", "鄂尔多斯市": "CN-150600",
    "呼伦贝尔市": "CN-150700", "巴彦淖尔市": "CN-150800", "乌兰察布市": "CN-150900",
    "兴安盟": "CN-152200", "锡林郭勒盟": "CN-152500", "阿拉善盟": "CN-152900",
    # 安徽
    "合肥市": "CN-340100", "芜湖市": "CN-340200", "蚌埠市": "CN-340300",
    "淮南市": "CN-340400", "马鞍山市": "CN-340500", "淮北市": "CN-340600",
    "铜陵市": "CN-340700", "安庆市": "CN-340800", "黄山市": "CN-341000",
    "滁州市": "CN-341100", "阜阳市": "CN-341200", "宿州市": "CN-341300",
    "六安市": "CN-341500", "亳州市": "CN-341600", "池州市": "CN-341700",
    "宣城市": "CN-341800",
    # 河北
    "石家庄市": "CN-130100", "唐山市": "CN-130200", "秦皇岛市": "CN-130300",
    "邯郸市": "CN-130400", "邢台市": "CN-130500", "保定市": "CN-130600",
    "张家口市": "CN-130700", "承德市": "CN-130800", "沧州市": "CN-130900",
    "廊坊市": "CN-131000", "衡水市": "CN-131100",
    # 河南
    "郑州市": "CN-410100", "开封市": "CN-410200", "洛阳市": "CN-410300",
    "平顶山市": "CN-410400", "安阳市": "CN-410500", "鹤壁市": "CN-410600",
    "新乡市": "CN-410700", "焦作市": "CN-410800", "濮阳市": "CN-410900",
    "许昌市": "CN-411000", "漯河市": "CN-411100", "三门峡市": "CN-411200",
    "南阳市": "CN-411300", "商丘市": "CN-411400", "信阳市": "CN-411500",
    "周口市": "CN-411600", "驻马店市": "CN-411700", "济源市": "CN-419001",
    # 湖北（仅纳入主表中的地级市/自治州，省直管县级市不纳入）
    "武汉市": "CN-420100", "黄石市": "CN-420200", "十堰市": "CN-420300",
    "宜昌市": "CN-420500", "襄阳市": "CN-420600", "鄂州市": "CN-420700",
    "荆门市": "CN-420800", "孝感市": "CN-420900", "荆州市": "CN-421000",
    "黄冈市": "CN-421100", "咸宁市": "CN-421200", "随州市": "CN-421300",
    "恩施州": "CN-422800",
    # 江苏
    "南京市": "CN-320100", "无锡市": "CN-320200", "徐州市": "CN-320300",
    "常州市": "CN-320400", "苏州市": "CN-320500", "南通市": "CN-320600",
    "连云港市": "CN-320700", "淮安市": "CN-320800", "盐城市": "CN-320900",
    "扬州市": "CN-321000", "镇江市": "CN-321100", "泰州市": "CN-321200",
    "宿迁市": "CN-321300",
    # 陕西
    "西安市": "CN-610100", "铜川市": "CN-610200", "宝鸡市": "CN-610300",
    "咸阳市": "CN-610400", "渭南市": "CN-610500", "延安市": "CN-610600",
    "汉中市": "CN-610700", "榆林市": "CN-610800", "安康市": "CN-610900",
    "商洛市": "CN-611000",
    # 贵州
    "贵阳市": "CN-520100", "六盘水市": "CN-520200", "遵义市": "CN-520300",
    "安顺市": "CN-520400", "毕节市": "CN-520500", "铜仁市": "CN-520600",
    "黔西南州": "CN-522300", "黔东南州": "CN-522600", "黔南州": "CN-522700",
}


SOURCE_SPECS = {
    "SRC-B2-GANSU-REGIONAL-FISCAL-2023": {
        "year": 2023,
        "path": "raw/province_fiscal/2023/secondary/gansu_2023_city_fiscal_rating_report.pdf",
        "text_path": "raw/province_fiscal/2023/secondary/gansu_2023_city_fiscal_rating_report_excerpt.txt",
        "url": "https://www.lhratings.com/file/fbb751f0dd1.pdf",
        "title": "地方政府与城投企业债务风险研究报告——甘肃篇（2024）",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2024-10-29",
        "page_number": "PDF第10页表6、第12页表7",
        "note": "B2精确表格；表6为2023年GDP、增速、常住人口，表7为2022—2023年政府性基金收入；资料来源为各地级市（州）财政决算报告和预算执行情况报告，均为全市/全州口径。",
    },
    "SRC-B2-GANSU-REGIONAL-FISCAL-2024": {
        "year": 2024,
        "path": "raw/province_fiscal/2024/secondary/gansu_2024_city_fiscal_rating_report.pdf",
        "text_path": "raw/province_fiscal/2024/secondary/gansu_2024_city_fiscal_rating_report_excerpt.txt",
        "url": "https://www.lhratings.com/file/ffdccf82874.pdf",
        "title": "地方政府与城投企业债务风险研究报告——甘肃篇（2025）",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2025-09-23",
        "page_number": "PDF第11页表2.2、第13页表2.3",
        "note": "B2精确表格；表2.2为2024年GDP、增速、常住人口，表2.3为2023—2024年政府性基金收入；资料来源为各地级市（州）财政决算报告和预算执行情况报告，均为全市/全州口径。",
    },
    "SRC-B2-QINGHAI-REGIONAL-FISCAL-2023": {
        "year": 2023,
        "path": "raw/province_fiscal/2023/secondary/qinghai_2023_city_fiscal_rating_report.pdf",
        "text_path": "raw/province_fiscal/2023/secondary/qinghai_2023_city_fiscal_rating_report_excerpt.txt",
        "url": "https://www.lhratings.com/file/fc16ef34547.pdf",
        "title": "地方政府与城投企业债务风险研究报告——青海篇（2024）",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2024-11-26",
        "page_number": "PDF第12页表2.2、第13页表2.3",
        "note": "B2精确表格；表2.2为2023年GDP、增速、常住人口，表2.3为2022—2023年政府性基金收入；资料来源为各州市财政决算报告和预算执行情况报告，均为全市/全州口径。",
    },
    "SRC-B2-QINGHAI-REGIONAL-FISCAL-2024": {
        "year": 2024,
        "path": "raw/province_fiscal/2024/secondary/qinghai_2024_city_fiscal_rating_report.pdf",
        "text_path": "raw/province_fiscal/2024/secondary/qinghai_2024_city_fiscal_rating_report_excerpt.txt",
        "url": "https://www.lhratings.com/file/ffef419b0cc.pdf",
        "title": "地方政府与城投企业债务风险研究报告——青海篇（2025）",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2025-09-26",
        "page_number": "PDF第11页表2.2、第13页表2.3",
        "note": "B2精确表格；表2.2为2024年GDP、增速、常住人口，表2.3为2023—2024年政府性基金收入；资料来源为各州市财政决算报告和预算执行情况报告，均为全市/全州口径。",
    },
    "SRC-B2-HUNAN-REGIONAL-FISCAL-2022": {
        "year": 2022,
        "path": "raw/province_fiscal/2022/secondary/hunan_2022_city_fiscal_rating_report.pdf",
        "text_path": "raw/province_fiscal/2022/secondary/hunan_2022_city_fiscal_rating_report_excerpt.txt",
        "url": "https://pdf.dfcfw.com/pdf/H3_AP202304251585806338_1.pdf?1682443639000.pdf=",
        "title": "区域信用面面观·湖南篇",
        "publisher": "华福证券研究所",
        "publication_date": "2023-04-25",
        "page_number": "PDF第14页，湖南省各地市（州）财政情况表",
        "note": "B2精确表格；只录入原表明确为全市/全州口径且可定位的行；怀化市市本级数据排除；株洲、湘潭、永州、张家界的基金值按原表明确说明回填为2021年值。",
    },
    "SRC-B2-ZHEJIANG-REGIONAL-FISCAL-2023": {
        "year": 2023,
        "path": "raw/province_fiscal/2023/secondary/zhejiang_2023_city_fiscal_rating_report.pdf",
        "text_path": "raw/province_fiscal/2023/secondary/zhejiang_2023_city_fiscal_rating_report_excerpt.txt",
        "url": "https://pdf.dfcfw.com/pdf/H3_AP202506051685194913_1.pdf?1749129621000.pdf=",
        "title": "区域研究专题：浙江省区域经济与信用观察",
        "publisher": "远东资信评估有限公司",
        "publication_date": "2025-06-05",
        "page_number": "PDF第7页表1",
        "note": "B2精确表格；表1列示2023年浙江省11个地市GDP、一般公共预算收入和政府性基金收入，Wind数据由远东资信整理，采用全市口径。",
    },
    "SRC-B2-SICHUAN-REGIONAL-FISCAL-2023": {
        "year": 2023,
        "path": "raw/province_fiscal/2023/secondary/sichuan_2023_city_fiscal_rating_report.pdf",
        "text_path": "raw/province_fiscal/2023/secondary/sichuan_2023_city_fiscal_rating_report_excerpt.txt",
        "url": "https://static.cninfo.com.cn/finalpage/2024-07-30/1220753311.pdf",
        "title": "四川省部分地级市/自治州经济财政指标情况",
        "publisher": "中证鹏元资信评估股份有限公司",
        "publication_date": "2024-07-30",
        "page_number": "PDF第9页表2",
        "note": "B2精确表格；表2明确列示部分地级市/自治州GDP、增速、一般公共预算收入和政府性基金收入，未披露值保持空白，不做推算。",
    },
    "SRC-B2-JILIN-REGIONAL-FISCAL-2024": {
        "year": 2024,
        "path": "raw/province_fiscal/2024/secondary/jilin_2024_city_fiscal_rating_report.pdf",
        "text_path": "raw/province_fiscal/2024/secondary/jilin_2024_city_fiscal_rating_report_excerpt.txt",
        "url": "https://www.lhratings.com/file/ffef41a3e31.pdf",
        "title": "地方政府与城投企业债务风险研究报告——吉林篇（2025）",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2025-09-26",
        "page_number": "PDF第11页表6、第13页表7",
        "note": "B2精确表格；表6为2024年GDP、增速、年末常住人口，表7为2023—2024年政府性基金收入；资料来源为各地市（州）统计公报、财政决算报告和预算执行情况报告，均为全市/全州口径。",
    },
    "SRC-B2-YUNNAN-REGIONAL-FISCAL-2023": {
        "year": 2023,
        "path": "raw/province_fiscal/2023/secondary/yunnan_2023_city_fiscal_rating_report.pdf",
        "text_path": "raw/province_fiscal/2023/secondary/yunnan_2023_city_fiscal_rating_report_excerpt.txt",
        "url": "https://www.lhratings.com/file/fb599cb3fc1.pdf",
        "title": "地方政府与城投企业债务风险研究报告——云南篇（2024）",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2024-11-26",
        "page_number": "PDF第10页表6、第12页表7",
        "note": "B2精确表格；表6为2023年GDP、增速、常住人口，表7为2022—2023年政府性基金收入；玉溪、丽江人口按原报告注释排除户籍口径，怒江人口因未获取保持空白。",
    },
    "SRC-B2-GUANGXI-REGIONAL-MACRO-2024": {
        "year": 2024,
        "path": "raw/province_fiscal/2024/secondary/guangxi_2024_city_fiscal_rating_report.pdf",
        "text_path": "raw/province_fiscal/2024/secondary/guangxi_2024_city_macro_rating_report_excerpt.txt",
        "url": "https://www.lhratings.com/file/g09ce7eb6da.pdf",
        "title": "地方政府与城投企业债务风险研究报告——广西篇（2025）",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2025-09-26",
        "page_number": "PDF第8页表6",
        "note": "B2精确表格；表6为2024年广西各地级市GDP、GDP增速和常住人口，资料来源为各地市统计公报，均为全市口径；不使用报告图表中的财政估读值。",
    },
    "SRC-B2-NINGXIA-REGIONAL-MACRO-2024": {
        "year": 2024,
        "path": "raw/province_fiscal/2024/secondary/ningxia_2024_city_fiscal_rating_report.pdf",
        "text_path": "raw/province_fiscal/2024/secondary/ningxia_2024_city_fiscal_rating_report_excerpt.txt",
        "url": "https://www.lhratings.com/file/g060864156f.pdf",
        "title": "地方政府与城投企业债务风险研究报告——宁夏篇（2025）",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2025-09-26",
        "page_number": "PDF第8页表6",
        "note": "B2精确表格；表6为2024年宁夏各地级市GDP、GDP增速和常住人口，资料来源为各市统计公报，均为全市口径；不使用报告图表中的财政估读值。",
    },
    "SRC-B2-TIBET-REGIONAL-MACRO-2024": {
        "year": 2024,
        "path": "raw/province_fiscal/2024/secondary/tibet_2024_city_fiscal_rating_report.pdf",
        "text_path": "raw/province_fiscal/2024/secondary/tibet_2024_city_fiscal_rating_report_excerpt.txt",
        "url": "https://www.lhratings.com/file/g04c6e70a5a.pdf",
        "title": "地方政府与城投企业债务风险研究报告——西藏自治区篇（2025）",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2025-09-26",
        "page_number": "PDF第8页表6",
        "note": "B2精确表格；表6为2024年西藏各地级市（区）GDP及增速，人口缺失值不回填；资料来源为各地统计公报，均为全市/全地区口径。",
    },
    "SRC-B2-LIAONING-REGIONAL-MACRO-2023": {
        "year": 2023,
        "path": "raw/province_fiscal/2023/secondary/liaoning_2023_city_macro_rating_report.pdf",
        "text_path": "raw/province_fiscal/2023/secondary/liaoning_2023_city_macro_rating_report_excerpt.txt",
        "url": "https://www.lhratings.com/file/fb599cb3b63.pdf",
        "title": "地方政府与城投企业债务风险研究报告——辽宁篇",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2024-11-26",
        "page_number": "PDF第8页表6",
        "note": "B2精确表格；表6为2023年辽宁省各地级市GDP、GDP增速和常住人口，常住人口缺失行保持空白；资料来源为各地统计公报，均为全市口径。",
    },
    "SRC-B2-INNER-MONGOLIA-REGIONAL-MACRO-2024": {
        "year": 2024,
        "path": "raw/province_fiscal/2024/secondary/inner_mongolia_2024_city_macro_rating_report.pdf",
        "text_path": "raw/province_fiscal/2024/secondary/inner_mongolia_2024_city_macro_rating_report_excerpt.txt",
        "url": "https://www.lhratings.com/file/ffef41a4110.pdf",
        "title": "地方政府与城投企业债务风险研究报告——内蒙古篇",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2025-09-26",
        "page_number": "PDF第12页表2.3",
        "note": "B2精确表格；表2.3为2024年内蒙古各地级市、盟GDP、GDP增速和常住人口，均为全市/全盟口径；不使用报告图表中的财政估读值。",
    },
    "SRC-B2-ANHUI-REGIONAL-MACRO-2024": {
        "year": 2024,
        "path": "raw/province_fiscal/2024/secondary/anhui_2024_city_macro_rating_report.pdf",
        "text_path": "raw/province_fiscal/2024/secondary/anhui_2024_city_macro_rating_report_excerpt.txt",
        "url": "https://www.lhratings.com/file/g060864362f.pdf",
        "title": "地方政府与城投企业债务风险研究报告——安徽篇（2025）",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2025-09-26",
        "page_number": "PDF第10页表6",
        "note": "B2精确表格；表6为2024年安徽省各地级市GDP、GDP增速和常住人口，均为全市口径；宣城市人口表格值与其他来源存在明显异常，按保守原则不录入该人口值；不使用报告图表中的财政估读值。",
    },
    "SRC-B2-HEBEI-REGIONAL-MACRO-2024": {
        "year": 2024,
        "path": "raw/province_fiscal/2025/secondary/hebei_2025_city_macro_rating_report.pdf",
        "text_path": "raw/province_fiscal/2025/secondary/hebei_2025_city_macro_rating_report_excerpt.txt",
        "url": "https://www.lhratings.com/file/g0b9dd75e66.pdf",
        "title": "地方政府与城投企业债务风险研究报告——河北篇（2025）",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2025-09-23",
        "page_number": "PDF第10页表4",
        "note": "B2精确表格；表4为2024年河北省各地级市GDP、GDP增速和年末常住人口，均为全市口径；不使用报告图表中的财政估读值。",
    },
    "SRC-B2-HENAN-REGIONAL-MACRO-2024": {
        "year": 2024,
        "path": "raw/province_fiscal/2025/secondary/henan_2025_city_macro_rating_report.pdf",
        "text_path": "raw/province_fiscal/2025/secondary/henan_2025_city_macro_rating_report_excerpt.txt",
        "url": "https://www.lhratings.com/file/g04c6e72d88.pdf",
        "title": "地方政府与城投企业债务风险研究报告——河南篇（2025）",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2025-09-23",
        "page_number": "PDF第12—13页表2.2",
        "note": "B2精确表格；表2.2为2024年河南省各地级市GDP、GDP增速和年末常住人口，均为全市口径；不使用报告图表中的财政估读值。",
    },
    "SRC-B2-HUBEI-REGIONAL-MACRO-2024": {
        "year": 2024,
        "path": "raw/province_fiscal/2025/secondary/hubei_2025_city_macro_rating_report.pdf",
        "text_path": "raw/province_fiscal/2025/secondary/hubei_2025_city_macro_rating_report_excerpt.txt",
        "url": "https://www.lhratings.com/file/g09ce7e13aa.pdf",
        "title": "地方政府与城投企业债务风险研究报告——湖北篇（2025）",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2025-09-23",
        "page_number": "PDF第13页表4",
        "note": "B2精确表格；表4为2024年湖北省各地级市（州）GDP、GDP增速和年末常住人口，均为全市/全州口径；省直管县级市不纳入本地级行政单元主表。",
    },
    "SRC-B2-JIANGSU-REGIONAL-MACRO-2024": {
        "year": 2024,
        "path": "raw/province_fiscal/2025/secondary/jiangsu_2025_city_macro_rating_report.pdf",
        "text_path": "raw/province_fiscal/2025/secondary/jiangsu_2025_city_macro_rating_report_excerpt.txt",
        "url": "https://www.lhratings.com/file/g0fa6dcf4bf.pdf",
        "title": "地方政府与城投企业债务风险研究报告——江苏篇（2025）",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2025-09-23",
        "page_number": "PDF第11页表6",
        "note": "B2精确表格；表6为2024年江苏省各地级市GDP、GDP增速和年末常住人口，均为全市口径；不使用报告图表中的财政估读值。",
    },
    "SRC-B2-SHAANXI-REGIONAL-MACRO-2024": {
        "year": 2024,
        "path": "raw/province_fiscal/2025/secondary/shaanxi_2025_city_macro_rating_report.pdf",
        "text_path": "raw/province_fiscal/2025/secondary/shaanxi_2025_city_macro_rating_report_excerpt.txt",
        "url": "https://www.lhratings.com/file/g074225471a.pdf",
        "title": "地方政府与城投企业债务风险研究报告——陕西篇（2025）",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2025-09-23",
        "page_number": "PDF第12页表5",
        "note": "B2精确表格；表5为2024年陕西省各地级市GDP、GDP增速和年末常住人口；带星号单元格为报告注明的2023年旧值，本批不录入；其余值按全市口径接入。",
    },
    "SRC-B2-GUIZHOU-REGIONAL-MACRO-2024": {
        "year": 2024,
        "path": "raw/province_fiscal/2025/secondary/guizhou_2025_city_macro_rating_report.pdf",
        "text_path": "raw/province_fiscal/2025/secondary/guizhou_2025_city_macro_rating_report_excerpt.txt",
        "url": "https://www.lhratings.com/file/g0a76d7b4fc.pdf",
        "title": "地方政府与城投企业债务风险研究报告——贵州篇（2025）",
        "publisher": "联合资信评估股份有限公司",
        "publication_date": "2025-09-23",
        "page_number": "PDF第9页表5",
        "note": "B2精确表格；表5为2024年贵州省各地级市（州）GDP、GDP增速和年末常住人口，均为全市/全州口径；不使用报告图表中的财政估读值。",
    },
}


def _r(source_doc_id: str, city_name: str, year: int, **fields: str) -> dict[str, Any]:
    row: dict[str, Any] = {
        "source_doc_id": source_doc_id,
        "city_name": city_name,
        "city_id": CITY_IDS[city_name],
        "year": year,
    }
    row.update({key: Decimal(value) for key, value in fields.items() if value not in {"", "-", "—"}})
    return row


ROWS: list[dict[str, Any]] = []


_GANSU_IDS = [
    "兰州市", "庆阳市", "酒泉市", "临夏回族自治州", "陇南市", "天水市", "白银市",
    "平凉市", "武威市", "定西市", "张掖市", "甘南藏族自治州", "金昌市", "嘉峪关市",
]
_GANSU_2023_MACRO = [
    ("3487.30", "4.40", "442.51"), ("1100.37", "8.50", "213.25"), ("908.68", "8.90", "104.27"),
    ("439.70", "6.50", "210.11"), ("602.70", "6.60", "234.22"), ("856.78", "5.40", "290.72"),
    ("672.30", "7.00", "148.81"), ("668.57", "5.60", "178.58"), ("708.08", "7.00", "142.73"),
    ("600.10", "6.60", "248.24"), ("608.01", "5.50", "110.46"), ("260.81", "6.00", "66.87"),
    ("567.73", "11.50", "43.20"), ("382.79", "8.70", "31.50"),
]
_GANSU_2022_FUND = ["80.79", "18.10", "21.96", "16.55", "12.64", "31.54", "7.98", "12.62", "9.98", "16.62", "5.59", "3.04", "3.46", "3.21"]
_GANSU_2023_FUND = ["64.57", "22.83", "18.24", "17.82", "16.64", "15.66", "14.48", "14.27", "12.50", "10.69", "9.41", "5.74", "4.45", "3.45"]
for city, (gdp, growth, pop), fund_2022, fund_2023 in zip(_GANSU_IDS, _GANSU_2023_MACRO, _GANSU_2022_FUND, _GANSU_2023_FUND):
    ROWS.append(_r("SRC-B2-GANSU-REGIONAL-FISCAL-2023", city, 2023, gdp_current_100m=gdp, gdp_real_growth_pct=growth, resident_population_10k=pop, gov_fund_revenue_100m=fund_2023))
    ROWS.append(_r("SRC-B2-GANSU-REGIONAL-FISCAL-2023", city, 2022, gov_fund_revenue_100m=fund_2022))

_GANSU_2024_MACRO = [
    ("3742.30", "5.00", "443.65"), ("1213.22", "5.10", "212.54"), ("1041.70", "7.70", "104.09"),
    ("506.00", "6.60", "209.93"), ("666.70", "5.50", "232.96"), ("952.25", "6.10", "289.18"),
    ("742.87", "5.50", "148.01"), ("722.77", "5.40", "177.27"), ("750.02", "5.90", "142.21"),
    ("737.11", "6.80", "247.40"), ("680.88", "5.30", "109.99"), ("256.33", "3.80", "74.84"),
    ("620.06", "13.60", "43.05"), ("370.70", "8.20", "31.51"),
]
_GANSU_2024_FUND = ["130.41", "13.57", "15.80", "13.21", "14.19", "12.93", "9.64", "10.00", "8.70", "8.80", "6.08", "8.62", "5.00", "3.57"]
for city, (gdp, growth, pop), fund in zip(_GANSU_IDS, _GANSU_2024_MACRO, _GANSU_2024_FUND):
    ROWS.append(_r("SRC-B2-GANSU-REGIONAL-FISCAL-2024", city, 2024, gdp_current_100m=gdp, gdp_real_growth_pct=growth, resident_population_10k=pop, gov_fund_revenue_100m=fund))


_QINGHAI_IDS = ["西宁市", "海西蒙古族藏族自治州", "海东市", "海南藏族自治州", "黄南藏族自治州", "海北藏族自治州", "玉树藏族自治州", "果洛藏族自治州"]
_QINGHAI_2023_MACRO = [("1801.13", "8.60", "248.10"), ("828.19", "0.00", "47.10"), ("580.13", "2.50", "133.80"), ("212.49", "4.00", "45.00"), ("113.47", "2.20", "28.20"), ("105.16", "3.90", "26.20"), ("79.13", "6.90", "43.40"), ("67.20", "3.80", "22.20")]
_QINGHAI_2022_FUND = ["54.24", "3.31", "11.97", "2.71", "1.77", "2.25", "0.19", "0.12"]
_QINGHAI_2023_FUND = ["32.08", "3.00", "13.94", "2.57", "0.36", "0.57", "0.25", "0.15"]
for city, (gdp, growth, pop), fund_2022, fund_2023 in zip(_QINGHAI_IDS, _QINGHAI_2023_MACRO, _QINGHAI_2022_FUND, _QINGHAI_2023_FUND):
    ROWS.append(_r("SRC-B2-QINGHAI-REGIONAL-FISCAL-2023", city, 2023, gdp_current_100m=gdp, gdp_real_growth_pct=growth, resident_population_10k=pop, gov_fund_revenue_100m=fund_2023))
    ROWS.append(_r("SRC-B2-QINGHAI-REGIONAL-FISCAL-2023", city, 2022, gov_fund_revenue_100m=fund_2022))

_QINGHAI_2024_MACRO = [("1862.09", "3.10", "247.69"), ("847.88", "1.10", "47.31"), ("605.46", "4.10", "132.86"), ("234.65", "5.90", "45.11"), ("123.04", "4.50", "28.22"), ("115.87", "5.10", "26.10"), ("92.42", "4.40", "43.43"), ("69.38", "0.10", "22.28")]
_QINGHAI_2024_FUND = ["22.87", "5.75", "8.99", "2.99", "0.25", "0.79", "0.25", "0.20"]
for city, (gdp, growth, pop), fund in zip(_QINGHAI_IDS, _QINGHAI_2024_MACRO, _QINGHAI_2024_FUND):
    ROWS.append(_r("SRC-B2-QINGHAI-REGIONAL-FISCAL-2024", city, 2024, gdp_current_100m=gdp, gdp_real_growth_pct=growth, resident_population_10k=pop, gov_fund_revenue_100m=fund))


for city, revenue, expenditure, fund in [
    ("长沙市", "1202.0", "1566.3", "1065.3"), ("岳阳市", "185.0", "570.5", "196.0"),
    ("常德市", "209.6", "637.5", "319.2"), ("衡阳市", "191.1", "633.3", "221.5"),
    ("郴州市", "178.0", "496.9", "159.6"), ("邵阳市", "128.0", "637.3", "153.5"),
    ("益阳市", "100.1", "400.8", "83.7"), ("娄底市", "91.7", "358.7", "61.6"),
    ("湘西土家族苗族自治州", "74.6", "353.3", "35.7"),
]:
    ROWS.append(_r("SRC-B2-HUNAN-REGIONAL-FISCAL-2022", city, 2022, general_public_revenue_100m=revenue, general_public_expenditure_100m=expenditure, gov_fund_revenue_100m=fund))
for city, fund in [("株洲市", "339.3"), ("湘潭市", "199.8"), ("永州市", "241.2"), ("张家界市", "73.4")]:
    ROWS.append(_r("SRC-B2-HUNAN-REGIONAL-FISCAL-2022", city, 2021, gov_fund_revenue_100m=fund))


for city, gdp, revenue, fund in [
    ("绍兴市", "7791.14", "578.75", "445.07"), ("湖州市", "4015.10", "410.50", "546.64"),
    ("嘉兴市", "7062.45", "632.02", "578.19"), ("舟山市", "2101.00", "193.51", "89.74"),
    ("台州市", "6241.00", "494.28", "626.06"), ("宁波市", "16453.00", "1785.86", "902.21"),
    ("金华市", "6011.27", "525.80", "859.98"), ("衢州市", "2125.20", "204.21", "303.71"),
    ("杭州市", "20059.00", "2616.81", "2233.40"), ("温州市", "8731.00", "622.68", "1310.70"),
    ("丽水市", "1964.40", "186.06", "405.59"),
]:
    ROWS.append(_r("SRC-B2-ZHEJIANG-REGIONAL-FISCAL-2023", city, 2023, gdp_current_100m=gdp, general_public_revenue_100m=revenue, gov_fund_revenue_100m=fund))


for city, gdp, growth, revenue, fund in [
    ("成都市", "22074.70", "6.00", "1929.30", "1886.60"), ("绵阳市", "4038.73", "8.00", "201.47", ""),
    ("宜宾市", "3806.64", "7.50", "313.99", "199.39"), ("泸州市", "2725.90", "5.60", "208.00", "165.00"),
    ("乐山市", "2447.50", "6.50", "159.14", "135.75"), ("凉山彝族自治州", "2261.11", "7.00", "204.80", ""),
    ("眉山市", "1737.00", "6.20", "159.84", "243.64"), ("广元市", "1179.82", "6.20", "68.12", ""),
]:
    ROWS.append(_r("SRC-B2-SICHUAN-REGIONAL-FISCAL-2023", city, 2023, gdp_current_100m=gdp, gdp_real_growth_pct=growth, general_public_revenue_100m=revenue, gov_fund_revenue_100m=fund))


for city, gdp, growth, pop in [
    ("长春市", "7632.19", "4.80", "908.51"), ("吉林市", "1633.20", "5.00", "349.48"),
    ("延边朝鲜族自治州", "1018.10", "4.40", "188.62"), ("松原市", "1002.18", "3.80", "209.00"),
    ("白城市", "614.24", "4.90", "145.06"), ("四平市", "580.60", "3.70", "163.93"),
    ("通化市", "576.79", "3.90", "116.97"), ("白山市", "567.85", "3.40", "88.88"),
    ("辽源市", "527.69", "4.50", "91.64"),
]:
    ROWS.append(_r("SRC-B2-JILIN-REGIONAL-FISCAL-2024", city, 2024, gdp_current_100m=gdp, gdp_real_growth_pct=growth, resident_population_10k=pop))
for city, fund_2023, fund_2024 in [
    ("长春市", "423.00", "332.65"), ("吉林市", "25.70", ""),
    ("延边朝鲜族自治州", "19.97", "20.36"), ("松原市", "13.10", "6.51"),
    ("通化市", "8.99", "9.20"), ("辽源市", "15.89", "15.63"),
    ("白城市", "1.17", "9.06"), ("白山市", "4.30", "5.64"),
]:
    ROWS.append(_r("SRC-B2-JILIN-REGIONAL-FISCAL-2024", city, 2023, gov_fund_revenue_100m=fund_2023))
    ROWS.append(_r("SRC-B2-JILIN-REGIONAL-FISCAL-2024", city, 2024, gov_fund_revenue_100m=fund_2024))


_YUNNAN_IDS = [
    "昆明市", "曲靖市", "红河哈尼族彝族自治州", "玉溪市", "楚雄彝族自治州", "大理白族自治州",
    "昭通市", "文山壮族苗族自治州", "保山市", "普洱市", "临沧市", "西双版纳傣族自治州",
    "丽江市", "德宏傣族景颇族自治州", "迪庆藏族自治州", "怒江傈僳族自治州",
]
_YUNNAN_2023_MACRO = [
    ("7864.76", "3.30", "868.00"), ("4048.91", "7.50", "568.80"), ("2889.42", "3.20", "436.30"),
    ("2564.80", "3.50", ""), ("1827.04", "5.50", "234.20"), ("1731.10", "2.00", "334.20"),
    ("1644.12", "7.70", "485.40"), ("1462.32", "5.10", "339.70"), ("1254.20", "1.40", "240.70"),
    ("1090.91", "3.60", "234.00"), ("1050.23", "3.80", "220.20"), ("778.27", "5.00", "133.30"),
    ("671.73", "7.50", ""), ("595.28", "2.10", "133.70"), ("303.74", "0.60", "39.50"),
    ("262.09", "6.20", ""),
]
_YUNNAN_2022_FUND = ["146.10", "57.12", "45.64", "62.43", "42.38", "15.79", "34.64", "27.81", "30.30", "21.02", "21.42", "15.27", "14.69", "19.97", "4.88", "4.37"]
_YUNNAN_2023_FUND = ["157.94", "52.68", "49.86", "38.73", "35.78", "20.73", "41.69", "39.17", "38.15", "24.72", "24.05", "24.23", "14.35", "17.98", "3.23", "4.96"]
for city, (gdp, growth, pop), fund_2022, fund_2023 in zip(_YUNNAN_IDS, _YUNNAN_2023_MACRO, _YUNNAN_2022_FUND, _YUNNAN_2023_FUND):
    macro = {"gdp_current_100m": gdp, "gdp_real_growth_pct": growth}
    if pop:
        macro["resident_population_10k"] = pop
    ROWS.append(_r("SRC-B2-YUNNAN-REGIONAL-FISCAL-2023", city, 2023, **macro, gov_fund_revenue_100m=fund_2023))
    ROWS.append(_r("SRC-B2-YUNNAN-REGIONAL-FISCAL-2023", city, 2022, gov_fund_revenue_100m=fund_2022))


for city, gdp, growth, pop in [
    ("南宁市", "5995.36", "3.00", "897.19"), ("柳州市", "2950.67", "1.50", "414.60"),
    ("桂林市", "2517.39", "3.10", "493.84"), ("玉林市", "2346.78", "4.30", "580.42"),
    ("百色市", "2004.73", "4.70", "346.47"), ("北海市", "1888.04", "5.40", "190.17"),
    ("钦州市", "1878.96", "5.20", "333.23"), ("梧州市", "1622.49", "7.20", "282.77"),
    ("贵港市", "1565.59", "4.30", "429.41"), ("河池市", "1404.15", "5.30", "331.35"),
    ("崇左市", "1312.86", "6.00", "204.61"), ("防城港市", "1167.55", "7.50", "107.98"),
    ("来宾市", "1030.42", "5.10", "202.03"), ("贺州市", "964.42", "5.20", "198.92"),
]:
    ROWS.append(_r("SRC-B2-GUANGXI-REGIONAL-MACRO-2024", city, 2024, gdp_current_100m=gdp, gdp_real_growth_pct=growth, resident_population_10k=pop))


for city, gdp, growth, pop in [
    ("银川市", "2939.53", "5.40", "291.47"), ("吴忠市", "933.72", "6.10", "141.53"),
    ("中卫市", "600.25", "5.80", "107.98"), ("石嘴山市", "565.53", "3.20", "73.94"),
    ("固原市", "463.73", "6.10", "114.08"),
]:
    ROWS.append(_r("SRC-B2-NINGXIA-REGIONAL-MACRO-2024", city, 2024, gdp_current_100m=gdp, gdp_real_growth_pct=growth, resident_population_10k=pop))


for city, gdp, growth, pop in [
    ("拉萨市", "990.04", "6.70", "87.64"), ("日喀则市", "464.30", "6.40", "81.45"),
    ("昌都市", "386.01", "6.40", ""), ("山南市", "304.42", "5.80", "35.75"),
    ("林芝市", "267.78", "6.30", ""), ("那曲市", "246.34", "6.10", "51.43"),
    ("阿里地区", "105.85", "", ""),
]:
    macro = {"gdp_current_100m": gdp}
    if growth:
        macro["gdp_real_growth_pct"] = growth
    if pop:
        macro["resident_population_10k"] = pop
    ROWS.append(_r("SRC-B2-TIBET-REGIONAL-MACRO-2024", city, 2024, **macro))


for city, gdp, growth, pop in [
    ("大连市", "8752.90", "6.00", "753.90"), ("沈阳市", "8122.10", "6.10", "920.40"),
    ("鞍山市", "2011.90", "5.70", ""), ("营口市", "1479.40", "5.30", "226.60"),
    ("盘锦市", "1382.10", "1.70", ""), ("锦州市", "1253.40", "5.40", "263.10"),
    ("朝阳市", "1043.70", "5.30", "278.80"), ("本溪市", "971.00", "5.80", ""),
    ("抚顺市", "949.30", "4.40", "174.80"), ("丹东市", "945.20", "6.10", "209.20"),
    ("葫芦岛市", "911.60", "6.00", "233.70"), ("辽阳市", "878.40", "1.60", "153.20"),
    ("铁岭市", "764.60", "5.40", "226.40"), ("阜新市", "602.00", "4.60", ""),
]:
    macro = {"gdp_current_100m": gdp, "gdp_real_growth_pct": growth}
    if pop:
        macro["resident_population_10k"] = pop
    ROWS.append(_r("SRC-B2-LIAONING-REGIONAL-MACRO-2023", city, 2023, **macro))


for city, gdp, growth, pop in [
    ("鄂尔多斯市", "6363.00", "6.40", "224.10"), ("包头市", "4575.10", "8.10", "277.20"),
    ("呼和浩特市", "4107.10", "6.10", "363.90"), ("赤峰市", "2322.10", "4.40", "393.10"),
    ("呼伦贝尔市", "1730.70", "3.50", "213.90"), ("通辽市", "1686.20", "4.00", "277.70"),
    ("巴彦淖尔市", "1242.30", "5.70", "148.90"), ("锡林郭勒盟", "1236.00", "4.60", "111.30"),
    ("乌兰察布市", "1214.20", "5.40", "158.10"), ("兴安盟", "807.70", "4.40", "137.20"),
    ("乌海市", "595.60", "4.10", "55.70"), ("阿拉善盟", "413.60", "6.00", "26.90"),
]:
    ROWS.append(_r("SRC-B2-INNER-MONGOLIA-REGIONAL-MACRO-2024", city, 2024, gdp_current_100m=gdp, gdp_real_growth_pct=growth, resident_population_10k=pop))


for city, gdp, growth, pop in [
    ("合肥市", "13507.70", "6.10", "1000.20"), ("芜湖市", "5120.50", "6.40", "379.70"),
    ("滁州市", "4034.40", "5.50", "405.60"), ("阜阳市", "3609.80", "5.50", "804.10"),
    ("安庆市", "3156.00", "6.00", "409.80"), ("马鞍山市", "2784.60", "6.00", "220.10"),
    ("宿州市", "2457.30", "5.10", "522.50"), ("亳州市", "2521.60", "6.10", "486.10"),
    ("蚌埠市", "2313.00", "5.20", "326.20"), ("六安市", "2307.50", "5.40", "430.40"),
    ("淮南市", "1716.00", "5.00", "301.90"), ("淮北市", "1405.90", "4.00", "193.20"),
    ("铜陵市", "1325.50", "6.40", "130.20"), ("池州市", "1177.80", "6.30", "132.40"),
    ("黄山市", "1134.00", "5.90", "131.70"), ("宣城市", "2053.50", "5.80", ""),
]:
    macro = {"gdp_current_100m": gdp, "gdp_real_growth_pct": growth}
    if pop:
        macro["resident_population_10k"] = pop
    ROWS.append(_r("SRC-B2-ANHUI-REGIONAL-MACRO-2024", city, 2024, **macro))


for city, gdp, growth, pop in [
    ("唐山市", "10003.9", "5.6", "772.28"), ("石家庄市", "8203.4", "5.5", "1124.66"),
    ("沧州市", "4722.8", "5.5", "722.77"), ("邯郸市", "4704.3", "6.1", "918.21"),
    ("保定市", "4773.3", "5.9", "904.62"), ("廊坊市", "3904.6", "5.8", "546.90"),
    ("邢台市", "2765.9", "4.5", "687.78"), ("秦皇岛市", "2128.6", "5.5", "311.14"),
    ("衡水市", "1971.8", "5.4", "412.99"), ("承德市", "1962.6", "5.9", "328.57"),
    ("张家口市", "1913.3", "4.6", "403.26"),
]:
    ROWS.append(_r("SRC-B2-HEBEI-REGIONAL-MACRO-2024", city, 2024, gdp_current_100m=gdp, gdp_real_growth_pct=growth, resident_population_10k=pop))

for city, gdp, growth, pop in [
    ("郑州市", "14532.10", "5.70", "1308.60"), ("洛阳市", "5818.60", "4.90", "708.10"),
    ("南阳市", "4879.08", "5.50", "945.40"), ("周口市", "3635.62", "6.50", "863.10"),
    ("新乡市", "3569.70", "4.90", "611.30"), ("许昌市", "3441.10", "6.00", "435.70"),
    ("驻马店市", "3342.70", "6.10", "671.10"), ("商丘市", "3272.27", "4.10", "762.80"),
    ("信阳市", "3073.36", "5.20", "600.20"), ("平顶山市", "2831.97", "4.00", "487.60"),
    ("开封市", "2761.10", "5.50", "469.80"), ("安阳市", "2672.10", "4.60", "539.40"),
    ("焦作市", "2369.20", "5.40", "349.60"), ("濮阳市", "2018.55", "5.10", "369.11"),
    ("漯河市", "1869.90", "6.80", "234.30"), ("三门峡市", "1618.69", "5.10", "200.70"),
    ("鹤壁市", "1094.39", "5.50", "155.90"), ("济源市", "789.56", "5.30", "72.30"),
]:
    ROWS.append(_r("SRC-B2-HENAN-REGIONAL-MACRO-2024", city, 2024, gdp_current_100m=gdp, gdp_real_growth_pct=growth, resident_population_10k=pop))

for city, gdp, growth, pop in [
    ("武汉市", "21106.23", "5.2", "1380.91"), ("宜昌市", "6191.12", "6.5", "392.65"),
    ("襄阳市", "6102.41", "5.9", "527.97"), ("荆州市", "3505.99", "6.3", "512.35"),
    ("孝感市", "3258.54", "7.0", "417.19"), ("黄冈市", "3216.65", "6.2", "579.24"),
    ("十堰市", "2565.84", "6.5", "314.22"), ("荆门市", "2459.68", "6.7", "255.07"),
    ("黄石市", "2305.81", "7.1", "243.53"), ("咸宁市", "1944.57", "6.1", "260.04"),
    ("恩施州", "1661.36", "5.8", "337.72"), ("随州市", "1442.35", "6.1", "200.39"),
    ("鄂州市", "1341.30", "6.5", "107.28"),
]:
    ROWS.append(_r("SRC-B2-HUBEI-REGIONAL-MACRO-2024", city, 2024, gdp_current_100m=gdp, gdp_real_growth_pct=growth, resident_population_10k=pop))

for city, gdp, growth, pop in [
    ("南京市", "18500.81", "4.5", "957.70"), ("苏州市", "26727.0", "6.0", "1298.7"),
    ("无锡市", "16263.29", "5.8", "750.50"), ("常州市", "10813.6", "6.1", "538.60"),
    ("镇江市", "5540.01", "5.9", "322.80"), ("南通市", "12421.9", "6.2", "775.0"),
    ("扬州市", "7809.64", "6.0", "458.68"), ("泰州市", "7020.95", "5.1", "447.40"),
    ("徐州市", "9537.12", "6.4", "901.00"), ("连云港市", "4663.13", "5.8", "458.17"),
    ("淮安市", "5413.02", "7.1", "452.35"), ("盐城市", "7779.2", "5.5", "667.1"),
    ("宿迁市", "4801.85", "6.9", "498.00"),
]:
    ROWS.append(_r("SRC-B2-JIANGSU-REGIONAL-MACRO-2024", city, 2024, gdp_current_100m=gdp, gdp_real_growth_pct=growth, resident_population_10k=pop))

for city, gdp, growth, pop in [
    ("西安市", "13317.78", "4.6", "1316.76"), ("榆林市", "7548.68", "6.0", "361.65"),
    ("咸阳市", "3001.27", "6.5", "408.06"), ("宝鸡市", "", "5.6", "325.37"),
    ("延安市", "2383.36", "5.5", "224.79"), ("渭南市", "2157.73", "5.7", "458.36"),
    ("汉中市", "", "6.2", "315.94"), ("安康市", "", "6.0", "245.22"),
    ("商洛市", "", "6.3", "201.16"), ("铜川市", "588.82", "6.4", ""),
]:
    macro = {"gdp_current_100m": gdp, "gdp_real_growth_pct": growth, "resident_population_10k": pop}
    ROWS.append(_r("SRC-B2-SHAANXI-REGIONAL-MACRO-2024", city, 2024, **macro))

for city, gdp, growth, pop in [
    ("贵阳市", "5777.41", "6.00", "660.25"), ("遵义市", "5027.20", "5.70", "649.45"),
    ("毕节市", "2457.59", "4.30", "662.16"), ("黔南州", "1947.16", "5.60", "350.12"),
    ("六盘水市", "1710.59", "5.20", "303.70"), ("黔西南州", "1649.81", "4.90", "316.15"),
    ("铜仁市", "1478.86", "4.20", "297.59"), ("黔东南州", "1432.38", "5.60", "374.03"),
    ("安顺市", "1186.11", "4.00", "246.55"),
]:
    ROWS.append(_r("SRC-B2-GUIZHOU-REGIONAL-MACRO-2024", city, 2024, gdp_current_100m=gdp, gdp_real_growth_pct=growth, resident_population_10k=pop))


def _merge(values: dict[tuple[str, str], dict[str, Any]], key: tuple[str, str], candidate: dict[str, Any]) -> None:
    prior = values.get(key)
    if prior is None:
        candidate["_field_sources"] = {
            field: dict(candidate) for field in candidate if field in _DATA_FIELDS
        }
        values[key] = candidate
        return
    field_sources = dict(prior.get("_field_sources") or {})
    ids = [item for item in str(prior.get("source_doc_id") or "").split(";") if item]
    if candidate["source_doc_id"] not in ids:
        ids.append(candidate["source_doc_id"])
    prior["source_doc_id"] = ";".join(ids)
    for field in _DATA_FIELDS:
        if field not in candidate:
            continue
        old = prior.get(field)
        old_source = field_sources.get(field, prior)
        if old is None:
            prior[field] = candidate[field]
            field_sources[field] = dict(candidate)
        elif old == candidate[field]:
            continue
        elif GRADE_RANK.get(candidate["source_grade"], -1) > GRADE_RANK.get(str(old_source.get("source_grade") or ""), -1):
            prior[field] = candidate[field]
            field_sources[field] = dict(candidate)
        else:
            conflicts = list(prior.get("_field_conflicts") or [])
            conflicts.append({"field": field, "prior_value": str(old), "candidate_value": str(candidate[field]), "prior_source_doc_id": str(old_source.get("source_doc_id") or ""), "candidate_source_doc_id": candidate["source_doc_id"]})
            prior["_field_conflicts"] = conflicts
    prior["_field_sources"] = field_sources


_DATA_FIELDS = {
    "gdp_current_100m", "gdp_real_growth_pct", "resident_population_10k",
    "general_public_revenue_100m", "general_public_expenditure_100m", "gov_fund_revenue_100m",
}


def load_regional_fiscal_sources(root: Path) -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    values: dict[tuple[str, str], dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    rows_by_source: dict[str, list[dict[str, Any]]] = {}
    for row in ROWS:
        rows_by_source.setdefault(str(row["source_doc_id"]), []).append(row)
    for source_doc_id, spec in SOURCE_SPECS.items():
        pdf_path = root / str(spec["path"])
        text_path = root / str(spec["text_path"])
        if not pdf_path.exists() or not text_path.exists():
            raise FileNotFoundError(f"区域批量来源归档缺失：{pdf_path} / {text_path}")
        content_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        for row in rows_by_source.get(source_doc_id, []):
            candidate: dict[str, Any] = {
                "source_doc_id": source_doc_id,
                "source_grade": SOURCE_GRADE,
                "source_format": "pdf",
                "data_status": "execution",
                "data_status_label": f"{row['year']}年执行数（评级报告精确表格）",
                "source_locator": f"{spec['text_path']}；{spec['page_number']}；城市={row['city_name']}；年份={row['year']}；行政范围=全市/全州",
                "table_name": spec["page_number"],
                "page_number": spec["page_number"],
            }
            for field in _DATA_FIELDS:
                if field not in row:
                    continue
                candidate[field] = row[field]
                unit = "%" if field == "gdp_real_growth_pct" else "万人" if field == "resident_population_10k" else "亿元"
                candidate[f"{field}_raw"] = row[field]
                candidate[f"{field}_raw_100m"] = row[field]
                candidate[f"{field}_raw_unit"] = unit
                candidate[f"{field}_evidence_excerpt"] = f"{row['city_name']}|{row['year']}|{row[field]}"
            _merge(values, (str(row["city_id"]), str(row["year"])), candidate)
        sources.append({
            "source_doc_id": source_doc_id,
            "publisher": spec["publisher"],
            "publisher_level": "评级机构公开披露精确表格",
            "document_title": spec["title"],
            "title_source": "rating_report_table",
            "attachment_title": pdf_path.name,
            "document_type": "评级报告地级行政区经济财政指标表",
            "source_url": spec["url"],
            "landing_page_url": spec["url"],
            "attachment_url": spec["url"],
            "canonical_url": spec["url"],
            "final_resolved_url": spec["url"],
            "file_name": pdf_path.name,
            "mime_type": "application/pdf",
            "publication_date": spec["publication_date"],
            "publication_date_raw": spec["publication_date"],
            "period_end": f"{spec['year']}-12-31",
            "downloaded_at": "2026-08-24T00:00:00+08:00",
            "content_hash_sha256": content_hash,
            "archive_uri": f"archive://national-prefecture-panel/{spec['path']}",
            "archive_backend": "internal_object",
            "archive_path": spec["path"],
            "page_count": "",
            "source_grade": SOURCE_GRADE,
            "http_status": "200",
            "access_status": "公开PDF已归档；表格行已人工核对",
            "supersedes_doc_id": "",
            "note": spec["note"],
        })
    return values, sources


__all__ = ["load_regional_fiscal_sources"]
