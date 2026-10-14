"""超额累退分段计算器（确定性内核，亮点）。

边界归属口径与逐段量化口径见 :mod:`safefee.tiered.calculator` 模块文档。
"""

from safefee.tiered.calculator import (
    Q2,
    TierLine,
    TierSpec,
    compute_tiered,
    quantize_money,
    tier_base,
    tiered_total,
    tiers_from_rules,
)

__all__ = [
    "Q2",
    "TierLine",
    "TierSpec",
    "compute_tiered",
    "quantize_money",
    "tier_base",
    "tiered_total",
    "tiers_from_rules",
]
