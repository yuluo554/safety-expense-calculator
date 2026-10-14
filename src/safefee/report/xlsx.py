"""XLSX 渲染器 —— **自写最小 OOXML writer**（零第三方依赖）。

**为什么自写**：引第三方库（openpyxl 等）会把**宿主系统标识与时间戳**写进 ZIP
元数据，破坏"同输入逐字节一致"的承诺。自写 writer 一律 ``ZIP_STORED`` +
``create_system=0`` + 固定 ``date_time``，于是**两轮导出 sha256 一致**可被实测背书。

**无外链**：单元格只写纯文本（URL 作为文本，不建超链接关系项）——断网可开。

**单一渲染源**：与 Markdown 渲染器读同一份 :class:`~safefee.report.sections.Section`
列表，故"两格式内容一致"是**结构性质**而非人工比对。
"""

import io
import zipfile
from typing import Sequence
from xml.sax.saxutils import escape

from safefee.report.sections import Section

#: 固定时间戳（1980-01-01）与 create_system=0（DOS/Windows 标识）
_FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)
_FIXED_CREATE_SYSTEM = 0
_FIXED_EXTERNAL_ATTR = 0

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
    "</Types>"
)

_ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
    "</Relationships>"
)

_WORKBOOK = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    '<sheets><sheet name="报告" sheetId="1" r:id="rId1"/></sheets>'
    "</workbook>"
)

_WORKBOOK_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
    "</Relationships>"
)


def _cell(ref: str, value: str, *, style: str = "") -> str:
    style_attr = ' s="%s"' % style if style else ""
    return '<c r="%s" t="inlineStr"%s><is><t xml:space="preserve">%s</t></is></c>' % (
        ref, style_attr, escape(value),
    )


def _column_name(index: int) -> str:
    name = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        name = chr(ord("A") + rem) + name
    return name


def _sheet_xml(sections: Sequence[Section]) -> str:
    rows = []
    row_index = 0
    for section in sections:
        row_index += 1
        rows.append('<row r="%d">%s</row>' % (row_index, _cell("A%d" % row_index, section.title, style="1")))
        if not section.enabled:
            row_index += 1
            note = section.disabled_note or "本次导出未启用本章节。"
            rows.append('<row r="%d">%s</row>' % (row_index, _cell("A%d" % row_index, note)))
            continue
        for paragraph in section.paragraphs:
            row_index += 1
            rows.append('<row r="%d">%s</row>' % (row_index, _cell("A%d" % row_index, paragraph)))
        if section.rows:
            row_index += 1
            cells = "".join(
                _cell("%s%d" % (_column_name(col), row_index), name, style="1")
                for col, name in enumerate(section.columns)
            )
            rows.append('<row r="%d">%s</row>' % (row_index, cells))
            for row in section.rows:
                row_index += 1
                cells = "".join(
                    _cell("%s%d" % (_column_name(col), row_index), value)
                    for col, value in enumerate(row)
                )
                rows.append('<row r="%d">%s</row>' % (row_index, cells))
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>" + "".join(rows) + "</sheetData>"
        "</worksheet>"
    )


def _zip_write(archive: zipfile.ZipFile, name: str, payload: str) -> None:
    info = zipfile.ZipInfo(name, date_time=_FIXED_DATE_TIME)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = _FIXED_CREATE_SYSTEM
    info.external_attr = _FIXED_EXTERNAL_ATTR
    archive.writestr(info, payload.encode("utf-8"))


def render_xlsx(sections: Sequence[Section]) -> bytes:
    """渲染为 XLSX 字节（**逐字节可复现**）。"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        _zip_write(archive, "[Content_Types].xml", _CONTENT_TYPES)
        _zip_write(archive, "_rels/.rels", _ROOT_RELS)
        _zip_write(archive, "xl/workbook.xml", _WORKBOOK)
        _zip_write(archive, "xl/_rels/workbook.xml.rels", _WORKBOOK_RELS)
        _zip_write(archive, "xl/worksheets/sheet1.xml", _sheet_xml(sections))
    return buffer.getvalue()


__all__ = ["render_xlsx"]
