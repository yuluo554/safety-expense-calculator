"""冻结产物与确定性测试。

* 规则包为**生成器冻结产物**：``--check`` 再生成逐字节一致；
* **禁 stdlib random / 禁 set 迭代序 / 禁系统时钟**（AST 静态断言）；
* 字节冻结**两层**：文本 EOL（CR 守门）+ zip 容器（``create_system=0``）。
"""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"


def _run_tool(name: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(TOOLS / name)] + list(args),
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",     # 子进程显式 encoding（无环境变量可替代）
        errors="replace",
    )


def test_rulesets_regeneration_is_byte_identical():
    result = _run_tool("gen_rulesets.py", "--check")
    assert result.returncode == 0, result.stdout
    assert "FROZEN_RULESETS_OK" in result.stdout


def test_samples_regeneration_is_byte_identical():
    result = _run_tool("gen_samples.py", "--check")
    assert result.returncode == 0, result.stdout
    assert "FROZEN_SAMPLES_OK" in result.stdout


def test_truth_skeleton_regeneration_is_byte_identical():
    result = _run_tool("gen_synthetic.py", "--check")
    assert result.returncode == 0, result.stdout
    assert "FROZEN_TRUTH_OK" in result.stdout


def _tool_ast(name: str) -> ast.Module:
    return ast.parse((TOOLS / name).read_text(encoding="utf-8"))


def test_generators_do_not_import_stdlib_random():
    """确定性生成纪律：**禁 stdlib random**（不承诺跨版本序列一致）。"""
    for name in ("gen_rulesets.py", "gen_samples.py", "gen_synthetic.py"):
        tree = _tool_ast(name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "random", "%s 不得 import random" % name
            if isinstance(node, ast.ImportFrom):
                assert node.module != "random", "%s 不得 from random import" % name


def test_generators_do_not_use_wall_clock():
    """确定性生成纪律：**禁系统时钟**（落盘产物不得含时间戳）。"""
    banned = {"datetime", "time"}
    for name in ("gen_rulesets.py", "gen_samples.py", "gen_synthetic.py"):
        tree = _tool_ast(name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in banned, "%s 不得 import %s" % (name, alias.name)


def test_generators_use_write_bytes_not_write_text():
    """确定性落盘：``write_bytes``（``write_text`` 默认把 ``\\n`` 翻成 ``\\r\\n``）。"""
    for name in ("gen_rulesets.py", "gen_samples.py", "gen_synthetic.py"):
        source = (TOOLS / name).read_text(encoding="utf-8")
        assert ".write_text(" not in source, "%s 应使用 write_bytes（避免 CRLF 漂移）" % name


def test_tracked_text_files_have_no_cr(root):
    """**CR 守门**：跟踪文本文件不得含 CR（EOL 门，跨机器复现性的前置）。"""
    offenders = []
    for path in sorted((root / "src").rglob("*.py")):
        if b"\r\n" in path.read_bytes():
            offenders.append(str(path.relative_to(root)))
    for path in sorted((root / "data").rglob("*.json")):
        if b"\r\n" in path.read_bytes():
            offenders.append(str(path.relative_to(root)))
    for path in sorted((root / "tests").rglob("*.py")):
        if b"\r\n" in path.read_bytes():
            offenders.append(str(path.relative_to(root)))
    assert not offenders, "以下文件含 CR（EOL 漂移）：%s" % ", ".join(offenders)


def test_frozen_rules_json_has_no_cr(data_dir):
    """冻结规则包不得含 CR（否则跨平台 sha256 漂移、完整性校验假失败）。"""
    offenders = [str(p) for p in (data_dir / "rules").rglob("*.json")
                 if b"\r\n" in p.read_bytes()]
    assert not offenders, "规则包含 CR：%s" % ", ".join(offenders)
