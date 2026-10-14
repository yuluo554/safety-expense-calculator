"""跨年对账（两轮比较）。

**四集合**：新增异常 / 已修复 / 持续异常 / 稳定。

三条硬纪律（动了会打挂基准）：

* **配对主键 = 稳定身份键**（``enterprise_id + year + item_key``），**不是内容指纹**
  ——用内容指纹配对时"已修复"必然内容变了 → 永远配不上 → **"已修复"永远检不出**；
  指纹变化**另立 ``content_changed`` 标记**，别让它退化成"新增 + 移除"；
* **对账口径单一实现源**（本模块的 :func:`observed_nonpass` / :func:`compare_nonpass`），
  真值测试与基准共用；
* **非 pass = 不符合 ∪ 未评估**；``不适用`` / 稳定 pass 排除在比较之外
  （``不适用`` 是"没看到"不是"缺失"，纳入比较会制造假"已修复"）。
"""

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

SET_NEW = "新增异常"
SET_FIXED = "已修复"
SET_PERSISTENT = "持续异常"
SET_STABLE = "稳定"

SETS = (SET_NEW, SET_FIXED, SET_PERSISTENT, SET_STABLE)


@dataclass(frozen=True)
class ObservedItem:
    """一件可对账的观测记录。"""

    key: str            # 稳定身份键
    state: str          # 四态 / 未评估
    content_sha256: str = ""

    def as_dict(self) -> dict:
        return {"key": self.key, "state": self.state, "content_sha256": self.content_sha256}


def observed_nonpass(items: Iterable[ObservedItem]) -> Dict[str, ObservedItem]:
    """取"非 pass"集合（不符合 ∪ 未评估）——**对账语义唯一实现源**。

    ``不适用`` 与 pass 态排除在外。
    """
    from safefee.spending import NON_PASS_STATES

    return {item.key: item for item in items if item.state in NON_PASS_STATES}


@dataclass(frozen=True)
class ReconcileReport:
    """两轮对账结论。"""

    new: Tuple[ObservedItem, ...]
    fixed: Tuple[ObservedItem, ...]
    persistent: Tuple[ObservedItem, ...]
    stable: Tuple[ObservedItem, ...]
    content_changed: Tuple[str, ...]      # 内容变化但状态未变的键

    def counts(self) -> Dict[str, int]:
        return {
            SET_NEW: len(self.new),
            SET_FIXED: len(self.fixed),
            SET_PERSISTENT: len(self.persistent),
            SET_STABLE: len(self.stable),
        }

    def as_dict(self) -> dict:
        return {
            "counts": self.counts(),
            "new": [i.as_dict() for i in self.new],
            "fixed": [i.as_dict() for i in self.fixed],
            "persistent": [i.as_dict() for i in self.persistent],
            "stable": [i.as_dict() for i in self.stable],
            "content_changed": list(self.content_changed),
        }


def compare_nonpass(
    baseline: Sequence[ObservedItem],
    current: Sequence[ObservedItem],
) -> ReconcileReport:
    """四集合划分——**唯一实现源**（基准与真值测试共用）。

    对账口径：**非 pass = 不符合 ∪ 未评估**；``不适用`` 与 pass 排除在比较之外。
    """
    from safefee.spending import NON_PASS_STATES

    base_index = {item.key: item for item in baseline}
    curr_index = {item.key: item for item in current}

    new: List[ObservedItem] = []
    fixed: List[ObservedItem] = []
    persistent: List[ObservedItem] = []
    stable: List[ObservedItem] = []
    changed: List[str] = []

    for key in sorted(set(base_index) | set(curr_index)):
        base_item = base_index.get(key)
        curr_item = curr_index.get(key)

        base_bad = base_item is not None and base_item.state in NON_PASS_STATES
        curr_bad = curr_item is not None and curr_item.state in NON_PASS_STATES

        if base_item is not None and curr_item is not None:
            if base_item.content_sha256 != curr_item.content_sha256:
                changed.append(key)

        if curr_bad and not base_bad:
            new.append(curr_item)
        elif base_bad and not curr_bad:
            fixed.append(base_item)
        elif base_bad and curr_bad:
            persistent.append(curr_item)
        else:
            stable.append(curr_item if curr_item is not None else base_item)

    return ReconcileReport(
        new=tuple(new), fixed=tuple(fixed), persistent=tuple(persistent),
        stable=tuple(stable), content_changed=tuple(changed),
    )


__all__ = [
    "SET_NEW",
    "SET_FIXED",
    "SET_PERSISTENT",
    "SET_STABLE",
    "SETS",
    "ObservedItem",
    "ReconcileReport",
    "observed_nonpass",
    "compare_nonpass",
]
