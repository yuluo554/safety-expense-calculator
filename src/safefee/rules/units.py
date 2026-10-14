"""定义性单位换算（``units.json``）。

**性质**：单位定义是**定义性事实**（1 万元 = 10000 元、1 亿元 = 10^8 元），
**不是政策数值**——因此可入 ``units.json`` 并豁免零政策字面量门禁（豁免口径见
tests/test_no_policy_literals.py）。政策数值一律只能来自规则包。

纪律：输入单位与规则包期望单位不一致时——
* 可**定义性精确换算** → 换算并记 ``warning``（**绝不静默通过**）；
* 不可判定 → 报错（退出码 2），**不静默猜测**。
"""

import json
from decimal import Decimal
from pathlib import Path
from typing import Dict, Optional, Tuple

from safefee.errors import SchemaError

_REQUIRED = ("CNY", "CNY10k", "CNY100m", "ton")


class UnitConverter:
    """货币/产量单位换算器；因子来自 ``units.json``。"""

    def __init__(self, factors: Dict[str, Decimal]) -> None:
        missing = [key for key in _REQUIRED if key not in factors]
        if missing:
            raise SchemaError("units.json 缺少必需单位：%s" % ", ".join(missing))
        self._factors = dict(factors)

    @property
    def factors(self) -> Dict[str, Decimal]:
        return dict(self._factors)

    def factor(self, unit: str) -> Decimal:
        try:
            return self._factors[unit]
        except KeyError:
            raise SchemaError("未知单位：%r（units.json 未登记）" % unit)

    def to_base(self, value: Decimal, unit: str) -> Tuple[Decimal, Optional[str]]:
        """换算到基准单位；返回 ``(值, warning 或 None)``。

        单位一致 → ``warning=None``；单位不一致但可定义性换算 → 返回 warning 文案。
        """
        factor = self.factor(unit)
        if factor == Decimal(1):
            return value, None
        converted = value * factor
        return converted, (
            "输入单位 %s 与规则包期望单位不一致，已按定义性换算（×%s）" % (unit, factor)
        )


def load_units(data_dir: Path) -> UnitConverter:
    """从 ``<data_dir>/rules/units.json`` 加载换算表。"""
    path = Path(data_dir) / "rules" / "units.json"
    if not path.is_file():
        raise SchemaError("缺少单位换算表：%s" % path)
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh, parse_float=Decimal)
    factors = payload.get("factors")
    if not isinstance(factors, dict):
        raise SchemaError("units.json 结构错误：缺少 factors 对象")
    return UnitConverter({k: Decimal(str(v)) for k, v in factors.items()})


__all__ = ["UnitConverter", "load_units"]
