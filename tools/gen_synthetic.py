"""合成企业台账 + 真值库生成器（确定性 RNG，固定 seed）。

**确定性纪律**：禁 stdlib ``random``、禁 ``set`` 迭代序、禁系统时钟——自研
``splitmix64``（stdlib ``random`` 不承诺跨版本序列一致）。落盘产物**无时间戳**，
两次运行/构建**逐字节一致**并配守门测试。

**M0 范围**：产出真值库的**结构骨架**（空目录 + README 说明），真值记录在 M1
逐条核对规则后由本生成器产出——**未核对不得落值**，故 M0 不产出带数值的期望值
（否则就是"凭空造进规则库"）。

用法::

    python tools/gen_synthetic.py
    python tools/gen_synthetic.py --check
"""

import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "truth"

MASK64 = (1 << 64) - 1


def splitmix64(state: int) -> "tuple[int, int]":
    """确定性 RNG（自研）：返回 ``(next_state, value)``。"""
    state = (state + 0x9E3779B97F4A7C15) & MASK64
    z = state
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    return state, z ^ (z >> 31)


README_TEXT = """# data/truth 合成企业台账与真值库

> **性质**：本目录全部为**合成数据**（虚构企业 + 测试号段 `90000000…SYN`），
> 不含任何真实企业名称、产能、营业收入或台账数据。
> **生成器**：`tools/gen_synthetic.py`（唯一写入者，禁手改）；`--check` 守门"再生成逐字节一致"。

## 目录约定

```
data/truth/
├─ README.md          # 本文件
├─ cases/             # 真值记录（M1 建）：每条含 enterprise + expect（金额/机制/also_expect）
└─ negatives/         # 误报对照集（M1 建）：显式声明"应零命中"与"应降级"的档案
```

## 真值语义（定稿一次，动了会打挂基准）

* `expect.amount` —— 主期望（应计提金额，两位小数）；
* `expect.also_expect` —— 同一注入隐含的其余结论（按"全部非 pass 字段集"对账）；
* `note` —— 该算例的注入说明。

## M0 状态

真值记录**尚未生成**：计提标准在 M1 逐条挂原文核对后才落值，
**未核对不得落值**（否则即"凭空造进规则库"）。
因此基准的 `synthetic_ledger` 套件当前如实记"该类用例未生成"，**不假装覆盖**。

## 算例覆盖计划（M1）

| 类别 | 算例 |
|---|---|
| 三类机制 | 煤炭（按产量）/ 危险品·冶金·机械制造·电力（按营业收入超额累退）/ 建设工程（按工程造价比例） |
| 边界 | 恰好等于分段点；上下最小货币单位（±0.01） |
| 单位口径错配 | 台账以"万元"填报、规则包以"元"计价 → 应报 warning（不静默） |
| 误报对照 | "应零命中"的干净档案；"应降级"的档案（单位可显式换算 → 只报 warning） |
| 双版本对照 | 同一对象分别按 136 号与 2012 版生成两套期望值 |
"""


def generate() -> Dict[str, bytes]:
    return {"README.md": README_TEXT.encode("utf-8")}


def write_all(files: Dict[str, bytes]) -> None:
    for rel, payload in sorted(files.items()):
        path = OUT_DIR / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    for sub in ("cases", "negatives"):
        (OUT_DIR / sub).mkdir(parents=True, exist_ok=True)
        keep = OUT_DIR / sub / ".gitkeep"
        if not keep.exists():
            keep.write_bytes(b"")


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
        print("FROZEN_TRUTH_DRIFT: %s" % ", ".join(mismatched))
        return 1
    print("FROZEN_TRUTH_OK（%d 份文件逐字节一致）" % len(files))
    return 0


def main(argv=None) -> int:
    from safefee._stdio import _ensure_utf8_stdio

    _ensure_utf8_stdio()
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--check" in argv:
        return check()
    files = generate()
    write_all(files)
    print("已生成真值库骨架 → %s" % OUT_DIR)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    raise SystemExit(main())
