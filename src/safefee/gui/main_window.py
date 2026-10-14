"""桌面界面主窗口（M5 交付）。

**分层纪律**（AST 静态门禁守住，见 ``tests/test_gui_layering.py``）：

* 界面层**不得直接 import 领域层内部模块**，唯一入口是 ``safefee.engine.pipeline``；
* **零判定逻辑**：不得做算术（``BinOp`` 且两侧非字符串字面量的 ``* / - // % **``）；
* **零政策数值字面量**：与引擎侧同一份禁用 token 表。

职责链：``cli.cmd_gui``（惰性导入 + 缺依赖退出码 3）→ 本模块 ``main()``
→ ``gui.widgets.build_window()``（Qt 全部隔离在这之下）→ ``gui.render``
（无 Qt 显示装配，三方对账的第三条腿）。
"""

import sys


def main() -> int:
    """启动界面（Qt 主循环；``Ctrl+C`` 交还终端常规退出）。"""
    from safefee.gui.widgets import build_window

    app, window = build_window()
    window.show()
    return app.exec()


__all__ = ["main"]
