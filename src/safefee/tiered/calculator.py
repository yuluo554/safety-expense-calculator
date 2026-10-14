"""超额累退分段计算（确定性内核）。

**边界归属口径（定稿一次，动了会打挂基准）**：段区间为 **``[lower, upper)``**
（下含上不含），与办法"不超过 X 元的部分 … 超过 X 元至 Y 元的部分"表述一致；
**恰好等于分段点**归入**下一段**（"超过 X 元"起点含）。该口径由基准的
``tiered_boundary`` 套件（含 ``{p-0.01, p, p+0.01}`` 邻域枚举）守住。

**逐段量化后求和**（不是"总额乘单一费率"）——这正是本工具存在的理由。
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Sequence, Tuple

#: 金额精度约定（量化口径，**非政策数值**，豁免零政策字面量门禁）
Q2 = Decimal("0.01")


def quantize_money(value: Decimal) -> Decimal:
    """金额统一两位小数 ``ROUND_HALF_UP``（呈现/落盘口径）。"""
    return Decimal(value).quantize(Q2, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class TierSpec:
    """一段超额累退区间。

    ``upper=None`` 表示无上界（最末段）。``rate`` 为费率（**来自规则包**）；
    ``rate=None`` 表示**未核对**（门控会拦截）。
    """

    lower: Decimal
    upper: Optional[Decimal]
    rate: Optional[Decimal]
    clause: str = ""
    status: str = "pending"


@dataclass(frozen=True)
class TierLine:
    """逐段分解明细（供审计核对"钱是怎么算出来的"）。"""

    index: int
    lower: Decimal
    upper: Optional[Decimal]
    base_in_tier: Decimal
    rate: Optional[Decimal]
    amount: Decimal
    clause: str

    def as_dict(self) -> dict:
        return {
            "index": self.index,
            "lower": str(self.lower),
            "upper": None if self.upper is None else str(self.upper),
            "base_in_tier": str(self.base_in_tier),
            "rate": None if self.rate is None else str(self.rate),
            "amount": str(self.amount),
            "clause": self.clause,
        }


def tier_base(value: Decimal, spec: TierSpec) -> Decimal:
    """计算某段内依据量（**边界口径 ``[lower, upper)``**）。"""
    remaining = Decimal(value) - spec.lower
    if remaining <= 0:
        return Decimal(0)
    if spec.upper is None:
        return remaining
    return min(remaining, spec.upper - spec.lower)


def compute_tiered(
    value: Decimal, tiers: Sequence[TierSpec]
) -> Tuple[TierLine, ...]:
    """逐段计算并返回明细。

    * ``value <= 0`` → 返回空明细（合计 0，由调用方量化）；
    * 段内金额逐段量化到分后求和（**合计 = 各段量化值之和**）；
    * 段内依据量为 0 的段仍输出（金额 0），保留完整分段结构便于核对。
    """
    value = Decimal(value)
    if value <= 0:
        return ()

    lines = []
    for index, spec in enumerate(tiers, start=1):
        base = tier_base(value, spec)
        rate = spec.rate if spec.rate is not None else Decimal(0)
        amount = quantize_money(base * rate)
        lines.append(
            TierLine(
                index=index,
                lower=spec.lower,
                upper=spec.upper,
                base_in_tier=base,
                rate=spec.rate,
                amount=amount,
                clause=spec.clause,
            )
        )
    return tuple(lines)


def tiered_total(lines: Sequence[TierLine]) -> Decimal:
    """合计 = 各段金额之和（已是量化值）。"""
    total = Decimal(0)
    for line in lines:
        total += line.amount
    return total


def tiers_from_rules(segments: Sequence[dict]) -> Tuple[TierSpec, ...]:
    """从规则包的段列表构造 :class:`TierSpec`（数值只来自规则包）。"""

    def _dec(raw) -> Optional[Decimal]:
        if raw is None:
            return None
        return Decimal(str(raw))

    specs = []
    for seg in segments:
        specs.append(
            TierSpec(
                lower=_dec(seg.get("lower")) or Decimal(0),
                upper=_dec(seg.get("upper")),
                rate=_dec(seg.get("rate")),
                clause=str(seg.get("clause", "")),
                status=str(seg.get("status", "pending")),
            )
        )
    specs.sort(key=lambda s: s.lower)
    return tuple(specs)


__all__ = [
    "Q2",
    "quantize_money",
    "TierSpec",
    "TierLine",
    "tier_base",
    "compute_tiered",
    "tiered_total",
    "tiers_from_rules",
]
