"""演示夹具生成器 —— README 里出现的每个输入文件都由本生成器产出。

**为什么必须由生成器产出**：README 引用的输入夹具若"本地因工作目录残留恰好存在"，
本地逐字执行 README 会一路全绿，直到干净环境（``git archive`` 导出树）才报"文件不存在"
——这是发布门最隐蔽的一类缺口。**凡 README 写到的输入路径，都必须由生成器/版本控制保证存在。**

产出（``data/samples/``，**全部合成数据**）：

* ``archive-coal.json`` —— 煤炭档案（按产量计提）
* ``archive-hazardous.json`` —— 危险品档案（按营业收入超额累退）
* ``archive-construction.json`` —— 建设工程档案（按工程造价比例）
* ``ledger-demo.csv`` —— 支出明细台账（含允许项与红线项）

确定性纪律：固定内容、无时间戳，两次生成**逐字节一致**。

用法::

    python tools/gen_samples.py
    python tools/gen_samples.py --check
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "samples"

#: 合成企业白名单号段（虚构名称 + 测试号段，见 data/README.md §四）
ARCHIVES = [
    {
        "file": "archive-coal.json",
        "payload": {
            "enterprise_id": "90000000SYN0000001A",
            "enterprise_name": "示例煤炭（合成）有限公司",
            "industry_id": "coal",
            "variant_id": "coal_high_gas",
            "year": 2024,
            "basis_kind": "output",
            "basis_value": "120000",
            "basis_unit": "ton",
        },
    },
    {
        "file": "archive-hazardous.json",
        "payload": {
            "enterprise_id": "90000000SYN0000002B",
            "enterprise_name": "示例危险品（合成）有限公司",
            "industry_id": "hazardous_chemicals",
            "year": 2024,
            "basis_kind": "revenue",
            "basis_value": "50000000",
            "basis_unit": "CNY",
        },
    },
    {
        "file": "archive-construction.json",
        "payload": {
            "enterprise_id": "90000000SYN0000003C",
            "enterprise_name": "示例建设工程（合成）有限公司",
            "industry_id": "construction",
            "variant_id": "municipal_port_highway",
            "year": 2024,
            "basis_kind": "project_cost",
            "basis_value": "80000000",
            "basis_unit": "CNY",
        },
    },
]

LEDGER_HEADER = "item_key,subject,summary,amount"
LEDGER_ROWS = [
    ("EXP-001", "安全费用", "煤矿安全改造支出", "120000.00"),
    ("EXP-002", "安全费用", "重大隐患治理支出", "80000.00"),
    ("EXP-003", "管理费用", "挪用于办公经费", "30000.00"),
    ("EXP-004", "安全费用", "安全生产标准化建设", "50000.00"),
]


def generate() -> Dict[str, bytes]:
    """产出全部演示夹具，返回 ``{相对路径: 字节}``。"""
    files: Dict[str, bytes] = {}
    for item in ARCHIVES:
        text = json.dumps(item["payload"], ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        files[item["file"]] = text.encode("utf-8")
    lines = [LEDGER_HEADER] + ["%s,%s,%s,%s" % row for row in LEDGER_ROWS]
    files["ledger-demo.csv"] = ("\n".join(lines) + "\n").encode("utf-8")
    return files


def write_all(files: Dict[str, bytes]) -> None:
    for rel, payload in sorted(files.items()):
        path = OUT_DIR / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)


def check() -> int:
    files = generate()
    mismatched: List[str] = []
    for rel, payload in sorted(files.items()):
        path = OUT_DIR / rel
        if not path.is_file():
            mismatched.append("%s（缺失）" % rel)
            continue
        if path.read_bytes() != payload:
            mismatched.append(rel)
    if mismatched:
        print("FROZEN_SAMPLES_DRIFT: %s" % ", ".join(mismatched))
        return 1
    print("FROZEN_SAMPLES_OK（%d 份文件逐字节一致）" % len(files))
    return 0


def main(argv=None) -> int:
    from safefee._stdio import _ensure_utf8_stdio

    _ensure_utf8_stdio()
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--check" in argv:
        return check()
    files = generate()
    write_all(files)
    print("已生成 %d 份演示夹具 → %s" % (len(files), OUT_DIR))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    raise SystemExit(main())
