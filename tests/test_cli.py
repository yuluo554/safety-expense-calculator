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
    assert "门控通过" in out  # M1 已核对作用域 → 放行（2012 版 progress 仍留 pending）


def test_rulesets_lists_two(capsys):
    assert main(["rulesets", "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["rulesets"]) == 2


def test_units_ok(capsys):
    assert main(["units"]) == EXIT_OK
    assert "CNY10k" in capsys.readouterr().out


def test_calc_verified_outputs_amount(data_dir, tmp_path, capsys):
    """M1 已核对煤炭 → calc 输出金额与条款依据（退出码 0）。"""
    archive = tmp_path / "a.json"
    archive.write_bytes(json.dumps({
        "enterprise_id": "90000000SYN0000001A",
        "enterprise_name": "示例（合成）",
        "industry_id": "coal", "variant_id": "coal_high_gas", "year": 2024,
        "basis_kind": "output", "basis_value": "1000", "basis_unit": "ton",
    }).encode("utf-8"))
    assert main(["calc", str(archive)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "30000.00" in out       # 第七条高瓦斯 30 元/吨 × 1000 吨
    assert "第七条" in out


def test_calc_all_twelve_industries_are_covered(data_dir, tmp_path, capsys):
    """**M2 验收门**：十二节全部可算（退出码 0），deferred 行业清零。"""
    cases = [
        ("noncoal_mine", "output", "100000", "ton", "nc_metal_underground"),
        ("oil_gas", "output", "1000", "ton", "og_crude_oil"),
        ("transport", "revenue", "1000000", "CNY", "general_freight"),
        ("metallurgy", "revenue", "2000000000", "CNY", None),
        ("machinery", "revenue", "2000000000", "CNY", None),
        ("fireworks", "revenue", "30000000", "CNY", None),
        ("civil_explosives", "revenue", "2000000000", "CNY", None),
        ("weapons", "revenue", "2000000000", "CNY", "wp_naval_ship"),
    ]
    for industry, kind, value, unit, variant in cases:
        archive = tmp_path / ("%s.json" % industry)
        payload = {
            "enterprise_id": "90000000SYN0000009Z", "enterprise_name": "示例（合成）",
            "industry_id": industry, "year": 2024,
            "basis_kind": kind, "basis_value": value, "basis_unit": unit,
        }
        if variant:
            payload["variant_id"] = variant
        archive.write_bytes(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        assert main(["calc", str(archive)]) == EXIT_OK, industry
        capsys.readouterr()


def test_calc_tiered_outputs_tier_lines(data_dir, tmp_path, capsys):
    """超额累退逐段明细随主输出（审计留痕）。"""
    archive = tmp_path / "h.json"
    archive.write_bytes(json.dumps({
        "enterprise_id": "90000000SYN0000002B",
        "enterprise_name": "示例危险品（合成）",
        "industry_id": "hazardous_chemicals", "year": 2024,
        "basis_kind": "revenue", "basis_value": "50000000", "basis_unit": "CNY",
    }).encode("utf-8"))
    assert main(["calc", str(archive)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "1350000.00" in out
    assert "段 1" in out and "第二十一条" in out


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


def test_bench_ok_all_suites_measured(capsys):
    """M1 后三类套件全部可评估且达标 → 退出码 0。"""
    assert main(["bench"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "未评估" not in out


def test_diff_between_versions(capsys):
    assert main(["diff", "--from-year", "2020", "--to-year", "2024"]) == EXIT_OK
    assert "对照" in capsys.readouterr().out


def test_gui_missing_dependency_is_exit_3(monkeypatch, capsys):
    """缺 PySide6 → 退出码 3（**不是裸异常**）。

    M5 起本机装有 PySide6，"缺依赖"场景用 import 桩构造（下一测试同型）；
    真实界面的启动路径由 ``tests/test_gui_smoke.py`` 以 offscreen 桩住
    ``app.exec`` 验证，**不在 CLI 测试里真进事件循环**。
    """
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("PySide6"):
            raise ImportError("mocked missing PySide6")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
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
    good.write_bytes(
        b"enterprise_id,year,industry_id,item_key,subject,summary,amount\n"
        b"90000000SYN0000001A,2024,coal,EXP-1,\xe5\xae\x89\xe5\x85\xa8,\xe6\x94\xaf\xe5\x87\xba,100.00\n"
    )
    bad = tmp_path / "ledger" / "bad.csv"
    bad.write_bytes(b"wrong,header\n1,2\n")

    out = tmp_path / "out"
    code = main(["scan", str(tmp_path / "ledger"), "--out", str(out)])
    assert code == EXIT_OK
    captured = capsys.readouterr().out
    assert "已处理 1 件" in captured
    assert "失败件" in captured
    assert (out / "scan-result.json").is_file()
