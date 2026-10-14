"""计提依据选择判定。

跨行业经营、承揽/承运净额口径（第五十三条）、多种灾害并存矿井从高提取等
**依据选择规则**显式判定并留痕。

**纪律**：档案属性缺失即列入 ``inputs_required`` → 运行时**必索**（退出码 2），
**绝不静默取 0/1**。
"""

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from safefee.errors import MissingInput


@dataclass(frozen=True)
class BasisDecision:
    """依据选择判定结果（含留痕）。"""

    chosen_variant: Optional[str]
    excluded: Tuple[Tuple[str, str], ...]   # (被排除项, 排除理由)
    clause: str
    inputs_required: Tuple[str, ...]        # 缺失字段：缺失即退出码 2

    def as_dict(self) -> dict:
        return {
            "chosen_variant": self.chosen_variant,
            "excluded": [{"item": item, "reason": reason} for item, reason in self.excluded],
            "clause": self.clause,
            "inputs_required": list(self.inputs_required),
        }


def choose_mine_variant(
    industry: dict,
    *,
    mine_type: Optional[str] = None,
    hazards: Sequence[str] = (),
) -> BasisDecision:
    """矿井变体选择：**多种灾害并存从高提取**。

    规则包在变体上声明 ``severity``（越大越"高"）与 ``conditions``；本函数按
    "命中的变体取 severity 最大者"判定，并留痕被排除项与理由。
    """
    variants = industry.get("variants") or []
    if not variants:
        return BasisDecision(chosen_variant=None, excluded=(), clause="", inputs_required=())

    if mine_type is None and not hazards:
        return BasisDecision(
            chosen_variant=None,
            excluded=(),
            clause=str(industry.get("clause", "")),
            inputs_required=("mine_type",),
        )

    matched = []
    for variant in variants:
        conditions = variant.get("conditions") or {}
        if "mine_type" in conditions and conditions["mine_type"] == mine_type:
            matched.append(variant)
        for hazard in hazards:
            if hazard in (conditions.get("hazards") or []):
                matched.append(variant)

    if not matched:
        raise MissingInput(
            "行业 %s 未匹配到任何矿井变体（mine_type=%r, hazards=%r）"
            % (industry.get("industry_id"), mine_type, list(hazards))
        )

    matched.sort(key=lambda v: (-int(v.get("severity", 0)), str(v.get("variant_id"))))
    chosen = matched[0]
    excluded = tuple(
        (str(v.get("variant_id")), "severity 低于选定变体（从高提取）")
        for v in matched[1:]
    )
    return BasisDecision(
        chosen_variant=str(chosen.get("variant_id")),
        excluded=excluded,
        clause=str(chosen.get("clause") or industry.get("clause", "")),
        inputs_required=(),
    )


__all__ = ["BasisDecision", "choose_mine_variant"]
