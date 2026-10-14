"""单位换算与口径一致性测试（元/万元错配必须报 warning，不静默）。"""

from decimal import Decimal

import pytest

from safefee.errors import SchemaError
from safefee.rules import load_units


def test_units_load(data_dir):
    units = load_units(data_dir)
    assert units.factor("CNY") == Decimal(1)
    assert units.factor("CNY10k") == Decimal(10000)
    assert units.factor("CNY100m") == Decimal(100000000)


def test_consistent_unit_yields_no_warning(data_dir):
    units = load_units(data_dir)
    value, warning = units.to_base(Decimal(100), "CNY")
    assert value == Decimal(100)
    assert warning is None


def test_mismatched_unit_yields_warning_not_silence(data_dir):
    """**单位口径错配必须报 warning**——元/万元错配是真实高频事故。"""
    units = load_units(data_dir)
    value, warning = units.to_base(Decimal(100), "CNY10k")
    assert value == Decimal(1000000)
    assert warning is not None
    assert "不一致" in warning


def test_unknown_unit_is_schema_error(data_dir):
    units = load_units(data_dir)
    with pytest.raises(SchemaError):
        units.factor("USD")


def test_missing_required_unit_rejected(tmp_path):
    import json

    rules_dir = tmp_path / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "units.json").write_bytes(
        (json.dumps({"factors": {"CNY": "1"}}, ensure_ascii=False) + "\n").encode("utf-8")
    )
    with pytest.raises(SchemaError):
        load_units(tmp_path)
