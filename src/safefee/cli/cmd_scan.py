"""``scan`` 子命令：批量台账扫描（接真四态核查）+ 跨年对账 + 报告导出。

**M3 接真**：逐件台账 CSV 读入 → 过 ``check`` 作用域门控 → 逐笔
``check_ledger`` 四态判定；逐笔结论以**稳定身份键**
（``enterprise_id + year + item_key``）登记为 :class:`ObservedItem`
→ ``--baseline`` 给定时四集合对账；``--report`` 给定时直接驱动报告导出。

**两条退出码纪律（动了会打挂基准）**：

* **失败件 ≠ 违规**——坏 CSV / 缺字段 / 年度无规则包 / 行业未覆盖是**未判定**
  （失败件单列、带原因码），**不改退出码**；
* **核查 ≠ 门控**——检出"不符合"属于**核查结论**（单列红线），不是门控拦截；
  退出码仍为 0，处置交给报告与对账（与 ``check`` 子命令的退出码 1 语义区分）。
"""

import csv
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from safefee.batch import ObservedItem, ScanFailure, compare_nonpass, scan_sources
from safefee.engine.pipeline import build_report_input, export_report
from safefee.evidence import sha256_text
from safefee.errors import EXIT_OK, ScanItemError
from safefee.rules import load_manifest
from safefee.tiered import quantize_money

#: 台账 CSV 必填列（M3 起含企业与年度，供稳定身份键与规则包定位）
LEDGER_REQUIRED = ("enterprise_id", "year", "industry_id", "item_key", "subject", "summary", "amount")


def _read_ledger_rows(path: Path) -> list:
    """读入批量台账 CSV（每行 = 一笔支出 + 所属企业与年度）。"""
    rows = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ScanItemError("parse_error", "台账表头为空：%s" % path.name)
        missing_cols = [col for col in LEDGER_REQUIRED if col not in (reader.fieldnames or [])]
        if missing_cols:
            raise ScanItemError("missing_field", "台账 %s 缺列：%s"
                                % (path.name, ", ".join(missing_cols)))
        for index, row in enumerate(reader, start=2):
            missing = [key for key in LEDGER_REQUIRED if not (row.get(key) or "").strip()]
            if missing:
                raise ScanItemError("missing_field", "台账第 %d 行缺字段：%s"
                                    % (index, ", ".join(missing)))
            try:
                year = int(str(row["year"]))
            except ValueError:
                raise ScanItemError("unknown_year", "台账第 %d 行年度不可解析：%r"
                                    % (index, row["year"]))
            try:
                amount = quantize_money(Decimal(str(row["amount"])))
            except ValueError as exc:
                raise ScanItemError("parse_error", "台账第 %d 行金额不可解析：%s"
                                    % (index, exc))
            rows.append({
                "enterprise_id": str(row["enterprise_id"]).strip(),
                "year": year,
                "industry_id": str(row["industry_id"]).strip(),
                "item_key": str(row["item_key"]).strip(),
                "subject": str(row["subject"]).strip(),
                "summary": str(row["summary"]).strip(),
                "amount": amount,
            })
    return rows


def _check_one(source: str, data_dir=None) -> dict:
    """单件处理：读台账 → 逐笔四态核查 → 返回可对账结论。

    年度无规则包 / 行业未覆盖 / 作用域门控拦截 → :class:`ScanItemError`
    （按原因码记失败件，**不中断整批、不改退出码**）。
    """
    from safefee.data_paths import find_data_dir
    from safefee.rules import check_scope, load_ruleset, load_spending

    path = Path(source)
    rows = _read_ledger_rows(path)
    root = find_data_dir(data_dir)
    manifest = load_manifest(root)

    observed: list = []
    findings: list = []
    redlines: list = []
    by_industry: dict = {}
    for row in rows:
        key = "%s|%s|%s" % (row["enterprise_id"], row["year"], row["item_key"])
        try:
            ref = manifest.resolve_year(row["year"])
        except Exception as exc:  # noqa: BLE001 —— 单件年度异常按原因码隔离
            raise ScanItemError("unknown_year", "第 %s 行：%s" % (row["item_key"], exc))
        industry_id = row["industry_id"]
        if industry_id not in by_industry:
            by_industry[industry_id] = (ref, load_ruleset(root, ref.directory),
                                        load_spending(root, ref.directory))
        ref, ruleset, spending = by_industry[industry_id]

        gate = check_scope(ruleset, "check", spending=spending)
        if not gate.ok:
            raise ScanItemError("gate_blocked", "行业 %s 支出条目存在未核对项，拒绝核查" % industry_id)

        from safefee.spending import LedgerItem, check_ledger

        report = check_ledger(spending, industry_id, [LedgerItem(
            item_key=row["item_key"], subject=row["subject"],
            summary=row["summary"], amount=row["amount"],
        )])
        finding = report.findings[0]
        findings.append(finding.as_dict())
        if finding.state == "不符合":
            redlines.append(finding.as_dict())
        # 内容指纹 = 本笔核查输入的指纹（对账 content_changed 标记用；键是稳定身份键）
        observed.append(ObservedItem(
            key=key, state=finding.state,
            content_sha256=sha256_text("%s|%s|%s|%s" % (
                row["subject"], row["summary"], row["amount"], industry_id)),
        ))

    return {
        "source": path.name,
        "counts": _count_states(findings),
        "findings": findings,
        "redlines": redlines,
        "observed": observed,
    }


def _count_states(findings: list) -> dict:
    counts: dict = {}
    for finding in findings:
        counts[finding["state"]] = counts.get(finding["state"], 0) + 1
    return counts


def run(args) -> int:
    directory = Path(args.directory)
    if not directory.is_dir():
        print("台账目录不存在：%s" % directory)
        return 2

    sources = sorted(str(path) for path in directory.glob("*.csv"))
    outcome = scan_sources(sources, lambda source: _check_one(source, args.data_dir))

    processed = list(outcome.processed)
    baseline = []
    if args.baseline:
        with Path(args.baseline).open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        baseline = [
            ObservedItem(item["key"], item["state"], item.get("content_sha256", ""))
            for item in payload.get("observed", [])
        ]
    current = [item for check_result in processed for item in check_result["observed"]]
    reconcile = compare_nonpass(baseline, current) if args.baseline else None

    result_payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "processed": [
            {key: value for key, value in check_result.items() if key != "observed"}
            for check_result in processed
        ],
        "failures": [failure.as_dict() for failure in outcome.failures],
        "observed": [item.as_dict() for item in current],
        "reconcile": reconcile.as_dict() if reconcile else None,
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "scan-result.json").write_bytes(
        (json.dumps(result_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )

    # 报告导出：scan 结果直接驱动报告（--report 可选）
    if getattr(args, "report", False):
        _export_scan_report(result_payload, out_dir)

    print("已处理 %d 件，失败 %d 件" % (len(processed), len(outcome.failures)))
    for failure in outcome.failures:
        print("  失败件 %s [%s] %s" % (failure.source, failure.reason_code, failure.detail))
    total_counts: dict = {}
    for check_result in processed:
        for state, count in check_result["counts"].items():
            total_counts[state] = total_counts.get(state, 0) + count
    for state in sorted(total_counts):
        print("  %s：%d" % (state, total_counts[state]))
    if reconcile:
        for name, count in sorted(reconcile.counts().items()):
            print("  %s：%d" % (name, count))

    # 失败件 ≠ 违规；核查结论（含不符合）不改退出码——处置交给报告与对账
    return EXIT_OK


def _export_scan_report(result_payload: dict, out_dir: Path) -> None:
    """scan 结果 → 报告（check + reconcile 章节；无计提结论故不触发溯源断言）。"""
    from safefee import __version__
    from safefee.report import ReportInput

    payload = ReportInput(
        ruleset_coordinate={
            "doc_no": "（批量扫描：见各台账年度对应规则包）",
            "ruleset_id": "scan",
            "generated_at": result_payload.get("generated_at", ""),
            "tool_version": __version__,
        },
        enterprise={"scan_source": "批量台账扫描"},
        check=_merge_check(result_payload),
        reconcile=result_payload.get("reconcile"),
        enabled=("check", "reconcile"),
    )
    export_report(payload, out_dir)


def _merge_check(result_payload: dict) -> dict:
    """把逐件核查结论合成单一 check 载荷（报告层消费 CheckReport.as_dict() 形态）。"""
    findings: list = []
    redlines: list = []
    for check_result in result_payload.get("processed", []):
        findings.extend(check_result.get("findings", []))
        redlines.extend(check_result.get("redlines", []))
    return {"counts": _count_states(findings), "findings": findings, "redlines": redlines}


__all__ = ["run"]
