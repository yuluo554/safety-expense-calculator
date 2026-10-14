"""数据目录定位（源码态 / 冻结态分支）。

优先级（**改优先级属"动了会打挂测试"的口径变更**，见 tests/test_data_paths.py）::

    1. explicit（CLI --data-dir）
    2. 环境变量 SAFEFEE_DATA_DIR
    3. 冻结态：sys._MEIPASS/data（PyInstaller 6）→ exe目录/_internal/data（5.x）→ exe目录/data
    4. 源码态：自本文件上溯，找含 data/rules/manifest.json 的目录
    5. 兜底：CWD/data

判定标准是"该目录下存在 ``rules/manifest.json``"，避免把无关的 ``data/`` 目录选中。
"""

import os
import sys
from pathlib import Path
from typing import Optional

from safefee.errors import DataDirNotFound

_MARKER = os.path.join("rules", "manifest.json")
_ENV_VAR = "SAFEFEE_DATA_DIR"


def is_frozen() -> bool:
    """是否运行在 PyInstaller 冻结态。"""
    return bool(getattr(sys, "frozen", False))


def _candidates(explicit: Optional[str] = None) -> list:
    out = []
    if explicit:
        out.append(Path(explicit))
    env = os.environ.get(_ENV_VAR)
    if env:
        out.append(Path(env))

    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            out.append(Path(meipass) / "data")
        exe_dir = Path(sys.executable).resolve().parent
        out.append(exe_dir / "_internal" / "data")  # PyInstaller 6.x onedir
        out.append(exe_dir / "data")                # PyInstaller 5.x 平铺布局

    here = Path(__file__).resolve()
    for parent in [here.parent] + list(here.parents):
        out.append(parent / "data")

    out.append(Path.cwd() / "data")
    return out


def find_data_dir(explicit: Optional[str] = None) -> Path:
    """返回数据目录绝对路径；找不到抛 :class:`DataDirNotFound`（退出码 2）。"""
    tried = []
    for candidate in _candidates(explicit):
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        tried.append(str(resolved))
        if (resolved / _MARKER).is_file():
            return resolved
    raise DataDirNotFound(
        "未找到数据目录（需含 %s）。已尝试：%s" % (_MARKER, " | ".join(tried))
    )


__all__ = ["find_data_dir", "is_frozen"]
