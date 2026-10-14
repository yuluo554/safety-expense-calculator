"""PySide6 界面件（**Qt 相关代码唯一所在**；``render.py`` 与测试不 import 它）。

纪律：本模块只做"拿 :mod:`safefee.gui.render` 的显示块上屏 + 调编排层动作 +
导出报告"，零判定逻辑、零政策数值（AST 三条守门守住）。异常处理只做
"把错误文本显示出来"，不吞成静默。
"""

from decimal import Decimal, InvalidOperation
from pathlib import Path

from safefee.engine import pipeline
from safefee.gui import render


def _make_app():
    """QApplication 单例（现有实例复用；offscreen 平台可跑）。"""
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _blocks_to_widget(blocks):
    """显示块序列 → 只读面板（标题加粗 + 行文本可选）。"""
    from PySide6 import QtWidgets
    from PySide6.QtCore import Qt

    container = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(container)
    for title, rows in blocks:
        heading = QtWidgets.QLabel("<b>%s</b>" % title)
        layout.addWidget(heading)
        for row in rows:
            line = QtWidgets.QLabel(str(row))
            line.setTextInteractionFlags(Qt.TextSelectableByMouse)
            line.setWordWrap(True)
            layout.addWidget(line)
    layout.addStretch(1)
    return container


def _result_area():
    from PySide6 import QtWidgets

    area = QtWidgets.QScrollArea()
    area.setWidgetResizable(True)
    return area


def _show_blocks(area, blocks):
    """把显示块挂进结果区（各页共用）。"""
    area.setWidget(_blocks_to_widget(blocks))


def _show_error(area, exc):
    """错误文本上屏（不吞、不自行判定）。"""
    from safefee.errors import SafeFeeError

    message = str(exc) if isinstance(exc, SafeFeeError) else "%s: %s" % (type(exc).__name__, exc)
    _show_blocks(area, [("错误", [message])])


def _form_row(form, label):
    from PySide6 import QtWidgets

    row = QtWidgets.QHBoxLayout()
    row.addWidget(QtWidgets.QLabel(label))
    edit = QtWidgets.QLineEdit()
    row.addWidget(edit)
    form.addLayout(row)
    return edit


def _choose_dir(window, title):
    """目录选择对话框 → Path 或 None（取消）。"""
    from PySide6 import QtWidgets

    chosen = QtWidgets.QFileDialog.getExistingDirectory(window, title)
    return Path(chosen) if chosen else None


def _calc_tab(window):
    """计提页：档案表单 → 计算 / 导出报告。"""
    from PySide6 import QtWidgets

    page = QtWidgets.QWidget()
    outer = QtWidgets.QVBoxLayout(page)
    form = QtWidgets.QVBoxLayout()
    fields = {
        "enterprise_id": _form_row(form, "企业编号"),
        "enterprise_name": _form_row(form, "企业名称"),
        "industry_id": _form_row(form, "行业代码（如 coal）"),
        "year": _form_row(form, "年度（如 2024）"),
        "basis_kind": _form_row(form, "依据类型（output/revenue/……）"),
        "basis_value": _form_row(form, "依据量"),
        "basis_unit": _form_row(form, "依据单位（ton/CNY/……）"),
        "variant_id": _form_row(form, "变体（可空，如 coal_high_gas）"),
    }
    outer.addLayout(form)

    buttons = QtWidgets.QHBoxLayout()
    run_button = QtWidgets.QPushButton("计算")
    export_button = QtWidgets.QPushButton("导出报告")
    buttons.addWidget(run_button)
    buttons.addWidget(export_button)
    outer.addLayout(buttons)

    area = _result_area()
    outer.addWidget(area)

    def _payload():
        return render.archive_payload(
            enterprise_id=fields["enterprise_id"].text().strip(),
            enterprise_name=fields["enterprise_name"].text().strip(),
            industry_id=fields["industry_id"].text().strip(),
            year=int(fields["year"].text().strip() or "0"),
            basis_kind=fields["basis_kind"].text().strip(),
            basis_value=fields["basis_value"].text().strip(),
            basis_unit=fields["basis_unit"].text().strip(),
            variant_id=fields["variant_id"].text().strip(),
        )

    def on_run():
        try:
            _show_blocks(area, render.run_calc_blocks(_payload()))
        except Exception as exc:  # noqa: BLE001 —— 界面只负责显示
            _show_error(area, exc)

    def on_export():
        from safefee.engine import build_case, build_report_input, export_report

        try:
            case = build_case(_payload())
            report = pipeline.compute_calc(case)
            if report.result is None:
                _show_blocks(area, [("导出", ["计提无结果（门控拦截或属性必索），不导出"])])
                return
            out = _choose_dir(window, "选择报告输出目录")
            if out is None:
                return
            written = export_report(build_report_input(case, report), out)
            _show_blocks(area, [("导出", [
                "已写出：%s" % ", ".join(path.name for path in written)])])
        except Exception as exc:  # noqa: BLE001
            _show_error(area, exc)

    run_button.clicked.connect(on_run)
    export_button.clicked.connect(on_export)
    return page


def _check_tab(window):
    """支出核查页：档案 + 台账 CSV → 四态结论。"""
    from PySide6 import QtWidgets

    page = QtWidgets.QWidget()
    outer = QtWidgets.QVBoxLayout(page)
    archive_edit = _form_row(outer, "企业档案 JSON 路径")
    ledger_edit = _form_row(outer, "支出台账 CSV 路径")
    run_button = QtWidgets.QPushButton("核查")
    outer.addWidget(run_button)
    area = _result_area()
    outer.addWidget(area)

    def on_run():
        try:
            payload = pipeline.load_archive(Path(archive_edit.text().strip()))
            case = pipeline.build_case(payload)
            report = pipeline.check_ledger_file(case, Path(ledger_edit.text().strip()))
            _show_blocks(area, render.check_blocks(report))
        except Exception as exc:  # noqa: BLE001
            _show_error(area, exc)

    run_button.clicked.connect(on_run)
    return page


def _progress_tab(window):
    """使用进度页：档案 + 应计提/实际使用 → 门槛判定。"""
    from PySide6 import QtWidgets

    page = QtWidgets.QWidget()
    outer = QtWidgets.QVBoxLayout(page)
    archive_edit = _form_row(outer, "企业档案 JSON 路径")
    accrued_edit = _form_row(outer, "年度应计提额（元）")
    used_edit = _form_row(outer, "当年实际使用额（元）")
    run_button = QtWidgets.QPushButton("判定")
    outer.addWidget(run_button)
    area = _result_area()
    outer.addWidget(area)

    def on_run():
        try:
            payload = pipeline.load_archive(Path(archive_edit.text().strip()))
            case = pipeline.build_case(payload)
            report = pipeline.compute_progress_for(
                case,
                accrued=Decimal(accrued_edit.text().strip()),
                used=Decimal(used_edit.text().strip()),
            )
            _show_blocks(area, render.progress_blocks(report))
        except InvalidOperation as exc:
            _show_error(area, exc)
        except Exception as exc:  # noqa: BLE001
            _show_error(area, exc)

    run_button.clicked.connect(on_run)
    return page


def _diff_tab(window):
    """版本对照页：两年度 → 差异清单 + 对照报告导出。"""
    from PySide6 import QtWidgets

    page = QtWidgets.QWidget()
    outer = QtWidgets.QVBoxLayout(page)
    from_edit = _form_row(outer, "起始年度（如 2020）")
    to_edit = _form_row(outer, "目标年度（如 2024）")
    buttons = QtWidgets.QHBoxLayout()
    run_button = QtWidgets.QPushButton("对照")
    export_button = QtWidgets.QPushButton("导出对照报告")
    buttons.addWidget(run_button)
    buttons.addWidget(export_button)
    outer.addLayout(buttons)
    area = _result_area()
    outer.addWidget(area)

    state = {"report": None}

    def on_run():
        try:
            report = pipeline.compute_diff(
                int(from_edit.text().strip() or "0"), int(to_edit.text().strip() or "0")
            )
            state["report"] = report
            _show_blocks(area, render.diff_blocks(report))
        except Exception as exc:  # noqa: BLE001
            _show_error(area, exc)

    def on_export():
        from safefee.engine import export_diff_report

        report = state["report"]
        if report is None:
            _show_blocks(area, [("导出", ["请先执行对照"])])
            return
        out = _choose_dir(window, "选择对照报告输出目录")
        if out is None:
            return
        written = export_diff_report(report, out)
        _show_blocks(area, [("导出", [
            "已写出：%s" % ", ".join(path.name for path in written)])])

    run_button.clicked.connect(on_run)
    export_button.clicked.connect(on_export)
    return page


def build_window():
    """主窗口：档案表单 + 四个结果页（计提/核查/进度/对照）。"""
    from PySide6 import QtWidgets

    app = _make_app()
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("企业安全生产费用提取与使用合规计算工作台")

    tabs = QtWidgets.QTabWidget()
    window.setCentralWidget(tabs)
    tabs.addTab(_calc_tab(window), "计提计算")
    tabs.addTab(_check_tab(window), "支出核查")
    tabs.addTab(_progress_tab(window), "使用进度")
    tabs.addTab(_diff_tab(window), "版本对照")

    window.resize(960, 640)
    return app, window


__all__ = ["build_window"]
