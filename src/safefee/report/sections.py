"""报告章节结构（**单一渲染源**）。

同一份报告要出 Markdown + XLSX 时，**两种格式都消费同一个章节结构函数**
（:func:`build_sections`）——于是"两格式内容一致"不再是"导出后肉眼比对"，
而是**结构上不可能不一致**（改一处两者同变）。

**报告必含四块**（政策/参数类交付的硬要求）：

1. 输入事实（企业档案 / 台账摘要）；
2. **参数来源块**（每项参数：发布机关 + 适用年度 + 文号 + URL + 抓取日期）
   ——让读者**不开仓库**也能核证"这个数字哪来的"；
3. 逐项计算过程（直接渲染引擎的 ``tiers``/``formula`` 留痕，**报告层不重算**，
   否则又是一处第二实现）；
4. 适用依据 + 免责声明。

**"未启用"的章节要显式写出**（"本次导出未启用 X（用 --with-check 启用）"），
不留空——**"没查"与"查了没问题"是两种截然不同的结论**。
"""

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

DISCLAIMER = (
    "免责声明：本报告为基于《企业安全生产费用提取和使用管理办法》条款的**计提测算"
    "与合规检查发现**，不构成会计、审计或法律意见；正式结论以主管财政部门与应急管理"
    "部门的执行口径、执业机构出具的正式意见为准。本工具全本地处理、零上传。"
)


@dataclass(frozen=True)
class Section:
    """一个报告章节。"""

    title: str
    kind: str                                  # text | table | note
    paragraphs: Tuple[str, ...] = ()
    columns: Tuple[str, ...] = ()
    rows: Tuple[Tuple[str, ...], ...] = ()
    enabled: bool = True
    disabled_note: str = ""

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "kind": self.kind,
            "paragraphs": list(self.paragraphs),
            "columns": list(self.columns),
            "rows": [list(row) for row in self.rows],
            "enabled": self.enabled,
            "disabled_note": self.disabled_note,
        }


@dataclass
class ReportInput:
    """报告输入（由编排层组装；报告层**不重算**）。"""

    ruleset_coordinate: dict = field(default_factory=dict)   # 规则包坐标（版本 + sha256 + 生成时间）
    enterprise: dict = field(default_factory=dict)
    accrual: Optional[dict] = None                            # AccrualResult.as_dict()
    check: Optional[dict] = None                              # CheckReport.as_dict()
    progress: Optional[dict] = None                           # ProgressResult.as_dict()
    reconcile: Optional[dict] = None                          # ReconcileReport.as_dict()
    parameter_sources: Sequence[dict] = ()                    # 参数来源块
    enabled: Tuple[str, ...] = ("calc", "check", "progress", "reconcile")


def build_sections(payload: ReportInput) -> List[Section]:
    """唯一章节结构源（Markdown 与 XLSX 渲染器各自读它）。"""
    sections: List[Section] = []

    # 0 规则包坐标（报告头）
    coord = payload.ruleset_coordinate or {}
    coord_lines = [
        "依据版本：%s（%s）" % (coord.get("doc_no", "—"), coord.get("ruleset_id", "—")),
        "生效年度：%s" % coord.get("effective_from", "—"),
        "规则包指纹（sha256）：%s" % coord.get("ruleset_sha256", "—"),
        "报告生成时间：%s" % coord.get("generated_at", "—"),
        "工具版本：%s" % coord.get("tool_version", "—"),
    ]
    sections.append(Section("规则包坐标", "text", paragraphs=tuple(coord_lines)))

    # 1 企业档案
    ent = payload.enterprise or {}
    ent_rows = tuple((str(k), str(v)) for k, v in sorted(ent.items()))
    sections.append(Section("企业档案", "table", columns=("项目", "值"), rows=ent_rows))

    # 2 计提明细
    if payload.accrual is not None:
        accrual = payload.accrual
        head = (
            "应计提金额：%s 元" % accrual.get("amount", "—"),
            "计提机制：%s" % accrual.get("mechanism", "—"),
            "计算公式：%s" % accrual.get("formula", "—"),
            "条款依据：%s" % accrual.get("clause", "—"),
        )
        sections.append(Section("计提明细", "text", paragraphs=head))
        tiers = accrual.get("tiers") or []
        if tiers:
            rows = tuple(
                (str(t.get("index")), str(t.get("lower")), str(t.get("upper")),
                 str(t.get("base_in_tier")), str(t.get("rate")), str(t.get("amount")),
                 str(t.get("clause")))
                for t in tiers
            )
            sections.append(Section(
                "超额累退逐段明细", "table",
                columns=("段", "下界", "上界", "段内依据量", "费率", "段内金额", "条款"),
                rows=rows,
            ))
    else:
        sections.append(Section("计提明细", "note", enabled=False,
                                disabled_note="本次导出未启用计提计算（用 calc 子命令生成）"))

    # 3 支出合规核查清单
    if payload.check is not None:
        check = payload.check
        rows = tuple(
            (f.get("item_key", ""), f.get("subject", ""), f.get("summary", ""),
             str(f.get("amount", "")), f.get("state", ""), f.get("clause", ""),
             f.get("reason", ""))
            for f in check.get("findings", [])
        )
        sections.append(Section(
            "支出合规核查清单", "table",
            columns=("键", "科目", "摘要", "金额", "判定", "条款", "理由"), rows=rows,
        ))
        redlines = check.get("redlines") or []
        if redlines:
            rrows = tuple(
                (r.get("item_key", ""), r.get("summary", ""), str(r.get("amount", "")),
                 r.get("clause", ""), r.get("reason", ""))
                for r in redlines
            )
            sections.append(Section(
                "红线项（禁止性条目命中）", "table",
                columns=("键", "摘要", "金额", "条款", "理由"), rows=rrows,
            ))
    else:
        sections.append(Section("支出合规核查清单", "note", enabled=False,
                                disabled_note="本次导出未启用支出核查（用 --with-check 启用）"))

    # 4 使用进度与披露
    if payload.progress is not None:
        prog = payload.progress
        lines = [
            "年度：%s" % prog.get("year", "—"),
            "年度应计提额：%s 元" % prog.get("accrued", "—"),
            "当年实际使用额：%s 元" % prog.get("used", "—"),
            "使用进度：%s" % prog.get("ratio", "—"),
            "门槛：%s" % prog.get("threshold", "—"),
            "是否触发披露义务：%s" % ("是" if prog.get("disclosure_required") else "否"),
            "条款依据：%s" % prog.get("clause", "—"),
        ]
        lines.extend("披露说明要点：%s" % p for p in prog.get("points", []))
        sections.append(Section("使用进度与披露", "text", paragraphs=tuple(lines)))
    else:
        sections.append(Section("使用进度与披露", "note", enabled=False,
                                disabled_note="本次导出未启用进度核查（用 progress 子命令生成）"))

    # 5 异常与对账台账
    if payload.reconcile is not None:
        rec = payload.reconcile
        counts = rec.get("counts", {})
        lines = ["%s：%d" % (k, v) for k, v in sorted(counts.items())]
        sections.append(Section("跨年对账", "text", paragraphs=tuple(lines)))
    else:
        sections.append(Section("跨年对账", "note", enabled=False,
                                disabled_note="本次导出未启用跨年对账（用 scan --baseline 启用）"))

    # 6 参数来源块
    sources = payload.parameter_sources or ()
    if sources:
        rows = tuple(
            (str(s.get("parameter", "")), str(s.get("issuer", "")),
             str(s.get("effective_year", "")), str(s.get("doc_no", "")),
             str(s.get("url", "")), str(s.get("fetched_at", "")))
            for s in sources
        )
        sections.append(Section(
            "参数来源块", "table",
            columns=("参数", "发布机关", "适用年度", "文号", "URL", "抓取日期"), rows=rows,
        ))
    else:
        sections.append(Section("参数来源块", "note", enabled=False,
                                disabled_note="本次导出未登记参数来源（规则包 provenance 为空）"))

    # 7 免责声明
    sections.append(Section("免责声明", "text", paragraphs=(DISCLAIMER,)))
    return sections


__all__ = ["DISCLAIMER", "Section", "ReportInput", "build_sections"]
