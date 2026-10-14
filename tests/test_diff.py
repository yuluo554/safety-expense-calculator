"""双版本差异对照测试（M2：九类配对覆盖 + 超额累退费率序列对照）。"""

from safefee.rules import load_ruleset
from safefee.ruleset import compare


def _pair(data_dir):
    return (load_ruleset(data_dir, "财企-2012-16"),
            load_ruleset(data_dir, "财资-2022-136"))


def test_diff_covers_all_nine_shared_industries(data_dir):
    """**M2 验收门**：九类配对全部进入对照（即便数值一致也记"已比对"）。"""
    old, new = _pair(data_dir)
    report = compare(old, new)
    expected = {"coal", "noncoal_mine", "construction", "hazardous_chemicals",
                "transport", "metallurgy", "machinery", "fireworks", "weapons"}
    assert expected <= set(report.compared_industries)


def test_diff_reports_known_numeric_upgrades(data_dir):
    """已核对的两版数值级差异必须被检出（不是"什么都没查"）。"""
    old, new = _pair(data_dir)
    report = compare(old, new)
    kinds = {(i.industry_id, i.variant_id): i for i in report.items}
    # 煤炭突出矿井 30 → 50（2022 拆档）
    assert kinds[("coal", "coal_outburst_rockburst")].new_value == "50"
    # 矿山工程 2.5% → 3.5%
    assert kinds[("construction", "mine_engineering")].kind == "rate_changed"
    assert kinds[("construction", "mine_engineering")].new_value == "0.035"
    # 非金属地下矿山 4 → 8 元/吨
    assert kinds[("noncoal_mine", "nc_nonmetal_underground")].new_value == "8"


def test_diff_captures_tiered_rate_sequences(data_dir):
    """超额累退行业的"数值"是费率序列——两版差异（危险品首档 4%→4.5%）不得静默漏掉。"""
    old, new = _pair(data_dir)
    report = compare(old, new)
    haz = next(i for i in report.items
               if i.industry_id == "hazardous_chemicals" and i.kind == "rate_changed")
    assert haz.old_value.startswith("0.04")
    assert haz.new_value.startswith("0.045")


def test_diff_detects_fireworks_structural_difference(data_dir):
    """烟花爆竹两版**分段点结构不同**（2012 四段 vs 2022 三段）→ 必须报差异。"""
    old, new = _pair(data_dir)
    report = compare(old, new)
    fw = [i for i in report.items if i.industry_id == "fireworks"]
    assert fw and fw[0].kind == "rate_changed"
    assert fw[0].old_value.count("|") == 3   # 四段
    assert fw[0].new_value.count("|") == 2   # 三段
