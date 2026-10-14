"""GUI 发行包入口（PyInstaller ``safefee-gui.exe`` 专用）。

与 ``python -m safefee gui`` 的差异：无控制台（spec ``console=False``）、
不经 argparse——直接进界面主循环。缺 PySide6 在冻结态不可达（已内嵌），
故此处无需退出码 3 兜底；源码态启动请走 ``safefee gui``。

编码守卫不在此安装：无控制台的窗口态没有 stdout 可保护
（守卫唯一实现源在 ``cli.main``，见 tests/test_stdio_guard.py 的入口清单）。
"""

import sys


def main() -> int:
    from safefee.gui.widgets import build_window

    app, window = build_window()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
