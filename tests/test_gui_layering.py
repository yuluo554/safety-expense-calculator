"""GUI 分层静态门禁（**三条齐上**——只守 import 面漏得掉一半）。

* **不 import 规则层**：界面层唯一入口是 ``safefee.engine.pipeline``；
* **无算术运算**：``BinOp`` 且两侧操作数均非字符串字面量的 ``* / - // % **``
  （字符串 ``*``/``+`` 是排版，不算）；
* **无政策数值字面量**：与引擎侧同一份禁用 token 表。

判别口诀：**"层里没有判定逻辑"要能被机器证明，而"不 import 引擎"只证明了通道，
没证明内容。**
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GUI_DIR = ROOT / "src" / "safefee" / "gui"

#: 界面层禁止直接 import 的领域层内部模块
FORBIDDEN_MODULES = (
    "safefee.rules", "safefee.ruleset", "safefee.accrual", "safefee.tiered",
    "safefee.spending", "safefee.batch", "safefee.bench", "safefee.truth",
    "safefee.report.sections", "safefee.rules.manifest",
)

#: 政策数值禁用 token（与 tools/scan_policy_literals.py 同源语义）
BANNED_NUMERIC_LITERALS = {
    "10000000", "100000000", "1000000000", "500000000", "5000000000",
    "0.045", "0.0225", "0.0055", "0.002", "0.035", "0.03", "0.025", "0.02", "0.015",
    "0.6", "0.60",
}


def _gui_files():
    return sorted(GUI_DIR.rglob("*.py"))


def test_gui_files_exist():
    assert _gui_files(), "GUI 包应存在（M0 占位）"


@pytest.mark.parametrize("path", _gui_files(), ids=lambda p: p.name)
def test_gui_does_not_import_domain_internals(path):
    """守门一：不 import 规则层（唯一入口 = engine.pipeline）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for forbidden in FORBIDDEN_MODULES:
                    assert not alias.name.startswith(forbidden), (
                        "%s 直接 import 领域层内部模块 %s" % (path.name, alias.name)
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for forbidden in FORBIDDEN_MODULES:
                assert not module.startswith(forbidden), (
                    "%s 直接 import 领域层内部模块 %s" % (path.name, module)
                )


@pytest.mark.parametrize("path", _gui_files(), ids=lambda p: p.name)
def test_gui_has_no_arithmetic_operations(path):
    """守门二：无算术 ``BinOp``（两侧操作数均非字符串字面量）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    banned_ops = (ast.Mult, ast.Div, ast.Sub, ast.FloorDiv, ast.Mod, ast.Pow)
    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, banned_ops):
            continue
        # 字符串 * int / str + str 是排版，不算判定逻辑
        operands = (node.left, node.right)
        if any(isinstance(op, ast.Constant) and isinstance(op.value, str) for op in operands):
            continue
        raise AssertionError(
            "%s 第 %d 行含算术运算（界面层不得做判定逻辑）"
            % (path.name, getattr(node, "lineno", -1))
        )


@pytest.mark.parametrize("path", _gui_files(), ids=lambda p: p.name)
def test_gui_has_no_policy_numeric_literals(path):
    """守门三：无政策数值字面量（与引擎侧同一份禁用表）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            assert str(node.value) not in BANNED_NUMERIC_LITERALS, (
                "%s 第 %d 行内联政策数值 %s" % (path.name, getattr(node, "lineno", -1), node.value)
            )


def test_gui_guard_is_falsifiable():
    """**可证伪**：构造含算术的样本 → 守门必须报错（防"门是空的"）。"""
    sample = ast.parse("def f(a, b):\n    return a * b\n")
    banned = (ast.Mult,)
    found = [
        node for node in ast.walk(sample)
        if isinstance(node, ast.BinOp) and isinstance(node.op, banned)
    ]
    assert found, "守门未能检出样本中的算术运算"
