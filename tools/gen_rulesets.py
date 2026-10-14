"""规则包生成器 —— **唯一写入者**（冻结产物禁手改）。

产出 ``data/rules/`` 全部文件：

* ``manifest.json`` —— 规则集索引 + **基准门槛**（数据非代码）+ 各文件 sha256；
* ``units.json`` —— 定义性单位换算（**非政策数值**，豁免零字面量门禁）；
* ``<ruleset>/ruleset.json`` —— 计提标准（十二节 / 九类）；
* ``<ruleset>/spending.json`` —— 支出范围条目（首期四行业）；
* ``<ruleset>/progress.json`` —— 使用进度门槛。

**M1 数据状态**：计提标准逐条挂官方原文核对后落值（抓取与核对记录见
``data/README.md`` §二与 ``data/knowledge/``）：

* 2022 版（财资〔2022〕136号）：**煤炭（第七条）/ 建设工程（第十七条）/
  危险品（第二十一条）/ 电力（第四十三条）** 四节逐条核对 → ``status="verified"``
  并落值；其余八节为**首期范围外（deferred，不进入计算路径）**，条款位置已定位但
  数值不落库（``status="pending"``、``value/rate=null``，附原因）；
* 2012 版（财企〔2012〕16号）：**煤炭（第五条）/ 建设工程（第七条）/
  危险品（第八条）** 三类逐条核对落值；其余六类同上留 ``pending``；
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
    ("noncoal_mine", "非煤矿山开采", "第十条", "by_output", "deferred"),
    ("oil_gas", "石油天然气开采", "第十四条", "by_revenue_tiered", "deferred"),
    ("construction", "建设工程施工", "第十七条", "by_project_cost", "in_scope"),
    ("hazardous_chemicals", "危险品生产与储存", "第二十一条", "by_revenue_tiered", "in_scope"),
    ("transport", "交通运输", "第二十四条", "by_revenue_tiered", "deferred"),
    ("metallurgy", "冶金", "第二十七条", "by_revenue_tiered", "deferred"),
    ("machinery", "机械制造", "第三十条", "by_revenue_tiered", "deferred"),
    ("fireworks", "烟花爆竹生产", "第三十三条", "by_revenue_tiered", "deferred"),
    ("civil_explosives", "民用爆炸物品生产", "第三十六条", "by_revenue_tiered", "deferred"),
    ("weapons", "武器装备研制生产与试验", "第三十九条", "by_revenue_tiered", "deferred"),
    ("power", "电力生产与供应", "第四十三条", "by_revenue_tiered", "in_scope"),
]

#: 2012 版九类（旧版，历史年度对照用；**石油天然气在 2012 版并入非煤矿山第六条**，
#: 武器装备为第十三条——均对国务院公报原文核对）
INDUSTRIES_2012 = [
    ("coal", "煤炭生产", "第五条", "by_output", "in_scope"),
    ("noncoal_mine", "非煤矿山开采", "第六条", "by_output", "deferred"),
    ("construction", "建设工程施工", "第七条", "by_project_cost", "in_scope"),
    ("hazardous_chemicals", "危险品生产与储存", "第八条", "by_revenue_tiered", "in_scope"),
    ("transport", "交通运输", "第九条", "by_revenue_tiered", "deferred"),
    ("metallurgy", "冶金", "第十条", "by_revenue_tiered", "deferred"),
    ("machinery", "机械制造", "第十一条", "by_revenue_tiered", "deferred"),
    ("fireworks", "烟花爆竹生产", "第十二条", "by_revenue_tiered", "deferred"),
    ("weapons", "武器装备研制生产与试验", "第十三条", "by_revenue_tiered", "deferred"),
]

PENDING_VALUE_NOTE_2022 = (
    "首期范围外（deferred，不进入计算路径）：条款与节次已对原文定位"
    "（data/knowledge/raw/136-body.paragraphs.txt），数值落库与机制重定型排期 M2"
)
PENDING_VALUE_NOTE_2012 = (
    "首期范围外（deferred，不进入计算路径）：条款与节次已对原文定位"
    "（data/knowledge/raw/2012-gongbao.txt），数值落库与机制重定型排期 M2"
)

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

#: 未落值行业的分段边界占位（**边界是结构，费率是数值**——pending 段 rate=null）
PLACEHOLDER_TIERS_4 = [
    ("0", "10000000"), ("10000000", "100000000"),
    ("100000000", "1000000000"), ("1000000000", None),
]
PLACEHOLDER_TIERS_6 = [
    ("0", "10000000"), ("10000000", "100000000"), ("100000000", "500000000"),
    ("500000000", "1000000000"), ("1000000000", "5000000000"), ("5000000000", None),
]

#: 支出范围条目（要点引用，非全文转载；红线条款 2022 版=第四条第三项、2012 版=第二十七条）
SPENDING_2022 = [
    ("SP-COAL-01", "coal", "第八条", "允许", "煤矿安全生产改造和重大事故隐患治理支出（第八条第三项要点）",
     ["安全改造", "隐患治理"]),
    ("SP-COAL-02", "coal", "第八条", "允许", "安全生产检查、咨询、标准化建设支出（第八条第六项要点）",
     ["标准化"]),
    ("SP-COAL-99", "coal", "第四条", "禁止", "专项核算、不得挤占挪用安全生产费用（红线，第四条第三项）",
     ["挤占", "挪用"]),
    ("SP-CONST-01", "construction", "第十九条", "允许", "完善、改造和维护安全防护设施设备支出（第十九条第一项要点）",
     ["安全防护"]),
    ("SP-CONST-99", "construction", "第四条", "禁止", "专项核算、不得挤占挪用安全生产费用（红线，第四条第三项）",
     ["挤占", "挪用"]),
    ("SP-HAZ-01", "hazardous_chemicals", "第二十二条", "允许", "完善安全防护设施设备与配备维护应急救援器材支出（第二十二条第一、二项要点）",
     ["安全防护", "应急救援器材"]),
    ("SP-HAZ-99", "hazardous_chemicals", "第四条", "禁止", "专项核算、不得挤占挪用安全生产费用（红线，第四条第三项）",
     ["挤占", "挪用"]),
    ("SP-POWER-01", "power", "第四十四条", "允许", "发电输电变配电设备设施安全防护与安全监控支出（第四十四条第一项要点）",
     ["安全防护", "安全监控"]),
    ("SP-POWER-99", "power", "第四条", "禁止", "专项核算、不得挤占挪用安全生产费用（红线，第四条第三项）",
     ["挤占", "挪用"]),
]

#: 2012 版支出范围（2012 版无电力行业类别 → 不登记电力条目）
SPENDING_2012 = [
    ("SP-COAL-01", "coal", "第十七条", "允许", "煤矿安全生产改造和重大隐患治理支出（第十七条第二项要点）",
     ["安全改造", "隐患治理"]),
    ("SP-COAL-02", "coal", "第十七条", "允许", "安全生产检查、评价、咨询、标准化建设支出（第十七条第五项要点）",
     ["标准化"]),
    ("SP-COAL-99", "coal", "第二十七条", "禁止", "专户核算、不得挤占挪用安全费用（红线，第二十七条）",
     ["挤占", "挪用"]),
    ("SP-CONST-01", "construction", "第十九条", "允许", "完善、改造和维护安全防护设施设备支出（第十九条第一项要点）",
     ["安全防护"]),
    ("SP-CONST-99", "construction", "第二十七条", "禁止", "专户核算、不得挤占挪用安全费用（红线，第二十七条）",
     ["挤占", "挪用"]),
    ("SP-HAZ-01", "hazardous_chemicals", "第二十条", "允许", "完善安全防护设施设备与配备维护应急救援器材支出（第二十条第一、二项要点）",
     ["安全防护", "应急救援器材"]),
    ("SP-HAZ-99", "hazardous_chemicals", "第二十七条", "禁止", "专户核算、不得挤占挪用安全费用（红线，第二十七条）",
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


def _segments(clause: str, rows, verified: bool, note: str, doc_no: str, url: str,
              snapshot: str, sha: str) -> List[dict]:
    out = []
    for lower, upper, rate in rows:
        item = {
            "clause": clause,
            "lower": lower,
            "provenance": _provenance(doc_no, clause, url, snapshot, sha, verified),
            "rate": rate if verified else None,
            "status": "verified" if verified else "pending",
            "upper": upper,
        }
        if not verified:
            item["reason"] = note
        out.append(item)
    return out


def _industry_entry(industry_id, name, clause, mechanism, implementation,
                    doc_no, url, snapshot, sha, *, coal_variants=None,
                    construction_variants=None, segments=None,
                    power_variants=None, pending_note=None):
    """一个行业条目：给了核对数据即 verified 落值，否则 pending（value/rate=null）。"""
    verified = pending_note is None
    entry = {
        "clause": clause,
        "implementation": implementation,
        "industry_id": industry_id,
        "industry_name": name,
        "mechanism": mechanism,
        "provenance": _provenance(doc_no, clause, url, snapshot, sha, verified),
        "status": "verified" if verified else "pending",
    }
    if not verified:
        entry["reason"] = pending_note
        entry["value"] = None
        entry["rate"] = None

    if coal_variants is not None:
        entry["variants"] = [
            {
                "clause": clause,
                "conditions": dict(conditions),
                "provenance": _provenance(doc_no, clause, url, snapshot, sha, verified),
                "severity": severity,
                "status": "verified" if verified else "pending",
                "unit": "CNY/ton",
                "value": value if verified else None,
                "variant_id": variant_id,
                "variant_name": variant_name,
            }
            for variant_id, variant_name, severity, value, conditions in coal_variants
        ]
    if construction_variants is not None:
        entry["variants"] = [
            {
                "clause": clause,
                "provenance": _provenance(doc_no, clause, url, snapshot, sha, verified),
                "rate": rate if verified else None,
                "status": "verified" if verified else "pending",
                "variant_id": variant_id,
                "variant_name": variant_name,
            }
            for variant_id, variant_name, rate in construction_variants
        ]
    if power_variants is not None:
        entry["variants"] = [
            {
                "clause": clause,
                "provenance": _provenance(doc_no, clause, url, snapshot, sha, verified),
                "segments": segments,
                "status": "verified" if verified else "pending",
                "variant_id": variant_id,
                "variant_name": variant_name,
            }
            for variant_id, variant_name, segments in power_variants
        ]
    if segments is not None:
        entry["segments"] = segments
    if mechanism == "by_revenue_tiered" and "segments" not in entry and "variants" not in entry:
        # 未落值行业的分段结构占位（费率留空）
        rows = PLACEHOLDER_TIERS_6 if industry_id == "power" else PLACEHOLDER_TIERS_4
        entry["segments"] = [
            {
                "clause": clause,
                "lower": lower,
                "provenance": _provenance(doc_no, clause, url, snapshot, sha, False),
                "rate": None,
                "reason": pending_note,
                "status": "pending",
                "upper": upper,
            }
            for lower, upper in rows
        ]
    return entry


def _build_ruleset(ruleset_id, doc_no, doc_title, issuer, issued_date, effective_from,
                   effective_to, supersedes, url, snapshot, sha, industries,
                   pending_note, coal, construction, haz_segments, power):
    entries = []
    for industry_id, name, clause, mechanism, implementation in industries:
        kwargs = {}
        if industry_id == "coal":
            kwargs["coal_variants"] = coal
        elif industry_id == "construction":
            kwargs["construction_variants"] = construction
        elif industry_id == "hazardous_chemicals":
            kwargs["segments"] = _segments(clause, haz_segments, True, "", doc_no, url, snapshot, sha)
        elif industry_id == "power":
            kwargs["power_variants"] = power
        if implementation == "deferred":
            kwargs["pending_note"] = pending_note
        entries.append(_industry_entry(
            industry_id, name, clause, mechanism, implementation,
            doc_no, url, snapshot, sha, **kwargs,
        ))
    return {
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


def _write_json(path: Path, payload) -> None:
    """确定性落盘：``write_bytes`` + 固定换行 + 排序键（不写 CR）。"""
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def generate() -> Dict[str, bytes]:
    """产出全部规则文件，返回 ``{相对路径: 字节}``（供 --check 比对）。"""
    doc_2022 = "财资〔2022〕136号"
    doc_2012 = "财企〔2012〕16号"

    ruleset_2022 = _build_ruleset(
        "财资-2022-136", doc_2022, "企业安全生产费用提取和使用管理办法",
        ("财政部", "应急部"), "2022-11-21", "2022-11-21", None, "财企-2012-16",
        URL_2022, SNAPSHOT_2022, SHA_2022_DOCX, INDUSTRIES_2022,
        PENDING_VALUE_NOTE_2022, COAL_2022, CONSTRUCTION_2022, HAZ_2022_SEGMENTS,
        (
            ("power_generation", "电力生产企业",
             _segments("第四十三条", POWER_GENERATION_SEGMENTS, True, "", doc_2022,
                       URL_2022, SNAPSHOT_2022, SHA_2022_DOCX)),
            ("power_supply", "电力供应企业",
             _segments("第四十三条", POWER_SUPPLY_SEGMENTS, True, "", doc_2022,
                       URL_2022, SNAPSHOT_2022, SHA_2022_DOCX)),
        ),
    )
    ruleset_2012 = _build_ruleset(
        "财企-2012-16", doc_2012, "企业安全生产费用提取和使用管理办法",
        ("财政部", "国家安全生产监督管理总局"), "2012-02-14", "2012-02-14",
        "2022-11-20", None,
        URL_2012, SNAPSHOT_2012, SHA_2012_HTM, INDUSTRIES_2012,
        PENDING_VALUE_NOTE_2012, COAL_2012, CONSTRUCTION_2012, HAZ_2012_SEGMENTS, None,
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
