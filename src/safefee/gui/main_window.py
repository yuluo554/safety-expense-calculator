"""桌面界面主窗口（M5 实现）。

**分层纪律**（AST 静态门禁守住）：

* 界面层**不得直接 import 领域层内部模块**，唯一入口是 ``safefee.engine.pipeline``；
* **零判定逻辑**：不得做算术（``BinOp`` 且两侧非字符串字面量的 ``* / - // % **``）；
* **零政策数值字面量**：与引擎侧同一份禁用 token 表。

M5 前此文件仅提供 ``main()`` 契约，供 ``cli.cmd_gui`` 的惰性导入路径可测。
"""


def main() -> int:
    """启动界面（M5 前：显式报告未实现，返回退出码 3 语义之外的明确提示）。"""
    from safefee.errors import OptionalDependencyMissing

    raise OptionalDependencyMissing("桌面界面将在 M5 交付（当前为 M0 骨架）")


__all__ = ["main"]
