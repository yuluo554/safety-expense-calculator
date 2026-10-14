"""status 门控（按**计算路径**分作用域）。

**纪律**：规则条目 ``status != "verified"`` **绝不进入计算路径**。

门控**按计算路径分作用域**——一份规则包承载多种用途的参数时，"整包全 verified
才放行"会让与某条路径无关的 pending 阻断整条路径：

============  ======================================  ==========================
作用域        校验的条目                               典型命令
============  ======================================  ==========================
``calc``      计提标准（mechanism / variant / 段）      ``safefee calc``
``check``     支出范围条目（spending.json）             ``safefee check``
``progress``  使用进度门槛（progress.json）             ``safefee progress``
============  ======================================  ==========================

**第三态 ``input_required``** 表示"**本不由规则包承载**、须运行时索取的外部输入"
（企业档案里的产量/营业收入、随工况而异的修正系数）——**不阻断门控**，但运行时
**必索**，缺失即退出码 2，**绝不静默取 0/1**。

判别口诀：**"未核对"（pending，拦门）与"本不由规则包承载"（input_required，
放行但必索）是两回事。**
"""

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from safefee.errors import ConfigError, GateBlocked

SCOPES = ("calc", "check", "progress")

#: 非阻断状态：``verified`` 可计算；``input_required`` 放行但运行时必索。
NON_BLOCKING = frozenset({"verified", "input_required"})


@dataclass(frozen=True)
class GateBlocker:
    """一条阻断门控的条目（供留痕）。"""

    path: str    # 条目定位，如 "industries[0].variants[1]"
    clause: str  # 条款号
    status: str  # 非 verified 的状态（通常 "pending"）
    reason: str


@dataclass(frozen=True)
class GateResult:
    """门控结论：``ok=False`` 时逐条列出 blocker。"""

    scope: str
    ok: bool
    blockers: Tuple[GateBlocker, ...]

    def describe(self) -> str:
        if self.ok:
            return "门控通过（作用域 %s）" % self.scope
        lines = ["门控拦截（作用域 %s）：%d 条未核对条目不得进入计算路径" % (self.scope, len(self.blockers))]
        for blocker in self.blockers:
            lines.append(
                "  - %s [%s] %s：%s" % (blocker.path, blocker.status, blocker.clause, blocker.reason)
            )
        return "\n".join(lines)


def _iter_statused(node, path: str) -> Iterable[Tuple[str, str, str, str]]:
    """递归收集带 ``status`` 的条目 → ``(path, clause, status, reason)``。"""
    if isinstance(node, dict):
        if "status" in node:
            yield (
                path,
                str(node.get("clause", "")),
                str(node["status"]),
                str(node.get("reason", "未挂原文核对")),
            )
            return
        for key, value in node.items():
            yield from _iter_statused(value, "%s.%s" % (path, key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _iter_statused(value, "%s[%d]" % (path, index))


def collect_blockers(payload, scope: str, root: str) -> Tuple[GateBlocker, ...]:
    """收集某作用域引用的条目里所有非 ``verified`` 项。"""
    blockers = []
    for path, clause, status, reason in _iter_statused(payload, root):
        if status in NON_BLOCKING:
            continue
        blockers.append(
            GateBlocker(path=path, clause=clause, status=status, reason=reason)
        )
    return tuple(blockers)


def _calc_blockers(ruleset: dict, industry_id: Optional[str] = None) -> Tuple[GateBlocker, ...]:
    """``calc`` 作用域的 blocker：只校验**首期可用**的计提条目。

    首期未覆盖（``implementation == "deferred"``）的行业**本就不参与计算路径**
    （被 :class:`~safefee.errors.NotCovered` 拒绝），其 pending 状态不应阻断
    **可用**行业的口径——否则"与核算无关的 pending 阻断核算路径"（见 plan/03 §3.5）。

    ``industry_id`` 给定时**只校验该行业**：这是"门控按计算路径分作用域"的最细粒度
    ——算 coal 时不被 machinery 的 pending 拖累（判别口诀：**"这条 pending 在
    *本次*计算路径上吗？"**）。
    """
    blockers = []
    if "mechanisms" in ruleset:
        blockers.extend(collect_blockers(ruleset["mechanisms"], "calc", "mechanisms"))
    for index, industry in enumerate(ruleset.get("industries", [])):
        if industry.get("implementation") == "deferred":
            continue
        if industry_id is not None and industry.get("industry_id") != industry_id:
            continue
        blockers.extend(
            collect_blockers(industry, "calc", "industries[%d]" % index)
        )
    return tuple(blockers)


def check_scope(
    ruleset: dict,
    scope: str,
    *,
    spending: dict = None,
    progress: dict = None,
    industry_id: Optional[str] = None,
) -> GateResult:
    """按作用域校验；返回 :class:`GateResult`（**不抛异常**，由调用方决定退出码）。

    ``ruleset`` 为计提规则集；``spending`` / ``progress`` 在对应作用域下必传；
    ``industry_id`` 用于把 ``calc`` 门控收窄到**本次计算路径**上的行业。
    """
    if scope not in SCOPES:
        raise ConfigError("未知门控作用域：%r（支持 %s）" % (scope, ", ".join(SCOPES)))

    blockers = ()
    if scope == "calc":
        blockers = _calc_blockers(ruleset, industry_id)
    elif scope == "check":
        if spending is None:
            raise ConfigError("作用域 check 需提供 spending 规则")
        blockers = collect_blockers(spending.get("entries", []), scope, "entries")
    elif scope == "progress":
        if progress is None:
            raise ConfigError("作用域 progress 需提供 progress 规则")
        blockers = collect_blockers(progress.get("thresholds", []), scope, "thresholds")

    return GateResult(scope=scope, ok=not blockers, blockers=tuple(blockers))


def require_scope(result: GateResult) -> None:
    """门控不通过即抛 :class:`GateBlocked`（退出码 1）。"""
    if not result.ok:
        raise GateBlocked(result.describe())


__all__ = [
    "SCOPES",
    "NON_BLOCKING",
    "GateBlocker",
    "GateResult",
    "check_scope",
    "collect_blockers",
    "require_scope",
]