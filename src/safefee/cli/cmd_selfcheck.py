"""``selfcheck`` / ``units`` / ``rulesets`` 子命令。"""

import json
from datetime import date
from pathlib import Path

from safefee.data_paths import find_data_dir
from safefee.engine import pipeline
from safefee.errors import EXIT_OK
from safefee.rules import load_manifest, load_units


def _review_anchor_lines(root) -> list:
    """规则包**复核锚**（``manifest.review_interval`` / ``next_review``）的提示行。

    费率/条款会换版，而"何时该复核"原先只写在 README 的一段非机读文字里；
    现由生成器写进 manifest（机读），此处把它显示出来并在**逾期时提示**。

    **只提示，不改退出码语义**（0/1/2/3 契约不动，见 plan/06 口径清单）：逾期不阻断计算，
    只是告诉你该重新核对官方原文并重生成规则包了。清单读不出来就静默跳过——本函数是
    附加信息，不得让 ``selfcheck`` 因它变红。
    """
    try:
        payload = json.loads((Path(root) / "rules" / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    next_review = payload.get("next_review")
    if not next_review:
        return []
    lines = ["规则包复核锚：复核周期 %s；下次复核 %s"
             % (payload.get("review_interval") or "未登记", next_review)]
    try:
        due = date.fromisoformat(str(next_review))
    except ValueError:
        return lines
    overdue = (date.today() - due).days
    if overdue > 0:
        lines.append(
            "  ! 已逾期 %d 天：费率/条款可能已换版，须重新核对官方原文并重生成规则包"
            % overdue
        )
    return lines


def run(args) -> int:
    root = find_data_dir(args.data_dir)
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
    for line in _review_anchor_lines(root):
        print(line)
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
