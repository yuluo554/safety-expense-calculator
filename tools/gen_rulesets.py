"""规则包生成器 —— **唯一写入者**（冻结产物禁手改）。

产出 ``data/rules/`` 全部文件：

* ``manifest.json`` —— 规则集索引 + **基准门槛**（数据非代码）+ 各文件 sha256；
* ``units.json`` —— 定义性单位换算（**非政策数值**，豁免零字面量门禁）；
* ``<ruleset>/ruleset.json`` —— 计提标准（十二节 / 九类）；
* ``<ruleset>/spending.json`` —— 支出范围条目（首期四行业）；
* ``<ruleset>/progress.json`` —— 使用进度门槛。

**M0 初态纪律**：计提标准**全部条目 ``status="pending"``、``value``/``rate`` 为
``null``**——**未挂原文核对不得落值**；M1 逐条核对后由本生成器重新产出。
因此 M0 的 ``calc``/``check``/``progress`` 三作用域门控**必然拦截**，这是**预期行为**
（门控生效的证据），不是缺陷。

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
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "rules"

SCHEMA_VERSION = 1

#: 2022 版十二节（节次与条款号来自 136 号办法条文结构；**数值留 M1 核对后落库**）
INDUSTRIES_2022 = [
    ("coal", "煤炭生产", "第七条", "by_output", "in_scope"),
    ("noncoal_mine", "非煤矿山开采", "第十条", "by_revenue_tiered", "deferred"),
    ("oil_gas", "石油天然气开采", "第十一条", "by_revenue_tiered", "deferred"),
    ("construction", "建设工程施工", "第十七条", "by_project_cost", "in_scope"),
    ("hazardous_chemicals", "危险品生产与储存", "第二十一条", "by_revenue_tiered", "in_scope"),
    ("transport", "交通运输", "第二十四条", "by_revenue_tiered", "deferred"),
    ("metallurgy", "冶金", "第二十六条", "by_revenue_tiered", "deferred"),
    ("machinery", "机械制造", "第二十七条", "by_revenue_tiered", "deferred"),
    ("fireworks", "烟花爆竹生产", "第二十九条", "by_revenue_tiered", "deferred"),
    ("civil_explosives", "民用爆炸物品生产", "第三十二条", "by_revenue_tiered", "deferred"),
    ("weapons", "武器装备研制生产与试验", "第三十六条", "by_revenue_tiered", "deferred"),
    ("power", "电力生产与供应", "第四十三条", "by_revenue_tiered", "in_scope"),
]

#: 2012 版九类（旧版，历史年度对照用）
INDUSTRIES_2012 = [
    ("coal", "煤炭生产", "第七条", "by_output", "in_scope"),
    ("noncoal_mine", "非煤矿山开采", "第九条", "by_revenue_tiered", "deferred"),
    ("oil_gas", "石油天然气开采", "第十条", "by_revenue_tiered", "deferred"),
    ("construction", "建设工程施工", "第十三条", "by_project_cost", "in_scope"),
    ("hazardous_chemicals", "危险品生产与储存", "第十六条", "by_revenue_tiered", "in_scope"),
    ("transport", "交通运输", "第十八条", "by_revenue_tiered", "deferred"),
    ("metallurgy", "冶金", "第二十条", "by_revenue_tiered", "deferred"),
    ("machinery", "机械制造", "第二十一条", "by_revenue_tiered", "deferred"),
    ("fireworks", "烟花爆竹生产", "第二十三条", "by_revenue_tiered", "deferred"),
]

#: 煤炭矿井变体（**数值留 M1 核对后落库**）
COAL_VARIANTS = [
    ("coal_outburst_rockburst", "煤（岩）与瓦斯（二氧化碳）突出矿井、冲击地压矿井", 4, "第七条",
     {"hazards": ["gas_outburst", "rockburst"]}),
    ("coal_high_gas", "高瓦斯矿井", 3, "第七条", {"mine_type": "high_gas"}),
    ("coal_other_underground", "其他井工矿井", 2, "第七条", {"mine_type": "other_underground"}),
    ("coal_opencast", "露天矿井", 1, "第七条", {"mine_type": "opencast"}),
]

#: 建设工程工程类别（**数值留 M1 核对后落库**）
CONSTRUCTION_VARIANTS = [
    ("mine_engineering", "矿山工程", "第十七条"),
    ("railway_building_rail_transit", "铁路、房屋建筑工程、城市轨道交通", "第十七条"),
    ("water_power_electric", "水利水电工程、电力工程", "第十七条"),
    ("smelting_mechanical_chemical_telecom", "冶炼工程、机电安装工程、化工石油工程、通信工程", "第十七条"),
    ("municipal_port_highway", "市政公用工程、港口与航道工程、公路工程", "第十七条"),
]

#: 支出范围条目（首期四行业；**criterion 为要点引用，非全文转载**）
SPENDING_ENTRIES = [
    ("SP-COAL-01", "coal", "第八条", "允许", "煤矿安全生产改造与重大隐患治理支出",
     ["安全改造", "隐患治理"]),
    ("SP-COAL-02", "coal", "第八条", "允许", "煤矿安全生产标准化建设与安全设备购置",
     ["安全生产标准化", "安全设备"]),
    ("SP-COAL-99", "coal", "第五条", "禁止", "不得侵占、挪用安全生产费用（红线）",
     ["挪用", "侵占"]),
    ("SP-CONST-01", "construction", "第十八条", "允许", "建设工程安全生产防护与文明施工支出",
     ["安全防护", "文明施工"]),
    ("SP-CONST-99", "construction", "第五条", "禁止", "不得以安全生产费用替代其他资金渠道应当列支的支出（红线）",
     ["替代其他资金"]),
    ("SP-HAZ-01", "hazardous_chemicals", "第二十二条", "允许", "危险品安全生产条件改善与应急救援器材支出",
     ["安全生产条件", "应急救援器材"]),
    ("SP-HAZ-99", "hazardous_chemicals", "第五条", "禁止", "不得侵占、挪用安全生产费用（红线）",
     ["挪用", "侵占"]),
    ("SP-POWER-01", "power", "第四十四条", "允许", "电力生产安全防护与并网安全支出",
     ["安全防护", "并网安全"]),
    ("SP-POWER-99", "power", "第五条", "禁止", "不得侵占、挪用安全生产费用（红线）",
     ["挪用", "侵占"]),
]

#: 进度门槛（**数值留 M1 核对后落库**）
PROGRESS_THRESHOLDS = [
    ("default", "第五十一条", "当年实际使用不足年度应计提金额规定比例须披露并提交书面说明",
     ["说明本年度实际使用情况与未达比例原因", "列示下一年度整改与使用计划",
      "说明结余资金结转安排"]),
]

UNITS = {
    "CNY": "1",
    "CNY10k": "10000",
    "CNY100m": "100000000",
    "ton": "1",
}


def _provenance(doc_no: str, clause: str, url: str, verified: bool = False):
    """条目出处（**无出处不得落库**；未核对时 fetched_at 为 null）。"""
    return {
        "doc_no": doc_no,
        "clause": clause,
        "url": url,
        "fetched_at": "2026-10-14" if verified else None,
        "verified": verified,
    }


def _industry_entry(industry_id, name, clause, mechanism, implementation, doc_no, url):
    entry = {
        "industry_id": industry_id,
        "industry_name": name,
        "clause": clause,
        "implementation": implementation,
        "mechanism": mechanism,
        "status": "pending",
        "provenance": _provenance(doc_no, clause, url),
    }
    if mechanism == "by_output" and industry_id == "coal":
        entry["variants"] = [
            {
                "variant_id": variant_id,
                "variant_name": variant_name,
                "severity": severity,
                "clause": variant_clause,
                "conditions": conditions,
                "unit": "CNY/ton",
                "value": None,
                "status": "pending",
                "provenance": _provenance(doc_no, variant_clause, url),
            }
            for variant_id, variant_name, severity, variant_clause, conditions in COAL_VARIANTS
        ]
    elif mechanism == "by_project_cost":
        entry["variants"] = [
            {
                "variant_id": variant_id,
                "variant_name": variant_name,
                "clause": variant_clause,
                "rate": None,
                "status": "pending",
                "provenance": _provenance(doc_no, variant_clause, url),
            }
            for variant_id, variant_name, variant_clause in CONSTRUCTION_VARIANTS
        ]
    elif mechanism == "by_revenue_tiered":
        entry["segments"] = [
            {
                "lower": lower,
                "upper": upper,
                "rate": None,
                "clause": clause,
                "status": "pending",
                "provenance": _provenance(doc_no, clause, url),
            }
            for lower, upper in _tier_bounds(industry_id)
        ]
    return entry


def _tier_bounds(industry_id: str):
    """分段边界（**边界是结构，费率是数值**——M0 只落边界、费率留 M1）。

    边界口径：段区间 ``[lower, upper)``，恰好等于分段点归下一段（见 plan/04 §4）。
    """
    if industry_id == "hazardous_chemicals":
        return [("0", "10000000"), ("10000000", "100000000"),
                ("100000000", "1000000000"), ("1000000000", None)]
    if industry_id == "power":
        return [("0", "10000000"), ("10000000", "100000000"),
                ("100000000", "500000000"), ("500000000", "1000000000"),
                ("1000000000", "5000000000"), ("5000000000", None)]
    return [("0", "10000000"), ("10000000", "100000000"),
            ("100000000", "1000000000"), ("1000000000", None)]


def build_ruleset(ruleset_id, doc_no, doc_title, issuer, issued_date, effective_from,
                  effective_to, supersedes, url, industries):
    return {
        "ruleset_id": ruleset_id,
        "doc_no": doc_no,
        "doc_title": doc_title,
        "issuer": list(issuer),
        "issued_date": issued_date,
        "effective_from_year": int(effective_from[:4]),
        "effective_to_year": None if effective_to is None else int(effective_to[:4]),
        "supersedes": supersedes,
        "status": "pending",
        "provenance": _provenance(doc_no, "全文", url),
        "industries": [
            _industry_entry(*item, doc_no, url) for item in industries
        ],
    }


def build_spending(doc_no, url):
    return {
        "doc_no": doc_no,
        "status": "pending",
        "entries": [
            {
                "entry_id": entry_id,
                "industry_id": industry_id,
                "clause": clause,
                "category": category,
                "criterion": criterion,
                "match_keywords": list(keywords),
                "status": "pending",
                "provenance": _provenance(doc_no, clause, url),
            }
            for entry_id, industry_id, clause, category, criterion, keywords in SPENDING_ENTRIES
        ],
    }


def build_progress(doc_no, url):
    return {
        "doc_no": doc_no,
        "status": "pending",
        "thresholds": [
            {
                "threshold_id": threshold_id,
                "clause": clause,
                "criterion": criterion,
                "threshold": None,
                "disclosure_points": list(points),
                "status": "pending",
                "provenance": _provenance(doc_no, clause, url),
            }
            for threshold_id, clause, criterion, points in PROGRESS_THRESHOLDS
        ],
    }


def _write_json(path: Path, payload) -> None:
    """确定性落盘：``write_bytes`` + 固定换行 + 排序键（不写 CR）。"""
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate() -> Dict[str, bytes]:
    """产出全部规则文件，返回 ``{相对路径: 字节}``（供 --check 比对）。"""
    doc_2022 = "财资〔2022〕136号"
    doc_2012 = "财企〔2012〕16号"
    url_2022 = "https://www.gov.cn/zhengce/zhengceku/2022-12/14/content_5731902.htm"
    url_2012 = "https://www.gov.cn/gongbao/content/2012/content_2177022.htm"

    ruleset_2022 = build_ruleset(
        "财资-2022-136", doc_2022, "企业安全生产费用提取和使用管理办法",
        ("财政部", "应急部"), "2022-11-21", "2022-11-21", None, "财企-2012-16",
        url_2022, INDUSTRIES_2022,
    )
    ruleset_2012 = build_ruleset(
        "财企-2012-16", doc_2012, "企业安全生产费用提取和使用管理办法",
        ("财政部", "国家安全生产监督管理总局"), "2012-02-14", "2012-02-14",
        "2022-11-20", None, url_2012, INDUSTRIES_2012,
    )

    files: Dict[str, bytes] = {}

    def _add(rel: str, payload) -> None:
        text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        files[rel] = text.encode("utf-8")

    _add("units.json", {"schema_version": SCHEMA_VERSION, "factors": UNITS})
    _add("财资-2022-136/ruleset.json", ruleset_2022)
    _add("财资-2022-136/spending.json", build_spending(doc_2022, url_2022))
    _add("财资-2022-136/progress.json", build_progress(doc_2022, url_2022))
    _add("财企-2012-16/ruleset.json", ruleset_2012)
    _add("财企-2012-16/spending.json", build_spending(doc_2012, url_2012))
    _add("财企-2012-16/progress.json", build_progress(doc_2012, url_2012))

    # manifest 最后组装（登记各文件 sha256）
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "tools/gen_rulesets.py",
        "rulesets": [
            {
                "ruleset_id": "财资-2022-136",
                "dir": "财资-2022-136",
                "doc_no": doc_2022,
                "doc_title": "企业安全生产费用提取和使用管理办法",
                "effective_from": "2022-11-21",
                "effective_to": None,
                "status": "pending",
                "files": {
                    name: hashlib.sha256(files["财资-2022-136/%s" % name]).hexdigest()
                    for name in ("ruleset.json", "spending.json", "progress.json")
                },
            },
            {
                "ruleset_id": "财企-2012-16",
                "dir": "财企-2012-16",
                "doc_no": doc_2012,
                "doc_title": "企业安全生产费用提取和使用管理办法",
                "effective_from": "2012-02-14",
                "effective_to": "2022-11-20",
                "status": "pending",
                "files": {
                    name: hashlib.sha256(files["财企-2012-16/%s" % name]).hexdigest()
                    for name in ("ruleset.json", "spending.json", "progress.json")
                },
            },
        ],
        "benchmark_thresholds": {
            "tiered_boundary": {"min_pass_ratio": 1.0, "max_false_positive": 0},
            "dual_version": {"min_consistency": 1.0},
            "synthetic_ledger": {"min_truth_match": 1.0},
        },
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
