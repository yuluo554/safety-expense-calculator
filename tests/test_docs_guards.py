"""文档与元数据守门（**自述不得与事实漂移**）。

两条各自对应一次实测教训：

1. **文档里的测试数会随里程碑漂移**：README 长期写「202 项」，而实测是
   ``205 passed, 4 skipped``（收集 209 项）——同一个仓里两个数字并存，且没有任何门禁
   比对过。故**断言 README 写死的条数 == ``pytest --collect-only`` 实测条数**。
2. **license 元数据的弃用有硬期限**：``license = { text = "MIT" }``（TOML 表）与
   ``License ::`` classifier 都被 setuptools 弃用，弃用文案写明
   "By 2027-Feb-18, ... your builds will no longer be supported"。故**断言 pyproject
   用 SPDX 字符串且不含 License :: classifier**。

**计数口径**：README 里写的是 **收集条数**（``--collect-only``），它在"装没装 PySide6"
两种环境下都相同（无 Qt 时那 4 条界面冒烟被**收集**后在调用期跳过，不是不收集）；
只有 PyYAML 缺失会让 ``test_ci_workflow`` 整个模块在**收集期**跳过、条数不可比，
故本条守门在无 PyYAML 环境下跳过（与 ``test_ci_workflow`` 同一句口径）。
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
PYPROJECT = ROOT / "pyproject.toml"


def test_readme_test_count_matches_collection():
    """README 写死的测试条数必须等于 ``pytest --collect-only`` 实测。"""
    pytest.importorskip("yaml", reason="计数口径以 dev extra 环境为准（缺 PyYAML 时收集数不可比）")

    match = re.search(r"tests/\s+(\d+)\s*项", README.read_text(encoding="utf-8"))
    assert match, "README 的项目结构树里应给出测试条数（形如 `tests/  N 项`）"
    claimed = int(match.group(1))

    proc = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "pytest", "-o", "addopts=",
         "--collect-only", "-q"],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )
    actual_match = re.search(r"(\d+)\s+tests? collected", proc.stdout)
    assert actual_match, "collect-only 输出未含收集条数：\n%s" % proc.stdout[-2000:]
    actual = int(actual_match.group(1))
    assert claimed == actual, (
        "README 写 %d 项，实测收集 %d 项 —— 新增/删除测试后请同步 README 与 docs/技术报告.md、"
        "plan/00-README总览.md（本口径只管 README 这一处，另两处靠人工同步）" % (claimed, actual)
    )


def test_pyproject_license_uses_spdx_string():
    """license 必须是 SPDX 字符串；不得再用 TOML 表写法或 ``License ::`` classifier。"""
    text = PYPROJECT.read_text(encoding="utf-8")
    # 只看**代码行**：注释里可以提到被弃用的写法（本文件的说明性注释就提到了）
    code_lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]

    offenders = [ln for ln in code_lines if ln.lstrip().startswith('"License ::')]
    assert not offenders, (
        "classifiers 里的 `License ::` 已被 setuptools 弃用（硬期限 2027-02-18），应删除：%s"
        % offenders
    )

    match = re.search(r"(?m)^license\s*=\s*(.+?)\s*$", text)
    assert match, "pyproject.toml 应声明 license"
    value = match.group(1)
    assert re.fullmatch(r'"[^"]+"', value), (
        "license 应为 SPDX 字符串（如 `license = \"MIT\"`），实测写法 %r —— "
        "TOML 表（{ text = ... }）与 file 引用均已被弃用" % value
    )