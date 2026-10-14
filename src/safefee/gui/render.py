"""GUI 显示装配（**无 Qt 依赖**——三方对账的第三条腿可脱离界面实测）。

只消费 :mod:`safefee.engine.pipeline` 的结果对象/纯字典；**行文本直接复用
``pipeline.format_*``**——"CLI stdout == GUI 展示"是**构造性质**（同一实现源），
不是导出后比对。零判定逻辑、零政策数值（AST 三条守门守住）。

界面层（``widgets.py``）把这里的 ``(标题, 行列表)`` 序列直接搬上屏幕。
"""

from typing import List, Tuple

from safefee.engine import pipeline

#: 显示块 =（标题，行文本序列）——界面表单与对账测试共用此形态
Block = Tuple[str, List[str]]

PANELS = ("计提计算", "支出核查", "使用进度", "版本对照")


def archive_payload(
    enterprise_id: str,
    enterprise_name: str,
    industry_id: str,
    year: int,
    basis_kind: str,
    basis_value: str,
    basis_unit: str,
    variant_id: str = "",
) -> dict:
    """表单输入 → 档案 payload（校验归 :func:`pipeline.build_case` 单一实现源）。"""
    payload = {
        "enterprise_id": enterprise_id,
        "enterprise_name": enterprise_name,
        "industry_id": industry_id,
        "year": year,
        "basis_kind": basis_kind,
        "basis_value": basis_value,
        "basis_unit": basis_unit,
    }
    if variant_id:
        payload["variant_id"] = variant_id
    return payload


def calc_blocks(report) -> List[Block]:
    """计提结果 → 显示块（行文本 = :func:`pipeline.format_calc`）。"""
    if report.result is None:
        return [("计提计算", ["无结果（门控拦截或属性必索）"])]
    return [("计提计算", pipeline.format_calc(report).split("\n"))]


def check_blocks(payload: dict) -> List[Block]:
    """核查结果 → 显示块（行文本 = :func:`pipeline.format_check`）。"""
    if payload.get("gate_blocked"):
        return [("支出核查", ["存在未核对条目，拒绝核查"])]
    return [("支出核查", pipeline.format_check(payload).split("\n"))]


def progress_blocks(payload: dict) -> List[Block]:
    """进度判定 → 显示块（行文本 = :func:`pipeline.format_progress`）。"""
    if payload.get("gate_blocked"):
        return [("使用进度", ["存在未核对条目，拒绝进度判定"])]
    return [("使用进度", pipeline.format_progress(payload).split("\n"))]


def diff_blocks(report) -> List[Block]:
    """差异对照 → 显示块（行文本 = :func:`pipeline.format_diff`）。"""
    if report is None:
        return [("版本对照", ["两年度锚定到同一规则集：无数值差异可对照"])]
    return [("版本对照", pipeline.format_diff(report).split("\n"))]


def blocks_to_text(blocks: List[Block]) -> str:
    """显示块 → 纯文本（对账测试用它和 CLI stdout 比对）。"""
    lines: List[str] = []
    for title, rows in blocks:
        lines.append(title)
        lines.extend(rows)
    return "\n".join(lines)


def run_calc_blocks(payload: dict, data_dir=None) -> List[Block]:
    """档案 payload → 计提显示块（异常原样上抛：GUI 不吞错、不自行判定）。"""
    case = pipeline.build_case(payload)
    report = pipeline.compute_calc(case, data_dir)
    if report.gate_blockers or report.inputs_required or report.result is None:
        raise _CalcNotOk(report)
    return calc_blocks(report)


class _CalcNotOk(Exception):
    """计提被门控拦截 / 属性必索 / 无结果——界面据此显示拦截原因。"""

    def __init__(self, report) -> None:
        super().__init__("calc_not_ok")
        self.report = report


__all__ = [
    "Block",
    "PANELS",
    "archive_payload",
    "blocks_to_text",
    "calc_blocks",
    "check_blocks",
    "diff_blocks",
    "progress_blocks",
    "run_calc_blocks",
]
