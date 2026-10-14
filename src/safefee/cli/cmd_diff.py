"""``diff`` 子命令：双版本差异对照。

对照编排收口在 ``pipeline.compute_diff``（GUI 同源）；stdout 文本用
``pipeline.format_diff``（CLI 与 GUI 同一实现源）。
"""

import json

from safefee.engine import pipeline
from safefee.errors import EXIT_OK


def run(args) -> int:
    report = pipeline.compute_diff(args.from_year, args.to_year, args.data_dir)
    if report is None:
        from safefee.data_paths import find_data_dir
        from safefee.rules import load_manifest

        ref = load_manifest(find_data_dir(args.data_dir)).resolve_year(int(args.from_year))
        print("两年度锚定到同一规则集（%s）：无数值差异可对照" % ref.ruleset_id)
        return EXIT_OK

    # 报告导出：单一渲染源（MD/XLSX/evidence 三件），不影响 stdout 摘要
    if getattr(args, "out", None):
        from safefee.ruleset.diff_report import export_diff_report

        written = export_diff_report(report, args.out)
        print("差异对照报告已导出：%s" % ", ".join(path.name for path in written))

    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
        return EXIT_OK

    print(pipeline.format_diff(report))
    return EXIT_OK


__all__ = ["run"]
