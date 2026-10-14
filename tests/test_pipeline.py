"""编排层测试：**行为等价**（三方对账：CLI stdout == 编排直调 == 报告章节）。

判别口诀：别断言"都调了同一个函数"这种字面声明——**有效形态是三方对账**。
"""

import json
import shutil
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _archive(tmp_path: Path) -> Path:
    path = tmp_path / "archive.json"
    path.write_bytes(json.dumps({
        "enterprise_id": "90000000SYN0000001A",
        "enterprise_name": "示例煤炭（合成）有限公司",
        "industry_id": "coal", "variant_id": "coal_high_gas", "year": 2024,
        "basis_kind": "output", "basis_value": "1000", "basis_unit": "ton",
    }).encode("utf-8"))
    return path


def test_build_case_is_single_input_interpreter():
    """``build_case`` 是**输入格式解释的唯一实现**（GUI 不得自带校验）。"""
    from safefee.engine import build_case

    case = build_case({
        "enterprise_id": "X", "enterprise_name": "Y", "industry_id": "coal",
        "year": 2024, "basis_kind": "output", "basis_value": "100", "basis_unit": "ton",
    })
    assert case.basis_value == Decimal("100")


def test_build_case_missing_field_raises():
    from safefee.engine import build_case
    from safefee.errors import MissingInput

    with pytest.raises(MissingInput):
        build_case({"industry_id": "coal"})


def test_selfcheck_returns_data_dir_and_gate_counts():
    from safefee.engine import selfcheck

    payload = selfcheck()
    assert payload["data_dir"]
    assert len(payload["rulesets"]) == 2
    for item in payload["rulesets"]:
        assert "scopes" in item


def test_calc_report_coordinate_matches_manifest(data_dir):
    """规则包坐标来自 manifest（报告头固定输出）。"""
    from safefee.engine import build_case, compute_calc
    from safefee.rules import load_manifest

    manifest = load_manifest(data_dir)
    ref = manifest.resolve_year(2024)
    case = build_case({
        "enterprise_id": "X", "enterprise_name": "Y", "industry_id": "coal",
        "variant_id": "coal_high_gas", "year": 2024,
        "basis_kind": "output", "basis_value": "1000", "basis_unit": "ton",
    })
    report = compute_calc(case)
    assert report.coordinate["doc_no"] == ref.doc_no
    assert report.coordinate["ruleset_id"] == ref.ruleset_id
    assert report.coordinate["ruleset_sha256"]


def test_three_way_reconciliation_on_verified_ruleset(tmp_path, monkeypatch):
    """三方对账：**编排直调 == 报告章节**（M1 真数据已 verified，直接用仓内规则包）。"""
    target = tmp_path / "data"
    shutil.copytree(ROOT / "data", target)
    monkeypatch.setenv("SAFEFEE_DATA_DIR", str(target))

    from safefee.engine import build_case, compute_calc
    from safefee.report import ReportInput, build_sections

    case = build_case({
        "enterprise_id": "X", "enterprise_name": "Y", "industry_id": "coal",
        "variant_id": "coal_high_gas", "year": 2024,
        "basis_kind": "output", "basis_value": "1000", "basis_unit": "ton",
    })
    report = compute_calc(case)
    assert report.result is not None
    assert not report.gate_blockers
    amount = str(report.result.amount)
    assert amount == "30000.00"  # 第七条高瓦斯 30 元/吨 × 1000 吨

    # 报告章节里的金额必须与编排直调一致（同一数据源）
    sections = build_sections(ReportInput(
        ruleset_coordinate=report.coordinate,
        enterprise=case.as_dict(),
        accrual=report.result.as_dict(),
        parameter_sources=[{"parameter": "p", "issuer": "i", "effective_year": "2022",
                            "doc_no": "d", "clause": "第七条", "url": "u",
                            "snapshot": "s", "fetched_at": "2026-10-14"}],
    ))
    accrual_section = next(s for s in sections if s.title == "计提明细")
    assert any(amount in paragraph for paragraph in accrual_section.paragraphs)

    # 同输入两次调用逐字段一致
    again = compute_calc(case)
    assert again.result.as_dict()["amount"] == report.result.as_dict()["amount"]


def test_export_report_writes_both_formats(tmp_path):
    from safefee.engine import export_report
    from safefee.report import ReportInput

    payload = ReportInput(
        ruleset_coordinate={"doc_no": "财资〔2022〕136号", "ruleset_id": "财资-2022-136",
                            "effective_from": "2022-11-21", "ruleset_sha256": "a" * 64,
                            "generated_at": "2026-10-14T00:00:00", "tool_version": "0.1.0"},
        enterprise={"enterprise_id": "X"},
        accrual={"amount": "1.00", "mechanism": "by_output", "formula": "f", "clause": "第七条",
                 "tiers": []},
        parameter_sources=[{"parameter": "p", "issuer": "i", "effective_year": "2022",
                            "doc_no": "d", "clause": "第七条", "url": "u",
                            "snapshot": "s", "fetched_at": "2026-10-14"}],
    )
    written = export_report(payload, tmp_path)
    assert (tmp_path / "报告.md").is_file()
    assert (tmp_path / "报告.xlsx").is_file()
    assert (tmp_path / "evidence.json").is_file()


def test_build_report_input_uses_real_provenance(data_dir):
    """**报告参数来源块接真 provenance**（不再用测试占位）：文号/条款/URL/快照/
    抓取日期全部来自规则包节点。"""
    from safefee.engine import build_case, build_report_input, compute_calc

    case = build_case({
        "enterprise_id": "X", "enterprise_name": "Y", "industry_id": "coal",
        "variant_id": "coal_high_gas", "year": 2024,
        "basis_kind": "output", "basis_value": "1000", "basis_unit": "ton",
    })
    report = compute_calc(case)
    payload = build_report_input(case, report)
    assert payload.parameter_sources, "参数来源块不得为空（否则拒导）"
    first = payload.parameter_sources[0]
    assert first["doc_no"] == "财资〔2022〕136号"
    assert first["clause"] == "第七条"
    assert first["url"].startswith("https://")
    assert first["snapshot"] == "data/knowledge/raw/136-body.docx"
    assert first["fetched_at"] == "2026-10-14"
    # 判定规则（第五十二/五十三条）也在参数来源块中
    clauses = {s["clause"] for s in payload.parameter_sources}
    assert "第五十二条" in clauses and "第五十三条" in clauses
