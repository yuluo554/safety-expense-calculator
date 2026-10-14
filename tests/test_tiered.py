"""超额累退分段计算器测试（**边界归属口径**是本项目的招牌口径之一）。

断言：段区间 ``[lower, upper)``；**恰好等于分段点归下一段**；
逐段量化后求和（不是"总额乘单一费率"）。
"""

from decimal import Decimal

from safefee.tiered import TierSpec, compute_tiered, tier_base, tiered_total


def _specs():
    """三段测试用区间（数值仅用于测试，不是政策数值）。"""
    return (
        TierSpec(Decimal(0), Decimal(100), Decimal("0.10"), "第一条"),
        TierSpec(Decimal(100), Decimal(500), Decimal("0.05"), "第二条"),
        TierSpec(Decimal(500), None, Decimal("0.01"), "第三条"),
    )


def test_empty_value_returns_no_lines():
    assert compute_tiered(Decimal(0), _specs()) == ()
    assert compute_tiered(Decimal(-1), _specs()) == ()


def test_below_first_bound():
    lines = compute_tiered(Decimal(50), _specs())
    assert lines[0].base_in_tier == Decimal(50)
    assert lines[0].amount == Decimal("5.00")
    assert tiered_total(lines) == Decimal("5.00")


def test_exactly_at_first_bound_goes_to_next_tier():
    """**恰好等于分段点归下一段**（段区间 [lower, upper)）。"""
    lines = compute_tiered(Decimal(100), _specs())
    assert lines[0].base_in_tier == Decimal(100)   # 第一段取满
    assert lines[1].base_in_tier == Decimal(0)     # 第二段 0
    assert lines[2].base_in_tier == Decimal(0)
    assert tiered_total(lines) == Decimal("10.00")


def test_just_above_first_bound_spills_to_next():
    lines = compute_tiered(Decimal("100.01"), _specs())
    assert lines[0].base_in_tier == Decimal(100)
    assert lines[1].base_in_tier == Decimal("0.01")
    assert lines[1].amount == Decimal("0.00")  # 0.01 × 0.05 = 0.0005 → 量化 0.00


def test_tier_base_boundary_semantics():
    spec = TierSpec(Decimal(100), Decimal(500), Decimal("0.05"))
    assert tier_base(Decimal(99), spec) == Decimal(0)
    assert tier_base(Decimal(100), spec) == Decimal(0)
    assert tier_base(Decimal(101), spec) == Decimal(1)
    assert tier_base(Decimal(500), spec) == Decimal(400)
    assert tier_base(Decimal(1000), spec) == Decimal(400)


def test_last_tier_is_unbounded():
    lines = compute_tiered(Decimal(1000), _specs())
    assert lines[2].upper is None
    assert lines[2].base_in_tier == Decimal(500)
    assert lines[2].amount == Decimal("5.00")


def test_total_is_sum_of_quantized_lines_not_single_rate():
    """合计 = 各段量化值之和（**不是总额乘单一费率**——这正是本工具的存在理由）。"""
    lines = compute_tiered(Decimal(600), _specs())
    expected = sum((line.amount for line in lines), Decimal(0))
    assert tiered_total(lines) == expected
    naive = (Decimal(600) * Decimal("0.10")).quantize(Decimal("0.01"))
    assert tiered_total(lines) != naive


def test_lines_preserve_clause_and_index():
    lines = compute_tiered(Decimal(600), _specs())
    assert [line.index for line in lines] == [1, 2, 3]
    assert lines[0].clause == "第一条"
    assert lines[2].clause == "第三条"


def test_zero_base_tiers_still_emitted():
    """段内依据量为 0 的段仍输出（保留完整分段结构便于核对）。"""
    lines = compute_tiered(Decimal(50), _specs())
    assert len(lines) == 3
    assert lines[1].base_in_tier == Decimal(0)
    assert lines[1].amount == Decimal("0.00")
