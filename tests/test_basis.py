"""依据选择判定测试（M2 主轴）：从高提取 / 属性缺失必索 / 跨行业 / 净额口径。

判定规则本身来自规则包（``basis_rules``：阈值 85% 是**数据**，不写死在引擎里）；
判定结论（chosen/excluded/clause）必须进 ``CalcReport`` 与报告。
"""

from decimal import Decimal

import pytest

from safefee.accrual import (
    BasisDecision,
    choose_mine_variant,
    decide_basis,
    resolve_multi_business,
    resolve_net_basis,
)
from safefee.engine import build_case, compute_calc
from safefee.errors import EXIT_USAGE
from safefee.rules import load_ruleset


@pytest.fixture(scope="module")
def ruleset(data_dir):
    return load_ruleset(data_dir, "财资-2022-136")


# ── 从高提取（第七条多种灾害并存）─────────────────────────────────────────

def test_mine_variant_chooses_highest_severity(ruleset):
    industry = next(i for i in ruleset["industries"] if i["industry_id"] == "coal")
    decision = choose_mine_variant(industry, mine_type="high_gas",
                                   hazards=["rockburst"])
    assert decision.chosen_variant == "coal_outburst_rockburst"  # severity 4 > 3
    assert decision.clause == "第七条"
    assert any("从高提取" in note for note in decision.notes)
    excluded = {item for item, _ in decision.excluded}
    assert "coal_high_gas" in excluded


def test_mine_variant_missing_attributes_is_input_required(ruleset):
    industry = next(i for i in ruleset["industries"] if i["industry_id"] == "coal")
    decision = choose_mine_variant(industry)
    assert decision.inputs_required == ("mine_type",)
    assert decision.chosen_variant is None


def test_compute_calc_requests_missing_mine_type(data_dir, tmp_path):
    """**属性缺失必索**：只给行业不给矿井属性 → ``inputs_required``（CLI 退出码 2）。"""
    case = build_case({
        "enterprise_id": "X", "enterprise_name": "Y", "industry_id": "coal",
        "year": 2024, "basis_kind": "output", "basis_value": "10000", "basis_unit": "ton",
    })
    report = compute_calc(case, str(data_dir))
    assert report.result is None
    assert report.inputs_required == ("mine_type",)
    assert report.basis and report.basis["clause"] == "第七条"


def test_compute_calc_from_high_extraction(data_dir):
    """多灾害并存 → 引擎按从高变体算（50 元/吨），判定留痕进结果。"""
    case = build_case({
        "enterprise_id": "X", "enterprise_name": "Y", "industry_id": "coal",
        "year": 2024, "basis_kind": "output", "basis_value": "10000", "basis_unit": "ton",
        "mine_type": "high_gas", "hazards": ["rockburst"],
    })
    report = compute_calc(case, str(data_dir))
    assert str(report.result.amount) == "500000.00"      # 50 元/吨 × 10000 吨
    assert report.result.variant_name and "冲击地压" in report.result.variant_name
    assert report.result.basis["kind"] == "mine_variant"


# ── 跨行业经营（第五十二条）────────────────────────────────────────────────

def test_multi_business_separate_accounting(ruleset):
    decision = resolve_multi_business(ruleset, [
        {"industry_id": "hazardous_chemicals", "revenue": "30000000",
         "separate_accounting": True},
        {"industry_id": "metallurgy", "revenue": "20000000", "separate_accounting": True},
    ])
    assert decision.kind == "multi_business"
    assert decision.chosen_industry is None
    assert decision.clause == "第五十二条"


def test_multi_business_highest_share_when_not_separable(ruleset):
    decision = resolve_multi_business(ruleset, [
        {"industry_id": "hazardous_chemicals", "revenue": "30000000"},
        {"industry_id": "metallurgy", "revenue": "20000000"},
    ])
    assert decision.chosen_industry == "hazardous_chemicals"   # 占比最高
    assert decision.clause == "第五十二条"


# ── 净额口径（第五十三条）─────────────────────────────────────────────────

def test_net_basis_applies_when_purchased_cost_above_threshold(ruleset):
    decision = resolve_net_basis(ruleset, revenue=Decimal("50000000"),
                                 purchased_cost=Decimal("45000000"), is_contractor=True)
    assert decision.basis_value == "5000000"       # 50000000 - 45000000
    assert decision.clause == "第五十三条"


def test_net_basis_not_applied_below_threshold(ruleset):
    decision = resolve_net_basis(ruleset, revenue=Decimal("50000000"),
                                 purchased_cost=Decimal("40000000"), is_contractor=True)
    assert decision.basis_value is None


def test_net_basis_threshold_is_data_not_code(ruleset):
    """阈值 85% 来自规则包（数据非代码）——改动规则包即改动判定。"""
    assert ruleset["basis_rules"]["net_basis"]["threshold"] == "0.85"


def test_compute_calc_net_basis_reduces_basis(data_dir):
    """净额口径命中 → 依据量取净额（营收 5×10^7 减外购 4.5×10^7 = 5×10^6）。"""
    case = build_case({
        "enterprise_id": "X", "enterprise_name": "Y", "industry_id": "hazardous_chemicals",
        "year": 2024, "basis_kind": "revenue", "basis_value": "50000000", "basis_unit": "CNY",
        "is_contractor": True, "revenue": "50000000", "purchased_cost": "45000000",
    })
    report = compute_calc(case, str(data_dir))
    assert report.basis["kind"] == "net_basis"
    assert report.basis["basis_value"] == "5000000"
    # 5×10^6 元 ≤ 首段上界 → 只落首段
    assert str(report.result.amount) == "225000.00"


def test_decide_basis_none_for_plain_case(data_dir):
    """普通档案（无多业务/净额/矿井属性）→ 判定为 none（不留痕噪声）。"""
    case = build_case({
        "enterprise_id": "X", "enterprise_name": "Y", "industry_id": "hazardous_chemicals",
        "year": 2024, "basis_kind": "revenue", "basis_value": "50000000", "basis_unit": "CNY",
    })
    decision = decide_basis(load_ruleset(data_dir, "财资-2022-136"), case)
    assert decision.kind == "none"
