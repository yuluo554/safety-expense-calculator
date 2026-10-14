"""计提引擎（三类计提机制，确定性内核）。

机制与条款依据：

* ``by_output`` —— 按产量计提（煤炭等），``金额 = 单价 × 产量``；
* ``by_revenue_tiered`` —— 按营业收入**超额累退**（危险品、冶金、机械制造、电力等）；
* ``by_project_cost`` —— 按建筑安装工程造价**比例**（建设工程施工）。

全部标准值与适用条件从规则包读取，**禁止硬编码**；金额全链路 ``Decimal``，
精确到分（``ROUND_HALF_UP``）；结论旁挂"第 X 条"。
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Sequence, Tuple

from safefee.errors import MissingInput, NotCovered, SchemaError
from safefee.tiered import TierLine, compute_tiered, quantize_money, tiered_total, tiers_from_rules

MECHANISMS = ("by_output", "by_revenue_tiered", "by_revenue_rate", "by_project_cost")

#: 各机制期望的输入单位（来自规则包 ``basis_unit`` 声明）
BASIS_KINDS = {
    "by_output": "output",
    "by_revenue_tiered": "revenue",
    "by_revenue_rate": "revenue",
    "by_project_cost": "project_cost",
}


@dataclass(frozen=True)
class AccrualRequest:
    """计提请求（输入契约）。"""

    industry_id: str
    basis_kind: str                  # output | revenue | project_cost
    basis_value: Decimal             # 依据量（吨 / 元 / 元）
    basis_unit: str                  # 输入单位（ton | CNY | CNY10k | CNY100m）
    year: int
    variant_id: Optional[str] = None
    warnings: Tuple[str, ...] = ()


@dataclass(frozen=True)
class AccrualResult:
    """计提结果（输出契约）。"""

    amount: Decimal
    mechanism: str
    formula: str
    clause: str
    industry_name: str
    variant_name: Optional[str]
    tiers: Tuple[TierLine, ...] = ()
    warnings: Tuple[str, ...] = ()
    provenance: Tuple[dict, ...] = ()
    basis: Optional[dict] = None          # 依据选择判定留痕（BasisDecision.as_dict()）

    def as_dict(self) -> dict:
        return {
            "amount": str(self.amount),
            "mechanism": self.mechanism,
            "formula": self.formula,
            "clause": self.clause,
            "industry_name": self.industry_name,
            "variant_name": self.variant_name,
            "tiers": [line.as_dict() for line in self.tiers],
            "warnings": list(self.warnings),
            "provenance": list(self.provenance),
            "basis": self.basis,
        }


def _find_industry(ruleset: dict, industry_id: str) -> dict:
    for item in ruleset.get("industries", []):
        if item.get("industry_id") == industry_id:
            return item
    raise SchemaError("规则包未登记行业：%r" % industry_id)


def _find_variant(industry: dict, variant_id: Optional[str]) -> Optional[dict]:
    variants = industry.get("variants") or []
    if not variants:
        return None
    if variant_id is None:
        if len(variants) == 1:
            return variants[0]
        raise MissingInput(
            "行业 %s 有多个变体，须显式指定 variant_id（可选：%s）"
            % (industry.get("industry_id"), ", ".join(str(v.get("variant_id")) for v in variants))
        )
    for variant in variants:
        if variant.get("variant_id") == variant_id:
            return variant
    raise SchemaError(
        "行业 %s 无此变体：%r" % (industry.get("industry_id"), variant_id)
    )


def _require_value(node: dict, key: str, where: str):
    value = node.get(key)
    if value is None:
        raise SchemaError(
            "%s 的 %r 未落值（status=%s）——门控应已拦截；未核对的值绝不参与计算"
            % (where, key, node.get("status", "pending"))
        )
    return value


def compute(ruleset: dict, request: AccrualRequest) -> AccrualResult:
    """按规则包计算应计提金额。

    调用方须先通过 ``calc`` 作用域门控（否则未核对条目会被 :class:`SchemaError` 拦下）。
    """
    industry = _find_industry(ruleset, request.industry_id)
    if industry.get("implementation") == "deferred":
        raise NotCovered(
            "行业 %s（%s）属首期未覆盖范围，暂不输出结论"
            % (industry.get("industry_id"), industry.get("industry_name", ""))
        )

    variant = _find_variant(industry, request.variant_id)
    # 机制可在**变体上覆写**（一个行业节内含不同计提机制的变体，如非煤矿山第十条
    # 的"地质勘探单位按工程总费用 2%"、石油天然气第十四条的"工程成本 2%"）。
    node = variant or industry
    mechanism = node.get("mechanism") or industry.get("mechanism")
    if mechanism not in MECHANISMS:
        raise SchemaError("未知计提机制：%r（支持 %s）" % (mechanism, ", ".join(MECHANISMS)))

    expected_kind = BASIS_KINDS[mechanism]
    if request.basis_kind != expected_kind:
        raise SchemaError(
            "行业 %s 的计提机制为 %s，依据类型应为 %r，收到 %r"
            % (request.industry_id, mechanism, expected_kind, request.basis_kind)
        )

    warnings = list(request.warnings)

    if mechanism == "by_output":
        unit_value = Decimal(str(_require_value(node, "value", "industry/variant")))
        amount = quantize_money(unit_value * Decimal(request.basis_value))
        clause = str(node.get("clause") or industry.get("clause", ""))
        formula = "%s（%s） × %s = %s 元" % (
            node.get("unit", ""), unit_value, request.basis_value, amount
        )
        return AccrualResult(
            amount=amount,
            mechanism=mechanism,
            formula=formula,
            clause=clause,
            industry_name=industry.get("industry_name", ""),
            variant_name=(node.get("variant_name") if variant else None),
            warnings=tuple(warnings),
            provenance=tuple(_prov_of(node, industry)),
        )

    if mechanism == "by_revenue_tiered":
        segments = node.get("segments")
        if not segments:
            raise SchemaError("超额累退行业 %s 缺少 segments" % request.industry_id)
        specs = tiers_from_rules(segments)
        lines = compute_tiered(Decimal(request.basis_value), specs)
        amount = tiered_total(lines)
        clause = str(node.get("clause") or industry.get("clause", ""))
        parts = ["%s×%s" % (line.base_in_tier, line.rate) for line in lines if line.base_in_tier > 0]
        formula = "超额累退逐段：%s = %s 元" % (" + ".join(parts), amount)
        return AccrualResult(
            amount=amount,
            mechanism=mechanism,
            formula=formula,
            clause=clause,
            industry_name=industry.get("industry_name", ""),
            variant_name=(node.get("variant_name") if variant else None),
            tiers=lines,
            warnings=tuple(warnings),
            provenance=tuple(_prov_of(node, industry)),
        )

    if mechanism == "by_revenue_rate":
        # 按营业收入**单一比例**（无分段，如交通运输普通货运 1% / 客运等 1.5%）
        rate = Decimal(str(_require_value(node, "rate", "industry/variant")))
        amount = quantize_money(rate * Decimal(request.basis_value))
        clause = str(node.get("clause") or industry.get("clause", ""))
        formula = "营业收入 %s 元 × 费率 %s = %s 元" % (
            request.basis_value, rate, amount
        )
        return AccrualResult(
            amount=amount,
            mechanism=mechanism,
            formula=formula,
            clause=clause,
            industry_name=industry.get("industry_name", ""),
            variant_name=(node.get("variant_name") if variant else None),
            warnings=tuple(warnings),
            provenance=tuple(_prov_of(node, industry)),
        )

    # by_project_cost
    rate = Decimal(str(_require_value(node, "rate", "industry/variant")))
    amount = quantize_money(rate * Decimal(request.basis_value))
    clause = str(node.get("clause") or industry.get("clause", ""))
    formula = "工程造价 %s 元 × 费率 %s = %s 元" % (request.basis_value, rate, amount)
    return AccrualResult(
        amount=amount,
        mechanism=mechanism,
        formula=formula,
        clause=clause,
        industry_name=industry.get("industry_name", ""),
        variant_name=(node.get("variant_name") if variant else None),
        warnings=tuple(warnings),
        provenance=tuple(_prov_of(node, industry)),
    )


def _prov_of(node: dict, industry: dict) -> list:
    prov = node.get("provenance") or industry.get("provenance") or []
    if isinstance(prov, dict):
        return [prov]
    return list(prov)


__all__ = [
    "MECHANISMS",
    "BASIS_KINDS",
    "AccrualRequest",
    "AccrualResult",
    "compute",
]
