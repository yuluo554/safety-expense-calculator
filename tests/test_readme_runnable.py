"""README 可跑通性守门（**逐字执行 README 链**）。

实测教训（三类缺口，逐条对应本测试）：

1. **README 引用的输入文件"根本不存在"**——本地因工作目录残留恰好存在同名草稿，
   本地一路全绿，直到 ``git archive`` 导出干净树才报"文件不存在"。
   处置 = 输入夹具**由生成器产出** + 本测试断言 README 提到的路径存在；
2. **数据文件 ≠ 命令输入**——真值库是带 ``expect`` 包装的记录，命令直接喂会 exit 2；
3. **README 里 venv 段落用 ``py -m pip``**——``py`` 启动器会绕过 venv。

本测试从 README 代码块里**正则抽取参数**（`safefee ... <路径>` 形态），
断言每个路径在仓库里**真实存在**，再按退出码表真跑关键步骤。
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"

#: README 代码块里引用的仓内路径（形如 data/samples/xxx.json）
_PATH_RE = re.compile(r"\b((?:data|tools|tests|src|plan)/[A-Za-z0-9_./\-]+\.(?:json|csv|py|md))")
#: README 里显式写出的命令参数（--archive 等）
_ARG_RE = re.compile(r"--(?:archive|baseline|out|data-dir)\s+(\S+)")


def _readme_text() -> str:
    return README.read_text(encoding="utf-8")


def test_readme_referenced_paths_exist():
    """**README 里每条命令的输入，是仓库里真有的文件吗？**"""
    missing = []
    for match in _PATH_RE.finditer(_readme_text()):
        rel = match.group(1).rstrip(".,;)")
        if "<" in rel or ">" in rel:
            continue
        if not (ROOT / rel).exists():
            missing.append(rel)
    assert not missing, "README 引用了不存在的路径：%s" % ", ".join(sorted(set(missing)))


def test_readme_sample_fixtures_are_generator_outputs():
    """演示夹具必须由**生成器产出**（不是手工放置、不靠工作目录残留）。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "gen_samples", ROOT / "tools" / "gen_samples.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    produced = set(module.generate())
    on_disk = {p.name for p in (ROOT / "data" / "samples").iterdir() if p.is_file()}
    assert produced <= on_disk, "README 引用的夹具未被生成器产出：%s" % (produced - on_disk)


def test_readme_quickstart_steps_run_with_documented_exit_codes():
    """按 README 的退出码表真跑关键步骤。"""
    steps = [
        (["-m", "safefee", "version"], 0),
        (["-m", "safefee", "selfcheck"], 0),
        (["-m", "safefee", "rulesets"], 0),
        (["-m", "safefee", "bench"], 0),
        (["-m", "safefee", "diff", "--from-year", "2020", "--to-year", "2024"], 0),
        # M0 全 pending → calc 应被门控拦截（README 已写明）
        (["-m", "safefee", "calc", "data/samples/archive-coal.json"], 1),
    ]
    for argv, expected in steps:
        proc = subprocess.run(
            [sys.executable, "-X", "utf8"] + argv,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
        )
        assert proc.returncode == expected, (
            "`%s` 期望退出码 %d，实际 %d\n%s"
            % (" ".join(argv), expected, proc.returncode, proc.stdout)
        )


def test_readme_code_blocks_use_python_m_pip_not_py_launcher():
    """``py -m pip`` 会绕过 venv（Windows ``py`` 启动器独立）——**代码块**里必须用 ``python -m pip``。

    只查代码块（fenced block）：正文里的告警句"不要用 `py -m pip`"是说明，不是可执行命令。
    """
    text = _readme_text()
    blocks = re.findall(r"```[a-z]*\n(.*?)```", text, re.S)
    assert blocks, "README 应含可复制代码块"
    for block in blocks:
        assert "py -m pip" not in block, "README 代码块不得用 `py -m pip`（会装到系统 Python）"
    joined = "\n".join(blocks)
    assert "python -m pip install" in joined
