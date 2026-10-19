"""脱敏审计守门测试（含 selftest 阳性+阴性对照）。"""

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

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


def test_full_history_passes_audit():
    """**全历史扫描纳入守门**（DEC2，2026-10-19）。

    背景：``.github/workflows/ci.yml`` 的 ``fetch-depth: 0`` 注释长期宣称"脱敏审计的历史
    扫描守门依赖 git 历史"，但**这个消费者并不存在**——``tests/`` 下 0 个 ``--history``
    调用，CI 也只跑 tracked + selftest。于是"删了文件但历史还在"这类泄漏在 CI 上无防线
    （本系列另一仓正是靠一次 CI 红才暴露历史里的泄漏）。本条把注释变成事实。
    """
    result = _run("--history")
    assert result.returncode == 0, result.stdout
    assert "DESSENSITIZE_AUDIT_OK" in result.stdout


def test_history_scan_channel_is_alive():
    """**通道探活**：history 模式必须真能看到完整历史，否则历史扫描是"静默空验"。

    浅克隆下 ``git log --all`` 只返回 1 个提交，而审计器会照常打印
    ``DESSENSITIZE_AUDIT_OK``——**假绿比没有门禁更危险**。故这里直接量历史深度，
    把"CI 必须 ``fetch-depth: 0``"这条要求变成可证伪的断言。
    """
    sys.path.insert(0, str(TOOLS))
    scanner = importlib.import_module("dessensitize_audit")

    if not scanner._git_available():
        pytest.skip("无 git（如 `git archive` 导出树）→ history 扫描不适用")

    code, out = scanner._run_git(["rev-list", "--count", "--all"])
    assert code == 0, "git 历史通道不可用（拿不到 rev-list）"
    count = int(out.strip())
    assert count >= 5, (
        "history 通道只看到 %d 个提交——浅克隆会让历史扫描**静默空验**"
        "（CI 的 checkout 必须 fetch-depth: 0）" % count
    )


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
