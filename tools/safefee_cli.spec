# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec：safefee CLI（onedir）。

M5 打包纪律（HANDOFF-M5 §二.3）：

* onedir 布局（PyInstaller 6.x：``exe 同目录 _internal/``）；
* **随包数据白名单** ``rules`` / ``truth`` / ``samples``（不整仓塞 data/——
  knowledge/raw 等核对底稿不进发行包）；
* 数据放 ``_internal/data/<白名单>``，与 :mod:`safefee.data_paths` 冻结态
  候选（``exe目录/_internal/data``）对齐；
* 构建后断言见 ``tools/verify_frozen.py``（数据目录定位 + 子命令自检 + 报告导出）。
"""

import os
import sys
from pathlib import Path

# SPECPATH = spec 文件所在目录（tools/）——仓库根是其父目录
ROOT = Path(os.path.abspath(SPECPATH)).resolve().parent
assert (ROOT / "data" / "rules" / "manifest.json").is_file(), "spec 仓库根定位失败"
DATA = ROOT / "data"

block_cipher = None

a = Analysis(
    [str(ROOT / "src" / "safefee" / "__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[
        (str(DATA / "rules"), "data/rules"),
        (str(DATA / "truth"), "data/truth"),
        (str(DATA / "samples"), "data/samples"),
    ],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pydoc_data"],
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="safefee",
    debug=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="safefee-cli",
)
