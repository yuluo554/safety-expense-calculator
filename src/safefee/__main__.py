"""``python -m safefee`` 入口（等价于 ``safefee`` 控制台命令）。

编码守卫由 ``safefee.cli.main:main`` 首行安装——本模块只做转发，不重复打印，
故不含独立守卫（守卫唯一实现源在 ``cli.main``，见 tests/test_stdio_guard.py 的入口清单）。
"""

from safefee.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
