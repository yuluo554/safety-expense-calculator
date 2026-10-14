"""真值库与误报对照集测试（M1 数据先行交付的守门）。

* 真值库可评估（用例数 > 0）且引擎重算全量对账；
* 边界档案（恰好等于分段点）与单位错配档案在库且通过；
* 双版本对照真值两侧都存在；
* 误报对照集声明完整（zero_hit / downgrade_warning）；
* ``evaluate_case`` 无 units 时错配用例如实失败（防静默）。
"""

import pytest

from safefee.bench import run_synthetic_ledger
from safefee.errors import ConfigError
from safefee.rules import load_manifest, load_ruleset, load_units
from safefee.truth import iter_cases, iter_negatives, evaluate_case

TRUTH_DIR = None  # 由 manifest.data_dir 派生


def _truth_dir(manifest):
    return manifest.data_dir / "truth"


def test_truth_library_is_generated_and_assessable(data_dir):
    manifest = load_manifest(data_dir)
    result = run_synthetic_ledger(manifest, _truth_dir(manifest),
                                  {ref.ruleset_id: load_ruleset(data_dir, ref.directory)
                                   for ref in manifest.refs})
    assert result.assessable is True
    assert result.total > 0
    assert result.met is True
    assert result.passed == result.total, result.failed


def test_truth_cases_cover_mechanisms_and_edges(data_dir):
    cases = list(iter_cases(data_dir / "truth"))
    mechanisms = {c.expect.get("mechanism") for c in cases}
    assert {"by_output", "by_revenue_tiered", "by_project_cost"} <= mechanisms
    ids = {c.case_id for c in cases}
    assert any("EDGE-AT" in i for i in ids), "缺恰好等于分段点档案"
    assert any("UNIT-MISMATCH" in i for i in ids), "缺元/万元错配档案"
    assert any(i.startswith("SYN-DUAL-COAL-2022") for i in ids)
    assert any(i.startswith("SYN-DUAL-COAL-2012") for i in ids)


def test_unit_mismatch_case_fails_without_units(data_dir):
    """错配真值依赖定义性换算：不给 units 时必须如实失败（防错配被静默）。"""
    case = next(c for c in iter_cases(data_dir / "truth")
                if c.case_id == "SYN-HAZ-UNIT-MISMATCH")
    ruleset = load_ruleset(data_dir, case.ruleset_id)
    with pytest.raises(AssertionError):
        evaluate_case(case, ruleset)


def test_unit_mismatch_case_passes_with_units(data_dir):
    case = next(c for c in iter_cases(data_dir / "truth")
                if c.case_id == "SYN-HAZ-UNIT-MISMATCH")
    ruleset = load_ruleset(data_dir, case.ruleset_id)
    evaluate_case(case, ruleset, load_units(data_dir))  # 不抛即通过


def test_negatives_declare_expectations(data_dir):
    negatives = list(iter_negatives(data_dir / "truth"))
    assert len(negatives) >= 5
    zero = [n for n in negatives if n.expect.get("zero_hit")]
    downgrade = [n for n in negatives if n.expect.get("downgrade_warning")]
    assert zero and downgrade, "误报对照集须同时声明零命中与应降级两类"
