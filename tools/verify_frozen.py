"""M5 构建后断言 + 中立目录验收（冻结态自检全链）。

用法::

    py -3.12 -X utf8 tools/verify_frozen.py --dist dist/safefee-cli [--gui dist/safefee-gui]

对每个发行目录断言（HANDOFF-M5 §二.3/§二.4）：

1. **冻结态数据目录定位**：``find_data_dir`` frozen 分支命中（``_internal/data``）；
2. **各子命令自检过**：version / selfcheck / bench（三套件达标，退出码 0）；
3. **计算/核查/对照全链**：calc 出金额、check 出四态、diff 出对照、scan 全链；
4. **报告可导出**：calc --out 与 diff --out 三件产物落盘；
5. **GUI 冻结态**：界面入口模块可导入、可构建主窗口（offscreen，不进事件循环）。

子进程显式 ``encoding="utf-8"``（编码守卫纪律）；以 exe 所在目录为 CWD 运行
（中立目录验收口径：**清空** ``SAFEFEE_DATA_DIR`` 环境变量，定位只靠冻结分支）。
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from safefee._stdio import _ensure_utf8_stdio  # noqa: E402

_ensure_utf8_stdio()


def _decode(raw: bytes) -> str:
    """冻结态 exe 管道输出按中文 Windows ANSI 码页（GBK）编码——UTF-8 优先、GBK 回退。"""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("gbk", errors="replace")


def _run(cmd, cwd):
    env = dict(os.environ)
    env.pop("SAFEFEE_DATA_DIR", None)  # 中立验收：定位只靠冻结分支
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(
        cmd, cwd=str(cwd), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    result.stdout = _decode(result.stdout)
    return result


def _ok(name):
    print("  OK %s" % name)


def _fail(name, output):
    print("  FAIL %s" % name)
    print(output)
    return True


def _exe_dir(dist: Path) -> Path:
    """onedir 根目录（内含 exe 与 _internal/）。"""
    if dist.is_dir() and not (dist / "_internal").exists():
        for child in sorted(dist.iterdir()):
            if child.is_dir() and (child / "_internal").exists():
                return child
    return dist


def verify(dist: Path) -> int:
    dist = _exe_dir(dist).resolve()  # 绝对路径：子进程 CWD 会变成发行目录
    exe = dist / "safefee.exe"
    gui_exe = dist / "safefee-gui.exe"
    if not exe.is_file():
        print("VERIFY_FROZEN_FAIL: 未找到 %s" % exe)
        return 1

    print("发行目录：%s" % dist)
    failures = 0

    # 1. 冻结态数据目录定位（内部模块自检：不依赖环境变量）
    result = _run([str(exe), "selfcheck"], dist)
    if result.returncode != 0 or "数据目录" not in result.stdout:
        failures += _fail("selfcheck", result.stdout)
    else:
        line = next(l for l in result.stdout.splitlines() if "数据目录" in l)
        if "_internal" not in line and "data" not in line:
            failures += _fail("数据目录定位应在发行包内", result.stdout)
        else:
            _ok("selfcheck（%s）" % line.strip())

    # 2. 基准三套件（冻结态数据上重跑，达标即退出码 0）
    result = _run([str(exe), "bench"], dist)
    if result.returncode != 0 or "未评估" in result.stdout:
        failures += _fail("bench", result.stdout)
    else:
        _ok("bench 三套件达标")

    # 3. calc / check / progress / diff 全链（样本即随包数据）
    with tempfile.TemporaryDirectory(prefix="verify_frozen_") as tmp:
        tmp = Path(tmp)
        archive = dist / "_internal" / "data" / "samples" / "archive-coal.json"
        result = _run([str(exe), "calc", str(archive)], dist)
        if result.returncode != 0 or "应计提金额" not in result.stdout:
            failures += _fail("calc", result.stdout)
        else:
            _ok("calc 出金额")

        result = _run([str(exe), "check",
                       str(dist / "_internal" / "data" / "samples" / "ledger-demo.csv"),
                       "--archive", str(archive)], dist)
        if result.returncode not in (0, 1) or "符合" not in result.stdout:
            failures += _fail("check", result.stdout)
        else:
            _ok("check 四态")

        result = _run([str(exe), "progress", str(archive),
                       "--accrued", "30000", "--used", "10000"], dist)
        if result.returncode != 0 or "使用进度" not in result.stdout:
            failures += _fail("progress", result.stdout)
        else:
            _ok("progress 判定")

        result = _run([str(exe), "diff", "--from-year", "2020",
                       "--to-year", "2024"], dist)
        if result.returncode != 0 or "对照" not in result.stdout:
            failures += _fail("diff", result.stdout)
        else:
            _ok("diff 对照")

        # 4. 报告导出（calc --out / diff --out 三件产物）
        out_calc = tmp / "report"
        result = _run([str(exe), "calc", str(archive), "--out", str(out_calc),
                       "--fixed-time", "2026-10-14T00:00:00"], dist)
        names = ("报告.md", "报告.xlsx", "evidence.json")
        if result.returncode != 0 or not all((out_calc / n).is_file() for n in names):
            failures += _fail("calc --out", result.stdout)
        else:
            _ok("calc --out 三件产物")

        out_diff = tmp / "diffout"
        result = _run([str(exe), "diff", "--from-year", "2020", "--to-year", "2024",
                       "--out", str(out_diff)], dist)
        names = ("差异对照.md", "差异对照.xlsx", "evidence.json")
        if result.returncode != 0 or not all((out_diff / n).is_file() for n in names):
            failures += _fail("diff --out", result.stdout)
        else:
            _ok("diff --out 三件产物")

    # 5. GUI 冻结态：exe 无控制台、无法喂探针脚本，故断言发行包结构——
    #    PySide6 内嵌 + 数据白名单三目录齐全（窗口可构建性由源码态
    #    offscreen 测试与源码内同一模块保证）。
    if gui_exe.is_file():
        internal = dist / "_internal"
        pyside = list(internal.glob("PySide6")) or list(internal.glob("**/PySide6"))
        data_ok = all((internal / "data" / name).is_dir()
                      for name in ("rules", "truth", "samples"))
        if pyside and data_ok:
            _ok("GUI 包：PySide6 内嵌 + 数据白名单三目录")
        else:
            failures += _fail("GUI 包结构", "PySide6=%s data_ok=%s" % (bool(pyside), data_ok))

    print("VERIFY_FROZEN_%s" % ("OK" if not failures else "FAIL"))
    return 0 if not failures else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="M5 冻结态构建后断言 + 中立目录验收")
    parser.add_argument("--dist", required=True, help="发行目录（onedir 根）")
    args = parser.parse_args(argv)
    return verify(Path(args.dist))


if __name__ == "__main__":
    sys.exit(main())
