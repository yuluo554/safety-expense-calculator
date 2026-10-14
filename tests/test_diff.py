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


# ---------------------------------------------------------------------------
# M4：diff --out 对照报告导出（单一渲染源 / 无外链 / 字节冻结 / 管道转义）
# ---------------------------------------------------------------------------

import re
import zipfile
from io import BytesIO

from safefee.cli.main import main
from safefee.errors import EXIT_OK
from safefee.ruleset.diff_report import build_diff_report_input, export_diff_report
from safefee.report import build_sections


def _diff_report(data_dir):
    old, new = _pair(data_dir)
    return compare(old, new)


def test_diff_report_input_maps_all_items(data_dir):
    """DiffReport 全部条目进差异对照章节（含费率序列与两版条款/文号列）。"""
    report = _diff_report(data_dir)
    payload = build_diff_report_input(report)
    sections = build_sections(payload)
    diff_section = next(s for s in sections if s.title == "双版本差异对照")
    assert diff_section.enabled
    assert len(diff_section.rows) == len(report.items)
    header = ("行业", "变体", "差异类型", "旧值", "新值", "旧版条款", "新版条款",
              "旧版文号", "新版文号")
    assert diff_section.columns == header
    # 费率序列整串进"新值"列（不拆单元格）
    haz = next(row for row in diff_section.rows if row[0] == "hazardous_chemicals")
    assert haz[4].startswith("0.045")


def test_diff_out_export_three_artifacts(data_dir, tmp_path):
    """``diff --out`` 产物三件：MD/XLSX/evidence；两格式消费同一章节结构。"""
    written = export_diff_report(_diff_report(data_dir), tmp_path)
    assert {p.name for p in written} == {"差异对照.md", "差异对照.xlsx", "evidence.json"}
    md = (tmp_path / "差异对照.md").read_text(encoding="utf-8")
    assert "双版本差异对照" in md
    assert "财企〔2012〕16号" in md and "财资〔2022〕136号" in md
    with zipfile.ZipFile(BytesIO((tmp_path / "差异对照.xlsx").read_bytes())) as archive:
        sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "双版本差异对照" in sheet
    evidence = (tmp_path / "evidence.json").read_text(encoding="utf-8")
    assert "差异对照.md" in evidence and "差异对照.xlsx" in evidence


def test_diff_out_markdown_no_external_links(data_dir, tmp_path):
    """**无外链**：对照报告不得出现 markdown 链接形态。"""
    export_diff_report(_diff_report(data_dir), tmp_path)
    md = (tmp_path / "差异对照.md").read_text(encoding="utf-8")
    assert not re.search(r"\]\(https?://", md)


def test_diff_out_artifacts_byte_reproducible(data_dir, tmp_path):
    """**字节冻结**：同输入两次导出，MD 与 XLSX 逐字节一致。"""
    export_diff_report(_diff_report(data_dir), tmp_path / "a")
    export_diff_report(_diff_report(data_dir), tmp_path / "b")
    for name in ("差异对照.md", "差异对照.xlsx", "evidence.json"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_diff_out_rate_pipes_escaped_in_markdown(data_dir, tmp_path):
    """费率序列的 ``|`` 进 Markdown 表格必须转义（否则撑破列）。"""
    export_diff_report(_diff_report(data_dir), tmp_path)
    md = (tmp_path / "差异对照.md").read_text(encoding="utf-8")
    assert "0.045\\|0.0225" in md


def test_diff_cli_out_exports_report(data_dir, tmp_path, capsys):
    """CLI 接线：``diff --out`` 退出码 0 且产物落盘。"""
    out = tmp_path / "diffout"
    assert main(["diff", "--from-year", "2020", "--to-year", "2024",
                 "--out", str(out)]) == EXIT_OK
    assert (out / "差异对照.md").is_file()
    assert (out / "差异对照.xlsx").is_file()
    assert (out / "evidence.json").is_file()


def test_diff_cli_same_ruleset_is_ok_without_output(tmp_path, capsys):
    """两年度同版 → 提示无数值差异、退出码 0、不写产物。"""
    assert main(["diff", "--from-year", "2024", "--to-year", "2025",
                 "--out", str(tmp_path)]) == EXIT_OK
    assert not (tmp_path / "差异对照.md").exists()
