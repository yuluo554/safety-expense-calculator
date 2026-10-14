"""年度 → 版本锚定与双版本差异对照。

**纪律**：指定年度即锚定该年度适用的规则版本——**杜绝"用新版标准重算旧台账"**。
办法"自印发之日起施行"，故**按日**锚定；档案只给年度时取该年度 1 月 1 日
（口径见 plan/04 §2.1）。
"""

from safefee.ruleset.anchor import resolve_for_year
from safefee.ruleset.diff import DiffItem, DiffReport, compare

__all__ = ["resolve_for_year", "DiffItem", "DiffReport", "compare"]
