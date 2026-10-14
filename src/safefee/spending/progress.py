"""使用进度与披露核查。

办法规定的**使用进度门槛**（第五十一条：当年实际使用不足年度应计提金额一定
比例的，须按规定披露并提交书面说明）由规则包承载——**门槛值不硬编码**。

``accrued == 0`` 时返回 ``not_applicable``（原文语义），而非除零。
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence, Tuple

from safefee.tiered import quantize_money


@dataclass(frozen=True)
class ProgressResult:
    """进度判定结果。"""

    year: int
    accrued: Decimal
    used: Decimal
    ratio: Decimal                 # used / accrued（accrued=0 时见 applicable）
    threshold: Decimal             # 门槛（来自规则包）
    applicable: bool
    disclosure_required: bool
    clause: str
    points: Tuple[str, ...]        # 披露说明要点

    def as_dict(self) -> dict:
        return {
            "year": self.year,
            "accrued": str(self.accrued),
            "used": str(self.used),
            "ratio": str(self.ratio),
            "threshold": str(self.threshold),
            "applicable": self.applicable,
            "disclosure_required": self.disclosure_required,
            "clause": self.clause,
            "points": list(self.points),
        }


def compute_progress(
    progress_rules: dict,
    *,
    year: int,
    accrued: Decimal,
    used: Decimal,
    threshold_id: str = "default",
) -> ProgressResult:
    """判定是否触发披露义务。

    ``progress_rules`` 为 ``progress.json``（须已过 ``progress`` 作用域门控）。
    """
    node = None
    for candidate in progress_rules.get("thresholds", []):
        if candidate.get("threshold_id") == threshold_id:
            node = candidate
            break
    if node is None:
        from safefee.errors import SchemaError
        raise SchemaError("progress.json 未登记门槛：%r" % threshold_id)

    threshold = Decimal(str(node["threshold"]))
    clause = str(node.get("clause", ""))
    points = tuple(node.get("disclosure_points", []))

    accrued = Decimal(accrued)
    used = Decimal(used)
    if accrued == 0:
        return ProgressResult(
            year=year, accrued=accrued, used=used, ratio=Decimal(0),
            threshold=threshold, applicable=False, disclosure_required=False,
            clause=clause, points=points,
        )

    ratio = quantize_money(used / accrued)
    return ProgressResult(
        year=year, accrued=accrued, used=used, ratio=ratio,
        threshold=threshold, applicable=True,
        disclosure_required=ratio < threshold,
        clause=clause, points=points,
    )


__all__ = ["ProgressResult", "compute_progress"]
