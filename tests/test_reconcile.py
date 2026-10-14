"""跨年对账测试（四集合 + 稳定身份键 + 内容变化标记）。"""

from safefee.batch import ObservedItem, compare_nonpass, observed_nonpass
from safefee.spending import STATE_COMPLIANT, STATE_NONCOMPLIANT, STATE_NOT_APPLICABLE


def test_new_anomaly_detected():
    baseline = [ObservedItem("k1", STATE_COMPLIANT)]
    current = [ObservedItem("k1", STATE_NONCOMPLIANT)]
    report = compare_nonpass(baseline, current)
    assert report.counts()["新增异常"] == 1


def test_fixed_detected_with_stable_key():
    """**配对用稳定身份键**——内容指纹变了也能认出"已修复"（否则永远检不出）。"""
    baseline = [ObservedItem("k1", STATE_NONCOMPLIANT, "aaa")]
    current = [ObservedItem("k1", STATE_COMPLIANT, "bbb")]
    report = compare_nonpass(baseline, current)
    assert report.counts()["已修复"] == 1
    assert "k1" in report.content_changed   # 指纹变化另立标记，不退化成"新增+移除"


def test_persistent_anomaly():
    baseline = [ObservedItem("k1", STATE_NONCOMPLIANT)]
    current = [ObservedItem("k1", STATE_NONCOMPLIANT)]
    report = compare_nonpass(baseline, current)
    assert report.counts()["持续异常"] == 1


def test_stable_pass():
    baseline = [ObservedItem("k1", STATE_COMPLIANT)]
    current = [ObservedItem("k1", STATE_COMPLIANT)]
    report = compare_nonpass(baseline, current)
    assert report.counts()["稳定"] == 1


def test_not_applicable_excluded_from_comparison():
    """``不适用`` 是"没看到"不是"缺失"——纳入比较会制造假"已修复"。"""
    baseline = [ObservedItem("k1", STATE_NOT_APPLICABLE)]
    current = [ObservedItem("k1", STATE_COMPLIANT)]
    report = compare_nonpass(baseline, current)
    assert report.counts()["稳定"] == 1
    assert report.counts()["已修复"] == 0


def test_non_pass_includes_noncompliant_and_not_assessed():
    items = [
        ObservedItem("a", STATE_NONCOMPLIANT),
        ObservedItem("b", "未评估"),
        ObservedItem("c", STATE_COMPLIANT),
        ObservedItem("d", STATE_NOT_APPLICABLE),
    ]
    nonpass = observed_nonpass(items)
    assert set(nonpass) == {"a", "b"}


def test_new_item_appears_in_new_set():
    report = compare_nonpass([], [ObservedItem("k9", STATE_NONCOMPLIANT)])
    assert report.counts()["新增异常"] == 1
