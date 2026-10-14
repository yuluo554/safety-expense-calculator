# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec：safefee GUI（onedir，内嵌 PySide6）。

与 CLI spec 同一份白名单纪律（rules/truth/samples）；窗口态无控制台
（``console=False``）。构建后断言同样走 ``tools/verify_frozen.py --gui``。
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
    [str(ROOT / "src" / "safefee" / "gui_app.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[
        (str(DATA / "rules"), "data/rules"),
        (str(DATA / "truth"), "data/truth"),
        (str(DATA / "samples"), "data/samples"),
    ],
    hiddenimports=["PySide6.QtWidgets", "PySide6.QtCore", "PySide6.QtGui"],
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
    name="safefee-gui",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="safefee-gui",
)
