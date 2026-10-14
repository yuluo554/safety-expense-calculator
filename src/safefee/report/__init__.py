"""报告导出（人读 Markdown + 机读 XLSX，**单一渲染源**）。"""

from safefee.report.markdown import render_markdown
from safefee.report.sections import DISCLAIMER, ReportInput, Section, build_sections
from safefee.report.xlsx import render_xlsx

__all__ = [
    "DISCLAIMER",
    "ReportInput",
    "Section",
    "build_sections",
    "render_markdown",
    "render_xlsx",
]
