"""零政策字面量门禁测试（含 **--selftest 阳性对照**）。

门禁的价值全在"它真的会红"——故本测试既断言当前仓库通过，也断言
**扫描器本身可证伪**（构造含禁用 token 的样本 → 必须报命中）。
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(TOOLS / "scan_policy_literals.py")] + list(args),
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )


def test_repo_passes_policy_literal_gate():
    result = _run()
    assert result.returncode == 0, result.stdout
    assert "NO_POLICY_LITERALS_OK" in result.stdout


def test_scanner_selftest_positive_control():
    """**阳性对照**：构造含禁用 token 的样本 → 扫描器必须报命中。"""
    result = _run("--selftest")
    assert result.returncode == 0, result.stdout
    assert "NO_POLICY_LITERALS_SELFTEST_OK" in result.stdout


def test_scanner_detects_injected_literal(tmp_path):
    """变异验证：把禁用 token 注入一份源码副本 → 扫描器必须变红。"""
    sys.path.insert(0, str(TOOLS))
    import importlib

    scanner = importlib.import_module("scan_policy_literals")
    hits = scanner.scan_text("VALUE = 10000000\n")
    assert hits, "扫描器未能检出注入的政策数值"
    assert hits[0][1] == "10000000"


def test_scanner_ignores_exempt_values():
    """豁免口径：定义性换算与精度约定不得误报。"""
    sys.path.insert(0, str(TOOLS))
    import importlib

    scanner = importlib.import_module("scan_policy_literals")
    assert scanner.scan_text("PRECISION = 0.01\n") == []
    assert scanner.scan_text("x = 10000  # audit-allow\n") == []
