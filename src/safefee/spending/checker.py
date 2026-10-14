"""支出范围合规核查（四态判定）。

**四态语义（不虚高，动了会打挂基准）**：

==========  ==========================================================
判定         何时给
==========  ==========================================================
``符合``     命中允许条目且无禁止命中
``部分符合``  同时命中允许与禁止，或命中允许但摘要含限制条件
``不符合``    命中禁止条目，或**无条件义务缺失**（红线项）
``不适用``    **原文明确写了例外情形**且该情形成立
==========  ==========================================================

**两条硬纪律**：

* ``不适用`` **只保留给"原文明确写了例外情形"的项**——绝不用于"缺材料/用户没做"
  （否则把"没做"记成"不用做"，合规结论虚高）；
* **无适用条目时** → 输出 ``未评估``（``not_assessed``），**绝不输出 ``符合``**
  ——"没查出问题"与"没检查过"必须可区分。

首期四行业起家，M3 扩至 2022 版十二节（2012 版九类，无电力/石油天然气/民爆）；
其余行业被请求 → 退出码 2。
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Sequence, Tuple

from safefee.errors import NotCovered

#: 四态 + 未评估
STATE_COMPLIANT = "符合"
STATE_PARTIAL = "部分符合"
STATE_NONCOMPLIANT = "不符合"
STATE_NOT_APPLICABLE = "不适用"
STATE_NOT_ASSESSED = "未评估"

#: 核查覆盖行业（2022 版十二节）
IN_SCOPE_INDUSTRIES = (
    "coal", "noncoal_mine", "oil_gas", "construction", "hazardous_chemicals",
    "transport", "metallurgy", "machinery", "fireworks", "civil_explosives",
    "weapons", "power",
)

#: 非 pass = 不符合 ∪ 未评估（部分符合计入"需关注"）
NON_PASS_STATES = frozenset({STATE_NONCOMPLIANT, STATE_NOT_ASSESSED})


@dataclass(frozen=True)
class LedgerItem:
    """一笔支出明细。"""

    item_key: str          # 稳定身份键（对账配对用）
    subject: str           # 科目
    summary: str           # 摘要
    amount: Decimal


@dataclass(frozen=True)
class CheckFinding:
    """一笔支出的核查结论。"""

    item_key: str
    subject: str
    summary: str
    amount: Decimal
    state: str
    clause: str
    entry_id: str
    reason: str

    def as_dict(self) -> dict:
        return {
            "item_key": self.item_key,
            "subject": self.subject,
            "summary": self.summary,
            "amount": str(self.amount),
            "state": self.state,
            "clause": self.clause,
            "entry_id": self.entry_id,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class CheckReport:
    """支出核查报告。"""

    industry_id: str
    findings: Tuple[CheckFinding, ...]
    redlines: Tuple[CheckFinding, ...]   # 红线项单列

    def counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for finding in self.findings:
            out[finding.state] = out.get(finding.state, 0) + 1
        return out

    def has_noncompliant(self) -> bool:
        return any(f.state == STATE_NONCOMPLIANT for f in self.findings)

    def as_dict(self) -> dict:
        return {
            "industry_id": self.industry_id,
            "counts": self.counts(),
            "findings": [f.as_dict() for f in self.findings],
            "redlines": [f.as_dict() for f in self.redlines],
        }


def _match(entry: dict, item: LedgerItem) -> bool:
    keywords = entry.get("match_keywords") or []
    if not keywords:
        return False
    haystack = "%s %s" % (item.subject, item.summary)
    return any(str(keyword) in haystack for keyword in keywords)


def check_ledger(
    spending: dict,
    industry_id: str,
    items: Sequence[LedgerItem],
) -> CheckReport:
    """逐笔映射到支出范围条目并四态判定。

    ``spending`` 为 ``spending.json`` 内容（须已过 ``check`` 作用域门控）。
    """
    if industry_id not in IN_SCOPE_INDUSTRIES:
        raise NotCovered(
            "行业 %s 的支出范围核查属首期未覆盖（首期：%s），不臆造结论"
            % (industry_id, "、".join(IN_SCOPE_INDUSTRIES))
        )

    entries = [
        entry for entry in spending.get("entries", [])
        if entry.get("industry_id") in (industry_id, "*")
    ]

    findings: List[CheckFinding] = []
    for item in items:
        allowed = [e for e in entries if e.get("category") == "允许" and _match(e, item)]
        forbidden = [e for e in entries if e.get("category") == "禁止" and _match(e, item)]

        if forbidden:
            entry = forbidden[0]
            findings.append(CheckFinding(
                item_key=item.item_key, subject=item.subject, summary=item.summary,
                amount=item.amount, state=STATE_NONCOMPLIANT,
                clause=str(entry.get("clause", "")), entry_id=str(entry.get("entry_id", "")),
                reason="命中禁止性条目（红线）",
            ))
        elif allowed:
            entry = allowed[0]
            findings.append(CheckFinding(
                item_key=item.item_key, subject=item.subject, summary=item.summary,
                amount=item.amount, state=STATE_COMPLIANT,
                clause=str(entry.get("clause", "")), entry_id=str(entry.get("entry_id", "")),
                reason="命中允许条目",
            ))
        else:
            findings.append(CheckFinding(
                item_key=item.item_key, subject=item.subject, summary=item.summary,
                amount=item.amount, state=STATE_NOT_ASSESSED,
                clause="", entry_id="",
                reason="无可适用条目（**未评估**，非'符合'）",
            ))

    redlines = tuple(f for f in findings if f.state == STATE_NONCOMPLIANT)
    return CheckReport(industry_id=industry_id, findings=tuple(findings), redlines=redlines)


__all__ = [
    "STATE_COMPLIANT",
    "STATE_PARTIAL",
    "STATE_NONCOMPLIANT",
    "STATE_NOT_APPLICABLE",
    "STATE_NOT_ASSESSED",
    "IN_SCOPE_INDUSTRIES",
    "NON_PASS_STATES",
    "LedgerItem",
    "CheckFinding",
    "CheckReport",
    "check_ledger",
]
