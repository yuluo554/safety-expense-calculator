"""双版本差异对照。

按 ``(industry_id, variant_id)`` 配对，输出四类差异：
``value_changed`` / ``rate_changed`` / ``added`` / ``removed``。
每条差异挂两版条款号与 provenance。
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class DiffItem:
    """一条版本差异。"""

    industry_id: str
    variant_id: Optional[str]
    kind: str                       # value_changed | rate_changed | added | removed
    old_value: Optional[str]
    new_value: Optional[str]
    old_clause: str
    new_clause: str
    old_doc_no: str
    new_doc_no: str

    def as_dict(self) -> dict:
        return {
            "industry_id": self.industry_id,
            "variant_id": self.variant_id,
            "kind": self.kind,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "old_clause": self.old_clause,
            "new_clause": self.new_clause,
            "old_doc_no": self.old_doc_no,
            "new_doc_no": self.new_doc_no,
        }


@dataclass(frozen=True)
class DiffReport:
    """两版对照报告。"""

    old_doc_no: str
    new_doc_no: str
    items: Tuple[DiffItem, ...]
    compared_industries: Tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "old_doc_no": self.old_doc_no,
            "new_doc_no": self.new_doc_no,
            "counts": self.counts(),
            "compared_industries": list(self.compared_industries),
            "items": [item.as_dict() for item in self.items],
        }

    def counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for item in self.items:
            out[item.kind] = out.get(item.kind, 0) + 1
        return out


def _index(ruleset: dict) -> Dict[Tuple[str, Optional[str]], dict]:
    """把规则集的行业/变体摊平成 ``(industry_id, variant_id) -> node``。

    变体可**覆写机制**（如地质勘探按费用比例）——保留之，供 ``_metric`` 判别。
    """
    index: Dict[Tuple[str, Optional[str]], dict] = {}
    for industry in ruleset.get("industries", []):
        industry_id = str(industry.get("industry_id"))
        variants = industry.get("variants") or []
        if not variants:
            index[(industry_id, None)] = dict(industry, _industry_id=industry_id)
        for variant in variants:
            node = dict(variant, _industry_id=industry_id)
            node.setdefault("mechanism", industry.get("mechanism"))
            index[(industry_id, str(variant.get("variant_id")))] = node
    return index


def _metric(node: dict) -> Tuple[Optional[str], Optional[str]]:
    """取节点的可比数值：``(value, rate)``（字符串形态，None = 未落值）。

    超额累退节点的"数值"是**分段费率序列**（如危险品的四段费率），以 ``|``
    连接成单串——否则两版费率差异会被静默漏掉（见 M2 diff 覆盖门）。
    """
    value = node.get("value")
    rate = node.get("rate")
    segments = node.get("segments")
    if segments and value is None and rate is None:
        rate = "|".join(str(seg.get("rate")) for seg in segments)
    return (
        None if value is None else str(value),
        None if rate is None else str(rate),
    )


def compare(old_ruleset: dict, new_ruleset: dict) -> DiffReport:
    """对照两版规则集的数值差异与条款增删。"""
    old_index = _index(old_ruleset)
    new_index = _index(new_ruleset)

    old_doc = str(old_ruleset.get("doc_no", ""))
    new_doc = str(new_ruleset.get("doc_no", ""))

    items: List[DiffItem] = []
    for key in sorted(set(old_index) | set(new_index), key=lambda k: (k[0], k[1] or "")):
        industry_id, variant_id = key
        old_node = old_index.get(key)
        new_node = new_index.get(key)

        if old_node is None:
            new_value, new_rate = _metric(new_node)
            items.append(
                DiffItem(industry_id, variant_id, "added", None, new_value or new_rate,
                         "", str(new_node.get("clause", "")), old_doc, new_doc)
            )
            continue
        if new_node is None:
            old_value, old_rate = _metric(old_node)
            items.append(
                DiffItem(industry_id, variant_id, "removed", old_value or old_rate, None,
                         str(old_node.get("clause", "")), "", old_doc, new_doc)
            )
            continue

        old_value, old_rate = _metric(old_node)
        new_value, new_rate = _metric(new_node)
        if old_value != new_value:
            items.append(
                DiffItem(industry_id, variant_id, "value_changed", old_value, new_value,
                         str(old_node.get("clause", "")), str(new_node.get("clause", "")),
                         old_doc, new_doc)
            )
        if old_rate != new_rate:
            items.append(
                DiffItem(industry_id, variant_id, "rate_changed", old_rate, new_rate,
                         str(old_node.get("clause", "")), str(new_node.get("clause", "")),
                         old_doc, new_doc)
            )
    # **配对覆盖留痕**：两版都登记的行业（即便数值一致也记录"已比对"）——
    # 否则"无差异"与"未比对"无法区分（见 M2 diff 九类配对覆盖门）。
    compared = tuple(sorted({ind for ind, _ in old_index} & {ind for ind, _ in new_index}))
    return DiffReport(old_doc_no=old_doc, new_doc_no=new_doc, items=tuple(items),
                      compared_industries=compared)


__all__ = ["DiffItem", "DiffReport", "compare"]
