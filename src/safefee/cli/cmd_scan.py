"""``scan`` 子命令：批量台账扫描 + 跨年对账。

**失败件 ≠ 违规**：失败件带原因码、单列，**不改退出码**。
"""

import csv
import json
from decimal import Decimal
from pathlib import Path

from safefee.batch import ObservedItem, ScanFailure, compare_nonpass, scan_sources
from safefee.errors import EXIT_GATE, EXIT_OK, ScanItemError
from safefee.tiered import quantize_money


def _load_ledger_items(path: Path) -> list:
    items = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        required = ("item_key", "subject", "summary", "amount")
        for index, row in enumerate(reader, start=2):
            missing = [key for key in required if not row.get(key)]
            if missing:
                raise ScanItemError("missing_field", "台账第 %d 行缺字段：%s"
                                    % (index, ", ".join(missing)))
            items.append({
                "item_key": str(row["item_key"]),
                "subject": str(row["subject"]),
                "summary": str(row["summary"]),
                "amount": quantize_money(Decimal(str(row["amount"]))),
            })
    return items


def _handler(source: str) -> ObservedItem:
    """单件处理：读台账 → 取状态（M0 骨架以"未评估"占位，M3 接入核查）。"""
    path = Path(source)
    items = _load_ledger_items(path)
    from safefee.evidence import sha256_file
    from safefee.spending import STATE_NOT_ASSESSED

    return ObservedItem(
        key="file:%s" % path.name,
        state=STATE_NOT_ASSESSED,
        content_sha256=sha256_file(path),
    )


def run(args) -> int:
    directory = Path(args.directory)
    if not directory.is_dir():
        print("台账目录不存在：%s" % directory)
        return 2

    sources = sorted(str(path) for path in directory.glob("*.csv"))
    outcome = scan_sources(sources, _handler)

    baseline = []
    if args.baseline:
        with Path(args.baseline).open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        baseline = [
            ObservedItem(item["key"], item["state"], item.get("content_sha256", ""))
            for item in payload.get("observed", [])
        ]

    reconcile = compare_nonpass(baseline, outcome.processed) if args.baseline else None

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "processed": [item.as_dict() for item in outcome.processed],
        "failures": [failure.as_dict() for failure in outcome.failures],
        "reconcile": reconcile.as_dict() if reconcile else None,
    }
    (out_dir / "scan-result.json").write_bytes(
        (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )

    print("已处理 %d 件，失败 %d 件" % (len(outcome.processed), len(outcome.failures)))
    for failure in outcome.failures:
        print("  失败件 %s [%s] %s" % (failure.source, failure.reason_code, failure.detail))
    if reconcile:
        for name, count in sorted(reconcile.counts().items()):
            print("  %s：%d" % (name, count))

    # 失败件 ≠ 违规：不因失败件改退出码
    return EXIT_OK


__all__ = ["run"]
