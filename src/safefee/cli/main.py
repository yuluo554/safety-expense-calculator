"""CLI 入口（argparse，零第三方依赖）。

退出码契约（锁进测试，重构不漂移）::

    0  成功        1  门控拦截 / 基准未达标 / 检出不符合
    2  输入用法错误   3  可选依赖缺失

**编码守卫**：``main`` 首行即 ``_ensure_utf8_stdio()``——本机 ``-X utf8`` 只救
"我们敲的命令"，救不了 CI 管道（cp1252）与用户终端。
"""

import argparse
import json
import sys
from pathlib import Path

from safefee import __version__
from safefee._stdio import _ensure_utf8_stdio
from safefee.errors import (
    EXIT_DEP,
    EXIT_GATE,
    EXIT_OK,
    EXIT_USAGE,
    GateBlocked,
    OptionalDependencyMissing,
    SafeFeeError,
    ScanItemError,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="safefee",
        description="企业安全生产费用提取与使用合规计算工作台（财资〔2022〕136号规则集）",
    )
    parser.add_argument("--data-dir", default=None, help="数据目录（默认自动定位）")
    parser.add_argument("--version", action="version", version="safefee %s" % __version__)
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("version", help="打印版本")

    sub.add_parser("selfcheck", help="数据目录定位 + 规则集加载 + 门控计数")
    sub.add_parser("units", help="单位换算表")

    p_rulesets = sub.add_parser("rulesets", help="规则集清单与状态")
    p_rulesets.add_argument("--json", action="store_true", help="以 JSON 输出")

    p_calc = sub.add_parser("calc", help="计提计算")
    p_calc.add_argument("archive", help="企业档案 JSON")
    p_calc.add_argument("--json", action="store_true", help="以 JSON 输出")

    p_check = sub.add_parser("check", help="支出范围合规核查")
    p_check.add_argument("ledger", help="支出明细台账 CSV")
    p_check.add_argument("--archive", required=True, help="企业档案 JSON（提供行业与年度）")
    p_check.add_argument("--json", action="store_true")

    p_prog = sub.add_parser("progress", help="使用进度与披露核查")
    p_prog.add_argument("archive", help="企业档案 JSON")
    p_prog.add_argument("--accrued", required=True, help="年度应计提额（元）")
    p_prog.add_argument("--used", required=True, help="当年实际使用额（元）")
    p_prog.add_argument("--json", action="store_true")

    p_scan = sub.add_parser("scan", help="批量台账扫描")
    p_scan.add_argument("directory", help="台账目录")
    p_scan.add_argument("--out", required=True, help="报告输出目录")
    p_scan.add_argument("--baseline", default=None, help="上轮结果 JSON（启用跨年对账）")
    p_scan.add_argument("--report", action="store_true", help="扫描结果直接驱动报告导出（MD/XLSX/evidence）")

    p_diff = sub.add_parser("diff", help="双版本差异对照")
    p_diff.add_argument("--from-year", type=int, required=True)
    p_diff.add_argument("--to-year", type=int, required=True)
    p_diff.add_argument("--out", default=None, help="对照报告输出目录（MD/XLSX/evidence）")
    p_diff.add_argument("--json", action="store_true")

    p_bench = sub.add_parser("bench", help="内置评测基准")
    p_bench.add_argument("--only", default=None, help="只跑某套件（未知名 → 退出码 2）")
    p_bench.add_argument("--json", action="store_true")

    sub.add_parser("gui", help="启动桌面界面（惰性导入 PySide6）")
    return parser


def main(argv=None) -> int:
    _ensure_utf8_stdio()
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return EXIT_USAGE

    try:
        return _dispatch(args)
    except OptionalDependencyMissing as exc:
        print("依赖缺失：%s" % exc, file=sys.stderr)
        return EXIT_DEP
    except GateBlocked as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_GATE
    except ScanItemError as exc:
        # 单件读取失败（坏 JSON / 缺文件 / 缺字段）→ 输入不可用（退出码 2）
        print("输入不可用（%s）：%s" % (exc.reason_code, exc.detail), file=sys.stderr)
        return EXIT_USAGE
    except SafeFeeError as exc:
        print("错误：%s" % exc, file=sys.stderr)
        return getattr(exc, "exit_code", EXIT_USAGE)
    except KeyboardInterrupt:
        return EXIT_USAGE


def _dispatch(args) -> int:
    command = args.command
    if command == "version":
        print("safefee %s" % __version__)
        return EXIT_OK
    if command == "selfcheck":
        from safefee.cli.cmd_selfcheck import run
        return run(args)
    if command == "units":
        from safefee.cli.cmd_selfcheck import run_units
        return run_units(args)
    if command == "rulesets":
        from safefee.cli.cmd_selfcheck import run_rulesets
        return run_rulesets(args)
    if command == "calc":
        from safefee.cli.cmd_calc import run
        return run(args)
    if command == "check":
        from safefee.cli.cmd_calc import run_check
        return run_check(args)
    if command == "progress":
        from safefee.cli.cmd_calc import run_progress
        return run_progress(args)
    if command == "scan":
        from safefee.cli.cmd_scan import run
        return run(args)
    if command == "diff":
        from safefee.cli.cmd_diff import run
        return run(args)
    if command == "bench":
        from safefee.cli.cmd_bench import run
        return run(args)
    if command == "gui":
        from safefee.cli.cmd_gui import run
        return run(args)
    raise AssertionError("未接线的子命令：%s" % command)


if __name__ == "__main__":
    raise SystemExit(main())
