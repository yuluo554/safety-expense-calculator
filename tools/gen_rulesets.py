"""规则包生成器 —— **唯一写入者**（冻结产物禁手改）。

产出 ``data/rules/`` 全部文件：

* ``manifest.json`` —— 规则集索引 + **基准门槛**（数据非代码）+ 各文件 sha256；
* ``units.json`` —— 定义性单位换算（**非政策数值**，豁免零字面量门禁）；
* ``<ruleset>/ruleset.json`` —— 计提标准（十二节 / 九类）；
* ``<ruleset>/spending.json`` —— 支出范围条目（M3 扩至 2022 版十二节 / 2012 版九类）；
* ``<ruleset>/progress.json`` —— 使用进度门槛。

**M2 数据状态**：计提标准逐条挂官方原文核对后**全部落值**（抓取与核对记录见
``data/README.md`` §二与 ``data/knowledge/``）：

* 2022 版（财资〔2022〕136号）：**十二节全部** ``status="verified"`` 带值；
  非煤矿山第十条机制按原文纠正为 **``by_output``**（原 M0 误标 ``by_revenue_tiered``），
  武器装备第三十九条为**五小类变体**（各自独立阶梯）；
* 2012 版（财企〔2012〕16号）：**九类全部** ``status="verified"`` 带值；
  烟花爆竹第十二条分段点（200 万 / 500 万 / 1000 万）与 2022 版结构不同，
  石油天然气并入非煤矿山第六条（含石油 17 元/吨、天然气 5 元/千方）；
* 使用进度门槛：2022 版第五十一条（不足 60% 须披露并书面说明）已核对落值；
  **2012 版无对应比例条款**（第十四条是结余达标时的缓提少提规则，结构不同）→
  显式留 ``pending`` 待 M2 重定型。

**确定性纪律**：禁 stdlib ``random``、禁 ``set`` 迭代序、禁系统时钟；落盘用
``write_bytes``（不写 CR），两次运行**逐字节一致**。

用法::

    python tools/gen_rulesets.py            # 生成
    python tools/gen_rulesets.py --check    # 校验"再生成逐字节一致"
"""

import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "rules"

SCHEMA_VERSION = 1

#: 官方原文快照（curl 直连落盘 ``data/knowledge/raw/``，逐份 sha256 登记）
URL_2022 = "https://www.gov.cn/zhengce/zhengceku/2022-12/14/content_5731902.htm"
SNAPSHOT_2022 = "data/knowledge/raw/136-body.docx"
SHA_2022_DOCX = "fd6e880a0228c71f7e519b82b04e71eb31364ead02fd93ae12da53c037cd8477"
URL_2012 = "https://www.gov.cn/gongbao/content/2012/content_2177022.htm"
SNAPSHOT_2012 = "data/knowledge/raw/2012-gongbao.htm"
SHA_2012_HTM = "0ab4597c079ce440d3482c774f39ec008f1edfe118d207dd86e8a05332899812"

FETCHED_AT = "2026-10-14"

#: 2022 版十二节（节次与条款号逐条对原文核对于 data/knowledge/raw/136-body.paragraphs.txt）
#: 元组：(industry_id, 名称, 提取条款, 机制, implementation)
INDUSTRIES_2022 = [
    ("coal", "煤炭生产", "第七条", "by_output", "in_scope"),
    ("noncoal_mine", "非煤矿山开采", "第十条", "by_output", "in_scope"),
    ("oil_gas", "石油天然气开采", "第十四条", "by_output", "in_scope"),
    ("construction", "建设工程施工", "第十七条", "by_project_cost", "in_scope"),
    ("hazardous_chemicals", "危险品生产与储存", "第二十一条", "by_revenue_tiered", "in_scope"),
    ("transport", "交通运输", "第二十四条", "by_revenue_rate", "in_scope"),
    ("metallurgy", "冶金", "第二十七条", "by_revenue_tiered", "in_scope"),
    ("machinery", "机械制造", "第三十条", "by_revenue_tiered", "in_scope"),
    ("fireworks", "烟花爆竹生产", "第三十三条", "by_revenue_tiered", "in_scope"),
    ("civil_explosives", "民用爆炸物品生产", "第三十六条", "by_revenue_tiered", "in_scope"),
    ("weapons", "武器装备研制生产与试验", "第三十九条", "by_revenue_tiered", "in_scope"),
    ("power", "电力生产与供应", "第四十三条", "by_revenue_tiered", "in_scope"),
]

#: 2012 版九类（旧版，历史年度对照用；**石油天然气在 2012 版并入非煤矿山第六条**，
#: 武器装备为第十三条——均对国务院公报原文核对）
INDUSTRIES_2012 = [
    ("coal", "煤炭生产", "第五条", "by_output", "in_scope"),
    ("noncoal_mine", "非煤矿山开采", "第六条", "by_output", "in_scope"),
    ("construction", "建设工程施工", "第七条", "by_project_cost", "in_scope"),
    ("hazardous_chemicals", "危险品生产与储存", "第八条", "by_revenue_tiered", "in_scope"),
    ("transport", "交通运输", "第九条", "by_revenue_rate", "in_scope"),
    ("metallurgy", "冶金", "第十条", "by_revenue_tiered", "in_scope"),
    ("machinery", "机械制造", "第十一条", "by_revenue_tiered", "in_scope"),
    ("fireworks", "烟花爆竹生产", "第十二条", "by_revenue_tiered", "in_scope"),
    ("weapons", "武器装备研制生产与试验", "第十三条", "by_revenue_tiered", "in_scope"),
]

#: ── 已核对数值（逐字比对原文；单位见各 variant 的 unit 字段）──────────────────

#: 2022 版煤炭第七条（吨煤提取标准；矿井变体 + 从高提取）
COAL_2022 = [
    ("coal_outburst_rockburst", "煤（岩）与瓦斯（二氧化碳）突出矿井、冲击地压矿井", 4,
     "50", {"hazards": ["gas_outburst", "rockburst"]}),
    ("coal_high_gas", "高瓦斯矿井，水文地质类型复杂、极复杂矿井，容易自燃煤层矿井", 3,
     "30", {"mine_type": "high_gas"}),
    ("coal_other_underground", "其他井工矿", 2, "15", {"mine_type": "other_underground"}),
    ("coal_opencast", "露天矿", 1, "5", {"mine_type": "opencast"}),
]

#: 2012 版煤炭第五条（突出与高瓦斯同档 30 元——2022 版拆分档位的对照素材）
COAL_2012 = [
    ("coal_outburst_high_gas", "煤（岩）与瓦斯（二氧化碳）突出矿井、高瓦斯矿井", 3,
     "30", {"hazards": ["gas_outburst"], "mine_type": "high_gas"}),
    ("coal_other_underground", "其他井工矿", 2, "15", {"mine_type": "other_underground"}),
    ("coal_opencast", "露天矿", 1, "5", {"mine_type": "opencast"}),
]

#: 2022 版非煤矿山第十条（**按原矿产量计提**——机制对原文纠正为 by_output）：
#: 金属露天 5 / 地下 15；核工业 25；非金属露天 3 / 地下 8；小型露天采石场 2。
#: 第十条第三款"地质勘探单位按地质勘查项目或工程总费用的 2%"为**机制覆写**变体。
#: 元组：(variant_id, variant_name, severity, kind, value, conditions, unit)
NONCOAL_2022 = [
    ("nc_metal_opencast", "金属矿山·露天矿山", 2, "value", "5",
     {"ore_type": "metal", "mine_type": "opencast"}, "CNY/ton"),
    ("nc_metal_underground", "金属矿山·地下矿山", 2, "value", "15",
     {"ore_type": "metal", "mine_type": "underground"}, "CNY/ton"),
    ("nc_nuclear", "核工业矿山", 2, "value", "25", {"ore_type": "nuclear"}, "CNY/ton"),
    ("nc_nonmetal_opencast", "非金属矿山·露天矿山", 2, "value", "3",
     {"ore_type": "nonmetal", "mine_type": "opencast"}, "CNY/ton"),
    ("nc_nonmetal_underground", "非金属矿山·地下矿山", 2, "value", "8",
     {"ore_type": "nonmetal", "mine_type": "underground"}, "CNY/ton"),
    ("nc_small_quarry", "小型露天采石场（年生产规模不超过 50 万吨的山坡型露天采石场）", 2,
     "value", "2", {"ore_type": "small_quarry"}, "CNY/ton"),
    ("nc_geological_exploration", "地质勘探单位（按地质勘查项目或工程总费用的 2%）", 1,
     "rate", "0.02", {"ore_type": "geological_exploration"}, "ratio"),
]

#: 2012 版非煤矿山第六条（**石油天然气并入本行业**）：石油 17 元/吨、天然气/煤层气 5 元/千方、
#: 金属露天 5/地下 10、核工业 25、非金属露天 2/地下 4、小型露天采石场 1；
#: 地质勘探单位按 2%。
NONCOAL_2012 = [
    ("nc_oil", "石油", 2, "value", "17", {"ore_type": "oil"}, "CNY/ton"),
    ("nc_gas", "天然气、煤层气（地面开采）", 2, "value", "5",
     {"ore_type": "gas"}, "CNY/kilo_m3"),
    ("nc_metal_opencast", "金属矿山·露天矿山", 2, "value", "5",
     {"ore_type": "metal", "mine_type": "opencast"}, "CNY/ton"),
    ("nc_metal_underground", "金属矿山·地下矿山", 2, "value", "10",
     {"ore_type": "metal", "mine_type": "underground"}, "CNY/ton"),
    ("nc_nuclear", "核工业矿山", 2, "value", "25", {"ore_type": "nuclear"}, "CNY/ton"),
    ("nc_nonmetal_opencast", "非金属矿山·露天矿山", 2, "value", "2",
     {"ore_type": "nonmetal", "mine_type": "opencast"}, "CNY/ton"),
    ("nc_nonmetal_underground", "非金属矿山·地下矿山", 2, "value", "4",
     {"ore_type": "nonmetal", "mine_type": "underground"}, "CNY/ton"),
    ("nc_small_quarry", "小型露天采石场（年采剥总量 50 万吨以下且最大开采高度不超过 50 米）", 2,
     "value", "1", {"ore_type": "small_quarry"}, "CNY/ton"),
    ("nc_geological_exploration", "地质勘探单位（按地质勘查项目或工程总费用的 2%）", 1,
     "rate", "0.02", {"ore_type": "geological_exploration"}, "ratio"),
]

#: 2022 版石油天然气第十四条（**按产量**）：每吨原油 20 元、每千立方米原气 7.5 元；
#: 钻井/物探/测井/录井/井下作业/油建/海油工程按项目或工程造价直接工程成本的 2%（**机制覆写**）。
OIL_GAS_2022 = [
    ("og_crude_oil", "陆上/海上采油（气）·原油", 2, "value", "20",
     {"operation": "production_oil"}, "CNY/ton"),
    ("og_natural_gas", "陆上/海上采油（气）·原气", 2, "value", "7.5",
     {"operation": "production_gas"}, "CNY/kilo_m3"),
    ("og_engineering", "钻井、物探、测井、录井、井下作业、油建、海油工程（按直接工程成本的 2%）", 1,
     "rate", "0.02", {"operation": "engineering"}, "ratio"),
]

#: 2022 版建设工程第十七条（以建筑安装工程造价为依据，按工程进度月末提取）
CONSTRUCTION_2022 = [
    ("mine_engineering", "矿山工程", "0.035"),
    ("railway_building_rail_transit", "铁路工程、房屋建筑工程、城市轨道交通工程", "0.03"),
    ("water_power_electric", "水利水电工程、电力工程", "0.025"),
    ("smelting_mechanical_chemical_telecom", "冶炼工程、机电安装工程、化工石油工程、通信工程", "0.02"),
    ("municipal_port_highway", "市政公用工程、港口与航道工程、公路工程", "0.015"),
]

#: 2012 版建设工程第七条（**档位归并与 2022 版不同**：房屋建筑/水利水电/电力/铁路/轨交同档）
CONSTRUCTION_2012 = [
    ("mine_engineering", "矿山工程", "0.025"),
    ("building_water_power_rail", "房屋建筑工程、水利水电工程、电力工程、铁路工程、城市轨道交通工程", "0.02"),
    ("municipal_smelting_others", "市政公用工程、冶炼工程、机电安装工程、化工石油工程、港口与航道工程、公路工程、通信工程", "0.015"),
]

#: 超额累退分段（费率 + 边界，全部逐字核对；边界口径 ``[lower, upper)``，见 plan/04 §4）
HAZ_2022_SEGMENTS = [
    ("0", "10000000", "0.045"),
    ("10000000", "100000000", "0.0225"),
    ("100000000", "1000000000", "0.0055"),
    ("1000000000", None, "0.002"),
]
HAZ_2012_SEGMENTS = [
    ("0", "10000000", "0.04"),
    ("10000000", "100000000", "0.02"),
    ("100000000", "1000000000", "0.005"),
    ("1000000000", None, "0.002"),
]

#: 2022 版冶金第二十七条（六段）
METALLURGY_2022_SEGMENTS = [
    ("0", "10000000", "0.03"),
    ("10000000", "100000000", "0.015"),
    ("100000000", "1000000000", "0.005"),
    ("1000000000", "5000000000", "0.002"),
    ("5000000000", "10000000000", "0.001"),
    ("10000000000", None, "0.0005"),
]
#: 2012 版冶金第十条（六段，与 2022 版同结构不同费率）
METALLURGY_2012_SEGMENTS = [
    ("0", "10000000", "0.03"),
    ("10000000", "100000000", "0.015"),
    ("100000000", "1000000000", "0.005"),
    ("1000000000", "5000000000", "0.002"),
    ("5000000000", "10000000000", "0.001"),
    ("10000000000", None, "0.0005"),
]

#: 2022 版机械制造第三十条（五段）
MACHINERY_2022_SEGMENTS = [
    ("0", "10000000", "0.0235"),
    ("10000000", "100000000", "0.0125"),
    ("100000000", "1000000000", "0.0025"),
    ("1000000000", "5000000000", "0.001"),
    ("5000000000", None, "0.0005"),
]
#: 2012 版机械制造第十一条（五段，费率不同）
MACHINERY_2012_SEGMENTS = [
    ("0", "10000000", "0.02"),
    ("10000000", "100000000", "0.01"),
    ("100000000", "1000000000", "0.002"),
    ("1000000000", "5000000000", "0.001"),
    ("5000000000", None, "0.0005"),
]

#: 2022 版烟花爆竹第三十三条（**三段**，分段点 1000 万 / 2000 万）
FIREWORKS_2022_SEGMENTS = [
    ("0", "10000000", "0.04"),
    ("10000000", "20000000", "0.03"),
    ("20000000", None, "0.025"),
]
#: 2012 版烟花爆竹第十二条（**四段**，分段点 200 万 / 500 万 / 1000 万——结构与 2022 版不同）
FIREWORKS_2012_SEGMENTS = [
    ("0", "2000000", "0.035"),
    ("2000000", "5000000", "0.03"),
    ("5000000", "10000000", "0.025"),
    ("10000000", None, "0.02"),
]

#: 2022 版民用爆炸物品第三十六条（四段）
CIVIL_EXPLOSIVES_2022_SEGMENTS = [
    ("0", "10000000", "0.04"),
    ("10000000", "100000000", "0.02"),
    ("100000000", "1000000000", "0.005"),
    ("1000000000", None, "0.002"),
]

#: 2022 版武器装备第三十九条（**五小类变体**，各自独立阶梯）
WEAPONS_2022 = [
    ("wp_military_hazardous_chemicals", "军工危险化学品（火炸药、推进剂、弹药、火箭导弹发动机、燃气发生器）", [
        ("0", "10000000", "0.05"),
        ("10000000", "100000000", "0.03"),
        ("100000000", "1000000000", "0.01"),
        ("1000000000", None, "0.005"),
    ]),
    ("wp_nuclear", "核装备及核燃料", [
        ("0", "10000000", "0.03"),
        ("10000000", "100000000", "0.02"),
        ("100000000", "1000000000", "0.005"),
        ("1000000000", None, "0.002"),
    ]),
    ("wp_naval_ship", "军用舰船（含修理）", [
        ("0", "10000000", "0.025"),
        ("10000000", "100000000", "0.0175"),
        ("100000000", "1000000000", "0.008"),
        ("1000000000", None, "0.004"),
    ]),
    ("wp_spacecraft", "飞船、卫星、军用飞机、坦克车辆、火炮、轻武器、大型天线等", [
        ("0", "10000000", "0.02"),
        ("10000000", "100000000", "0.015"),
        ("100000000", "1000000000", "0.005"),
        ("1000000000", "10000000000", "0.002"),
        ("10000000000", None, "0.001"),
    ]),
    ("wp_other_military_hazardous", "其他军用危险品", [
        ("0", "10000000", "0.04"),
        ("10000000", "100000000", "0.02"),
        ("100000000", "1000000000", "0.005"),
        ("1000000000", None, "0.002"),
    ]),
]

#: 2012 版武器装备第十三条（**五小类变体**；火炸药类名与核工程条款位置不同）
WEAPONS_2012 = [
    ("wp_military_hazardous_chemicals", "火炸药及其制品（含能材料，炸药、火药、推进剂，发动机，弹箭，引信、火工品）", [
        ("0", "10000000", "0.05"),
        ("10000000", "100000000", "0.03"),
        ("100000000", "1000000000", "0.01"),
        ("1000000000", None, "0.005"),
    ]),
    ("wp_nuclear", "核装备及核燃料", [
        ("0", "10000000", "0.03"),
        ("10000000", "100000000", "0.02"),
        ("100000000", "1000000000", "0.005"),
        ("1000000000", None, "0.002"),
    ]),
    ("wp_naval_ship", "军用舰船（含修理）", [
        ("0", "10000000", "0.025"),
        ("10000000", "100000000", "0.0175"),
        ("100000000", "1000000000", "0.008"),
        ("1000000000", None, "0.004"),
    ]),
    ("wp_spacecraft", "飞船、卫星、军用飞机、坦克车辆、火炮、轻武器、大型天线等", [
        ("0", "10000000", "0.02"),
        ("10000000", "100000000", "0.015"),
        ("100000000", "1000000000", "0.005"),
        ("1000000000", "10000000000", "0.002"),
        ("10000000000", None, "0.001"),
    ]),
    ("wp_other_military_hazardous", "其他军用危险品", [
        ("0", "10000000", "0.04"),
        ("10000000", "100000000", "0.02"),
        ("100000000", "1000000000", "0.005"),
        ("1000000000", None, "0.002"),
    ]),
]

#: 2022 版电力第四十三条：**生产与供应两套标准**（变体拆分）
POWER_GENERATION_SEGMENTS = [
    ("0", "10000000", "0.03"),
    ("10000000", "100000000", "0.015"),
    ("100000000", "1000000000", "0.01"),
    ("1000000000", "5000000000", "0.008"),
    ("5000000000", "10000000000", "0.006"),
    ("10000000000", None, "0.002"),
]
POWER_SUPPLY_SEGMENTS = [
    ("0", "50000000000", "0.005"),
    ("50000000000", "100000000000", "0.004"),
    ("100000000000", "200000000000", "0.003"),
    ("200000000000", None, "0.002"),
]

#: 交通运输：2022 版第二十四条（普通货运 1%；客运/管道/危险品等特殊货运 1.5%）
TRANSPORT_2022 = [
    ("general_freight", "普通货运业务", "0.01"),
    ("passenger_special_freight", "客运业务、管道运输、危险品等特殊货运业务", "0.015"),
]
#: 2012 版第九条（同结构；费率一致）
TRANSPORT_2012 = [
    ("general_freight", "普通货运业务", "0.01"),
    ("passenger_special_freight", "客运业务、管道运输、危险品等特殊货运业务", "0.015"),
]

#: 支出范围条目（要点引用，非全文转载；红线条款 2022 版=第四条第三项、2012 版=第二十七条）。
#: M3 扩至十二节（2022）/九类（2012）：每行业 2~3 条允许条目 + 1 条红线，
#: 关键词取自各节"应当用于以下支出"条款的要点词（逐条对原文核对，快照见 data/knowledge/raw/）。
SPENDING_2022 = [
    # 煤炭（第八条；红线第四条）
    ("SP-COAL-01", "coal", "第八条", "允许", "煤矿安全生产改造和重大事故隐患治理支出（第八条第三项要点）",
     ["安全改造", "隐患治理"]),
    ("SP-COAL-02", "coal", "第八条", "允许", "安全生产检查、咨询、标准化建设支出（第八条第六项要点）",
     ["标准化"]),
    ("SP-COAL-03", "coal", "第八条", "允许", "安全生产宣传、教育、培训和从业人员发现并报告事故隐患的奖励支出（第八条第八项要点）",
     ["培训", "宣传教育"]),
    ("SP-COAL-04", "coal", "第八条", "允许", "应急救援技术装备设施配置维护保养与应急救援队伍建设、应急预案制修订与应急演练支出（第八条第四项要点）",
     ["应急救援"]),
    ("SP-COAL-99", "coal", "第四条", "禁止", "专项核算、不得挤占挪用安全生产费用（红线，第四条第三项）",
     ["挤占", "挪用"]),
    # 非煤矿山（第十二条）
    ("SP-NONCOAL-01", "noncoal_mine", "第十二条", "允许", "完善、改造和维护安全防护设施设备（不含“三同时”要求初期投入的安全设施）和重大事故隐患治理支出（第十二条第一项要点）",
     ["安全防护", "隐患治理"]),
    ("SP-NONCOAL-02", "noncoal_mine", "第十二条", "允许", "安全生产检查、评估评价、咨询、标准化建设支出（第十二条第四项要点）",
     ["标准化"]),
    ("SP-NONCOAL-03", "noncoal_mine", "第十二条", "允许", "尾矿库闭库、销库费用支出（第十二条第九项要点）",
     ["尾矿库闭库"]),
    ("SP-NONCOAL-99", "noncoal_mine", "第四条", "禁止", "专项核算、不得挤占挪用安全生产费用（红线，第四条第三项）",
     ["挤占", "挪用"]),
    # 石油天然气（第十五条）
    ("SP-OILGAS-01", "oil_gas", "第十五条", "允许", "完善、改造和维护安全防护设施设备支出（第十五条第一项要点）",
     ["安全防护", "防井喷"]),
    ("SP-OILGAS-02", "oil_gas", "第十五条", "允许", "野外或海上作业应急食品、应急器械、应急药品支出（第十五条第九项要点）",
     ["应急药品", "应急器械"]),
    ("SP-OILGAS-99", "oil_gas", "第四条", "禁止", "专项核算、不得挤占挪用安全生产费用（红线，第四条第三项）",
     ["挤占", "挪用"]),
    # 建设工程（第十九条）
    ("SP-CONST-01", "construction", "第十九条", "允许", "完善、改造和维护安全防护设施设备支出（第十九条第一项要点）",
     ["安全防护"]),
    ("SP-CONST-02", "construction", "第十九条", "允许", "应急救援技术装备设施配置及维护保养与应急救援队伍建设、应急预案制修订与应急演练支出（第十九条第二项要点）",
     ["应急救援"]),
    ("SP-CONST-99", "construction", "第四条", "禁止", "专项核算、不得挤占挪用安全生产费用（红线，第四条第三项）",
     ["挤占", "挪用"]),
    # 危险品（第二十二条）
    ("SP-HAZ-01", "hazardous_chemicals", "第二十二条", "允许", "完善安全防护设施设备与配备维护应急救援器材支出（第二十二条第一、二项要点）",
     ["安全防护", "应急救援器材"]),
    ("SP-HAZ-02", "hazardous_chemicals", "第二十二条", "允许", "配备和更新现场作业人员安全防护用品支出（第二十二条第五项要点）",
     ["安全防护用品"]),
    ("SP-HAZ-99", "hazardous_chemicals", "第四条", "禁止", "专项核算、不得挤占挪用安全生产费用（红线，第四条第三项）",
     ["挤占", "挪用"]),
    # 交通运输（第二十五条）
    ("SP-TRANS-01", "transport", "第二十五条", "允许", "完善、改造和维护安全防护设施设备支出（第二十五条第一项要点）",
     ["安全防护"]),
    ("SP-TRANS-02", "transport", "第二十五条", "允许", "购置、安装和使用具有行驶记录功能的车辆卫星定位装置、视频监控装置、船舶通信导航定位和自动识别系统等支出（第二十五条第二项要点）",
     ["卫星定位", "视频监控"]),
    ("SP-TRANS-03", "transport", "第二十五条", "允许", "安全生产责任保险及承运人责任保险支出（第二十五条第十一项要点）",
     ["承运人责任保险", "安全生产责任保险"]),
    ("SP-TRANS-99", "transport", "第四条", "禁止", "专项核算、不得挤占挪用安全生产费用（红线，第四条第三项）",
     ["挤占", "挪用"]),
    # 冶金（第二十八条）
    ("SP-MET-01", "metallurgy", "第二十八条", "允许", "完善、改造和维护安全防护设备设施支出（第二十八条第一项要点）",
     ["安全防护"]),
    ("SP-MET-02", "metallurgy", "第二十八条", "允许", "安全生产宣传、教育、培训和从业人员发现并报告事故隐患的奖励支出（第二十八条第五项要点）",
     ["培训"]),
    ("SP-MET-99", "metallurgy", "第四条", "禁止", "专项核算、不得挤占挪用安全生产费用（红线，第四条第三项）",
     ["挤占", "挪用"]),
    # 机械制造（第三十一条）
    ("SP-MAC-01", "machinery", "第三十一条", "允许", "完善、改造和维护安全防护设施设备支出，含大型起重机械安装安全监控管理系统支出（第三十一条第一项要点）",
     ["安全防护", "安全监控管理系统"]),
    ("SP-MAC-02", "machinery", "第三十一条", "允许", "配备、维护、保养应急救援器材、设备支出和应急救援队伍建设、应急预案制修订与应急演练支出（第三十一条第二项要点）",
     ["应急救援"]),
    ("SP-MAC-99", "machinery", "第四条", "禁止", "专项核算、不得挤占挪用安全生产费用（红线，第四条第三项）",
     ["挤占", "挪用"]),
    # 烟花爆竹（第三十四条）
    ("SP-FW-01", "fireworks", "第三十四条", "允许", "完善、改造和维护安全设备设施支出（第三十四条第一项要点）",
     ["安全设施", "防护屏障"]),
    ("SP-FW-02", "fireworks", "第三十四条", "允许", "配备、维护、保养防爆机械电器设备支出（第三十四条第二项要点）",
     ["防爆"]),
    ("SP-FW-99", "fireworks", "第四条", "禁止", "专项核算、不得挤占挪用安全生产费用（红线，第四条第三项）",
     ["挤占", "挪用"]),
    # 民用爆炸物品（第三十七条）
    ("SP-CE-01", "civil_explosives", "第三十七条", "允许", "完善、改造和维护安全防护设施设备支出（第三十七条第一项要点）",
     ["安全防护"]),
    ("SP-CE-02", "civil_explosives", "第三十七条", "允许", "配备、维护、保养应急救援器材、设备支出和应急救援队伍建设、应急预案制修订与应急演练支出（第三十七条第二项要点）",
     ["应急救援"]),
    ("SP-CE-99", "civil_explosives", "第四条", "禁止", "专项核算、不得挤占挪用安全生产费用（红线，第四条第三项）",
     ["挤占", "挪用"]),
    # 武器装备（第四十一条）
    ("SP-WP-01", "weapons", "第四十一条", "允许", "完善、改造和维护安全防护设施设备支出（第四十一条第一项要点）",
     ["安全防护"]),
    ("SP-WP-02", "weapons", "第四十一条", "允许", "高新技术和特种专用设备安全鉴定评估、安全性能检验检测及操作人员上岗培训支出（第四十一条第四项要点）",
     ["上岗培训", "安全鉴定"]),
    ("SP-WP-03", "weapons", "第四十一条", "允许", "军工核设施（含核废物）防泄漏、防辐射的设施设备支出（第四十一条第七项要点）",
     ["防辐射", "防泄漏"]),
    ("SP-WP-99", "weapons", "第四条", "禁止", "专项核算、不得挤占挪用安全生产费用（红线，第四条第三项）",
     ["挤占", "挪用"]),
    # 电力（第四十四条）
    ("SP-POWER-01", "power", "第四十四条", "允许", "发电输电变配电设备设施安全防护与安全监控支出（第四十四条第一项要点）",
     ["安全防护", "安全监控"]),
    ("SP-POWER-02", "power", "第四十四条", "允许", "配备和更新现场作业人员安全防护用品支出（第四十四条第六项要点）",
     ["安全防护用品"]),
    ("SP-POWER-99", "power", "第四条", "禁止", "专项核算、不得挤占挪用安全生产费用（红线，第四条第三项）",
     ["挤占", "挪用"]),
]

#: 2012 版支出范围（第十七~二十五条；红线第二十七条；2012 版无石油天然气/
#: 民用爆炸物品/电力行业类别 → 不登记对应条目）
SPENDING_2012 = [
    # 煤炭（第十七条）
    ("SP-COAL-01", "coal", "第十七条", "允许", "煤矿安全生产改造和重大隐患治理支出（第十七条第二项要点）",
     ["安全改造", "隐患治理"]),
    ("SP-COAL-02", "coal", "第十七条", "允许", "安全生产检查、评价、咨询、标准化建设支出（第十七条第五项要点）",
     ["标准化"]),
    ("SP-COAL-03", "coal", "第十七条", "允许", "安全生产宣传、教育、培训支出（第十七条第七项要点）",
     ["培训"]),
    ("SP-COAL-99", "coal", "第二十七条", "禁止", "专户核算、不得挤占挪用安全费用（红线，第二十七条）",
     ["挤占", "挪用"]),
    # 非煤矿山（第十八条）
    ("SP-NONCOAL-01", "noncoal_mine", "第十八条", "允许", "完善、改造和维护安全防护设施设备（不含“三同时”要求初期投入的安全设施）和重大安全隐患治理支出（第十八条第一项要点）",
     ["安全防护", "隐患治理"]),
    ("SP-NONCOAL-02", "noncoal_mine", "第十八条", "允许", "安全生产检查、评价、咨询、标准化建设支出（第十八条第四项要点）",
     ["标准化"]),
    ("SP-NONCOAL-03", "noncoal_mine", "第十八条", "允许", "尾矿库闭库及闭库后维护费用支出（第十八条第九项要点）",
     ["尾矿库闭库"]),
    ("SP-NONCOAL-99", "noncoal_mine", "第二十七条", "禁止", "专户核算、不得挤占挪用安全费用（红线，第二十七条）",
     ["挤占", "挪用"]),
    # 建设工程（第十九条）
    ("SP-CONST-01", "construction", "第十九条", "允许", "完善、改造和维护安全防护设施设备支出（第十九条第一项要点）",
     ["安全防护"]),
    ("SP-CONST-02", "construction", "第十九条", "允许", "配备、维护、保养应急救援器材、设备支出和应急演练支出（第十九条第二项要点）",
     ["应急救援"]),
    ("SP-CONST-99", "construction", "第二十七条", "禁止", "专户核算、不得挤占挪用安全费用（红线，第二十七条）",
     ["挤占", "挪用"]),
    # 危险品（第二十条）
    ("SP-HAZ-01", "hazardous_chemicals", "第二十条", "允许", "完善安全防护设施设备与配备维护应急救援器材支出（第二十条第一、二项要点）",
     ["安全防护", "应急救援器材"]),
    ("SP-HAZ-02", "hazardous_chemicals", "第二十条", "允许", "配备和更新现场作业人员安全防护用品支出（第二十条第五项要点）",
     ["安全防护用品"]),
    ("SP-HAZ-99", "hazardous_chemicals", "第二十七条", "禁止", "专户核算、不得挤占挪用安全费用（红线，第二十七条）",
     ["挤占", "挪用"]),
    # 交通运输（第二十一条）
    ("SP-TRANS-01", "transport", "第二十一条", "允许", "完善、改造和维护安全防护设施设备支出（第二十一条第一项要点）",
     ["安全防护"]),
    ("SP-TRANS-02", "transport", "第二十一条", "允许", "购置、安装和使用具有行驶记录功能的车辆卫星定位装置、船舶通信导航定位和自动识别系统、电子海图等支出（第二十一条第二项要点）",
     ["卫星定位"]),
    ("SP-TRANS-99", "transport", "第二十七条", "禁止", "专户核算、不得挤占挪用安全费用（红线，第二十七条）",
     ["挤占", "挪用"]),
    # 冶金（第二十二条）
    ("SP-MET-01", "metallurgy", "第二十二条", "允许", "完善、改造和维护安全防护设施设备支出（第二十二条第一项要点）",
     ["安全防护"]),
    ("SP-MET-02", "metallurgy", "第二十二条", "允许", "安全生产宣传、教育、培训支出（第二十二条第五项要点）",
     ["培训"]),
    ("SP-MET-99", "metallurgy", "第二十七条", "禁止", "专户核算、不得挤占挪用安全费用（红线，第二十七条）",
     ["挤占", "挪用"]),
    # 机械制造（第二十三条）
    ("SP-MAC-01", "machinery", "第二十三条", "允许", "完善、改造和维护安全防护设施设备支出，含大型起重机械安装安全监控管理系统支出（第二十三条第一项要点）",
     ["安全防护", "安全监控管理系统"]),
    ("SP-MAC-02", "machinery", "第二十三条", "允许", "配备、维护、保养应急救援器材、设备支出和应急演练支出（第二十三条第二项要点）",
     ["应急救援"]),
    ("SP-MAC-99", "machinery", "第二十七条", "禁止", "专户核算、不得挤占挪用安全费用（红线，第二十七条）",
     ["挤占", "挪用"]),
    # 烟花爆竹（第二十四条）
    ("SP-FW-01", "fireworks", "第二十四条", "允许", "完善、改造和维护安全设备设施支出（第二十四条第一项要点）",
     ["安全设施", "防护屏障"]),
    ("SP-FW-02", "fireworks", "第二十四条", "允许", "配备、维护、保养防爆机械电器设备支出（第二十四条第二项要点）",
     ["防爆"]),
    ("SP-FW-99", "fireworks", "第二十七条", "禁止", "专户核算、不得挤占挪用安全费用（红线，第二十七条）",
     ["挤占", "挪用"]),
    # 武器装备（第二十五条）
    ("SP-WP-01", "weapons", "第二十五条", "允许", "完善、改造和维护安全防护设施设备支出（第二十五条第一项要点）",
     ["安全防护"]),
    ("SP-WP-02", "weapons", "第二十五条", "允许", "高新技术和特种专用设备安全鉴定评估、安全性能检验检测及操作人员上岗培训支出（第二十五条第四项要点）",
     ["上岗培训", "安全鉴定"]),
    ("SP-WP-03", "weapons", "第二十五条", "允许", "军工核设施（含核废物）防泄漏、防辐射的设施设备支出（第二十五条第七项要点）",
     ["防辐射", "防泄漏"]),
    ("SP-WP-99", "weapons", "第二十七条", "禁止", "专户核算、不得挤占挪用安全费用（红线，第二十七条）",
     ["挤占", "挪用"]),
]

#: 使用进度门槛：2022 版第五十一条已核对；**2012 版无对应比例条款 → 显式 pending**
PROGRESS_2022 = [
    ("default", "第五十一条", "当年实际使用的安全生产费用不足年度应计提金额60%的，除按规定进行信息披露外，还应当于下一年度4月底前按属地监管权限向县级以上负有安全生产监督管理职责的部门提交经企业董事会、股东会等机构审议的书面说明",
     ["按规定进行信息披露",
      "于下一年度4月底前按属地监管权限提交书面说明",
      "书面说明须经企业董事会、股东会等机构审议"],
     "0.6"),
]
PROGRESS_2012 = [
    ("default", "第十四条",
     "2012 版无按比例披露条款：第十四条为上年末结余达标（中小微企业达上年营业收入5%、大型企业达1.5%）时经批准可缓提少提的规则，与 2022 版第五十一条结构不同——门槛不套用，待 M2 重定型",
     [], None),
]

UNITS = {
    "CNY": "1",
    "CNY10k": "10000",
    "CNY100m": "100000000",
    "ton": "1",
    "kilo_m3": "1",
}


def _provenance(doc_no: str, clause: str, url: str, snapshot: str, sha: str,
                verified: bool) -> dict:
    """条目出处（无出处不得落库；``verified=False`` 时 fetched_at 留空）。"""
    return {
        "clause": clause,
        "doc_no": doc_no,
        "fetched_at": FETCHED_AT if verified else None,
        "raw_sha256": sha,
        "snapshot": snapshot,
        "url": url,
        "verified": verified,
    }


def _segments(clause: str, rows, doc_no: str, url: str, snapshot: str, sha: str) -> List[dict]:
    """把 ``(lower, upper, rate)`` 三元组渲染为段条目（全部 verified）。"""
    out = []
    for lower, upper, rate in rows:
        out.append({
            "clause": clause,
            "lower": lower,
            "provenance": _provenance(doc_no, clause, url, snapshot, sha, True),
            "rate": rate,
            "status": "verified",
            "upper": upper,
        })
    return out


def _output_variants(clause, rows, doc_no, url, snapshot, sha, *, unit="CNY/ton"):
    """按产量变体（value + unit + severity + conditions）。

    行有两种形态：

    * 5 元组 ``(variant_id, variant_name, severity, value, conditions)`` —— 纯
      ``by_output``（煤炭）；
    * 7 元组 ``(variant_id, variant_name, severity, kind, value, conditions, unit)``
      —— ``kind == "rate"`` 的行**覆写机制**为 ``by_project_cost``（地质勘探/工程
      成本按费用比例计提），其余为 ``by_output``。
    """
    out = []
    for row in rows:
        if len(row) == 5:
            variant_id, variant_name, severity, value, conditions = row
            kind, row_unit = "value", unit
        else:
            variant_id, variant_name, severity, kind, value, conditions, row_unit = row
        node = {
            "clause": clause,
            "conditions": dict(conditions),
            "provenance": _provenance(doc_no, clause, url, snapshot, sha, True),
            "severity": severity,
            "status": "verified",
            "unit": row_unit,
            "variant_id": variant_id,
            "variant_name": variant_name,
        }
        if kind == "rate":
            node["mechanism"] = "by_project_cost"
            node["rate"] = value
        else:
            node["value"] = value
        out.append(node)
    return out


def _rate_variants(clause, rows, doc_no, url, snapshot, sha):
    """按造价/收入比例变体（rate）。"""
    return [
        {
            "clause": clause,
            "provenance": _provenance(doc_no, clause, url, snapshot, sha, True),
            "rate": rate,
            "status": "verified",
            "variant_id": variant_id,
            "variant_name": variant_name,
        }
        for variant_id, variant_name, rate in rows
    ]


def _tiered_variants(clause, rows, doc_no, url, snapshot, sha):
    """超额累退变体（各自独立 segments 阶梯）。"""
    return [
        {
            "clause": clause,
            "provenance": _provenance(doc_no, clause, url, snapshot, sha, True),
            "segments": _segments(clause, segments, doc_no, url, snapshot, sha),
            "status": "verified",
            "variant_id": variant_id,
            "variant_name": variant_name,
        }
        for variant_id, variant_name, segments in rows
    ]


def _industry_entry(industry_id, name, clause, mechanism, implementation,
                    doc_no, url, snapshot, sha, **kwargs):
    """一个行业条目：M2 后全部 verified 落值。"""
    entry = {
        "clause": clause,
        "implementation": implementation,
        "industry_id": industry_id,
        "industry_name": name,
        "mechanism": mechanism,
        "provenance": _provenance(doc_no, clause, url, snapshot, sha, True),
        "status": "verified",
    }
    entry.update(kwargs)
    return entry


def _build_ruleset(ruleset_id, doc_no, doc_title, issuer, issued_date, effective_from,
                   effective_to, supersedes, url, snapshot, sha, industries,
                   coal, noncoal, construction, transport, haz_segments,
                   metallurgy_segments, machinery_segments, fireworks_segments,
                   civil_explosives_segments, weapons, power, oil_gas=None,
                   basis_rules=None):
    entries = []
    for industry_id, name, clause, mechanism, implementation in industries:
        kwargs = {}
        if industry_id == "coal":
            kwargs["variants"] = _output_variants(clause, coal, doc_no, url, snapshot, sha)
        elif industry_id == "noncoal_mine":
            kwargs["variants"] = _output_variants(clause, noncoal, doc_no, url, snapshot, sha)
        elif industry_id == "oil_gas":
            kwargs["variants"] = _output_variants(clause, oil_gas, doc_no, url, snapshot, sha)
        elif industry_id == "construction":
            kwargs["variants"] = _rate_variants(clause, construction, doc_no, url, snapshot, sha)
        elif industry_id == "transport":
            kwargs["variants"] = _rate_variants(clause, transport, doc_no, url, snapshot, sha)
        elif industry_id == "hazardous_chemicals":
            kwargs["segments"] = _segments(clause, haz_segments, doc_no, url, snapshot, sha)
        elif industry_id == "metallurgy":
            kwargs["segments"] = _segments(clause, metallurgy_segments, doc_no, url, snapshot, sha)
        elif industry_id == "machinery":
            kwargs["segments"] = _segments(clause, machinery_segments, doc_no, url, snapshot, sha)
        elif industry_id == "fireworks":
            kwargs["segments"] = _segments(clause, fireworks_segments, doc_no, url, snapshot, sha)
        elif industry_id == "civil_explosives":
            kwargs["segments"] = _segments(clause, civil_explosives_segments, doc_no, url, snapshot, sha)
        elif industry_id == "weapons":
            kwargs["variants"] = _tiered_variants(clause, weapons, doc_no, url, snapshot, sha)
        elif industry_id == "power":
            kwargs["variants"] = _tiered_variants(clause, power, doc_no, url, snapshot, sha)
        entries.append(_industry_entry(
            industry_id, name, clause, mechanism, implementation,
            doc_no, url, snapshot, sha, **kwargs,
        ))
    out = {
        "doc_no": doc_no,
        "doc_title": doc_title,
        "effective_from_year": int(effective_from[:4]),
        "effective_to_year": None if effective_to is None else int(effective_to[:4]),
        "industries": entries,
        "issuer": list(issuer),
        "provenance": _provenance(doc_no, "全文", url, snapshot, sha, True),
        "ruleset_id": ruleset_id,
        "status": "verified",
        "supersedes": supersedes,
    }
    if basis_rules is not None:
        out["basis_rules"] = basis_rules
    return out


#: 依据选择判定规则（第五十二条跨行业经营 / 第五十三条承揽承运净额口径）——
#: 判定所需的**阈值是数据**（不写死在引擎里）：净额口径要求"外购材料和服务成本
#: 高于自客户取得营业收入 85% 以上"。
def _basis_rules(doc_no, url, snapshot, sha) -> dict:
    return {
        "multi_business": {
            "clause": "第五十二条",
            "criterion": (
                "企业同时开展两项及两项以上以营业收入为计提依据的业务，能够按业务类别"
                "分别核算的，按各项业务计提标准分别提取；不能分别核算的，按营业收入占比"
                "最高业务对应的提取标准对各项合计营业收入计提"
            ),
            "provenance": _provenance(doc_no, "第五十二条", url, snapshot, sha, True),
            "status": "verified",
        },
        "net_basis": {
            "clause": "第五十三条",
            "criterion": (
                "企业作为承揽人或承运人向客户提供纳入本办法规定范围的服务，且外购材料"
                "和服务成本高于自客户取得营业收入 85% 以上的，可以将营业收入扣除相关"
                "外购材料和服务成本的净额，作为计提依据"
            ),
            "provenance": _provenance(doc_no, "第五十三条", url, snapshot, sha, True),
            "status": "verified",
            "threshold": "0.85",
        },
    }


def build_spending(doc_no, url, snapshot, sha, rows) -> dict:
    return {
        "doc_no": doc_no,
        "entries": [
            {
                "category": category,
                "clause": clause,
                "criterion": criterion,
                "entry_id": entry_id,
                "industry_id": industry_id,
                "match_keywords": list(keywords),
                "provenance": _provenance(doc_no, clause, url, snapshot, sha, True),
                "status": "verified",
            }
            for entry_id, industry_id, clause, category, criterion, keywords in rows
        ],
        "status": "verified",
    }


def build_progress(doc_no, url, snapshot, sha, rows) -> dict:
    thresholds = []
    for threshold_id, clause, criterion, points, threshold in rows:
        verified = threshold is not None
        node = {
            "clause": clause,
            "criterion": criterion,
            "disclosure_points": list(points),
            "provenance": _provenance(doc_no, clause, url, snapshot, sha, verified),
            "status": "verified" if verified else "pending",
            "threshold": threshold,
            "threshold_id": threshold_id,
        }
        if not verified:
            node["reason"] = criterion
        thresholds.append(node)
    return {
        "doc_no": doc_no,
        "status": "verified" if all(t["status"] == "verified" for t in thresholds) else "pending",
        "thresholds": thresholds,
    }


def generate() -> Dict[str, bytes]:
    """产出全部规则文件，返回 ``{相对路径: 字节}``（供 --check 比对）。"""
    doc_2022 = "财资〔2022〕136号"
    doc_2012 = "财企〔2012〕16号"

    ruleset_2022 = _build_ruleset(
        "财资-2022-136", doc_2022, "企业安全生产费用提取和使用管理办法",
        ("财政部", "应急部"), "2022-11-21", "2022-11-21", None, "财企-2012-16",
        URL_2022, SNAPSHOT_2022, SHA_2022_DOCX, INDUSTRIES_2022,
        COAL_2022, NONCOAL_2022, CONSTRUCTION_2022, TRANSPORT_2022, HAZ_2022_SEGMENTS,
        METALLURGY_2022_SEGMENTS, MACHINERY_2022_SEGMENTS, FIREWORKS_2022_SEGMENTS,
        CIVIL_EXPLOSIVES_2022_SEGMENTS, WEAPONS_2022,
        (
            ("power_generation", "电力生产企业", POWER_GENERATION_SEGMENTS),
            ("power_supply", "电力供应企业", POWER_SUPPLY_SEGMENTS),
        ),
        oil_gas=OIL_GAS_2022,
        basis_rules=_basis_rules(doc_2022, URL_2022, SNAPSHOT_2022, SHA_2022_DOCX),
    )
    ruleset_2012 = _build_ruleset(
        "财企-2012-16", doc_2012, "企业安全生产费用提取和使用管理办法",
        ("财政部", "国家安全生产监督管理总局"), "2012-02-14", "2012-02-14",
        "2022-11-20", None,
        URL_2012, SNAPSHOT_2012, SHA_2012_HTM, INDUSTRIES_2012,
        COAL_2012, NONCOAL_2012, CONSTRUCTION_2012, TRANSPORT_2012, HAZ_2012_SEGMENTS,
        METALLURGY_2012_SEGMENTS, MACHINERY_2012_SEGMENTS, FIREWORKS_2012_SEGMENTS,
        CIVIL_EXPLOSIVES_2022_SEGMENTS, WEAPONS_2012,
        None,
        oil_gas=None,
    )

    files: Dict[str, bytes] = {}

    def _add(rel: str, payload) -> None:
        text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        files[rel] = text.encode("utf-8")

    _add("units.json", {"schema_version": SCHEMA_VERSION, "factors": UNITS})
    _add("财资-2022-136/ruleset.json", ruleset_2022)
    _add("财资-2022-136/spending.json", build_spending(doc_2022, URL_2022, SNAPSHOT_2022, SHA_2022_DOCX, SPENDING_2022))
    _add("财资-2022-136/progress.json", build_progress(doc_2022, URL_2022, SNAPSHOT_2022, SHA_2022_DOCX, PROGRESS_2022))
    _add("财企-2012-16/ruleset.json", ruleset_2012)
    _add("财企-2012-16/spending.json", build_spending(doc_2012, URL_2012, SNAPSHOT_2012, SHA_2012_HTM, SPENDING_2012))
    _add("财企-2012-16/progress.json", build_progress(doc_2012, URL_2012, SNAPSHOT_2012, SHA_2012_HTM, PROGRESS_2012))

    # manifest 最后组装（登记各文件 sha256）
    manifest = {
        "benchmark_thresholds": {
            "dual_version": {"min_consistency": 1.0},
            "synthetic_ledger": {"min_truth_match": 1.0},
            "tiered_boundary": {"max_false_positive": 0, "min_pass_ratio": 1.0},
        },
        "generated_by": "tools/gen_rulesets.py",
        "rulesets": [
            {
                "dir": "财资-2022-136",
                "doc_no": doc_2022,
                "doc_title": "企业安全生产费用提取和使用管理办法",
                "effective_from": "2022-11-21",
                "effective_to": None,
                "files": {
                    name: hashlib.sha256(files["财资-2022-136/%s" % name]).hexdigest()
                    for name in ("ruleset.json", "spending.json", "progress.json")
                },
                "ruleset_id": "财资-2022-136",
                "status": "verified",
            },
            {
                "dir": "财企-2012-16",
                "doc_no": doc_2012,
                "doc_title": "企业安全生产费用提取和使用管理办法",
                "effective_from": "2012-02-14",
                "effective_to": "2022-11-20",
                "files": {
                    name: hashlib.sha256(files["财企-2012-16/%s" % name]).hexdigest()
                    for name in ("ruleset.json", "spending.json", "progress.json")
                },
                "ruleset_id": "财企-2012-16",
                "status": "verified",
            },
        ],
        "schema_version": SCHEMA_VERSION,
    }
    _add("manifest.json", manifest)
    return files


def write_all(files: Dict[str, bytes]) -> None:
    for rel, payload in sorted(files.items()):
        path = DATA_DIR / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)


def check() -> int:
    """校验"再生成逐字节一致"；不一致 → 退出码 1。"""
    files = generate()
    mismatched: List[str] = []
    for rel, payload in sorted(files.items()):
        path = DATA_DIR / rel
        if not path.is_file():
            mismatched.append("%s（缺失）" % rel)
            continue
        if path.read_bytes() != payload:
            mismatched.append(rel)
    if mismatched:
        print("FROZEN_RULESETS_DRIFT: %s" % ", ".join(mismatched))
        return 1
    print("FROZEN_RULESETS_OK（%d 份文件逐字节一致）" % len(files))
    return 0


def main(argv=None) -> int:
    from safefee._stdio import _ensure_utf8_stdio

    _ensure_utf8_stdio()
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--check" in argv:
        return check()
    files = generate()
    write_all(files)
    print("已生成 %d 份规则文件 → %s" % (len(files), DATA_DIR))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    raise SystemExit(main())
