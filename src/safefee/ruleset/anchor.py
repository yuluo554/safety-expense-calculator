"""年度 → 规则版本锚定。"""

from safefee.rules.manifest import Manifest, RulesetRef


def resolve_for_year(manifest: Manifest, year: int) -> RulesetRef:
    """按年度锚定规则集（内部按该年度 1 月 1 日判定）。

    无匹配 → :class:`~safefee.errors.NoRulesetForYear`（退出码 2）；
    多匹配 → :class:`~safefee.errors.AmbiguousRuleset`（配置错误）。
    """
    return manifest.resolve_year(int(year))


__all__ = ["resolve_for_year"]
