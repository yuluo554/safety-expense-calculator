"""计提引擎测试（三类机制 + 单位口径 + 未落值拦截）。"""

from decimal import Decimal

import pytest

from safefee.accrual import AccrualRequest, compute
from safefee.errors import MissingInput, NotCovered, SchemaError


def _ruleset_by_output():
    return {
        "industries": [
            {
                "industry_id": "coal",
                "industry_name": "煤炭生产",
                "mechanism": "by_output",
                "implementation": "in_scope",
                "clause": "第七条",
                "status": "verified",
                "variants": [
                    {"variant_id": "high_gas", "variant_name": "高瓦斯矿井",
                     "unit": "CNY/ton", "value": Decimal("30"), "clause": "第七条",
                     "status": "verified"},
                    {"variant_id": "opencast", "variant_name": "露天矿井",
                     "unit": "CNY/ton", "value": Decimal("5"), "clause": "第七条",
                     "status": "verified"},
                ],
            }
        ]
    }


def test_by_output_multiplies_unit_value():
    request = AccrualRequest("coal", "output", Decimal("1000"), "ton", 2024, "high_gas")
    result = compute(_ruleset_by_output(), request)
    assert result.amount == Decimal("30000.00")
    assert result.mechanism == "by_output"
    assert result.clause == "第七条"


def test_variant_required_when_multiple():
    request = AccrualRequest("coal", "output", Decimal("1000"), "ton", 2024, None)
    with pytest.raises(MissingInput):
        compute(_ruleset_by_output(), request)


def test_unset_value_is_schema_error():
    """未落值（pending）条目即使绕过门控也**不得**参与计算。"""
    ruleset = _ruleset_by_output()
    ruleset["industries"][0]["variants"][0]["value"] = None
    request = AccrualRequest("coal", "output", Decimal("1000"), "ton", 2024, "high_gas")
    with pytest.raises(SchemaError):
        compute(ruleset, request)


def test_deferred_industry_rejected():
    ruleset = _ruleset_by_output()
    ruleset["industries"][0]["implementation"] = "deferred"
    request = AccrualRequest("coal", "output", Decimal("1000"), "ton", 2024, "high_gas")
    with pytest.raises(NotCovered):
        compute(ruleset, request)


def test_basis_kind_mismatch_is_schema_error():
    request = AccrualRequest("coal", "revenue", Decimal("1000"), "CNY", 2024, "high_gas")
    with pytest.raises(SchemaError):
        compute(_ruleset_by_output(), request)


def test_by_project_cost_applies_rate():
    ruleset = {
        "industries": [{
            "industry_id": "construction", "industry_name": "建设工程施工",
            "mechanism": "by_project_cost", "implementation": "in_scope",
            "clause": "第十七条", "status": "verified",
            "variants": [{"variant_id": "mine", "variant_name": "矿山工程",
                          "rate": Decimal("0.035"), "clause": "第十七条", "status": "verified"}],
        }]
    }
    request = AccrualRequest("construction", "project_cost", Decimal("1000000"), "CNY", 2024, "mine")
    result = compute(ruleset, request)
    assert result.amount == Decimal("35000.00")
    assert result.mechanism == "by_project_cost"


def test_by_revenue_tiered_emits_tier_lines():
    ruleset = {
        "industries": [{
            "industry_id": "hazardous_chemicals", "industry_name": "危险品生产与储存",
            "mechanism": "by_revenue_tiered", "implementation": "in_scope",
            "clause": "第二十一条", "status": "verified",
            "segments": [
                {"lower": "0", "upper": "1000", "rate": "0.1", "clause": "第二十一条",
                 "status": "verified"},
                {"lower": "1000", "upper": None, "rate": "0.02", "clause": "第二十一条",
                 "status": "verified"},
            ],
        }]
    }
    request = AccrualRequest("hazardous_chemicals", "revenue", Decimal("2000"), "CNY", 2024)
    result = compute(ruleset, request)
    assert len(result.tiers) == 2
    assert result.amount == Decimal("120.00")   # 1000×0.1 + 1000×0.02
