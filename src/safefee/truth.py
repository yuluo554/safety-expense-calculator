"""合成台账真值库读取与对账（**对账语义单一实现源**）。

真值库形态：``data/truth/cases/*.json``，每条记录

```jsonc
{
  "case_id": "SYN-COAL-001",
  "ruleset_id": "财资-2022-136",
  "enterprise": { ...档案字段... },
  "expect": {
    "amount": "150000.00",          // 主期望
    "mechanism": "by_output",
    "also_expect": { "clause": "第七条" }   // 同一注入隐含的其余结论
  },
  "note": "…"
}
```

**纪律**：

* **不许改真值凑引擎**；但两种情形要分清——① 检查器谓词自身不自洽 → **只改谓词**；
  ② 真值口径本身错误（不是引擎算错、是"该按哪条口径算"定错了）→ **引擎与真值必须
  同源修正**（两边一起改）。判别 = "错的是**校验方式**还是**被校验的口径**？"；
* 两种情形的共同验收门 = 冻结生成器的 ``--check`` 仍通过。
"""

import json
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Iterator, List, Optional
from safefee.accrual import AccrualRequest, compute
from safefee.engine.pipeline import build_case


@dataclass(frozen=True)
class TruthCase:
    """一条真值记录。"""

    case_id: str
    ruleset_id: str
    enterprise: dict
    expect: dict
    note: str = ""

    @property
    def expected_amount(self) -> Optional[Decimal]:
        raw = self.expect.get("amount")
        return None if raw is None else Decimal(str(raw))


def iter_cases(truth_dir: Path) -> Iterator[TruthCase]:
    """遍历真值库；目录不存在 → 空迭代（基准如实记"未生成"，不假装覆盖）。"""
    cases_dir = Path(truth_dir) / "cases"
    if not cases_dir.is_dir():
        return
    for path in sorted(cases_dir.glob("*.json")):
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh, parse_float=Decimal)
        yield TruthCase(
            case_id=str(payload.get("case_id") or path.stem),
            ruleset_id=str(payload.get("ruleset_id", "")),
            enterprise=payload.get("enterprise") or {},
            expect=payload.get("expect") or {},
            note=str(payload.get("note", "")),
        )


def evaluate_case(case: TruthCase, ruleset: dict, units=None) -> None:
    """重算并断言与真值一致；不一致抛 :class:`AssertionError`（带字段级说明）。

    ``units``（:class:`~safefee.rules.units.UnitConverter`）给出时先做与编排层
    ``compute_calc`` 相同的定义性换算（元/万元错配真值用例依赖它；``None`` 时
    沿用旧路径——档案值原样进入计算）。
    """
    case_obj = build_case(case.enterprise)
    warnings: List[str] = []
    basis_value = case_obj.basis_value
    basis_unit = case_obj.basis_unit
    if units is not None:
        basis_value, unit_warning = units.to_base(case_obj.basis_value, case_obj.basis_unit)
        if unit_warning:
            warnings.append(unit_warning)
        basis_unit = "CNY" if case_obj.basis_kind != "output" else case_obj.basis_unit
    request = AccrualRequest(
        industry_id=case_obj.industry_id,
        basis_kind=case_obj.basis_kind,
        basis_value=basis_value,
        basis_unit=basis_unit,
        year=case_obj.year,
        variant_id=case_obj.variant_id,
        warnings=tuple(warnings),
    )
    result = compute(ruleset, request)

    expected = case.expected_amount
    if expected is not None and result.amount != expected:
        raise AssertionError("金额不符：期望 %s 实际 %s" % (expected, result.amount))

    expected_mechanism = case.expect.get("mechanism")
    if expected_mechanism is not None and result.mechanism != expected_mechanism:
        raise AssertionError("机制不符：期望 %s 实际 %s" % (expected_mechanism, result.mechanism))

    expected_warning = case.expect.get("unit_warning")
    if expected_warning is not None:
        if not result.warnings:
            raise AssertionError("期望单位口径 warning 未产生（错配被静默？）")
        if not any(expected_warning in w for w in result.warnings):
            raise AssertionError(
                "warning 文案不符：期望含 %r 实际 %r" % (expected_warning, list(result.warnings))
            )
    elif not case.expect.get("allow_warnings") and result.warnings:
        raise AssertionError("干净档案不应产生 warning：%r" % (list(result.warnings),))

    also = case.expect.get("also_expect") or {}
    for key, value in also.items():
        actual = getattr(result, key, None)
        if actual is None:
            raise AssertionError("also_expect 字段 %r 在结果中不存在" % key)
        if str(actual) != str(value):
            raise AssertionError(
                "also_expect %s 不符：期望 %s 实际 %s" % (key, value, actual)
            )


@dataclass(frozen=True)
class NegativeCase:
    """一条误报对照记录（``negatives/`` 目录）。

    **基准层只读声明，不自行挑选对照档案**：``expect.zero_hit`` —— 应零命中
    （干净档案：计提正确、不产生任何 warning）；``expect.downgrade_warning`` ——
    单位可显式换算 → 只报 ``warning``（不静默、不拦截）。
    """

    negative_id: str
    ruleset_id: str
    enterprise: dict
    expect: dict
    note: str = ""


def iter_negatives(truth_dir: Path) -> Iterator[NegativeCase]:
    """遍历误报对照集；目录不存在 → 空迭代。"""
    neg_dir = Path(truth_dir) / "negatives"
    if not neg_dir.is_dir():
        return
    for path in sorted(neg_dir.glob("*.json")):
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh, parse_float=Decimal)
        yield NegativeCase(
            negative_id=str(payload.get("negative_id") or path.stem),
            ruleset_id=str(payload.get("ruleset_id", "")),
            enterprise=payload.get("enterprise") or {},
            expect=payload.get("expect") or {},
            note=str(payload.get("note", "")),
        )


def evaluate_negative(case: NegativeCase, ruleset: dict, units=None) -> None:
    """误报对照断言：干净档案必须零命中零 warning；降级档案必须只报 warning。"""
    case_obj = build_case(case.enterprise)
    warnings: List[str] = []
    basis_value = case_obj.basis_value
    basis_unit = case_obj.basis_unit
    if units is not None:
        basis_value, unit_warning = units.to_base(case_obj.basis_value, case_obj.basis_unit)
        if unit_warning:
            warnings.append(unit_warning)
        basis_unit = "CNY" if case_obj.basis_kind != "output" else case_obj.basis_unit
    request = AccrualRequest(
        industry_id=case_obj.industry_id,
        basis_kind=case_obj.basis_kind,
        basis_value=basis_value,
        basis_unit=basis_unit,
        year=case_obj.year,
        variant_id=case_obj.variant_id,
        warnings=tuple(warnings),
    )
    result = compute(ruleset, request)

    expected = case.expect.get("amount")
    if expected is not None and result.amount != Decimal(str(expected)):
        raise AssertionError("金额不符：期望 %s 实际 %s" % (expected, result.amount))

    if case.expect.get("zero_hit") and result.warnings:
        raise AssertionError("干净档案应零命中，实际产生 warning：%r" % (list(result.warnings),))

    if case.expect.get("downgrade_warning"):
        if not result.warnings:
            raise AssertionError("应降级为 warning 的档案未产生 warning（错配被静默？）")
        bad = [w for w in result.warnings if "不一致" not in w]
        if bad:
            raise AssertionError("降级档案出现非单位口径 warning：%r" % (bad,))


__all__ = ["TruthCase", "NegativeCase", "iter_cases", "iter_negatives", "evaluate_case", "evaluate_negative"]
