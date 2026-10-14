"""桌面 GUI（M5 实现；此处仅占位，保证 ``gui`` 子命令的惰性导入契约可测）。

**分层纪律**：界面层**只消费编排层公开函数**（``safefee.engine.pipeline``），
零判定逻辑、零政策数值——由 AST 静态门禁守住（见 tests/test_gui_layering.py）。
"""


def main() -> int:
    """启动桌面界面。"""
    from safefee.gui import main_window

    return main_window.main()


__all__ = ["main"]
