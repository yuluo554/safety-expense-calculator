"""status 门控测试（**本项目的核心纪律**）。

断言：

* ``pending`` 条目**绝不进入计算路径**；
* 门控**按计算路径分作用域**（``calc``/``check``/``progress``），互不误伤；
* ``input_required`` **不阻断**门控（放行但运行时必索）；
* ``calc`` 门控**收窄到本次计算的行业**——算 coal 时不被 machinery 的 pending 拖累；
* ``deferred`` 行业**不阻断**可用行业的口径。
"""

from pathlib import Path

import pytest

from safefee.errors import ConfigError
from safefee.rules import check_scope, load_manifest, load_progress, load_ruleset, load_spending


@pytest.fixture(scope="module")
def ruleset_2022(data_dir):
    return load_ruleset(data_dir, "财资-2022-136")


def test_scope_calc_blocks_on_pending(ruleset_2022):
    """M0 规则包全 pending → calc 门控必然拦截（**门控生效的证据**，不是缺陷）。"""
    result = check_scope(ruleset_2022, "calc", industry_id="coal")
    assert result.ok is False
    assert len(result.blockers) > 0
    assert all(b.status == "pending" for b in result.blockers)


def test_scope_calc_narrows_to_industry(ruleset_2022):
    """门控收窄：coal 的 blocker 只应来自 coal 行业。"""
    coal = check_scope(ruleset_2022, "calc", industry_id="coal")
    assert all("industries[0]" in b.path for b in coal.blockers)


def test_deferred_industry_not_blocking_available(ruleset_2022):
    """deferred 行业的 pending **不得**阻断可用行业（与核算无关的 pending 不该拦路）。"""
    result = check_scope(ruleset_2022, "calc", industry_id="coal")
    deferred_ids = {
        i.get("industry_id") for i in ruleset_2022["industries"]
        if i.get("implementation") == "deferred"
    }
    for blocker in result.blockers:
        assert not any("deferred" in blocker.reason for _ in [0])
        # 逐条确认 blocker 不来自 deferred 行业
        for index, industry in enumerate(ruleset_2022["industries"]):
            if industry.get("industry_id") in deferred_ids:
                assert "industries[%d]" % index not in blocker.path


def test_scope_check_blocks_on_pending(data_dir, ruleset_2022):
    spending = load_spending(data_dir, "财资-2022-136")
    result = check_scope(ruleset_2022, "check", spending=spending)
    assert result.ok is False
    assert all(b.status == "pending" for b in result.blockers)


def test_scope_progress_blocks_on_pending(data_dir, ruleset_2022):
    progress = load_progress(data_dir, "财资-2022-136")
    result = check_scope(ruleset_2022, "progress", progress=progress)
    assert result.ok is False
    assert all(b.status == "pending" for b in result.blockers)


def test_unknown_scope_is_config_error(ruleset_2022):
    with pytest.raises(ConfigError):
        check_scope(ruleset_2022, "nope")


def test_verified_entries_pass_gate():
    """verified 条目 + input_required 条目都应放行（**input_required 不阻断**）。"""
    ruleset = {
        "mechanisms": {"status": "verified"},
        "industries": [
            {
                "industry_id": "coal",
                "implementation": "in_scope",
                "status": "verified",
                "variants": [
                    {"variant_id": "v1", "status": "verified"},
                    {"variant_id": "v2", "status": "input_required"},
                ],
            }
        ],
    }
    result = check_scope(ruleset, "calc", industry_id="coal")
    assert result.ok is True
    assert result.blockers == ()


def test_gate_result_describe_lists_blockers(ruleset_2022):
    result = check_scope(ruleset_2022, "calc", industry_id="coal")
    text = result.describe()
    assert "门控拦截" in text
    assert "第七条" in text
