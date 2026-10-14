"""计提依据选择判定。

把办法里**"该按哪条口径提"**的规则显式判定并留痕：

============  ==========================================================
条款           判定
============  ==========================================================
第七条/第十条   多种灾害并存矿井**从高提取**（变体 severity 最大者）
第五十二条      跨行业经营：能分别核算按业务分别提；不能按占比最高业务
第五十三条      承揽/承运净额口径：外购成本 > 营业收入 85% 可按净额
============  ==========================================================

**纪律**：判定所需的**阈值（85%）与规则文本都来自规则包**（数据非代码）；
档案属性缺失即列入 ``inputs_required`` → 运行时**必索**（退出码 2），
**绝不静默取 0/1**；判定结论（chosen/excluded/clause）进结果与报告。
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Sequence, Tuple

from safefee.errors import MissingInput


@dataclass(frozen=True)
class BasisDecision:
    """依据选择判定结果（含留痕）。

    ``kind`` 标记命中哪条判定规则；``inputs_required`` 非空表示**档案属性缺失**，
    运行时必索（退出码 2）。
    """

    kind: str                                   # mine_variant | multi_business | net_basis | none
    clause: str = ""
    chosen_variant: Optional[str] = None
    chosen_industry: Optional[str] = None
    excluded: Tuple[Tuple[str, str], ...] = ()  # (被排除项, 排除理由)
    inputs_required: Tuple[str, ...] = ()
    basis_value: Optional[str] = None           # 净额口径后的依据量（字符串 Decimal）
    notes: Tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "clause": self.clause,
            "chosen_variant": self.chosen_variant,
            "chosen_industry": self.chosen_industry,
            "excluded": [{"item": item, "reason": reason} for item, reason in self.excluded],
            "inputs_required": list(self.inputs_required),
            "basis_value": self.basis_value,
            "notes": list(self.notes),
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
        return BasisDecision(kind="none", clause=str(industry.get("clause", "")))

    if mine_type is None and not hazards:
        return BasisDecision(
            kind="mine_variant",
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
        kind="mine_variant",
        clause=str(chosen.get("clause") or industry.get("clause", "")),
        chosen_variant=str(chosen.get("variant_id")),
        excluded=excluded,
        notes=("多种灾害并存矿井从高提取",),
    )


def resolve_multi_business(
    ruleset: dict,
    businesses: Sequence[dict],
) -> BasisDecision:
    """第五十二条：跨行业经营。

    ``businesses`` 每项 = ``{industry_id, revenue, separate_accounting?}``：

    * **能分别核算** → 逐业务按各自标准分别提取（``chosen_industry`` 留空，
      ``notes`` 列出各项）；
    * **不能分别核算** → 取**营业收入占比最高**业务的标准，对**合计营业收入**计提
      （``chosen_industry`` = 最高业务）。
    """
    rule = (ruleset.get("basis_rules") or {}).get("multi_business") or {}
    clause = str(rule.get("clause", "第五十二条"))
    if not businesses:
        return BasisDecision(kind="none", clause=clause)

    can_separate = all(bool(b.get("separate_accounting")) for b in businesses)
    if can_separate:
        notes = tuple(
            "分别核算：%s 营收 %s" % (b.get("industry_id"), b.get("revenue"))
            for b in businesses
        )
        return BasisDecision(kind="multi_business", clause=clause, notes=notes)

    ranked = sorted(
        businesses,
        key=lambda b: (-Decimal(str(b.get("revenue", 0))), str(b.get("industry_id"))),
    )
    chosen = ranked[0]
    excluded = tuple(
        (str(b.get("industry_id")), "营业收入占比低于选定业务（不能分别核算）")
        for b in ranked[1:]
    )
    return BasisDecision(
        kind="multi_business",
        clause=clause,
        chosen_industry=str(chosen.get("industry_id")),
        excluded=excluded,
        notes=("不能分别核算：按营业收入占比最高业务对合计营业收入计提",),
    )


def resolve_net_basis(
    ruleset: dict,
    *,
    revenue: Optional[Decimal],
    purchased_cost: Optional[Decimal],
    is_contractor: bool = False,
) -> BasisDecision:
    """第五十三条：承揽人/承运人净额口径。

    外购材料和服务成本 **高于**自客户取得营业收入 **85%**（阈值来自规则包）时，
    可按"营业收入 − 外购材料和服务成本"的净额作为计提依据。
    """
    rule = (ruleset.get("basis_rules") or {}).get("net_basis") or {}
    clause = str(rule.get("clause", "第五十三条"))
    if not is_contractor:
        return BasisDecision(kind="none", clause=clause)
    if revenue is None or purchased_cost is None:
        return BasisDecision(
            kind="net_basis",
            clause=clause,
            inputs_required=("revenue", "purchased_cost"),
        )
    threshold = Decimal(str(rule.get("threshold", "0")))
    ratio = (purchased_cost / revenue) if revenue else Decimal(0)
    if ratio > threshold:
        net = revenue - purchased_cost
        return BasisDecision(
            kind="net_basis",
            clause=clause,
            basis_value=str(net),
            notes=("外购成本占营业收入 %s%%（> 规则包阈值 %s%%）→ 按净额计提"
                   % ((ratio * 100).quantize(Decimal("0.01")), (threshold * 100).quantize(Decimal("0.01"))),),
        )
    return BasisDecision(
        kind="net_basis",
        clause=clause,
        notes=("外购成本占营业收入 %s%%（未高于阈值 %s%%）→ 不适用净额口径"
               % ((ratio * 100).quantize(Decimal("0.01")), (threshold * 100).quantize(Decimal("0.01"))),),
    )


def decide_basis(ruleset: dict, case) -> BasisDecision:
    """编排全部依据选择判定（``compute_calc`` 调用）。

    优先级：跨行业（第五十二条）→ 净额口径（第五十三条）→ 矿井变体从高提取。
    判定所需的档案属性缺失即进 ``inputs_required``（调用方据此退出码 2）。
    """
    raw: Dict[str, object] = getattr(case, "raw", {}) or {}

    businesses = raw.get("businesses") or []
    if businesses:
        multi = resolve_multi_business(ruleset, businesses)
        if multi.chosen_industry:
            return multi
        if multi.kind != "none":
            return multi

    revenue = raw.get("revenue")
    if raw.get("is_contractor") or raw.get("purchased_cost") is not None:
        net = resolve_net_basis(
            ruleset,
            revenue=None if revenue is None else Decimal(str(revenue)),
            purchased_cost=(None if raw.get("purchased_cost") is None
                            else Decimal(str(raw["purchased_cost"]))),
            is_contractor=bool(raw.get("is_contractor")),
        )
        if net.inputs_required or net.basis_value is not None:
            return net

    industry = _find_industry(ruleset, case.industry_id)
    variants = industry.get("variants") or []
    if variants and any(v.get("conditions") for v in variants):
        # 矿井类行业：未显式指定 variant 时按档案属性从高提取
        if not case.variant_id:
            return choose_mine_variant(
                industry,
                mine_type=raw.get("mine_type"),
                hazards=raw.get("hazards") or (),
            )
    return BasisDecision(kind="none", clause=str(industry.get("clause", "")))


def _find_industry(ruleset: dict, industry_id: str) -> dict:
    for item in ruleset.get("industries", []):
        if item.get("industry_id") == industry_id:
            return item
    return {}


__all__ = [
    "BasisDecision",
    "choose_mine_variant",
    "resolve_multi_business",
    "resolve_net_basis",
    "decide_basis",
]
