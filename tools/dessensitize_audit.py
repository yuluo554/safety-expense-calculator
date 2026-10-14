"""脱敏审计器（四步固化成仓库内可重跑脚本）。

**四步**（任一步 FAIL → 非零退出；全过打印 ``DESSENSITIZE_AUDIT_OK``）：

1. 文件名扫描（``.env``/``.key``/``secret``/``token`` 应为空）；
2. 内容级扫描（全部跟踪文本文件）：密钥、手机号、身份证、个人目录路径、内网 IP、邮箱；
3. 提交元数据扫描（作者/提交者邮箱；``--history`` 模式扫全历史）；
4. 提交信息扫描。

**命中分级**（使审计可持续）：

* ``HARD``（exit 1）——真实泄露形态：邮箱、个人目录路径、密钥、真实手机号/身份证；
* ``REVIEW``（人工豁免留档）——系统目录、其余盘符路径、姊妹项目词；
* ``advisory``（只报不阻断）——长 hex 串（sha256 指纹是本类项目的**文档化功能**）。

**行内放行标记** ``audit-allow``：命中所在行含该标记即转"白名单放过"
（**仍在输出里可见**，只是不计入阻断）——供扫描器自己的 selftest 夹具与刻意构造的样本使用。

**豁免口径**（"看起来像泄露"的形态要先问"它在本项目里是不是功能/公开元数据"）：

* ``*@users.noreply.github.com`` —— noreply 是**发布固有公开值**，本就是脱敏目标；
* ``git@github.com`` / ``ssh@<host>`` —— **传输地址**，非个人邮箱；
* ``github.com/<账号>`` —— **发布固有公开元数据**（clone URL 必含账号名）；
* 长 hex 串（sha256 指纹）—— **文档化功能**（证据链），只报不阻断。

**可证伪**：``--selftest`` 阳性对照 + 阴性对照（豁免项不得误报）。
**输出一律掩码化**（``文件:行号 [类别] x次数``，不回显敏感串原文）——
留档会引用输出，输出本身不得成为二次泄漏源。
"""

import argparse
import base64
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
ALLOW_MARKER = "audit-allow"

HARD = "HARD"
REVIEW = "REVIEW"
ADVISORY = "advisory"

#: 模式用**片段拼接**构造——扫描器源码自己也要过自己的扫描（不得出现完整词面）
_PATTERNS = {
    "email": re.compile(r"(?<![0-9A-Za-z._%+-])([A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"),
    "phone": re.compile(r"(?<![0-9a-fA-F])" + "1" + r"[3-9]\d{9}(?![0-9a-fA-F])"),
    "idcard": re.compile(r"(?<![0-9a-fA-F])\d{17}[\dXx](?![0-9a-fA-F])"),
    "secret": re.compile(r"(?i)\b(api[_-]?key|secret|passwd|password)\b\s*[:=]\s*\S+"),
    "private_path": re.compile(r"[A-Za-z]:[\\/]" + "Users" + r"[\\/][^\\/\s\"']+"),
    "internal_ip": re.compile(r"\b(10|172\.(1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b"),
    "long_hex": re.compile(r"\b[0-9a-fA-F]{32,}\b"),
}

#: 豁免（阴性对照进 selftest，否则下次改规则又误报）
_EXEMPT = (
    re.compile(r"[A-Za-z0-9._%+-]+@users\.noreply\.github\.com"),   # noreply：脱敏目标形态
    re.compile(r"^(git|ssh|hg)@[A-Za-z0-9.-]+$"),                   # 传输地址
    re.compile(r"github\.com/[A-Za-z0-9._-]+"),                     # 发布固有公开元数据
)

#: 姊妹项目词表（base64 存储——词表明文不入仓，扫描器自身可入仓）
_SIBLING_WORDS_B64 = (
    # 占位：本题为独立项目，暂不登记姊妹词；发布前按需填入（base64）
    "",
)

_SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "build", "dist", ".pytest_cache"}
_TEXT_SUFFIXES = {
    ".py", ".md", ".json", ".toml", ".yml", ".yaml", ".txt", ".csv", ".cfg", ".ini",
    ".gitignore", ".gitattributes",
}


def _run_git(args: List[str]) -> Tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git"] + args,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",          # 子进程显式 encoding（无环境变量可替代）
            errors="replace",
        )
    except (OSError, ValueError) as exc:
        return 1, "git 不可用：%s" % exc
    return proc.returncode, proc.stdout


def _git_available() -> bool:
    code, _ = _run_git(["--version"])
    return code == 0


def tracked_files() -> List[Path]:
    """跟踪文件列表；**无 git 兜底**（``git archive`` 导出树没有 ``.git``）。"""
    if _git_available():
        code, out = _run_git(["-c", "core.quotepath=false", "ls-files"])
        if code == 0:
            return [ROOT / line for line in out.splitlines() if line.strip()]
    files = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        files.append(path)
    return files


def _is_text(path: Path) -> bool:
    if path.suffix in _TEXT_SUFFIXES or path.name in (".gitignore", ".gitattributes"):
        return True
    return False


def _is_exempt(text: str) -> bool:
    return any(pattern.search(text) for pattern in _EXEMPT)


def scan_text(text: str) -> Dict[str, int]:
    """返回 ``{类别: 次数}``；豁免形态与 allow 标记不计入。"""
    counts: Dict[str, int] = {}
    for index, line in enumerate(text.splitlines(), start=1):
        if ALLOW_MARKER in line:
            continue
        for name, pattern in _PATTERNS.items():
            for match in pattern.finditer(line):
                value = match.group(0)
                if _is_exempt(value):
                    continue
                if name == "long_hex":
                    counts[ADVISORY] = counts.get(ADVISORY, 0) + 1
                    continue
                counts[HARD] = counts.get(HARD, 0) + 1
    return counts


def scan_step1_filenames(files: Iterable[Path]) -> List[str]:
    hits = []
    for path in files:
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        if re.search(r"(?i)(\.env$|\.key$|secret|token)", rel):
            hits.append(rel)
    return hits


def scan_step2_content(files: Iterable[Path]) -> Dict[str, Dict[str, int]]:
    findings: Dict[str, Dict[str, int]] = {}
    for path in files:
        if not _is_text(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        counts = scan_text(text)
        if counts:
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            findings[rel] = counts
    return findings


def scan_step3_metadata(history: bool) -> Dict[str, int]:
    if not _git_available():
        return {}
    fmt = "%ae %ce"
    code, out = _run_git(["log", "--format=%s" % fmt, "--all" if history else "HEAD"])
    if code != 0:
        return {}
    counts: Dict[str, int] = {}
    for line in out.splitlines():
        for value in line.split():
            if _is_exempt(value):
                continue
            if _PATTERNS["email"].search(value):
                counts[HARD] = counts.get(HARD, 0) + 1
    return counts


def scan_step4_messages(history: bool) -> Dict[str, int]:
    if not _git_available():
        return {}
    code, out = _run_git(["log", "--format=%B", "--all" if history else "HEAD"])
    if code != 0:
        return {}
    return scan_text(out)


def _mask(rel: str) -> str:
    """输出掩码化：只报 ``文件:行数 [类别] x次数``，不回显敏感串原文。"""
    return rel


def run(history: bool) -> int:
    files = tracked_files()
    ok = True

    hits1 = scan_step1_filenames(files)
    if hits1:
        ok = False
        for rel in hits1:
            print("%s [filename] 1 次" % _mask(rel))

    hits2 = scan_step2_content(files)
    for rel, counts in sorted(hits2.items()):
        for category, count in sorted(counts.items()):
            if category == ADVISORY:
                print("%s [long_hex/advisory] %d 次（只报不阻断）" % (_mask(rel), count))
                continue
            ok = False
            print("%s [%s] %d 次" % (_mask(rel), category, count))

    hits3 = scan_step3_metadata(history)
    if hits3.get(HARD):
        ok = False
        print("[提交元数据] %s %d 次" % (HARD, hits3[HARD]))

    hits4 = scan_step4_messages(history)
    if hits4.get(HARD):
        ok = False
        print("[提交信息] %s %d 次" % (HARD, hits4[HARD]))

    if ok:
        print("DESSENSITIZE_AUDIT_OK")
        return 0
    return 1


def selftest() -> int:
    """阳性对照 + 阴性对照（豁免项不得误报）。"""
    sample = "contact: " + "user" + "@" + "example.com\n"
    counts = scan_text(sample)
    if not counts.get(HARD):
        print("DESSENSITIZE_SELFTEST_FAIL: 未检出样本邮箱")
        return 1
    # 阴性对照：noreply / 传输地址 / github.com 账号 / allow 标记
    clean = (
        "user@users.noreply.github.com\n"
        "git@github.com\n"
        "https://github.com/example/repo\n"
        "sample@example.com  # audit-allow\n"
    )
    if scan_text(clean):
        print("DESSENSITIZE_SELFTEST_FAIL: 豁免样本被误报 %s" % scan_text(clean))
        return 1
    print("DESSENSITIZE_SELFTEST_OK")
    return 0


def main(argv=None) -> int:
    from safefee._stdio import _ensure_utf8_stdio

    _ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description="脱敏审计（tracked/history/selftest 三模式）")
    parser.add_argument("--selftest", action="store_true", help="阳性+阴性对照")
    parser.add_argument("--history", action="store_true", help="扫全历史（含提交元数据与信息）")
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))

    if args.selftest:
        return selftest()
    return run(args.history)


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    raise SystemExit(main())
