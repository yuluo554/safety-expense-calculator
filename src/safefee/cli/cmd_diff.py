"""``diff`` 子命令：双版本差异对照。"""

import json

from safefee.data_paths import find_data_dir
from safefee.errors import EXIT_OK
from safefee.rules import load_manifest, load_ruleset
from safefee.ruleset import compare


def run(args) -> int:
    root = find_data_dir(args.data_dir)
    manifest = load_manifest(root)
    old_ref = manifest.resolve_year(int(args.from_year))
    new_ref = manifest.resolve_year(int(args.to_year))
    if old_ref.ruleset_id == new_ref.ruleset_id:
        print("两年度锚定到同一规则集（%s）：无数值差异可对照" % old_ref.ruleset_id)
        return EXIT_OK

    old_ruleset = load_ruleset(root, old_ref.directory)
    new_ruleset = load_ruleset(root, new_ref.directory)
    report = compare(old_ruleset, new_ruleset)

    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
        return EXIT_OK

    print("对照：%s → %s" % (report.old_doc_no, report.new_doc_no))
    print("已比对行业（%d）：%s" % (len(report.compared_industries),
                                    "、".join(report.compared_industries)))
    for kind, count in sorted(report.counts().items()):
        print("  %s：%d" % (kind, count))
    for item in report.items:
        print("  %s/%s %s：%s → %s（%s → %s）"
              % (item.industry_id, item.variant_id or "—", item.kind,
                 item.old_value or "—", item.new_value or "—",
                 item.old_clause or "—", item.new_clause or "—"))
    return EXIT_OK


__all__ = ["run"]
