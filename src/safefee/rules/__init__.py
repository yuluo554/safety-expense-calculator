"""规则包加载与 status 门控（「依据文件 × 版本」组织）。

模块职责：
* :mod:`safefee.rules.units` —— 定义性单位换算（非政策数值）；
* :mod:`safefee.rules.manifest` —— manifest 加载、指纹校验、年度→版本锚定、基准门槛；
* :mod:`safefee.rules.loader` —— 规则集文件加载；
* :mod:`safefee.rules.gate` —— 按计算路径分作用域的 status 门控。

纪律：规则包是**生成器冻结产物，禁手改**；manifest 登记 sha256，加载时逐份校验。
"""

from safefee.rules.gate import GateBlocker, GateResult, check_scope
from safefee.rules.loader import load_progress, load_ruleset, load_spending
from safefee.rules.manifest import Manifest, RulesetRef, load_manifest
from safefee.rules.units import UnitConverter, load_units

__all__ = [
    "GateBlocker",
    "GateResult",
    "check_scope",
    "load_progress",
    "load_ruleset",
    "load_spending",
    "Manifest",
    "RulesetRef",
    "load_manifest",
    "UnitConverter",
    "load_units",
]
