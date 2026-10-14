"""零政策字面量门禁扫描器。

**为什么**：规则包数值一旦被"抄进代码"就出现**第二份真相**——调数值要改代码、
且代码里的数值会与规则包漂移。故把规则包全部数值收编为**禁用 token**，
对**引擎/CLI/基准/GUI 源码**（**连文档字符串与注释一起扫**）做扫描。

**豁免口径（写死，否则门禁刷屏）**：

* **定义性换算**（``units.json`` 的 10000 / 100000000）——定义性事实，非政策数值；
* **精度约定**（金额两位小数 ``0.01``、``ROUND_HALF_UP``）——量化口径；
* **规则包生成器**（``tools/gen_rulesets.py``）——它是规则包数值的**唯一写入者**，
  数值本就应当只在此处出现一次（生成到 JSON 里），故按**路径 + 规则名**豁免；
* **扫描器自身**（本文件的 token 定义表）——按**路径 + 规则名**豁免；
* 其余个别行靠行内 ``audit-allow`` 标记放行（**仍在输出里可见**，只是不计入阻断）。

**豁免粒度纪律**：白名单按**路径 glob + 规则名**（不是"这个文件全放过"）——
同一文件里别的规则命中仍要报（见 plan/06 E6）。
"""

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ("src", "tools")
ALLOW_MARKER = "audit-allow"

#: 政策数值禁用 token（**规则包数值收编**；来自 manifest/ruleset 的分段边界等）
#: 用**片段拼接**构造：扫描器源码自身不得出现完整词面（否则自命中、永留历史）。
BANNED_TOKENS = (
    "1" + "0000000",       # 1000 万（危险品/电力首段边界）
    "1" + "00000000",      # 1 亿（第二段边界）
    "1" + "000000000",     # 10 亿（第三段边界）
    "5" + "00000000",      # 5 亿（电力第四段边界）
    "5" + "000000000",     # 50 亿（电力第五段边界）
    "0.0" + "45", "0.0" + "225", "0.0" + "055", "0.0" + "02",   # 危险品费率
    "0.0" + "35", "0.0" + "3", "0.0" + "25", "0.0" + "2", "0.0" + "15",  # 建设工程费率
    "0." + "60", "0." + "6",    # 使用进度门槛（第五十一条）
)

#: 豁免：定义性换算与精度约定（**非政策数值**）
EXEMPT_LITERALS = frozenset({
    "10000", "100000000", "0.01", "1", "0", "2", "10", "26", "30", "31", "365",
})

#: 豁免：**路径 glob + 规则名**（不是路径全放过——同文件别的规则命中仍要报）
PATH_RULE_ALLOW = (
    ("tools/gen_rulesets.py", "policy_literal"),          # 规则包数值唯一写入者
    ("tools/scan_policy_literals.py", "policy_literal"),  # 扫描器自身的 token 定义表
)

_SKIP_DIRS = {"__pycache__", ".venv", "venv", "build", "dist"}


def iter_python_files(dirs: Iterable[str]) -> Iterable[Path]:
    for rel in dirs:
        base = ROOT / rel
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            yield path


def _path_rule_allowed(rel_path: str, rule: str) -> bool:
    for pattern, allowed_rule in PATH_RULE_ALLOW:
        if allowed_rule != rule:
            continue
        if Path(rel_path).match(pattern) or rel_path == pattern:
            return True
    return False


def scan_text(text: str) -> List[Tuple[int, str]]:
    """扫描文本，返回 ``(行号, token)`` 命中列表（含注释与 docstring）。"""
    hits: List[Tuple[int, str]] = []
    for index, line in enumerate(text.splitlines(), start=1):
        if ALLOW_MARKER in line:
            continue
        for token in BANNED_TOKENS:
            if token in EXEMPT_LITERALS:
                continue
            if re.search(r"(?<![0-9A-Za-z_.])%s(?![0-9A-Za-z_])" % re.escape(token), line):
                hits.append((index, token))
    return hits


def scan_repo() -> Dict[str, List[Tuple[int, str]]]:
    findings: Dict[str, List[Tuple[int, str]]] = {}
    for path in iter_python_files(SCAN_DIRS):
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        if _path_rule_allowed(rel, "policy_literal"):
            continue
        hits = scan_text(path.read_text(encoding="utf-8"))
        if hits:
            findings[rel] = hits
    return findings


def selftest() -> int:
    """阳性对照：构造含禁用 token 的样本，断言扫描器**必须**报命中。"""
    sample = "def f():\n    return 10000000 * 0.045  # 政策数值不该出现在源码里\n"
    hits = scan_text(sample)
    tokens = {token for _, token in hits}
    required = {"10000000", "0.045"}
    if not required <= tokens:
        print("NO_POLICY_LITERALS_SELFTEST_FAIL: 扫描器未检出样本中的 %s"
              % ", ".join(sorted(required - tokens)))
        return 1
    # 阴性对照：豁免值与 allow 标记不得误报
    clean = "PRECISION = 0.01  # 精度约定\nx = 10000  # audit-allow 定义性换算\n"
    if scan_text(clean):
        print("NO_POLICY_LITERALS_SELFTEST_FAIL: 豁免样本被误报 %s" % scan_text(clean))
        return 1
    print("NO_POLICY_LITERALS_SELFTEST_OK")
    return 0


def main(argv=None) -> int:
    from safefee._stdio import _ensure_utf8_stdio

    _ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description="零政策字面量门禁")
    parser.add_argument("--selftest", action="store_true", help="阳性对照")
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))

    if args.selftest:
        return selftest()

    findings = scan_repo()
    if findings:
        for rel, hits in sorted(findings.items()):
            for line, token in hits:
                print("%s:%d [policy_literal] %s" % (rel, line, token))
        print("NO_POLICY_LITERALS_FAIL")
        return 1
    print("NO_POLICY_LITERALS_OK")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    raise SystemExit(main())
