"""编排层（CLI 与 GUI 的**唯一**入口）。

把全链路编排上收成一组公开函数——CLI 与 GUI **共用同一编排**，前端只渲染结果、
**零政策数值、零判定逻辑**。测试断言**行为等价（三方对账：CLI stdout == 编排直调
== 报告章节）**，而非"都调了同一个函数"这种字面声明。

数据目录定位、门控、计算、核查、进度、扫描、导出全在此收口；
``build_case`` 是**输入格式解释的唯一实现**（GUI 不得自带校验）。
"""

import json
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from safefee import __version__
from safefee.accrual import AccrualRequest, AccrualResult, compute, decide_basis
from safefee.batch import ObservedItem, ScanFailure, ScanOutcome, compare_nonpass, scan_sources
from safefee.data_paths import find_data_dir
from safefee.errors import (
    MissingInput,
    OptionalDependencyMissing,
    SchemaError,
    ScanItemError,
)
from safefee.evidence import Evidence
from safefee.report import ReportInput, build_parameter_sources, build_sections, render_markdown, render_xlsx
from safefee.rules import (
    check_scope,
    load_manifest,
    load_progress,
    load_ruleset,
    load_spending,
    load_units,
)
from safefee.rules.manifest import sha256_file
from safefee.spending import LedgerItem, check_ledger, compute_progress
from safefee.tiered import quantize_money

FORMATS = ("md", "xlsx")


@dataclass
class Case:
    """归一后的企业档案（输入契约的规范形态）。"""

    enterprise_id: str
    enterprise_name: str
    industry_id: str
    year: int
    basis_kind: str
    basis_value: Decimal
    basis_unit: str
    variant_id: Optional[str] = None
    raw: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "enterprise_id": self.enterprise_id,
            "enterprise_name": self.enterprise_name,
            "industry_id": self.industry_id,
            "year": self.year,
            "basis_kind": self.basis_kind,
            "basis_value": str(self.basis_value),
            "basis_unit": self.basis_unit,
            "variant_id": self.variant_id,
        }


@dataclass
class CalcReport:
    """计提计算结果（含门控与坐标留痕）。"""

    case: Case
    coordinate: dict
    result: Optional[AccrualResult]
    gate_blockers: Tuple[object, ...] = ()
    warnings: Tuple[str, ...] = ()
    basis: Optional[dict] = None
    inputs_required: Tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "coordinate": self.coordinate,
            "case": self.case.as_dict(),
            "result": self.result.as_dict() if self.result else None,
            "warnings": list(self.warnings),
            "basis": self.basis,
            "inputs_required": list(self.inputs_required),
        }


def build_case(payload: dict) -> Case:
    """档案校验 + 归一 —— **输入格式解释的唯一实现**。

    缺必填字段 → :class:`MissingInput`（退出码 2），**绝不静默取 0/1**。
    """
    required = (
        "enterprise_id", "enterprise_name", "industry_id", "year",
        "basis_kind", "basis_value", "basis_unit",
    )
    missing = [key for key in required if payload.get(key) in (None, "")]
    if missing:
        raise MissingInput("档案缺少必填字段：%s" % ", ".join(missing))
    return Case(
        enterprise_id=str(payload["enterprise_id"]),
        enterprise_name=str(payload["enterprise_name"]),
        industry_id=str(payload["industry_id"]),
        year=int(payload["year"]),
        basis_kind=str(payload["basis_kind"]),
        basis_value=Decimal(str(payload["basis_value"])),
        basis_unit=str(payload["basis_unit"]),
        variant_id=(str(payload["variant_id"]) if payload.get("variant_id") else None),
        raw=dict(payload),
    )


def load_archive(path: Path) -> dict:
    """读入档案 JSON（``parse_float=Decimal``）。"""
    try:
        with Path(path).open("r", encoding="utf-8") as fh:
            return json.load(fh, parse_float=Decimal)
    except FileNotFoundError:
        raise ScanItemError("parse_error", "档案文件不存在：%s" % path)
    except ValueError as exc:
        raise ScanItemError("parse_error", "档案不是合法 JSON：%s（%s）" % (path, exc))


def compute_calc(
    case: Case, data_dir: Optional[str] = None, *, fixed_time: Optional[str] = None
) -> CalcReport:
    """门控 → **依据选择判定** → 计算 → 结果（含规则包坐标与判定留痕）。

    依据选择判定（第五十二/五十三条、从高提取）在计算**之前**收口：

    * 档案属性缺失（如矿井 ``mine_type``）→ ``inputs_required`` 非空 → 调用方退出码 2；
    * 净额口径命中 → 用净额替换依据量，并把判定留痕进结果与报告。

    ``fixed_time``（E21）：替换报告头的生成时间——"逐字节可复现"按它断言，
    默认（None）含真实时间。
    """
    root = find_data_dir(data_dir)
    manifest = load_manifest(root)
    ref = manifest.resolve_year(case.year)
    ruleset = load_ruleset(root, ref.directory)
    units = load_units(root)

    gate = check_scope(ruleset, "calc", industry_id=case.industry_id)
    coordinate = _coordinate(ref, root, manifest, fixed_time)

    warnings: List[str] = []
    basis_value, unit_warning = units.to_base(case.basis_value, case.basis_unit)
    if unit_warning:
        warnings.append(unit_warning)

    if not gate.ok:
        return CalcReport(case=case, coordinate=coordinate, result=None,
                          gate_blockers=gate.blockers, warnings=tuple(warnings))

    decision = decide_basis(ruleset, case)
    if decision.inputs_required:
        # **必索**：档案属性缺失 → 调用方据此退出码 2（绝不静默取 0/1）
        return CalcReport(case=case, coordinate=coordinate, result=None,
                          warnings=tuple(warnings), basis=decision.as_dict(),
                          inputs_required=decision.inputs_required)

    variant_id = case.variant_id or decision.chosen_variant
    if decision.basis_value is not None:
        basis_value = Decimal(decision.basis_value)
        warnings.append("依据选择：第五十三条净额口径生效——依据量取净额 %s 元"
                        % decision.basis_value)

    request = AccrualRequest(
        industry_id=case.industry_id,
        basis_kind=case.basis_kind,
        basis_value=basis_value,
        basis_unit="CNY" if case.basis_kind != "output" else case.basis_unit,
        year=case.year,
        variant_id=variant_id,
        warnings=tuple(warnings),
    )
    result = compute(ruleset, request)
    # 请求已把 warnings 带入结果；此处按出现序去重（避免同一条提示重复列出）
    merged = tuple(dict.fromkeys(warnings + list(result.warnings)))
    basis_payload = decision.as_dict() if decision.kind != "none" else None
    if basis_payload is not None and result.basis is None:
        result = replace(result, basis=basis_payload)
    return CalcReport(case=case, coordinate=coordinate, result=result,
                      gate_blockers=(), warnings=merged, basis=basis_payload)


def check_ledger_file(
    case: Case, ledger_path: Path, data_dir: Optional[str] = None,
    *, fixed_time: Optional[str] = None,
) -> dict:
    """支出核查（须先过 ``check`` 作用域门控）。``fixed_time`` 见 :func:`compute_calc`。"""
    root = find_data_dir(data_dir)
    manifest = load_manifest(root)
    ref = manifest.resolve_year(case.year)
    spending = load_spending(root, ref.directory)
    gate = check_scope(load_ruleset(root, ref.directory), "check", spending=spending)
    if not gate.ok:
        return {"gate_blocked": True, "blockers": [b.__dict__ for b in gate.blockers],
                "coordinate": _coordinate(ref, root, manifest, fixed_time)}
    items = _read_ledger(ledger_path)
    report = check_ledger(spending, case.industry_id, items)
    payload = report.as_dict()
    payload["coordinate"] = _coordinate(ref, root, manifest, fixed_time)
    return payload


def _read_ledger(path: Path) -> List[LedgerItem]:
    """读入台账 CSV（零依赖）；缺字段记原因码。"""
    import csv

    items: List[LedgerItem] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        required = ("item_key", "subject", "summary", "amount")
        for index, row in enumerate(reader, start=2):
            missing = [key for key in required if not row.get(key)]
            if missing:
                raise ScanItemError(
                    "missing_field", "台账第 %d 行缺字段：%s" % (index, ", ".join(missing))
                )
            items.append(LedgerItem(
                item_key=str(row["item_key"]),
                subject=str(row["subject"]),
                summary=str(row["summary"]),
                amount=quantize_money(Decimal(str(row["amount"]))),
            ))
    return items


def compute_progress_for(
    case: Case, *, accrued: Decimal, used: Decimal,
    data_dir: Optional[str] = None, fixed_time: Optional[str] = None,
) -> dict:
    """使用进度判定（须先过 ``progress`` 作用域门控）。``fixed_time`` 见 :func:`compute_calc`。"""
    root = find_data_dir(data_dir)
    manifest = load_manifest(root)
    ref = manifest.resolve_year(case.year)
    progress_rules = load_progress(root, ref.directory)
    gate = check_scope(load_ruleset(root, ref.directory), "progress", progress=progress_rules)
    if not gate.ok:
        return {"gate_blocked": True, "blockers": [b.__dict__ for b in gate.blockers],
                "coordinate": _coordinate(ref, root, manifest, fixed_time)}
    result = compute_progress(
        progress_rules, year=case.year, accrued=accrued, used=used
    )
    payload = result.as_dict()
    payload["coordinate"] = _coordinate(ref, root, manifest, fixed_time)
    return payload


def compute_diff(
    from_year: int, to_year: int, data_dir: Optional[str] = None,
) -> object:
    """双版本差异对照（``diff`` 的编排；同版返回 ``None`` 表示无数值差异）。"""
    root = find_data_dir(data_dir)
    manifest = load_manifest(root)
    old_ref = manifest.resolve_year(int(from_year))
    new_ref = manifest.resolve_year(int(to_year))
    if old_ref.ruleset_id == new_ref.ruleset_id:
        return None
    from safefee.ruleset import compare

    return compare(load_ruleset(root, old_ref.directory),
                   load_ruleset(root, new_ref.directory))


def scan(
    sources: Sequence[str],
    *,
    case_loader,
    handler,
) -> ScanOutcome:
    """批量扫描：**单件异常不中断整批**、失败件单列（**不改退出码**）。"""
    return scan_sources(sources, handler)


def export_report(
    report_input: ReportInput,
    out_dir: Path,
    *,
    formats: Sequence[str] = FORMATS,
) -> List[Path]:
    """导出报告（Markdown + XLSX），并**断言溯源完整性**（不满足即拒导）。"""
    _assert_traceability(report_input)
    sections = build_sections(report_input)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    written: List[Path] = []
    evidence = Evidence()
    if "md" in formats:
        md_path = out_dir / "报告.md"
        md_text = render_markdown(sections)
        md_path.write_bytes(md_text.encode("utf-8"))
        evidence.add_bytes("报告.md", md_text.encode("utf-8"))
        written.append(md_path)
    if "xlsx" in formats:
        xlsx_bytes = render_xlsx(sections)
        xlsx_path = out_dir / "报告.xlsx"
        xlsx_path.write_bytes(xlsx_bytes)
        evidence.add_bytes("报告.xlsx", xlsx_bytes)
        written.append(xlsx_path)

    evidence_path = out_dir / "evidence.json"
    evidence_path.write_bytes(evidence.to_json().encode("utf-8"))
    written.append(evidence_path)
    return written


def build_report_input(
    case: Case,
    report: CalcReport,
    *,
    check: Optional[dict] = None,
    progress: Optional[dict] = None,
    reconcile: Optional[dict] = None,
    data_dir: Optional[str] = None,
) -> ReportInput:
    """组装报告输入：**参数来源块接真 provenance**（不再用测试占位）。

    从规则包逐节点提取出处（发布机关/适用年度/文号/条款/URL/快照/sha256/抓取日期），
    收窄到**本次计算路径上的行业/变体**——读者不开仓库即可核证"这个数字哪来的"。
    """
    root = find_data_dir(data_dir)
    manifest = load_manifest(root)
    ref = manifest.resolve_year(case.year)
    ruleset = load_ruleset(root, ref.directory)
    sources = build_parameter_sources(
        ruleset,
        industry_id=case.industry_id,
        variant_id=(case.variant_id
                    or (report.basis or {}).get("chosen_variant")),
    )
    return ReportInput(
        ruleset_coordinate=report.coordinate,
        enterprise=case.as_dict(),
        accrual=report.result.as_dict() if report.result else None,
        check=check,
        progress=progress,
        reconcile=reconcile,
        parameter_sources=sources,
    )


def export_diff_report(report, out_dir: Path) -> list:
    """差异对照报告导出收口（GUI 经此导出；ruleset.diff_report 不直接进界面层）。"""
    from safefee.ruleset.diff_report import export_diff_report as _export

    return _export(report, Path(out_dir))


def _assert_traceability(report_input: ReportInput) -> None:
    """**溯源完整性硬约束**：有计提结论 → 参数来源块必须有**可核证的真出处**。

    "半溯源"比"无溯源"更危险（读者以为已可核证）——故做成**导出前断言**：
    参数来源块非空，且每行都带 文号 + 条款 + URL + 快照 + sha256 + 抓取日期。
    """
    sections = build_sections(report_input)
    source_rows = []
    for section in sections:
        if section.title == "参数来源块" and section.enabled:
            source_rows = list(section.rows)
    if report_input.accrual is not None and not source_rows:
        raise SchemaError(
            "溯源完整性不满足：计提结论存在但参数来源块为空——拒导（半溯源不可接受）"
        )
    # 参数行必须携带可核证出处（列序：参数/发布机关/适用年度/文号/条款/URL/快照/抓取日期）
    for row in source_rows:
        if len(row) < 8 or not row[3] or not row[4] or not row[5] or not row[7]:
            raise SchemaError(
                "溯源完整性不满足：参数来源行缺少 文号/条款/URL/抓取日期 ——拒导（%s）" % (row,)
            )


def selfcheck(data_dir: Optional[str] = None) -> dict:
    """数据目录定位 + 规则集加载 + 门控计数。"""
    root = find_data_dir(data_dir)
    manifest = load_manifest(root)
    units = load_units(root)
    rulesets = []
    for ref in manifest.refs:
        ruleset = load_ruleset(root, ref.directory)
        scopes = {}
        for scope in ("calc", "check", "progress"):
            spending = load_spending(root, ref.directory) if scope == "check" else None
            progress = load_progress(root, ref.directory) if scope == "progress" else None
            try:
                gate = check_scope(ruleset, scope, spending=spending, progress=progress)
                scopes[scope] = {"ok": gate.ok, "blockers": len(gate.blockers)}
            except Exception as exc:  # noqa: BLE001 —— 自检不因单作用域缺失而中断
                scopes[scope] = {"ok": False, "error": str(exc)}
        rulesets.append({"ref": ref.as_dict(), "scopes": scopes})
    return {
        "data_dir": str(root),
        "units": sorted(units.factors),
        "rulesets": rulesets,
    }


def _coordinate(ref, root: Path, manifest, fixed_time: Optional[str] = None) -> dict:
    """规则包坐标（报告头固定输出）。``fixed_time``（E21）替换生成时间。"""
    ruleset_path = root / "rules" / ref.directory / "ruleset.json"
    return {
        "ruleset_id": ref.ruleset_id,
        "doc_no": ref.doc_no,
        "doc_title": ref.doc_title,
        "effective_from": ref.effective_from.isoformat(),
        "effective_to": ref.effective_to.isoformat() if ref.effective_to else None,
        "status": ref.status,
        "ruleset_sha256": sha256_file(ruleset_path) if ruleset_path.is_file() else "",
        "tool_version": __version__,
        "generated_at": fixed_time or datetime.now().isoformat(timespec="seconds"),
    }


# ---------------------------------------------------------------------------
# 结果文本格式化（CLI 与 GUI 的**同一实现源**——三方对账按此对齐）。
# 纯函数、只渲染传入结果：零判定逻辑、零政策数值（数值都在结果对象里）。
# ---------------------------------------------------------------------------

def format_calc(report: CalcReport) -> str:
    """计提结果 → 面向人的文本（与 ``calc`` CLI stdout 同一实现源）。"""
    case = report.case
    result = report.result
    if result is None:
        return ""
    lines = [
        "企业：%s（%s）" % (case.enterprise_name, case.enterprise_id),
        "规则包：%s（%s）" % (report.coordinate["doc_no"], report.coordinate["ruleset_id"]),
        "计提机制：%s" % result.mechanism,
        "计算公式：%s" % result.formula,
        "条款依据：%s" % result.clause,
    ]
    if report.basis:
        lines.append("依据选择：%s（条款 %s）"
                     % (report.basis.get("kind"), report.basis.get("clause")))
        for note in report.basis.get("notes", []):
            lines.append("  - %s" % note)
        for item in report.basis.get("excluded", []):
            lines.append("  排除 %s：%s" % (item.get("item"), item.get("reason")))
    lines.append("应计提金额：%s 元" % result.amount)
    for line in result.tiers:
        lines.append("  段 %d：%s ~ %s × %s = %s（%s）"
                     % (line.index, line.lower, line.upper or "∞", line.rate,
                        line.amount, line.clause))
    for warning in report.warnings:
        lines.append("提示：%s" % warning)
    return "\n".join(lines)


def format_check(payload: dict) -> str:
    """支出核查结果 → 面向人的文本（与 ``check`` CLI stdout 同一实现源）。"""
    lines = []
    for key, count in sorted(payload["counts"].items()):
        lines.append("%s：%d" % (key, count))
    for finding in payload["findings"]:
        lines.append("  %s | %s | %s | %s | %s"
                     % (finding["item_key"], finding["state"], finding["amount"],
                        finding["clause"] or "—", finding["reason"]))
    return "\n".join(lines)


def format_progress(payload: dict) -> str:
    """进度判定结果 → 面向人的文本（与 ``progress`` CLI stdout 同一实现源）。"""
    if not payload["applicable"]:
        return "年度应计提额为 0：进度门槛不适用"
    lines = [
        "使用进度：%s（门槛 %s）" % (payload["ratio"], payload["threshold"]),
        "是否触发披露义务：%s" % ("是" if payload["disclosure_required"] else "否"),
        "条款依据：%s" % payload["clause"],
    ]
    for point in payload["points"]:
        lines.append("  - %s" % point)
    return "\n".join(lines)


def format_diff(report) -> str:
    """差异对照结果 → 面向人的文本（与 ``diff`` CLI stdout 同一实现源）。"""
    lines = [
        "对照：%s → %s" % (report.old_doc_no, report.new_doc_no),
        "已比对行业（%d）：%s" % (len(report.compared_industries),
                                 "、".join(report.compared_industries)),
    ]
    for kind, count in sorted(report.counts().items()):
        lines.append("  %s：%d" % (kind, count))
    for item in report.items:
        lines.append("  %s/%s %s：%s → %s（%s → %s）"
                     % (item.industry_id, item.variant_id or "—", item.kind,
                        item.old_value or "—", item.new_value or "—",
                        item.old_clause or "—", item.new_clause or "—"))
    return "\n".join(lines)


__all__ = [
    "FORMATS",
    "Case",
    "CalcReport",
    "build_case",
    "build_report_input",
    "load_archive",
    "compute_calc",
    "check_ledger_file",
    "compute_progress_for",
    "compute_diff",
    "export_diff_report",
    "format_calc",
    "format_check",
    "format_progress",
    "format_diff",
    "scan",
    "export_report",
    "selfcheck",
]
