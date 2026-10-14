"""支出核查四态语义 + 使用进度测试（**判定语义不虚高**）。"""

from decimal import Decimal

import pytest

from safefee.errors import NotCovered
from safefee.spending import (
    STATE_COMPLIANT,
    STATE_NONCOMPLIANT,
    STATE_NOT_ASSESSED,
    LedgerItem,
    check_ledger,
    compute_progress,
)


def _spending():
    return {
        "entries": [
            {"entry_id": "SP-1", "industry_id": "coal", "clause": "第八条",
             "category": "允许", "criterion": "安全改造", "match_keywords": ["安全改造"],
             "status": "verified"},
            {"entry_id": "SP-99", "industry_id": "coal", "clause": "第五条",
             "category": "禁止", "criterion": "不得挪用", "match_keywords": ["挪用"],
             "status": "verified"},
        ]
    }


def test_allowed_item_is_compliant():
    report = check_ledger(_spending(), "coal",
                          [LedgerItem("E1", "安全费用", "煤矿安全改造支出", Decimal("100"))])
    assert report.findings[0].state == STATE_COMPLIANT
    assert report.findings[0].clause == "第八条"


def test_forbidden_item_is_noncompliant_and_redlined():
    report = check_ledger(_spending(), "coal",
                          [LedgerItem("E2", "管理费用", "挪用于办公", Decimal("100"))])
    assert report.findings[0].state == STATE_NONCOMPLIANT
    assert len(report.redlines) == 1
    assert report.has_noncompliant() is True


def test_no_matching_entry_is_not_assessed_not_compliant():
    """**无适用条目 → 未评估，绝不输出"符合"**（"没查出问题" ≠ "没检查过"）。"""
    report = check_ledger(_spending(), "coal",
                          [LedgerItem("E3", "其他", "无关支出", Decimal("100"))])
    assert report.findings[0].state == STATE_NOT_ASSESSED
    assert report.findings[0].state != STATE_COMPLIANT


def test_out_of_scope_industry_rejected():
    """未覆盖行业 → 退出码 2 语义（**不臆造结论**）。"""
    with pytest.raises(NotCovered):
        check_ledger(_spending(), "no_such_industry", [])


def test_progress_below_threshold_requires_disclosure():
    rules = {"thresholds": [{"threshold_id": "default", "clause": "第五十一条",
                             "threshold": "0.6", "status": "verified",
                             "disclosure_points": ["说明使用情况"]}]}
    result = compute_progress(rules, year=2024, accrued=Decimal("100"), used=Decimal("50"))
    assert result.applicable is True
    assert result.disclosure_required is True
    assert result.ratio == Decimal("0.50")


def test_progress_above_threshold_no_disclosure():
    rules = {"thresholds": [{"threshold_id": "default", "clause": "第五十一条",
                             "threshold": "0.6", "status": "verified",
                             "disclosure_points": []}]}
    result = compute_progress(rules, year=2024, accrued=Decimal("100"), used=Decimal("80"))
    assert result.disclosure_required is False


def test_progress_zero_accrued_is_not_applicable():
    """``accrued == 0`` → 不适用（原文语义），**不是除零**。"""
    rules = {"thresholds": [{"threshold_id": "default", "clause": "第五十一条",
                             "threshold": "0.6", "status": "verified",
                             "disclosure_points": []}]}
    result = compute_progress(rules, year=2024, accrued=Decimal("0"), used=Decimal("0"))
    assert result.applicable is False
    assert result.disclosure_required is False
