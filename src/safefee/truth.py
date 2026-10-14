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


def evaluate_case(case: TruthCase, ruleset: dict) -> None:
    """重算并断言与真值一致；不一致抛 :class:`AssertionError`（带字段级说明）。"""
    case_obj = build_case(case.enterprise)
    request = AccrualRequest(
        industry_id=case_obj.industry_id,
        basis_kind=case_obj.basis_kind,
        basis_value=case_obj.basis_value,
        basis_unit=case_obj.basis_unit,
        year=case_obj.year,
        variant_id=case_obj.variant_id,
    )
    result = compute(ruleset, request)

    expected = case.expected_amount
    if expected is not None and result.amount != expected:
        raise AssertionError("金额不符：期望 %s 实际 %s" % (expected, result.amount))

    expected_mechanism = case.expect.get("mechanism")
    if expected_mechanism is not None and result.mechanism != expected_mechanism:
        raise AssertionError("机制不符：期望 %s 实际 %s" % (expected_mechanism, result.mechanism))

    also = case.expect.get("also_expect") or {}
    for key, value in also.items():
        actual = getattr(result, key, None)
        if actual is None:
            raise AssertionError("also_expect 字段 %r 在结果中不存在" % key)
        if str(actual) != str(value):
            raise AssertionError(
                "also_expect %s 不符：期望 %s 实际 %s" % (key, value, actual)
            )


__all__ = ["TruthCase", "iter_cases", "evaluate_case"]
