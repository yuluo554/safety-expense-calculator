"""M5 验收门测试：行为等价三方对账 + 报告复现（E21）+ 界面冒烟。

三方对账口诀（沿用 M1 形态）：**别断言"都调了同一个函数"这种字面声明——
有效形态是三方对账**：同一输入下 CLI stdout == 编排直调格式化 == GUI 显示块。

演示素材可复现（E21 口径）：默认报告头含真实时间；"逐字节可复现"按
``--fixed-time`` 断言——同输入两次导出 sha256 一致。
"""

import builtins
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from safefee.cli.main import main
from safefee.errors import EXIT_DEP, EXIT_OK
from safefee.evidence import sha256_bytes

ROOT = Path(__file__).resolve().parent.parent

ARCHIVE = {
    "enterprise_id": "90000000SYN0000001A",
    "enterprise_name": "示例煤炭（合成）有限公司",
    "industry_id": "coal", "variant_id": "coal_high_gas", "year": 2024,
    "basis_kind": "output", "basis_value": "1000", "basis_unit": "ton",
}
FIXED_TIME = "2026-10-14T00:00:00"


def _write_archive(tmp_path: Path) -> Path:
    path = tmp_path / "archive.json"
    path.write_bytes(json.dumps(ARCHIVE, ensure_ascii=False).encode("utf-8"))
    return path


# ---------------------------------------------------------------------------
# 一、行为等价三方对账（CLI stdout == 编排直调 format_* == GUI 显示块）
# ---------------------------------------------------------------------------

def test_three_way_calc_matches(tmp_path, capsys):
    """计提：CLI stdout 逐行 == ``format_calc`` == ``calc_blocks`` 拼接。"""
    from safefee.engine import build_case, compute_calc, format_calc
    from safefee.gui import render

    archive = _write_archive(tmp_path)
    assert main(["calc", str(archive)]) == EXIT_OK
    stdout = capsys.readouterr().out.rstrip("\n")

    case = build_case(dict(ARCHIVE))
    report = compute_calc(case)
    formatted = format_calc(report)
    gui_text = render.blocks_to_text(render.calc_blocks(report))

    assert stdout == formatted
    # GUI 显示块复用 format_calc 行文本（构造性同源）
    assert gui_text.split("\n", 1)[1] == formatted  # 去掉块标题后逐行相等
    assert "30000.00" in gui_text  # 第七条高瓦斯 30 元/吨 × 1000 吨


def test_three_way_check_matches(data_dir, tmp_path, capsys):
    """支出核查：CLI stdout == ``format_check`` == ``check_blocks`` 拼接。"""
    from safefee.engine import build_case, check_ledger_file, format_check
    from safefee.gui import render

    archive = _write_archive(tmp_path)
    ledger = tmp_path / "ledger.csv"
    ledger.write_bytes(
        "item_key,subject,summary,amount\n"
        "EXP-001,安全费用,煤矿安全改造支出,120000.00\n"
        "EXP-002,管理费用,挪用于办公经费,30000.00\n".encode("utf-8")
    )
    assert main(["check", str(ledger), "--archive", str(archive)]) == 1  # 检出红线
    stdout = capsys.readouterr().out.rstrip("\n")

    case = build_case(dict(ARCHIVE))
    payload = check_ledger_file(case, ledger)
    formatted = format_check(payload)
    gui_text = render.blocks_to_text(render.check_blocks(payload))

    assert stdout == formatted
    assert gui_text.split("\n", 1)[1] == formatted
    assert "不符合" in gui_text and "命中禁止性条目" in gui_text


def test_three_way_progress_matches(data_dir, tmp_path, capsys):
    """进度判定：CLI stdout == ``format_progress`` == ``progress_blocks``。"""
    from decimal import Decimal

    from safefee.engine import build_case, compute_progress_for, format_progress
    from safefee.gui import render

    archive = _write_archive(tmp_path)
    assert main(["progress", str(archive),
                 "--accrued", "30000", "--used", "10000"]) == EXIT_OK
    stdout = capsys.readouterr().out.rstrip("\n")

    case = build_case(dict(ARCHIVE))
    payload = compute_progress_for(case, accrued=Decimal("30000"), used=Decimal("10000"))
    formatted = format_progress(payload)
    gui_text = render.blocks_to_text(render.progress_blocks(payload))

    assert stdout == formatted
    assert gui_text.split("\n", 1)[1] == formatted
    assert "使用进度：0.33（门槛 0.6）" in gui_text
    assert "是否触发披露义务：" in gui_text


def test_three_way_diff_matches(data_dir, capsys):
    """版本对照：CLI stdout == ``format_diff`` == ``diff_blocks``。"""
    from safefee.engine import compute_diff, format_diff
    from safefee.gui import render

    assert main(["diff", "--from-year", "2020", "--to-year", "2024"]) == EXIT_OK
    stdout = capsys.readouterr().out.rstrip("\n")

    report = compute_diff(2020, 2024)
    formatted = format_diff(report)
    gui_text = render.blocks_to_text(render.diff_blocks(report))

    assert stdout == formatted
    assert gui_text.split("\n", 1)[1] == formatted


def test_gui_blocks_are_pipeline_only():
    """GUI 显示装配只消费编排层结果（构造结果后无需数据目录即可装配）。"""
    from safefee.engine import build_case, compute_calc
    from safefee.gui import render

    case = build_case(dict(ARCHIVE))
    report = compute_calc(case)
    blocks = render.calc_blocks(report)
    assert blocks[0][0] == "计提计算"
    assert any("应计提金额" in row for _, rows in blocks for row in rows)


def test_calc_not_ok_surfaces_blockers(tmp_path):
    """门控拦截 / 属性必索 → ``run_calc_blocks`` 上抛，界面层不静默。"""
    from safefee.errors import MissingInput
    from safefee.gui import render

    with pytest.raises(MissingInput):
        render.run_calc_blocks({"industry_id": "coal"})


# ---------------------------------------------------------------------------
# 二、演示素材可复现（E21 口径：--fixed-time 两次 sha256 一致）
# ---------------------------------------------------------------------------

def test_calc_out_fixed_time_byte_reproducible(tmp_path):
    """``calc --out --fixed-time``：同输入两次导出三件产物 sha256 一致。"""
    from safefee.engine import build_case, build_report_input, compute_calc, export_report

    out1, out2 = tmp_path / "a", tmp_path / "b"
    for out in (out1, out2):
        case = build_case(dict(ARCHIVE))
        report = compute_calc(case, fixed_time=FIXED_TIME)
        export_report(build_report_input(case, report), out)
    for name in ("报告.md", "报告.xlsx", "evidence.json"):
        assert sha256_bytes((out1 / name).read_bytes()) == \
               sha256_bytes((out2 / name).read_bytes()), name


def test_calc_cli_fixed_time_flag_exports(tmp_path):
    """CLI 接线：``calc --out --fixed-time`` 退出码 0 且产物落盘。"""
    archive = _write_archive(tmp_path)
    out = tmp_path / "report"
    assert main(["calc", str(archive), "--out", str(out),
                 "--fixed-time", FIXED_TIME]) == EXIT_OK
    assert (out / "报告.md").is_file()
    assert (out / "报告.xlsx").is_file()
    assert "2026-10-14T00:00:00" in (out / "报告.md").read_text(encoding="utf-8")


def test_calc_default_report_carries_real_time(tmp_path):
    """默认（无 --fixed-time）报告头含真实时间（E21：默认不承诺逐字节复现）。"""
    from safefee.engine import build_case, compute_calc

    report = compute_calc(build_case(dict(ARCHIVE)))
    assert report.coordinate["generated_at"] != FIXED_TIME


def test_diff_out_stays_byte_reproducible(data_dir, tmp_path):
    """M4 口径沿用：差异对照报告**默认**即字节冻结（对照报告不含生成时间）。"""
    from safefee.ruleset.diff_report import export_diff_report

    out1, out2 = tmp_path / "a", tmp_path / "b"
    from safefee.engine import compute_diff

    report = compute_diff(2020, 2024)
    export_diff_report(report, out1)
    export_diff_report(report, out2)
    for name in ("差异对照.md", "差异对照.xlsx", "evidence.json"):
        assert (out1 / name).read_bytes() == (out2 / name).read_bytes()


# ---------------------------------------------------------------------------
# 三、界面冒烟（offscreen：窗口能建、四个页签在、导出走通）
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def qapp():
    """offscreen QApplication（CI 无显示器的等价校验）。"""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def test_gui_missing_dep_contract_via_stub(monkeypatch):
    """缺依赖契约（cmd_gui 层）：ImportError → ``OptionalDependencyMissing``。"""
    from safefee.cli import cmd_gui

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("PySide6") or name.startswith("safefee.gui"):
            raise ImportError("mocked missing PySide6")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    from safefee.errors import OptionalDependencyMissing

    with pytest.raises(OptionalDependencyMissing):
        cmd_gui.run(None)


def test_gui_window_builds_offscreen(qapp):
    """offscreen 建主窗口：四个页签、界面骨架可运行。"""
    from PySide6 import QtWidgets

    from safefee.gui.widgets import build_window

    app, window = build_window()
    from PySide6 import QtWidgets

    tabs = window.centralWidget()
    assert isinstance(tabs, QtWidgets.QTabWidget)
    assert tabs.count() == 4
    assert [tabs.tabText(i) for i in range(tabs.count())] == [
        "计提计算", "支出核查", "使用进度", "版本对照"]
    window.close()


def test_gui_calc_tab_end_to_end(qapp, tmp_path, monkeypatch):
    """界面动作全链：表单 → 计算 → 显示金额；导出走目录直选。"""
    from PySide6 import QtWidgets

    from safefee.engine import build_case, compute_calc
    from safefee.gui import widgets

    app, window = widgets.build_window()
    tabs = window.centralWidget()
    calc_page = tabs.widget(0)
    edits = calc_page.findChildren(QtWidgets.QLineEdit)
    buttons = [b for b in calc_page.findChildren(QtWidgets.QPushButton)]
    run_button = next(b for b in buttons if b.text() == "计算")

    values = [ARCHIVE["enterprise_id"], ARCHIVE["enterprise_name"],
              ARCHIVE["industry_id"], str(ARCHIVE["year"]), ARCHIVE["basis_kind"],
              ARCHIVE["basis_value"], ARCHIVE["basis_unit"], ARCHIVE["variant_id"]]
    for edit, value in zip(edits, values):
        edit.setText(value)
    run_button.click()

    shown = calc_page.findChildren(QtWidgets.QScrollArea)[0].widget()
    text = "\n".join(lbl.text() for lbl in shown.findChildren(QtWidgets.QLabel))
    assert "30000.00" in text and "第七条" in text

    # 导出：monkeypatch 目录选择 → 真导出（界面动作 = 编排层同一实现源）
    out = tmp_path / "gui-report"
    monkeypatch.setattr(widgets, "_choose_dir", lambda *a, **k: out)
    export_button = next(b for b in buttons if b.text() == "导出报告")
    export_button.click()
    assert (out / "报告.md").is_file()

    # 同输入编排直调金额一致（GUI 动作没有第二条计算路径）
    case = build_case(dict(ARCHIVE))
    assert str(compute_calc(case).result.amount) == "30000.00"
    window.close()


def test_gui_check_tab_end_to_end(qapp, tmp_path):
    """核查页全链：档案 + 台账路径 → 显示四态结论。"""
    from PySide6 import QtWidgets

    from safefee.gui import widgets

    archive = _write_archive(tmp_path)
    ledger = tmp_path / "ledger.csv"
    ledger.write_bytes(
        "item_key,subject,summary,amount\n"
        "EXP-001,安全费用,煤矿安全改造支出,120000.00\n".encode("utf-8"))

    app, window = widgets.build_window()
    tabs = window.centralWidget()
    page = tabs.widget(1)
    edits = page.findChildren(QtWidgets.QLineEdit)
    edits[0].setText(str(archive))
    edits[1].setText(str(ledger))
    next(b for b in page.findChildren(QtWidgets.QPushButton) if b.text() == "核查").click()

    shown = page.findChildren(QtWidgets.QScrollArea)[0].widget()
    text = "\n".join(lbl.text() for lbl in shown.findChildren(QtWidgets.QLabel))
    assert "符合" in text
    window.close()


def test_gui_diff_tab_end_to_end(qapp):
    """对照页全链：两年度 → 差异计数；同年度 → 提示无数值差异。"""
    from PySide6 import QtWidgets

    from safefee.gui import widgets

    app, window = widgets.build_window()
    tabs = window.centralWidget()
    page = tabs.widget(3)
    edits = page.findChildren(QtWidgets.QLineEdit)
    edits[0].setText("2020")
    edits[1].setText("2024")
    next(b for b in page.findChildren(QtWidgets.QPushButton) if b.text() == "对照").click()

    shown = page.findChildren(QtWidgets.QScrollArea)[0].widget()
    text = "\n".join(lbl.text() for lbl in shown.findChildren(QtWidgets.QLabel))
    assert "财企〔2012〕16号 → 财资〔2022〕136号" in text
    window.close()


def test_gui_missing_dependency_full_import_lock(monkeypatch):
    """**可证伪**：从 import 到调用完成全路径打桩 → 退出码 3 语义保持。"""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("PySide6"):
            raise ImportError("mocked missing PySide6")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    from safefee.cli import cmd_gui
    from safefee.errors import OptionalDependencyMissing

    with pytest.raises(OptionalDependencyMissing):
        cmd_gui.run(None)
