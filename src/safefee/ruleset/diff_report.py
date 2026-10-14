"""双版本差异对照报告导出（``diff --out``）。

复用 :mod:`safefee.report` 的**单一渲染源**：把 :class:`~safefee.ruleset.diff.DiffReport`
装配成 :class:`~safefee.report.ReportInput`，Markdown 与 XLSX 渲染器消费同一章节结构
——"两格式内容一致"是结构性质，不是导出后比对。

无计提结论 → 溯源断言不触发；未启用的章节（计提/核查/进度/对账）按报告层纪律
**显式写出**说明而非留空。产物同 scan --report：MD/XLSX/evidence 三件。
"""

from pathlib import Path

from safefee.evidence import Evidence
from safefee.report import ReportInput, build_sections, render_markdown, render_xlsx

#: 差异四态的中文列名（与 DiffItem.kind 一一对应）
KIND_LABELS = {
    "value_changed": "数值变更",
    "rate_changed": "费率变更",
    "added": "新增",
    "removed": "移除",
}


def build_diff_report_input(report) -> ReportInput:
    """DiffReport → 报告输入（差异对照表为唯一实内容章节）。"""
    from safefee import __version__

    rows = tuple(
        (item.industry_id,
         item.variant_id or "—",
         KIND_LABELS.get(item.kind, item.kind),
         item.old_value or "—",
         item.new_value or "—",
         item.old_clause or "—",
         item.new_clause or "—",
         item.old_doc_no,
         item.new_doc_no)
        for item in report.items
    )
    return ReportInput(
        ruleset_coordinate={
            "doc_no": "%s → %s" % (report.old_doc_no, report.new_doc_no),
            "ruleset_id": "diff",
            "tool_version": __version__,
        },
        enterprise={"对照范围": "已比对行业 %d 个：%s" % (
            len(report.compared_industries), "、".join(report.compared_industries))},
        diff={"rows": rows},
        enabled=(),
    )


def export_diff_report(report, out_dir: Path):
    """导出差异对照报告（差异对照.md / 差异对照.xlsx / evidence.json），返回写盘路径。"""
    payload = build_diff_report_input(report)
    sections = build_sections(payload)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    written = []
    evidence = Evidence()
    md_path = out_dir / "差异对照.md"
    md_text = render_markdown(sections, title="双版本差异对照报告")
    md_path.write_bytes(md_text.encode("utf-8"))
    evidence.add_bytes("差异对照.md", md_text.encode("utf-8"))
    written.append(md_path)

    xlsx_path = out_dir / "差异对照.xlsx"
    xlsx_bytes = render_xlsx(sections)
    xlsx_path.write_bytes(xlsx_bytes)
    evidence.add_bytes("差异对照.xlsx", xlsx_bytes)
    written.append(xlsx_path)

    evidence_path = out_dir / "evidence.json"
    evidence_path.write_bytes(evidence.to_json().encode("utf-8"))
    written.append(evidence_path)
    return written


__all__ = ["build_diff_report_input", "export_diff_report", "KIND_LABELS"]
