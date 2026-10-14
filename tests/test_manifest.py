"""manifest / 年度锚定 / 规则包完整性测试。"""

from datetime import date
from pathlib import Path

import pytest

from safefee.errors import (
    AmbiguousRuleset,
    ConfigError,
    IntegrityError,
    NoRulesetForYear,
    SchemaError,
)
from safefee.rules import load_manifest


def test_manifest_loads_and_lists_two_rulesets(data_dir):
    manifest = load_manifest(data_dir)
    ids = {ref.ruleset_id for ref in manifest.refs}
    assert ids == {"财资-2022-136", "财企-2012-16"}


def test_anchor_2012_for_old_year(data_dir):
    manifest = load_manifest(data_dir)
    ref = manifest.resolve_year(2020)
    assert ref.ruleset_id == "财企-2012-16"


def test_anchor_2022_for_new_year(data_dir):
    manifest = load_manifest(data_dir)
    ref = manifest.resolve_year(2024)
    assert ref.ruleset_id == "财资-2022-136"


def test_anchor_is_by_day_not_by_year(data_dir):
    """办法"自印发之日起施行"（2022-11-21）→ **按日**锚定。"""
    manifest = load_manifest(data_dir)
    assert manifest.resolve(date(2022, 11, 20)).ruleset_id == "财企-2012-16"
    assert manifest.resolve(date(2022, 11, 21)).ruleset_id == "财资-2022-136"


def test_year_anchor_boundary_2022_vs_2023(data_dir):
    """**年度锚定边界（M2）**：只给年度时取该年 1 月 1 日 ——
    ``year=2022`` → 2012 版（2022-01-01 < 2022-11-21）；``year=2023`` → 136 号。"""
    manifest = load_manifest(data_dir)
    assert manifest.resolve_year(2022).ruleset_id == "财企-2012-16"
    assert manifest.resolve_year(2023).ruleset_id == "财资-2022-136"


def test_year_before_any_ruleset_is_error(data_dir):
    manifest = load_manifest(data_dir)
    with pytest.raises(NoRulesetForYear):
        manifest.resolve_year(2011)


def test_threshold_missing_is_config_error(data_dir):
    """门槛是数据不是代码：缺失即配置错误（**不回落默认值**）。"""
    manifest = load_manifest(data_dir)
    with pytest.raises(ConfigError):
        manifest.threshold_for("no_such_suite")


def test_thresholds_registered_for_three_suites(data_dir):
    manifest = load_manifest(data_dir)
    for suite in ("tiered_boundary", "dual_version", "synthetic_ledger"):
        assert manifest.threshold_for(suite)


def test_integrity_check_detects_tampering(data_dir, tmp_path):
    """规则包被手改 → :class:`IntegrityError`（冻结纪律被破坏可检出）。

    M2 后全部条目已 ``verified``，故注入 **带值的费率** 改动（而非 pending→verified）。
    """
    import shutil

    target = tmp_path / "data"
    shutil.copytree(data_dir, target)
    ruleset = target / "rules" / "财资-2022-136" / "ruleset.json"
    ruleset.write_bytes(ruleset.read_bytes().replace(b'"0.035"', b'"0.99"'))
    with pytest.raises(IntegrityError):
        load_manifest(target)


def test_unknown_schema_version_rejected(data_dir, tmp_path):
    import json
    import shutil

    target = tmp_path / "data"
    shutil.copytree(data_dir, target)
    manifest_path = target / "rules" / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["schema_version"] = 999
    manifest_path.write_bytes(
        (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    with pytest.raises(SchemaError):
        load_manifest(target)


def test_ambiguous_ruleset_detected(tmp_path):
    """重叠的生效区间 → :class:`AmbiguousRuleset`（配置错误）。"""
    import json

    rules_dir = tmp_path / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "units.json").write_bytes(b'{"factors": {}}\n')
    for name in ("a", "b"):
        (rules_dir / name).mkdir()
        (rules_dir / name / "ruleset.json").write_bytes(b'{"industries": []}\n')
    manifest = {
        "schema_version": 1,
        "rulesets": [
            {"ruleset_id": "a", "dir": "a", "doc_no": "A", "effective_from": "2020-01-01",
             "effective_to": None, "status": "pending", "files": {}},
            {"ruleset_id": "b", "dir": "b", "doc_no": "B", "effective_from": "2020-01-01",
             "effective_to": None, "status": "pending", "files": {}},
        ],
        "benchmark_thresholds": {},
    }
    (rules_dir / "manifest.json").write_bytes(
        (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    loaded = load_manifest(tmp_path)
    with pytest.raises(AmbiguousRuleset):
        loaded.resolve_year(2024)
