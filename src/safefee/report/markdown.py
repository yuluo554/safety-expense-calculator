"""Markdown 渲染器（消费 :func:`safefee.report.sections.build_sections`）。

**无外链**：产物中不得出现 URL 之外的可点击外链形态（URL 仅作纯文本出现在
"参数来源块"列内）；章节"未启用"时**显式写出**说明而非留空。
"""

from typing import Sequence

from safefee.report.sections import Section


def render_markdown(sections: Sequence[Section], *, title: str = "安全生产费用计提与合规核查报告") -> str:
    """渲染为 Markdown 文本（固定换行 ``\\n``，无时间戳注入）。"""
    lines = ["# %s" % title, ""]
    for section in sections:
        lines.append("## %s" % section.title)
        lines.append("")
        if not section.enabled:
            lines.append("> %s" % (section.disabled_note or "本次导出未启用本章节。"))
            lines.append("")
            continue
        if section.paragraphs:
            for paragraph in section.paragraphs:
                lines.append("- %s" % paragraph)
            lines.append("")
        if section.rows:
            lines.append("| " + " | ".join(section.columns) + " |")
            lines.append("|" + "|".join([" --- "] * len(section.columns)) + "|")
            for row in section.rows:
                # 单元格内的 `|`（如费率序列）必须转义，否则撑破表格列
                cells = (str(cell).replace("|", "\\|") for cell in row)
                lines.append("| " + " | ".join(cells) + " |")
            lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


__all__ = ["render_markdown"]
