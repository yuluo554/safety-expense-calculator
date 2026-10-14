"""脱敏审计守门测试（含 selftest 阳性+阴性对照）。"""

import importlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(TOOLS / "dessensitize_audit.py")] + list(args),
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )


def test_audit_selftest_passes():
    result = _run("--selftest")
    assert result.returncode == 0, result.stdout
    assert "DESSENSITIZE_SELFTEST_OK" in result.stdout


def test_tracked_tree_passes_audit():
    result = _run()
    assert result.returncode == 0, result.stdout
    assert "DESSENSITIZE_AUDIT_OK" in result.stdout


def test_audit_detects_injected_email():
    """变异验证：扫描器必须能检出真实泄露形态。"""
    sys.path.insert(0, str(TOOLS))
    scanner = importlib.import_module("dessensitize_audit")
    hits = scanner.scan_text("owner: " + "real" + "@" + "example.com\n")
    assert hits.get(scanner.HARD)


def test_audit_exempts_noreply_and_transport_addresses():
    """**豁免项进阴性对照**（否则下次改规则又误报）。"""
    sys.path.insert(0, str(TOOLS))
    scanner = importlib.import_module("dessensitize_audit")
    assert scanner.scan_text("user@users.noreply.github.com\n") == {}
    assert scanner.scan_text("git@github.com\n") == {}
    assert scanner.scan_text("https://github.com/example/repo\n") == {}


def test_audit_output_does_not_echo_sensitive_strings():
    """**输出掩码化**：留档会引用输出，输出本身不得成为二次泄漏源。"""
    sys.path.insert(0, str(TOOLS))
    scanner = importlib.import_module("dessensitize_audit")
    masked = scanner._mask("some/path/file.py")
    assert masked == "some/path/file.py"
    source = (TOOLS / "dessensitize_audit.py").read_text(encoding="utf-8")
    assert "value)" not in source or "counts" in source
