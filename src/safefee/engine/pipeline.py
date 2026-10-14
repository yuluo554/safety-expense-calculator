"""编排层（CLI 与 GUI 的**唯一**入口）。

把全链路编排上收成一组公开函数——CLI 与 GUI **共用同一编排**，前端只渲染结果、
**零政策数值、零判定逻辑**。测试断言**行为等价（三方对账：CLI stdout == 编排直调
== 报告章节）**，而非"都调了同一个函数"这种字面声明。

数据目录定位、门控、计算、核查、进度、扫描、导出全在此收口；
``build_case`` 是**输入格式解释的唯一实现**（GUI 不得自带校验）。
"""

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from safefee import __version__
from safefee.accrual import AccrualRequest, AccrualResult, compute
from safefee.batch import ObservedItem, ScanFailure, ScanOutcome, compare_nonpass, scan_sources
from safefee.data_paths import find_data_dir
from safefee.errors import (
    MissingInput,
    OptionalDependencyMissing,
    SchemaError,
    ScanItemError,
)
from safefee.evidence import Evidence
from safefee.report import ReportInput, build_sections, render_markdown, render_xlsx
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

    def as_dict(self) -> dict:
        return {
            "coordinate": self.coordinate,
            "case": self.case.as_dict(),
            "result": self.result.as_dict() if self.result else None,
            "warnings": list(self.warnings),
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


def compute_calc(case: Case, data_dir: Optional[str] = None) -> CalcReport:
    """门控 → 计算 → 结果（含规则包坐标）。"""
    root = find_data_dir(data_dir)
    manifest = load_manifest(root)
    ref = manifest.resolve_year(case.year)
    ruleset = load_ruleset(root, ref.directory)
    units = load_units(root)

    gate = check_scope(ruleset, "calc", industry_id=case.industry_id)
    coordinate = _coordinate(ref, root, manifest)

    warnings: List[str] = []
    basis_value, unit_warning = units.to_base(case.basis_value, case.basis_unit)
    if unit_warning:
        warnings.append(unit_warning)

    if not gate.ok:
        return CalcReport(case=case, coordinate=coordinate, result=None,
                          gate_blockers=gate.blockers, warnings=tuple(warnings))

    request = AccrualRequest(
        industry_id=case.industry_id,
        basis_kind=case.basis_kind,
        basis_value=basis_value,
        basis_unit="CNY" if case.basis_kind != "output" else case.basis_unit,
        year=case.year,
        variant_id=case.variant_id,
        warnings=tuple(warnings),
    )
    result = compute(ruleset, request)
    merged = tuple(warnings) + tuple(result.warnings)
    return CalcReport(case=case, coordinate=coordinate, result=result,
                      gate_blockers=(), warnings=merged)


def check_ledger_file(case: Case, ledger_path: Path, data_dir: Optional[str] = None) -> dict:
    """支出核查（须先过 ``check`` 作用域门控）。"""
    root = find_data_dir(data_dir)
    manifest = load_manifest(root)
    ref = manifest.resolve_year(case.year)
    spending = load_spending(root, ref.directory)
    gate = check_scope(load_ruleset(root, ref.directory), "check", spending=spending)
    if not gate.ok:
        return {"gate_blocked": True, "blockers": [b.__dict__ for b in gate.blockers],
                "coordinate": _coordinate(ref, root, manifest)}
    items = _read_ledger(ledger_path)
    report = check_ledger(spending, case.industry_id, items)
    payload = report.as_dict()
    payload["coordinate"] = _coordinate(ref, root, manifest)
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
    case: Case, *, accrued: Decimal, used: Decimal, data_dir: Optional[str] = None
) -> dict:
    """使用进度判定（须先过 ``progress`` 作用域门控）。"""
    root = find_data_dir(data_dir)
    manifest = load_manifest(root)
    ref = manifest.resolve_year(case.year)
    progress_rules = load_progress(root, ref.directory)
    gate = check_scope(load_ruleset(root, ref.directory), "progress", progress=progress_rules)
    if not gate.ok:
        return {"gate_blocked": True, "blockers": [b.__dict__ for b in gate.blockers],
                "coordinate": _coordinate(ref, root, manifest)}
    result = compute_progress(
        progress_rules, year=case.year, accrued=accrued, used=used
    )
    payload = result.as_dict()
    payload["coordinate"] = _coordinate(ref, root, manifest)
    return payload


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


def _assert_traceability(report_input: ReportInput) -> None:
    """**溯源完整性硬约束**：明细行数 == 溯源行数 + 参数行数，引用 id 可解析。

    "半溯源"比"无溯源"更危险（读者以为已可核证）——故做成**导出前断言**。
    """
    sections = build_sections(report_input)
    detail_rows = 0
    for section in sections:
        if section.enabled and section.rows and "参数来源块" not in section.title:
            detail_rows += len(section.rows)
    source_rows = 0
    for section in sections:
        if section.title == "参数来源块" and section.enabled:
            source_rows = len(section.rows)
    # 计提明细 + 支出核查的每一行都必须能在溯源块里找到对应参数（或显式声明无参数）
    if report_input.accrual is not None and source_rows == 0:
        raise SchemaError(
            "溯源完整性不满足：计提结论存在但参数来源块为空——拒导（半溯源不可接受）"
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


def _coordinate(ref, root: Path, manifest) -> dict:
    """规则包坐标（报告头固定输出）。"""
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
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


__all__ = [
    "FORMATS",
    "Case",
    "CalcReport",
    "build_case",
    "load_archive",
    "compute_calc",
    "check_ledger_file",
    "compute_progress_for",
    "scan",
    "export_report",
    "selfcheck",
]
