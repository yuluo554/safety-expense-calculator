"""CLI 退出码三语义测试（**锁进测试，重构不漂移**）。

0 成功 / 1 门控拦截或基准未达标或检出不符合 / 2 输入用法错误 / 3 可选依赖缺失。
"""

import json
from pathlib import Path

import pytest

from safefee.cli.main import main
from safefee.errors import EXIT_DEP, EXIT_GATE, EXIT_OK, EXIT_USAGE


def test_version_ok(capsys):
    assert main(["version"]) == EXIT_OK
    assert "safefee" in capsys.readouterr().out


def test_no_command_is_usage_error(capsys):
    assert main([]) == EXIT_USAGE


def test_selfcheck_ok(capsys):
    assert main(["selfcheck"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "数据目录" in out
    assert "门控拦截" in out  # M0 全 pending → 门控必然拦截


def test_rulesets_lists_two(capsys):
    assert main(["rulesets", "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["rulesets"]) == 2


def test_units_ok(capsys):
    assert main(["units"]) == EXIT_OK
    assert "CNY10k" in capsys.readouterr().out


def test_calc_gate_blocks_pending(data_dir, tmp_path, capsys):
    """M0 全 pending → calc 被门控拦截（退出码 1）。"""
    archive = tmp_path / "a.json"
    archive.write_bytes(json.dumps({
        "enterprise_id": "90000000SYN0000001A",
        "enterprise_name": "示例（合成）",
        "industry_id": "coal", "variant_id": "coal_high_gas", "year": 2024,
        "basis_kind": "output", "basis_value": "1000", "basis_unit": "ton",
    }).encode("utf-8"))
    assert main(["calc", str(archive)]) == EXIT_GATE
    assert "不得进入计算路径" in capsys.readouterr().err


def test_calc_missing_field_is_usage_error(tmp_path, capsys):
    archive = tmp_path / "bad.json"
    archive.write_bytes(b'{"industry_id": "coal"}')
    assert main(["calc", str(archive)]) == EXIT_USAGE
    assert "缺少必填字段" in capsys.readouterr().err


def test_calc_missing_file_is_usage_error(capsys):
    assert main(["calc", "no-such-file.json"]) == EXIT_USAGE


def test_bench_only_unknown_suite_is_usage_error(capsys):
    """``--only`` 未知名 → 退出码 2（**别静默跳过**）。"""
    assert main(["bench", "--only", "nope"]) == EXIT_USAGE
    assert "未知基准套件" in capsys.readouterr().err


def test_bench_ok_with_unmeasured_suites(capsys):
    """可评估套件达标 + 未评估套件（用例数为 0）不阻断 → 退出码 0。"""
    assert main(["bench"]) == EXIT_OK


def test_diff_between_versions(capsys):
    assert main(["diff", "--from-year", "2020", "--to-year", "2024"]) == EXIT_OK
    assert "对照" in capsys.readouterr().out


def test_gui_missing_dependency_is_exit_3(capsys):
    """缺 PySide6 → 退出码 3（**不是裸异常**）。"""
    assert main(["gui"]) == EXIT_DEP
    assert "依赖缺失" in capsys.readouterr().err


def test_gui_import_stub_returns_exit_3(monkeypatch, capsys):
    """用 ``__import__`` 打桩让 PySide6 抛 ImportError → 断言走 exit 3 而非崩。"""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("PySide6"):
            raise ImportError("mocked missing PySide6")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert main(["gui"]) == EXIT_DEP


def test_scan_failure_isolation(data_dir, tmp_path, capsys):
    """**失败件 ≠ 违规**：坏件不中断整批、不改退出码。"""
    good = tmp_path / "ledger" / "ok.csv"
    good.parent.mkdir(parents=True)
    good.write_bytes(b"item_key,subject,summary,amount\nEXP-1,\xe5\xae\x89\xe5\x85\xa8,\xe6\x94\xaf\xe5\x87\xba,100.00\n")
    bad = tmp_path / "ledger" / "bad.csv"
    bad.write_bytes(b"wrong,header\n1,2\n")

    out = tmp_path / "out"
    code = main(["scan", str(tmp_path / "ledger"), "--out", str(out)])
    assert code == EXIT_OK
    captured = capsys.readouterr().out
    assert "已处理 1 件" in captured
    assert "失败件" in captured
    assert (out / "scan-result.json").is_file()
