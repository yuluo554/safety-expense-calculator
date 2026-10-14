"""``bench`` 子命令：内置评测基准。

退出码三语义：0 达标 / 1 未达标 / 2 输入、坐标或用例名错误。
``--only`` 未知名 → 退出码 2（**别静默跳过**）。
"""

import json

from safefee.bench import SUITES, run_all
from safefee.data_paths import find_data_dir
from safefee.errors import EXIT_GATE, EXIT_OK
from safefee.rules import load_manifest


def run(args) -> int:
    root = find_data_dir(args.data_dir)
    manifest = load_manifest(root)
    results = run_all(manifest, only=args.only)

    if args.json:
        print(json.dumps({"results": [r.as_dict() for r in results]}, ensure_ascii=False, indent=2))
    else:
        for result in results:
            if not result.assessable:
                print("套件 %s：**未评估**（用例数为 0，不声称达标也不判未达标）" % result.suite)
            else:
                print("套件 %s：%d/%d 通过，达标=%s"
                      % (result.suite, result.passed, result.total, result.met))
            print("  %s" % result.notes)
            for failure in result.failed[:5]:
                print("  失败：%s" % failure)

    # 退出码判据：可评估的套件必须达标；**未评估的套件不阻断**（"没测" ≠ "未达标"）
    blocking = [r for r in results if r.assessable and not r.met]
    return EXIT_OK if not blocking else EXIT_GATE


__all__ = ["run", "SUITES"]
