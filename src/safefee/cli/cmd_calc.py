"""``calc`` / ``check`` / ``progress`` 子命令。"""

import json
import sys
from decimal import Decimal
from pathlib import Path

from safefee.engine import pipeline
from safefee.errors import EXIT_GATE, EXIT_OK


def run(args) -> int:
    payload = pipeline.load_archive(Path(args.archive))
    case = pipeline.build_case(payload)
    report = pipeline.compute_calc(case, args.data_dir)

    if report.gate_blockers:
        for blocker in report.gate_blockers:
            print("未核对条目不得进入计算路径：%s [%s] %s"
                  % (blocker.path, blocker.status, blocker.clause), file=sys.stderr)
        return EXIT_GATE

    result = report.result
    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
        return EXIT_OK

    print("企业：%s（%s）" % (case.enterprise_name, case.enterprise_id))
    print("规则包：%s（%s）" % (report.coordinate["doc_no"], report.coordinate["ruleset_id"]))
    print("计提机制：%s" % result.mechanism)
    print("计算公式：%s" % result.formula)
    print("条款依据：%s" % result.clause)
    print("应计提金额：%s 元" % result.amount)
    for line in result.tiers:
        print("  段 %d：%s ~ %s × %s = %s（%s）"
              % (line.index, line.lower, line.upper or "∞", line.rate, line.amount, line.clause))
    for warning in report.warnings:
        print("提示：%s" % warning)
    return EXIT_OK


def run_check(args) -> int:
    payload = pipeline.load_archive(Path(args.archive))
    case = pipeline.build_case(payload)
    report = pipeline.check_ledger_file(case, Path(args.ledger), args.data_dir)

    if report.get("gate_blocked"):
        for blocker in report["blockers"]:
            print("未核对条目不得进入核查路径：%s [%s]" % (blocker["path"], blocker["status"]))
        return EXIT_GATE

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for key, count in sorted(report["counts"].items()):
            print("%s：%d" % (key, count))
        for finding in report["findings"]:
            print("  %s | %s | %s | %s | %s"
                  % (finding["item_key"], finding["state"], finding["amount"],
                     finding["clause"] or "—", finding["reason"]))
    return EXIT_GATE if report["redlines"] else EXIT_OK


def run_progress(args) -> int:
    payload = pipeline.load_archive(Path(args.archive))
    case = pipeline.build_case(payload)
    report = pipeline.compute_progress_for(
        case,
        accrued=Decimal(str(args.accrued)),
        used=Decimal(str(args.used)),
        data_dir=args.data_dir,
    )
    if report.get("gate_blocked"):
        for blocker in report["blockers"]:
            print("未核对条目不得进入进度判定：%s [%s]" % (blocker["path"], blocker["status"]))
        return EXIT_GATE

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return EXIT_OK

    if not report["applicable"]:
        print("年度应计提额为 0：进度门槛不适用")
        return EXIT_OK
    print("使用进度：%s（门槛 %s）" % (report["ratio"], report["threshold"]))
    print("是否触发披露义务：%s" % ("是" if report["disclosure_required"] else "否"))
    print("条款依据：%s" % report["clause"])
    for point in report["points"]:
        print("  - %s" % point)
    return EXIT_OK
