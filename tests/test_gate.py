"""status 门控测试（**本项目的核心纪律**）。

断言：

* ``pending`` 条目**绝不进入计算路径**（M1 后以 2012 版 progress 留存项为活体样本）；
* 门控**按计算路径分作用域**（``calc``/``check``/``progress``），互不误伤；
* ``calc`` 门控**收窄到本次计算的行业**——算 coal 时不被 deferred 行业的 pending 拖累；
* ``deferred`` 行业**不阻断**可用行业的口径；
* M1 已核对落值的行业（verified）→ 三作用域全放行。
"""

from pathlib import Path

import pytest

from safefee.errors import ConfigError
from safefee.rules import check_scope, load_manifest, load_progress, load_ruleset, load_spending


@pytest.fixture(scope="module")
def ruleset_2022(data_dir):
    return load_ruleset(data_dir, "财资-2022-136")


@pytest.fixture(scope="module")
def ruleset_2012(data_dir):
    return load_ruleset(data_dir, "财企-2012-16")


def test_m1_verified_calc_scope_passes(ruleset_2022):
    """M1 已核对四节（煤炭/建设工程/危险品/电力）→ calc 门控放行。"""
    for industry_id in ("coal", "construction", "hazardous_chemicals", "power"):
        result = check_scope(ruleset_2022, "calc", industry_id=industry_id)
        assert result.ok is True, (industry_id, result.describe())


def test_pending_never_enters_gate_pass(data_dir, ruleset_2012):
    """**pending 绝不放行**：2012 版 progress 门槛留 pending（第十四条，无对应比例
    条款）→ progress 门控拦截（活体样本：M1 后仓库里唯一的门控级 pending）。"""
    progress = load_progress(data_dir, "财企-2012-16")
    result = check_scope(ruleset_2012, "progress", progress=progress)
    assert result.ok is False
    assert len(result.blockers) > 0
    assert all(b.status == "pending" for b in result.blockers)


def test_deferred_pending_skipped_by_calc_gate(ruleset_2012):
    """deferred 行业的 pending **不产生 calc blocker**——它们本就不在计算路径上
    （引擎以"首期未覆盖"拒绝），不属于门控职责；in_scope 行业已全量核对。"""
    for industry_id in ("metallurgy", "transport", "machinery"):
        result = check_scope(ruleset_2012, "calc", industry_id=industry_id)
        assert result.ok is True, (industry_id, result.describe())


def test_scope_calc_narrows_to_industry():
    """门控收窄：pending 只在**本次行业**路径上时才成为 blocker（合成规则集）。"""
    ruleset = {
        "industries": [
            {"industry_id": "coal", "implementation": "in_scope", "status": "verified",
             "clause": "第七条",
             "variants": [{"variant_id": "v", "status": "verified", "clause": "第七条"}]},
            {"industry_id": "machinery", "implementation": "in_scope", "status": "pending",
             "clause": "第三十条", "reason": "未核对"},
        ],
    }
    coal = check_scope(ruleset, "calc", industry_id="coal")
    assert coal.ok is True and coal.blockers == ()
    machinery = check_scope(ruleset, "calc", industry_id="machinery")
    assert machinery.ok is False
    assert all("industries[1]" in b.path for b in machinery.blockers)


def test_deferred_industry_not_blocking_available(ruleset_2022):
    """deferred 行业的 pending **不得**阻断可用行业（与核算无关的 pending 不该拦路）。"""
    for industry_id in ("coal", "construction", "hazardous_chemicals", "power"):
        result = check_scope(ruleset_2022, "calc", industry_id=industry_id)
        assert result.ok is True, (industry_id, result.describe())


def test_scope_check_passes_m1(data_dir, ruleset_2022):
    """M1 支出条目（要点引用 + 红线条款）已核对 → check 门控放行。"""
    spending = load_spending(data_dir, "财资-2022-136")
    result = check_scope(ruleset_2022, "check", spending=spending)
    assert result.ok is True


def test_scope_progress_2022_passes(data_dir, ruleset_2022):
    """2022 版第五十一条（60%）已核对落值 → progress 门控放行。"""
    progress = load_progress(data_dir, "财资-2022-136")
    result = check_scope(ruleset_2022, "progress", progress=progress)
    assert result.ok is True


def test_scope_progress_2012_pending_block(data_dir, ruleset_2012):
    """2012 版无对应比例条款（显式 pending）→ progress 门控拦截（诚实留白）。"""
    progress = load_progress(data_dir, "财企-2012-16")
    result = check_scope(ruleset_2012, "progress", progress=progress)
    assert result.ok is False
    assert all(b.status == "pending" for b in result.blockers)
    assert all(b.clause == "第十四条" for b in result.blockers)


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


def test_gate_result_describe_lists_blockers(data_dir, ruleset_2012):
    progress = load_progress(data_dir, "财企-2012-16")
    result = check_scope(ruleset_2012, "progress", progress=progress)
    text = result.describe()
    assert "门控拦截" in text
    assert "第十四条" in text
