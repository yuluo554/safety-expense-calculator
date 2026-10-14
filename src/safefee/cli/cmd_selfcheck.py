"""``selfcheck`` / ``units`` / ``rulesets`` 子命令。"""

import json

from safefee.data_paths import find_data_dir
from safefee.engine import pipeline
from safefee.errors import EXIT_OK
from safefee.rules import load_manifest, load_units


def run(args) -> int:
    payload = pipeline.selfcheck(args.data_dir)
    print("数据目录：%s" % payload["data_dir"])
    print("单位表：%s" % ", ".join(payload["units"]))
    for item in payload["rulesets"]:
        ref = item["ref"]
        print("规则集 %s（%s）生效自 %s 状态 %s"
              % (ref["ruleset_id"], ref["doc_no"], ref["effective_from"], ref["status"]))
        for scope, info in sorted(item["scopes"].items()):
            if info.get("ok"):
                print("  - 作用域 %s：门控通过" % scope)
            elif "error" in info:
                print("  - 作用域 %s：规则缺失（%s）" % (scope, info["error"]))
            else:
                print("  - 作用域 %s：门控拦截，%d 条未核对" % (scope, info["blockers"]))
    return EXIT_OK


def run_units(args) -> int:
    root = find_data_dir(args.data_dir)
    units = load_units(root)
    for name in sorted(units.factors):
        print("%s = %s" % (name, units.factors[name]))
    return EXIT_OK


def run_rulesets(args) -> int:
    root = find_data_dir(args.data_dir)
    manifest = load_manifest(root)
    refs = [ref.as_dict() for ref in manifest.refs]
    if args.json:
        print(json.dumps({"rulesets": refs}, ensure_ascii=False, indent=2))
    else:
        for ref in refs:
            print("%s | %s | 生效自 %s | 至 %s | 状态 %s"
                  % (ref["ruleset_id"], ref["doc_no"], ref["effective_from"],
                     ref["effective_to"] or "—", ref["status"]))
    return EXIT_OK
