"""``calc`` / ``check`` / ``progress`` 子命令。

展示文本（``format_*``）与 GUI **同一实现源**（``engine.pipeline``）——
CLI 只做"调编排 → 打文本 → 按退出码表返回"，不自带格式化。
"""

import sys
from decimal import Decimal
from pathlib import Path

from safefee.engine import pipeline
from safefee.errors import EXIT_GATE, EXIT_OK, EXIT_USAGE


def run(args) -> int:
    payload = pipeline.load_archive(Path(args.archive))
    case = pipeline.build_case(payload)
    report = pipeline.compute_calc(case, args.data_dir,
                                   fixed_time=getattr(args, "fixed_time", None))

    if report.gate_blockers:
        for blocker in report.gate_blockers:
            print("未核对条目不得进入计算路径：%s [%s] %s"
                  % (blocker.path, blocker.status, blocker.clause), file=sys.stderr)
        return EXIT_GATE

    if report.inputs_required:
        # **必索**：档案属性缺失（如矿井 mine_type）→ 退出码 2，绝不静默取 0/1
        print("档案缺少依据选择所需属性，无法判定：%s（条款 %s）"
              % (", ".join(report.inputs_required),
                 (report.basis or {}).get("clause", "")), file=sys.stderr)
        return EXIT_USAGE

    if getattr(args, "out", None):
        from safefee.engine import build_report_input, export_report

        written = export_report(
            build_report_input(case, report, data_dir=args.data_dir), Path(args.out)
        )
        print("报告已导出：%s" % ", ".join(path.name for path in written))

    print(pipeline.format_calc(report))
    return EXIT_OK


def run_check(args) -> int:
    payload = pipeline.load_archive(Path(args.archive))
    case = pipeline.build_case(payload)
    report = pipeline.check_ledger_file(
        case, Path(args.ledger), args.data_dir,
        fixed_time=getattr(args, "fixed_time", None),
    )

    if report.get("gate_blocked"):
        for blocker in report["blockers"]:
            print("未核对条目不得进入核查路径：%s [%s]" % (blocker["path"], blocker["status"]))
        return EXIT_GATE

    if args.json:
        import json

        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(pipeline.format_check(report))
    return EXIT_GATE if report["redlines"] else EXIT_OK


def run_progress(args) -> int:
    payload = pipeline.load_archive(Path(args.archive))
    case = pipeline.build_case(payload)
    report = pipeline.compute_progress_for(
        case,
        accrued=Decimal(str(args.accrued)),
        used=Decimal(str(args.used)),
        data_dir=args.data_dir,
        fixed_time=getattr(args, "fixed_time", None),
    )
    if report.get("gate_blocked"):
        for blocker in report["blockers"]:
            print("未核对条目不得进入进度判定：%s [%s]" % (blocker["path"], blocker["status"]))
        return EXIT_GATE

    if args.json:
        import json

        print(json.dumps(report, ensure_ascii=False, indent=2))
        return EXIT_OK

    print(pipeline.format_progress(report))
    return EXIT_OK
