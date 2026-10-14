"""基准测试：达标判定、门槛随 manifest、``--only`` 白名单、**可证伪探活**。"""

from decimal import Decimal

import pytest

from safefee.bench import SUITES, run_all, run_tiered_boundary
from safefee.errors import ConfigError
from safefee.rules import load_manifest
from safefee.tiered import TierSpec, compute_tiered


def test_suites_registered():
    assert set(SUITES) == {"tiered_boundary", "dual_version", "synthetic_ledger"}


def test_tiered_boundary_suite_meets_threshold(data_dir):
    manifest = load_manifest(data_dir)
    from safefee.rules import load_ruleset
    rulesets = [load_ruleset(data_dir, ref.directory) for ref in manifest.refs]
    result = run_tiered_boundary(manifest, rulesets)
    assert result.assessable is True
    assert result.met is True
    assert result.passed == result.total


def test_only_unknown_suite_is_config_error(data_dir):
    manifest = load_manifest(data_dir)
    with pytest.raises(ConfigError):
        run_all(manifest, only="nope")


def test_only_whitelisted_suite_runs(data_dir):
    manifest = load_manifest(data_dir)
    results = run_all(manifest, only="tiered_boundary")
    assert len(results) == 1
    assert results[0].suite == "tiered_boundary"


def test_threshold_missing_raises_config_error(tmp_path):
    """门槛是数据不是代码：缺失即配置错误（**不回落默认值**）。"""
    from safefee.rules.manifest import Manifest

    manifest = Manifest(tmp_path, {"rulesets": [], "benchmark_thresholds": {}})
    with pytest.raises(ConfigError):
        manifest.threshold_for("tiered_boundary")


def test_unmeasured_suite_is_not_claimed_met(data_dir):
    """**"没测" ≠ "达标"**：用例数为 0 的套件既不声称达标，也不判未达标。"""
    manifest = load_manifest(data_dir)
    results = run_all(manifest)
    for result in results:
        if result.total == 0:
            assert result.assessable is False
            assert result.met is False


def test_falsifiability_probe_boundary_assertion():
    """**可证伪探活**：注入一个缺陷（段宽计算错误）→ 断言基准的检查器**必须**报错。

    防"基准全绿只是因为它什么都没查"。
    """
    from safefee.bench import _assert_boundary_consistent

    good = (TierSpec(Decimal(0), Decimal(100), Decimal("0.1")),
            TierSpec(Decimal(100), None, Decimal("0.01")))
    _assert_boundary_consistent(Decimal(150), good)   # 正常：不抛

    # 注入缺陷：段上界 < 下界（非法区间）→ 检查器必须检出
    broken = (TierSpec(Decimal(0), Decimal(100), Decimal("0.1")),
              TierSpec(Decimal(50), Decimal(60), Decimal("0.01")))
    with pytest.raises(AssertionError):
        _assert_boundary_consistent(Decimal(150), broken)


def test_falsifiability_probe_detects_base_sum_mismatch(monkeypatch):
    """注入缺陷：段内依据量之和 ≠ 依据量 → 检查器必须报错。"""
    import safefee.bench as bench

    def broken_compute(value, specs):
        from safefee.tiered import TierLine, quantize_money
        # 故意丢掉最后一段（缺陷注入）
        return (TierLine(1, Decimal(0), Decimal(100), Decimal(50), Decimal("0.1"),
                         quantize_money(Decimal("5")), "x"),)

    monkeypatch.setattr(bench, "compute_tiered", broken_compute)
    with pytest.raises(AssertionError):
        bench._assert_boundary_consistent(Decimal(150),
                                          (TierSpec(Decimal(0), Decimal(100), Decimal("0.1")),))
