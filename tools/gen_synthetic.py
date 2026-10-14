"""合成企业台账 + 真值库生成器（确定性 RNG，固定 seed）。

**确定性纪律**：禁 stdlib ``random``、禁 ``set`` 迭代序、禁系统时钟——自研
``splitmix64``（stdlib ``random`` 不承诺跨版本序列一致）。落盘产物**无时间戳**，
两次运行/构建**逐字节一致**并配守门测试。

**M1 范围**：计提标准逐条挂原文核对落值后（见 ``tools/gen_rulesets.py``），
本生成器产出真值库：

* ``cases/`` —— 三类机制算例 + 恰好等于分段点边界档案（±0.01 邻域）+ 元/万元
  错配档案 + 双版本对照真值（同一对象按 136 号与 2012 版各一套期望）；
* ``negatives/`` —— 误报对照集：显式声明"应零命中"的干净档案与"应降级为
  warning"的单位换算档案（基准层只读声明，不自行挑选）。

**双重记账**（防"真值抄引擎"）：期望金额由**独立计算路径**得出——生成器只用
规则包 JSON 里的原始数值做一次性公式演算（分段 = Σ 边界内分段 × 费率），**不调
用 ``safefee`` 引擎**；基准层再用引擎重算对账。两边一致才叫达标。

用法::

    python tools/gen_synthetic.py
    python tools/gen_synthetic.py --check
"""

import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "truth"
RULES_DIR = ROOT / "data" / "rules"

MASK64 = (1 << 64) - 1
SEED = 0x5A17FEE0A11CE5


def splitmix64(state: int) -> "tuple[int, int]":
    """确定性 RNG（自研）：返回 ``(next_state, value)``。"""
    state = (state + 0x9E3779B97F4A7C15) & MASK64
    z = state
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    return state, z ^ (z >> 31)


Q2 = Decimal("0.01")


def _q2(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Q2, rounding=ROUND_HALF_UP)


def _load_ruleset(ruleset_dir: str) -> dict:
    path = RULES_DIR / ruleset_dir / "ruleset.json"
    return json.loads(path.read_bytes().decode("utf-8"), parse_float=Decimal)


def _industry(ruleset: dict, industry_id: str) -> dict:
    for item in ruleset["industries"]:
        if item["industry_id"] == industry_id:
            return item
    raise KeyError("规则包 %s 无行业 %s" % (ruleset.get("ruleset_id"), industry_id))


def _variant(industry: dict, variant_id: str) -> Optional[dict]:
    for item in industry.get("variants") or []:
        if item["variant_id"] == variant_id:
            return item
    return None


def _accrual_direct(ruleset: dict, industry_id: str, basis: Decimal,
                    variant_id: Optional[str] = None) -> Tuple[Decimal, dict]:
    """**独立计算路径**：只用规则包 JSON 原始数值做一次性演算（不走 safefee 引擎）。

    返回 ``(两位小数金额, 期望附注)``——附注含机制、条款、变体名，供真值记录引用。
    """
    industry = _industry(ruleset, industry_id)
    mechanism = industry["mechanism"]
    node = (_variant(industry, variant_id) if variant_id else industry) or industry

    if mechanism == "by_output":
        amount = _q2(Decimal(str(node["value"])) * basis)
        return amount, {"mechanism": mechanism, "clause": str(node["clause"]),
                        "variant_name": node.get("variant_name")}
    if mechanism == "by_project_cost":
        amount = _q2(Decimal(str(node["rate"])) * basis)
        return amount, {"mechanism": mechanism, "clause": str(node["clause"]),
                        "variant_name": node.get("variant_name")}

    # by_revenue_tiered：Σ 段内依据量 × 段费率（边界口径 [lower, upper)）
    segments = node["segments"] if "segments" in node else industry["segments"]
    total = Decimal(0)
    for seg in sorted(segments, key=lambda s: Decimal(str(s["lower"]))):
        lower = Decimal(str(seg["lower"]))
        upper = None if seg["upper"] is None else Decimal(str(seg["upper"]))
        if basis <= lower:
            break
        base = basis - lower
        if upper is not None:
            base = min(base, upper - lower)
        total += _q2(base * Decimal(str(seg["rate"])))
    return _q2(total), {"mechanism": mechanism, "clause": str(node.get("clause") or industry["clause"]),
                        "variant_name": node.get("variant_name")}


def _enterprise(name: str, code: str, industry_id: str, year: int, basis_kind: str,
                basis_value: str, basis_unit: str, variant_id: Optional[str] = None) -> dict:
    payload = {
        "basis_kind": basis_kind,
        "basis_unit": basis_unit,
        "basis_value": basis_value,
        "enterprise_id": code,
        "enterprise_name": name,
        "industry_id": industry_id,
        "year": year,
    }
    if variant_id:
        payload["variant_id"] = variant_id
    return payload


def _case(case_id: str, ruleset_id: str, enterprise: dict, amount: Decimal,
          accrual_note: dict, note: str, **extra) -> dict:
    expect = {
        "amount": str(amount),
        "mechanism": accrual_note["mechanism"],
        "also_expect": {"clause": accrual_note["clause"]},
    }
    expect.update(extra)
    return {
        "case_id": case_id,
        "enterprise": enterprise,
        "expect": expect,
        "note": note,
        "ruleset_id": ruleset_id,
    }


def _negative(negative_id: str, ruleset_id: str, enterprise: dict, expect: dict,
              note: str) -> dict:
    return {
        "enterprise": enterprise,
        "expect": expect,
        "negative_id": negative_id,
        "note": note,
        "ruleset_id": ruleset_id,
    }


def _segment_bounds(industry: dict) -> List[Decimal]:
    """从规则包分段结构推导全部分段点（**不复制字面量**——数值只活在规则包）。"""
    bounds = set()
    for seg in industry.get("segments") or []:
        if seg.get("upper") is not None:
            bounds.add(Decimal(str(seg["upper"])))
    return sorted(bounds)


def _tier_cases(ruleset_id: str, ruleset: dict) -> List[dict]:
    """危险品/电力超额累退：常规点 + 恰好等于分段点 + ±0.01 邻域。"""
    cases: List[dict] = []
    haz = _industry(ruleset, "hazardous_chemicals")
    bounds = _segment_bounds(haz)
    # 常规档内点：取各段中点（段下界与上界的平均值，同样从规则包推导）
    mids: List[Decimal] = []
    segs = sorted(haz["segments"], key=lambda s: Decimal(str(s["lower"])))
    for seg in segs:
        lower = Decimal(str(seg["lower"]))
        upper = None if seg["upper"] is None else Decimal(str(seg["upper"]))
        mids.append(lower + (upper - lower) / 2 if upper is not None else lower * 2)
    del mids[-1]  # 末段无上界，中点无意义（深端点单列）
    deep = segs[-2]["lower"] if len(segs) >= 2 else None  # 次末段下界作为深端点
    for label, basis in zip(
        ("mid-tier%d" % i for i in range(1, len(mids) + 1)), mids,
    ):
        amount, note = _accrual_direct(ruleset, "hazardous_chemicals", basis)
        cases.append(_case(
            "SYN-HAZ-%s" % label.upper(), ruleset_id,
            _enterprise("示例危险品（合成）有限公司", "90000000SYN0000002B",
                        "hazardous_chemicals", 2024, "revenue", str(basis), "CNY"),
            amount, note, "危险品常规档内点 %s（营收 %s 元）" % (label, basis),
        ))
    # 深端点：次末段下界（大营收仍正确分段）
    if deep is not None:
        amount, note = _accrual_direct(ruleset, "hazardous_chemicals", Decimal(str(deep)))
        cases.append(_case(
            "SYN-HAZ-DEEP-TIER", ruleset_id,
            _enterprise("示例危险品（合成）有限公司", "90000000SYN0000002B",
                        "hazardous_chemicals", 2024, "revenue", str(deep), "CNY"),
            amount, note, "危险品深端点（次末段下界 %s 元）" % deep,
        ))
    # 分段点邻域（{p-0.01, p, p+0.01}）
    for bound in bounds:
        for delta, tag in ((Decimal("-0.01"), "BELOW"), (Decimal("0"), "AT"),
                           (Decimal("0.01"), "ABOVE")):
            basis = bound + delta
            amount, note = _accrual_direct(ruleset, "hazardous_chemicals", basis)
            cases.append(_case(
                "SYN-HAZ-EDGE-%s-%s" % (bound, tag), ruleset_id,
                _enterprise("示例危险品（合成）有限公司", "90000000SYN0000002B",
                            "hazardous_chemicals", 2024, "revenue", str(basis), "CNY"),
                amount, note,
                "危险品恰好等于/邻近分段点 %s 元（%s；边界口径 [lower, upper)，"
                "恰好等于归下一段）" % (bound, tag),
            ))
    # 电力：生产/供应两套标准各一例（取点同样从规则包推导：供应段一的中点 /
    # 生产第四段下界，不复制字面量）
    power = _industry(ruleset, "power")
    gen_node = _variant(power, "power_generation")
    sup_node = _variant(power, "power_supply")
    sup_first_upper = Decimal(str(sup_node["segments"][0]["upper"]))
    gen_deep_lower = Decimal(str(gen_node["segments"][3]["lower"]))
    for variant_id, label, basis in (
        ("power_generation", "GEN", gen_deep_lower),
        ("power_supply", "SUP", sup_first_upper),
    ):
        amount, note = _accrual_direct(ruleset, "power", basis, variant_id)
        cases.append(_case(
            "SYN-POWER-%s" % label, ruleset_id,
            _enterprise("示例电力（合成）有限公司", "90000000SYN0000005E",
                        "power", 2024, "revenue", str(basis), "CNY", variant_id),
            amount, note,
            "电力%s（第四十三条 %s）营收 %s 元" % (
                "生产" if variant_id == "power_generation" else "供应", variant_id, basis),
        ))
    return cases


def _build_cases() -> List[dict]:
    cases: List[dict] = []
    rs_2022 = _load_ruleset("财资-2022-136")
    rs_2012 = _load_ruleset("财企-2012-16")

    # ── 按产量（煤炭，2022 版）───────────────────────────────────────────────
    for variant_id, basis in (
        ("coal_outburst_rockburst", "80000"),
        ("coal_high_gas", "120000"),
        ("coal_other_underground", "300000"),
        ("coal_opencast", "1000000"),
    ):
        amount, note = _accrual_direct(rs_2022, "coal", Decimal(basis), variant_id)
        cases.append(_case(
            "SYN-COAL-%s" % variant_id.replace("coal_", "").upper(), "财资-2022-136",
            _enterprise("示例煤炭（合成）有限公司", "90000000SYN0000001A", "coal", 2024,
                        "output", basis, "ton", variant_id),
            amount, note, "煤炭按产量（第七条 %s）× %s 吨" % (variant_id, basis),
        ))

    # ── 按工程造价比例（建设工程，2022 版）───────────────────────────────────
    for variant_id, basis in (
        ("mine_engineering", "30000000"),
        ("railway_building_rail_transit", "80000000"),
        ("municipal_port_highway", "80000000"),
    ):
        amount, note = _accrual_direct(rs_2022, "construction", Decimal(basis), variant_id)
        cases.append(_case(
            "SYN-CONST-%s" % variant_id.split("_")[0].upper(), "财资-2022-136",
            _enterprise("示例建设工程（合成）有限公司", "90000000SYN0000003C",
                        "construction", 2024, "project_cost", basis, "CNY", variant_id),
            amount, note, "建设工程按造价比例（第十七条 %s）× %s 元" % (variant_id, basis),
        ))

    # ── 超额累退（危险品 + 电力，2022 版）───────────────────────────────────
    cases.extend(_tier_cases("财资-2022-136", rs_2022))

    # ── 元/万元错配（台账以万元填报，规则包以元计价 → warning + 定义性换算）────
    basis_wan = Decimal("5000")  # 5000 万元 = 5000 万×10000 = 5×10^7 元
    amount, note = _accrual_direct(rs_2022, "hazardous_chemicals", basis_wan * Decimal("10000"))
    cases.append(_case(
        "SYN-HAZ-UNIT-MISMATCH", "财资-2022-136",
        _enterprise("示例危险品（合成）有限公司", "90000000SYN0000002B",
                    "hazardous_chemicals", 2024, "revenue", str(basis_wan), "CNY10k"),
        amount, note,
        "单位口径错配：档案以 CNY10k 填报 5000，规则包以元计价——"
        "定义性换算 ×10000 后按 5×10^7 元计算，且必须报 warning（不静默）",
        unit_warning="不一致",
    ))

    # ── 双版本对照：同一对象按 136 号与 2012 版各算一套期望 ─────────────────
    for ruleset_id, ruleset in (("财资-2022-136", rs_2022), ("财企-2012-16", rs_2012)):
        # 煤炭突出/高瓦斯（2022 拆档 50/30；2012 同档 30）
        for variant_2022, variant_2012 in (
            ("coal_outburst_rockburst", "coal_outburst_high_gas"),
            ("coal_high_gas", "coal_outburst_high_gas"),
        ):
            variant_id = variant_2022 if ruleset_id == "财资-2022-136" else variant_2012
            basis = Decimal("100000")
            amount, note = _accrual_direct(ruleset, "coal", basis, variant_id)
            cases.append(_case(
                "SYN-DUAL-COAL-%s" % ("2022" if ruleset_id == "财资-2022-136" else "2012"),
                ruleset_id,
                _enterprise("示例煤炭（合成）有限公司", "90000000SYN0000001A", "coal",
                            2024, "output", str(basis), "ton", variant_id),
                amount, note,
                "双版本对照（%s，%s）× %s 吨" % (ruleset_id, variant_id, basis),
            ))
        # 危险品（两版同机制不同费率）
        basis = Decimal("50000000")
        amount, note = _accrual_direct(ruleset, "hazardous_chemicals", basis)
        cases.append(_case(
            "SYN-DUAL-HAZ-%s" % ("2022" if ruleset_id == "财资-2022-136" else "2012"),
            ruleset_id,
            _enterprise("示例危险品（合成）有限公司", "90000000SYN0000002B",
                        "hazardous_chemicals", 2024, "revenue", str(basis), "CNY"),
            amount, note, "双版本对照（%s）危险品营收 %s 元" % (ruleset_id, basis),
        ))
        # 建设工程矿山工程（2.5% → 3.5%）
        basis = Decimal("30000000")
        amount, note = _accrual_direct(ruleset, "construction", basis, "mine_engineering")
        cases.append(_case(
            "SYN-DUAL-CONST-%s" % ("2022" if ruleset_id == "财资-2022-136" else "2012"),
            ruleset_id,
            _enterprise("示例建设工程（合成）有限公司", "90000000SYN0000003C",
                        "construction", 2024, "project_cost", str(basis), "CNY",
                        "mine_engineering"),
            amount, note, "双版本对照（%s）矿山工程造价 %s 元" % (ruleset_id, basis),
        ))

    # ── 确定性 RNG 消费（splitmix64 为真值库预留的扰动源：当前算例集为定值设计，
    #    后续批量台账扩展时以 rng 序派生档案，禁 stdlib random）─────────────────
    state, _ = splitmix64(SEED)
    assert state != 0  # RNG 通电自检（确定性纪律）
    return cases


def _build_negatives() -> List[dict]:
    negatives: List[dict] = []

    # 干净档案：计提正确、无任何 warning（应零命中）
    clean_enterprises = [
        ("示例煤炭（合成）有限公司", "90000000SYN0000001A", "coal", "output",
         "120000", "ton", "coal_high_gas"),
        ("示例建设工程（合成）有限公司", "90000000SYN0000003C", "construction",
         "project_cost", "80000000", "CNY", "municipal_port_highway"),
        ("示例危险品（合成）有限公司", "90000000SYN0000002B", "hazardous_chemicals",
         "revenue", "50000000", "CNY", None),
    ]
    for index, (name, code, industry, kind, value, unit, variant) in enumerate(clean_enterprises, 1):
        negatives.append(_negative(
            "NEG-CLEAN-%03d" % index, "财资-2022-136",
            _enterprise(name, code, industry, 2024, kind, value, unit, variant),
            {"zero_hit": True},
            "干净档案：应零命中（不产生任何 warning，计提正确）",
        ))

    # 应降级档案：单位可显式换算 → 只报 warning（不静默、不拦截）
    negatives.append(_negative(
        "NEG-DOWNGRADE-001", "财资-2022-136",
        _enterprise("示例危险品（合成）有限公司", "90000000SYN0000002B",
                    "hazardous_chemicals", 2024, "revenue", "2000", "CNY10k"),
        {"downgrade_warning": True},
        "应降级：CNY10k 可定义性换算 → 只报单位口径 warning",
    ))
    negatives.append(_negative(
        "NEG-DOWNGRADE-002", "财资-2022-136",
        _enterprise("示例危险品（合成）有限公司", "90000000SYN0000002B",
                    "hazardous_chemicals", 2024, "revenue", "0.3", "CNY100m"),
        {"downgrade_warning": True},
        "应降级：CNY100m 可定义性换算 → 只报单位口径 warning",
    ))
    return negatives


README_TEXT = """# data/truth 合成企业台账与真值库

> **性质**：本目录全部为**合成数据**（虚构企业 + 测试号段 `90000000…SYN`），
> 不含任何真实企业名称、产能、营业收入或台账数据。
> **生成器**：`tools/gen_synthetic.py`（唯一写入者，禁手改）；`--check` 守门"再生成逐字节一致"。

## 目录约定

```
data/truth/
├─ README.md          # 本文件
├─ cases/             # 真值记录：每条含 enterprise + expect（金额/机制/also_expect）
└─ negatives/         # 误报对照集：显式声明"应零命中"与"应降级"的档案
```

## 真值语义（定稿一次，动了会打挂基准）

* `expect.amount` —— 主期望（应计提金额，两位小数）；
* `expect.mechanism` / `expect.also_expect` —— 机制与条款依据等隐含结论；
* `expect.unit_warning` —— 元/万元错配档案期望的单位口径 warning 文案片段；
* `negatives/*/expect.zero_hit` —— 干净档案应零命中（无任何 warning）；
* `negatives/*/expect.downgrade_warning` —— 单位可显式换算 → 只报 warning；
* `note` —— 该算例的注入说明。

## 双重记账（防"真值抄引擎"）

期望金额由**独立计算路径**得出：生成器只用规则包 JSON 的原始数值做一次性公式
演算（分段 = Σ 段内依据量 × 段费率），**不调用 safefee 引擎**；基准
`synthetic_ledger` 套件再用引擎全量重算对账——两边一致才算达标。

## 算例覆盖（M1）

| 类别 | 算例 |
|---|---|
| 三类机制 | 煤炭（按产量，第七条 4 变体）/ 建设工程（按造价比例，第十七条 3 类别）/ 危险品与电力（超额累退，含生产/供应两套标准） |
| 边界 | 恰好等于分段点（1000 万 / 1 亿 / 10 亿）及 ±0.01 邻域（`[lower, upper)` 口径：恰好等于归下一段） |
| 单位口径错配 | 台账以 CNY10k 填报、规则包以元计价 → 定义性换算 + 必报 warning |
| 误报对照 | `negatives/`：3 份干净档案（应零命中）+ 2 份应降级档案（CNY10k / CNY100m → 只报 warning） |
| 双版本对照 | 同一对象（煤炭/危险品/矿山工程）分别按 136 号与 2012 版生成两套期望值 |
"""


def generate() -> Dict[str, bytes]:
    files: Dict[str, bytes] = {"README.md": README_TEXT.encode("utf-8")}
    for case in _build_cases():
        name = "%s.json" % case["case_id"]
        text = json.dumps(case, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        files["cases/%s" % name] = text.encode("utf-8")
    for negative in _build_negatives():
        name = "%s.json" % negative["negative_id"]
        text = json.dumps(negative, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        files["negatives/%s" % name] = text.encode("utf-8")
    return files


def write_all(files: Dict[str, bytes]) -> None:
    for rel, payload in sorted(files.items()):
        path = OUT_DIR / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    for sub in ("cases", "negatives"):
        (OUT_DIR / sub).mkdir(parents=True, exist_ok=True)
        keep = OUT_DIR / sub / ".gitkeep"
        if not keep.exists():
            keep.write_bytes(b"")


def check() -> int:
    files = generate()
    mismatched: List[str] = []
    for rel, payload in sorted(files.items()):
        path = OUT_DIR / rel
        if not path.is_file():
            mismatched.append("%s（缺失）" % rel)
            continue
        if path.read_bytes() != payload:
            mismatched.append(rel)
    # 陈旧文件：目录里存在而生成器不再产出的 .json（生成器是唯一写入者）
    expected = {OUT_DIR / rel for rel in files}
    for sub in ("cases", "negatives"):
        folder = OUT_DIR / sub
        if folder.is_dir():
            for path in sorted(folder.glob("*.json")):
                if path not in expected:
                    mismatched.append("%s（陈旧：生成器已不再产出）" % path.relative_to(OUT_DIR).as_posix())
    if mismatched:
        print("FROZEN_TRUTH_DRIFT: %s" % ", ".join(mismatched))
        return 1
    print("FROZEN_TRUTH_OK（%d 份文件逐字节一致）" % len(files))
    return 0


def main(argv=None) -> int:
    from safefee._stdio import _ensure_utf8_stdio

    _ensure_utf8_stdio()
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--check" in argv:
        return check()
    files = generate()
    write_all(files)
    print("已生成真值库（cases %d + negatives %d + README）→ %s"
          % (len(_build_cases()), len(_build_negatives()), OUT_DIR))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    raise SystemExit(main())
