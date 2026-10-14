"""控制台编码加固。

``py -X utf8``（本机习惯）只改"我们敲的那条命令"的 stdio，救不了 CI 管道
（cp1252）与用户终端。处置 = 入口按 ``stream.encoding`` **探针**决定是否
``reconfigure``：

* 该编码**能**渲染中文（cp936/utf-8）→ 保持不动（中文控制台不乱码）；
* 该编码**不能**渲染中文（cp1252/ascii）→ 就地 reconfigure 为 utf-8，
  ``errors="replace"`` 兜底，保证不因中文输出崩 ``UnicodeEncodeError``。

同族加固另有两条（缺一不可）：子进程显式 ``encoding=``（无环境变量可替代）、
CI ``env: PYTHONUTF8=1``。
"""

import sys

_PROBE_CHAR = "\u4e2d"  # 探针字符（中文），用于判断当前编码能否渲染 CJK


def _ensure_utf8_stdio() -> None:
    """就地加固 stdout/stderr 编码；失败静默（不因编码问题中断主流程）。"""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        encoding = getattr(stream, "encoding", None)
        if not encoding:
            continue
        try:
            _PROBE_CHAR.encode(encoding)
        except (UnicodeEncodeError, LookupError):
            pass
        else:
            continue  # 能渲染中文：保持不动
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
