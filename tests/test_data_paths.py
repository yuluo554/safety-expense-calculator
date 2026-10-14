"""数据目录定位测试（源码态 / 冻结态分支，**改优先级属"动了会打挂测试"**）。"""

import os
from pathlib import Path

import pytest

from safefee import data_paths
from safefee.errors import DataDirNotFound


def test_explicit_data_dir_wins(data_dir):
    assert data_paths.find_data_dir(str(data_dir)) == data_dir.resolve()


def test_env_var_used_when_no_explicit(data_dir, monkeypatch):
    monkeypatch.setenv("SAFEFEE_DATA_DIR", str(data_dir))
    assert data_paths.find_data_dir() == data_dir.resolve()


def test_source_tree_fallback(data_dir):
    assert data_paths.find_data_dir() == data_dir.resolve()


def test_bad_explicit_path_falls_back_to_source_tree(data_dir, tmp_path):
    """显式/环境路径不存在时**按优先级回落**（健壮性设计，不是静默忽略）。"""
    assert data_paths.find_data_dir(str(tmp_path / "nope")) == data_dir.resolve()


def test_no_candidate_found_raises(monkeypatch):
    """**所有候选都落空** → :class:`DataDirNotFound`（退出码 2），不静默返回空。"""
    monkeypatch.setattr(data_paths, "_candidates", lambda explicit=None: [])
    with pytest.raises(DataDirNotFound):
        data_paths.find_data_dir()


def test_is_frozen_false_in_source_mode():
    assert data_paths.is_frozen() is False


def test_frozen_branch_prefers_meipass(data_dir, monkeypatch, tmp_path):
    """冻结态分支：``sys._MEIPASS/data`` 优先（PyInstaller 6）。"""
    frozen_root = tmp_path / "frozen"
    (frozen_root / "data" / "rules").mkdir(parents=True)
    (frozen_root / "data" / "rules" / "manifest.json").write_bytes(b'{"schema_version": 1}\n')

    monkeypatch.setattr(data_paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(data_paths.sys, "_MEIPASS", str(frozen_root), raising=False)
    monkeypatch.delenv("SAFEFEE_DATA_DIR", raising=False)
    assert data_paths.find_data_dir() == (frozen_root / "data").resolve()


def test_frozen_branch_falls_back_to_exe_internal(data_dir, monkeypatch, tmp_path):
    """冻结态分支：``exe目录/_internal/data``（PyInstaller 6 onedir）。"""
    exe_dir = tmp_path / "dist"
    (exe_dir / "_internal" / "data" / "rules").mkdir(parents=True)
    (exe_dir / "_internal" / "data" / "rules" / "manifest.json").write_bytes(b"{}\n")

    monkeypatch.setattr(data_paths.sys, "frozen", True, raising=False)
    monkeypatch.delattr(data_paths.sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(data_paths.sys, "executable", str(exe_dir / "safefee.exe"))
    monkeypatch.delenv("SAFEFEE_DATA_DIR", raising=False)
    assert data_paths.find_data_dir() == (exe_dir / "_internal" / "data").resolve()
