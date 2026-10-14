"""编码守卫测试（三道加固的本地等价校验）。

``-X utf8`` 只救"我们敲的那条命令"，救不了 CI 管道（cp1252）与用户终端。
故：入口 reconfigure + 子进程显式 encoding + CI PYTHONUTF8=1。
本测试用 cp1252 流复现"CI 管道"场景，**本机即可跑，不必等 CI**。
"""

import ast
import io
from pathlib import Path

import pytest

from safefee._stdio import _ensure_utf8_stdio

ROOT = Path(__file__).resolve().parent.parent


def test_entry_guard_reconfigures_cp1252_stream(monkeypatch):
    """cp1252 流（CI 管道）→ 入口守卫必须 reconfigure 为 utf-8，中文不再崩。"""
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    monkeypatch.setattr("sys.stdout", stream)
    monkeypatch.setattr("sys.stderr", io.TextIOWrapper(io.BytesIO(), encoding="cp1252"))

    _ensure_utf8_stdio()
    assert stream.encoding.lower() in ("utf-8", "utf8")
    stream.write("中文输出测试")   # 若不 reconfigure 会 UnicodeEncodeError


def test_entry_guard_keeps_cp936_unchanged(monkeypatch):
    """中文控制台（cp936）→ 保持不动（否则本机终端乱码）。"""
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp936")
    monkeypatch.setattr("sys.stdout", stream)
    monkeypatch.setattr("sys.stderr", io.TextIOWrapper(io.BytesIO(), encoding="cp936"))

    _ensure_utf8_stdio()
    assert stream.encoding.lower() in ("cp936", "gbk", "gb2312")


def test_entry_guard_handles_stream_without_reconfigure(monkeypatch):
    """不支持 reconfigure 的流（如 StringIO）→ 静默跳过，不抛异常。"""
    monkeypatch.setattr("sys.stdout", io.StringIO())
    monkeypatch.setattr("sys.stderr", io.StringIO())
    _ensure_utf8_stdio()   # 不抛即通过


def _entry_sources():
    """所有"会打印"的可执行入口（含 tools 下每个脚本）。

    ``__main__.py`` 只做转发（守卫唯一实现源在 ``cli.main``），不在本清单内。
    """
    files = [ROOT / "src" / "safefee" / "cli" / "main.py"]
    files.extend(sorted((ROOT / "tools").glob("*.py")))
    return files


@pytest.mark.parametrize("path", _entry_sources(), ids=lambda p: p.name)
def test_every_printing_entry_has_stdio_guard(path):
    """**每个会打印的入口都要装编码守卫**——含里程碑后期新增的 tools 脚本。

    实测教训：漏守 tools 脚本 → CI windows job 全崩在辅助脚本的 print 上。
    """
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    attrs = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    has_guard = "_ensure_utf8_stdio" in calls or "_ensure_utf8_stdio" in attrs
    assert has_guard, "%s 未调用 _ensure_utf8_stdio（CI 中文输出会崩）" % path.name


def test_tools_scripts_use_explicit_subprocess_encoding():
    """子进程显式 ``encoding=``（**无环境变量可替代**）。"""
    for path in sorted((ROOT / "tools").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "subprocess.run" in source or "subprocess.check" in source:
            assert "encoding=" in source, (
                "%s 调用子进程但未显式指定 encoding（locale 解码会 UnicodeDecodeError）"
                % path.name
            )
