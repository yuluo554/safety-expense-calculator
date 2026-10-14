"""``gui`` 子命令：惰性导入 PySide6。

**惰性导入纪律**：``try`` 必须包住**从 import 到调用完成**的整条路径
——不是只包 import 那一行。分层越严（重件只许在函数体内 import），
边界越靠后越容易漏包。

回归 = 用 ``builtins.__import__`` 打桩让 ``PySide6`` 抛 ImportError，
断言返回退出码 3 而非裸异常（本机即可复现，不必等 CI）。
"""

from safefee.errors import EXIT_DEP


def run(args) -> int:
    from safefee.errors import OptionalDependencyMissing

    try:
        from safefee.gui import main_window

        return main_window.main()
    except ImportError as exc:
        raise OptionalDependencyMissing(
            "桌面界面需要 PySide6：源码态请安装 pip install -e \".[gui]\"；"
            "若为发行包（exe），本发行包未内嵌该功能（%s）" % exc
        )


__all__ = ["run"]
