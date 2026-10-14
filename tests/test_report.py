"""报告导出测试（单一渲染源 / 无外链 / 溯源完整性 / 字节可复现）。"""

import re
import zipfile
from io import BytesIO

import pytest

from safefee.report import ReportInput, build_sections, render_markdown, render_xlsx


def _report_input() -> ReportInput:
    return ReportInput(
        ruleset_coordinate={
            "doc_no": "财资〔2022〕136号", "ruleset_id": "财资-2022-136",
            "effective_from": "2022-11-21", "ruleset_sha256": "a" * 64,
            "generated_at": "2026-10-14T00:00:00", "tool_version": "0.1.0",
        },
        enterprise={"enterprise_id": "90000000SYN0000001A", "industry_id": "coal", "year": 2024},
        accrual={
            "amount": "30000.00", "mechanism": "by_output",
            "formula": "CNY/ton × 30 × 1000 = 30000.00 元", "clause": "第七条",
            "tiers": [],
        },
        parameter_sources=[
            {"parameter": "煤炭高瓦斯矿井单价", "issuer": "财政部、应急部",
             "effective_year": "2022", "doc_no": "财资〔2022〕136号", "clause": "第七条",
             "url": "https://www.gov.cn/", "snapshot": "data/knowledge/raw/136-body.docx",
             "fetched_at": "2026-10-14"},
        ],
    )


def test_single_rendering_source_feeds_both_formats():
    """两格式消费**同一章节结构**——内容一致是**结构性质**。"""
    sections = build_sections(_report_input())
    md = render_markdown(sections)
    xlsx = render_xlsx(sections)
    assert "规则包坐标" in md
    assert b"xl/worksheets/sheet1.xml" in xlsx
    # XLSX 内也含同样的章节标题（证明同一结构源）
    with zipfile.ZipFile(BytesIO(xlsx)) as archive:
        sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
    for section in sections:
        if section.enabled:
            assert section.title in md
            assert section.title in sheet


def test_markdown_has_no_external_links():
    """**无外链**：报告可断网可开——URL 仅作纯文本，不得是 markdown 链接形态。"""
    md = render_markdown(build_sections(_report_input()))
    assert not re.search(r"\]\(https?://", md)


def test_xlsx_has_no_external_relationships():
    """XLSX 不得含 External 关系项（无外链硬断言）。"""
    xlsx = render_xlsx(build_sections(_report_input()))
    with zipfile.ZipFile(BytesIO(xlsx)) as archive:
        for name in archive.namelist():
            if name.endswith(".rels"):
                assert b"External" not in archive.read(name)


def test_disabled_sections_are_explicit_not_blank():
    """**未启用章节显式写出**——"没查"与"查了没问题"必须可区分。"""
    payload = ReportInput(ruleset_coordinate={"doc_no": "X"}, enterprise={"a": "b"})
    sections = build_sections(payload)
    md = render_markdown(sections)
    assert "本次导出未启用支出核查" in md
    assert "本次导出未启用进度核查" in md


def test_disclaimer_always_present():
    md = render_markdown(build_sections(_report_input()))
    assert "免责声明" in md
    assert "不构成会计、审计或法律意见" in md


def test_xlsx_is_byte_reproducible():
    """**机读产物逐字节可复现**（自写 writer：ZIP_STORED + create_system=0 + 固定时间戳）。"""
    sections = build_sections(_report_input())
    first = render_xlsx(sections)
    second = render_xlsx(sections)
    assert first == second


def test_xlsx_zip_entries_have_fixed_create_system():
    """zip 容器冻结：``create_system`` 必须固定（跨平台不漂移）。"""
    xlsx = render_xlsx(build_sections(_report_input()))
    with zipfile.ZipFile(BytesIO(xlsx)) as archive:
        for info in archive.infolist():
            assert info.create_system == 0
            assert info.date_time == (1980, 1, 1, 0, 0, 0)
            assert info.compress_type == zipfile.ZIP_STORED


def test_markdown_is_byte_reproducible():
    sections = build_sections(_report_input())
    assert render_markdown(sections) == render_markdown(sections)


def test_traceability_requires_parameter_sources():
    """**溯源完整性硬约束**：有计提结论却无参数来源块 → 拒导（半溯源不可接受）。"""
    from safefee.engine.pipeline import export_report
    from safefee.errors import SchemaError

    payload = ReportInput(
        ruleset_coordinate={"doc_no": "X"},
        enterprise={"a": "b"},
        accrual={"amount": "1.00", "mechanism": "by_output", "formula": "f", "clause": "第七条",
                 "tiers": []},
        parameter_sources=[],
    )
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(SchemaError):
            export_report(payload, tmp)


def test_export_writes_evidence_and_both_formats(tmp_path):
    from safefee.engine.pipeline import export_report

    written = export_report(_report_input(), tmp_path)
    names = {p.name for p in written}
    assert names == {"报告.md", "报告.xlsx", "evidence.json"}
    evidence = (tmp_path / "evidence.json").read_text(encoding="utf-8")
    assert "报告.xlsx" in evidence
    assert "报告.md" in evidence
