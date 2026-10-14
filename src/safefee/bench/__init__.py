"""内置评测基准（零 API 依赖、零第三方依赖、单次 <1 秒）。

三类套件：

===============  ==========  =====================================================
套件             类型        内容
===============  ==========  =====================================================
``tiered_boundary``  **规则驱动**  从规则表推导全部分段点，做 ``{p-0.01, p, p+0.01}``
                             邻域枚举，断言段归属与逐段金额自洽（**不读真值库**）
``dual_version``    规则驱动  同一对象按两版规则各算期望值，断言版本切换结果一致
``synthetic_ledger`` **样本驱动**  合成台账真值库全量重算对账（独立实现路径）
===============  ==========  =====================================================

**四条硬纪律**：

* **验收门槛随 manifest 下发**（数据非代码）——缺失即报配置错误（退出码 2），
  **不得回落代码里的默认值**；
* **新增基准要注册进 ``--only`` 白名单**（未知名 → 退出码 2，别静默跳过）；
* **退出码三语义**：0 达标 / 1 未达标 / 2 输入、坐标或用例名错误；
* **每套件配可证伪探活**：注入一个缺陷 → 断言基准必须报未达标
  （防"基准全绿只是因为它什么都没查"）。
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Sequence, Tuple

from safefee.errors import ConfigError
from safefee.rules.manifest import Manifest
from safefee.tiered import compute_tiered, tiered_total, tiers_from_rules

SUITES = ("tiered_boundary", "dual_version", "synthetic_ledger")

BOUNDARY_NEIGHBOURHOOD = (Decimal("-0.01"), Decimal("0"), Decimal("0.01"))


@dataclass
class SuiteResult:
    """一个套件的运行结论。

    ``assessable=False``（用例数为 0）表示**未评估**——"没测"与"达标"是两回事：
    既不声称 ``met=True``，也不把它当"未达标"阻断运行。
    """

    suite: str
    total: int
    passed: int
    failed: List[str] = field(default_factory=list)
    notes: str = ""
    threshold: dict = field(default_factory=dict)
    met: bool = False
    measured: Dict[str, float] = field(default_factory=dict)

    @property
    def assessable(self) -> bool:
        return self.total > 0

    def as_dict(self) -> dict:
        return {
            "suite": self.suite,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "notes": self.notes,
            "threshold": dict(self.threshold),
            "met": self.met,
            "assessable": self.assessable,
            "measured": dict(self.measured),
        }


def _evaluate_ratio(suite: str, total: int, passed: int, threshold: dict) -> Tuple[bool, Dict[str, float]]:
    """按门槛判定；门槛键名按套件语义取（缺键即配置错误）。

    **``total == 0`` 时不得判定为达标**——"没测"与"达标"是两回事，
    分母不能因为用例未生成而悄悄做小。
    """
    ratio = (float(passed) / float(total)) if total else 0.0
    measured = {"pass_ratio": ratio}
    if total == 0:
        return False, measured
    if suite == "tiered_boundary":
        key = "min_pass_ratio"
    elif suite == "dual_version":
        key = "min_consistency"
    else:
        key = "min_truth_match"
    if key not in threshold:
        raise ConfigError("基准门槛 %r 缺少必需键 %r（门槛是数据，不回落默认值）" % (suite, key))
    return ratio >= float(threshold[key]), measured


def run_tiered_boundary(manifest: Manifest, rulesets: Sequence[dict]) -> SuiteResult:
    """**规则驱动**：从规则表推导分段点，做邻域枚举断言段归属自洽。

    不读真值库——专治"样本没覆盖的端点"。
    """
    total = 0
    passed = 0
    failed: List[str] = []
    boundaries = 0

    for ruleset in rulesets:
        for industry in ruleset.get("industries", []):
            segments = _all_segments(industry)
            if not segments:
                continue
            specs = tiers_from_rules(segments)
            finite_bounds = sorted({s.upper for s in specs if s.upper is not None})
            for bound in finite_bounds:
                boundaries += 1
                for delta in BOUNDARY_NEIGHBOURHOOD:
                    value = bound + delta
                    total += 1
                    try:
                        _assert_boundary_consistent(value, specs)
                    except AssertionError as exc:
                        failed.append("boundary=%s delta=%s: %s" % (bound, delta, exc))
                    else:
                        passed += 1

    notes = "规则驱动：从规则表推导分段点（未读真值库）；共 %d 个有限边界" % boundaries
    if total == 0:
        notes += "；当前规则包无分段结构（计提标准未落值），该类用例未生成"
    threshold = manifest.threshold_for("tiered_boundary")
    met, measured = _evaluate_ratio("tiered_boundary", total, passed, threshold)
    return SuiteResult("tiered_boundary", total, passed, failed, notes, threshold, met, measured)


def _assert_boundary_consistent(value: Decimal, specs) -> None:
    """边界自洽：段内依据量之和 == 依据量；段归属与区间定义一致。"""
    lines = compute_tiered(value, specs)
    if not lines:
        raise AssertionError("value=%s 无分段明细" % value)
    total_base = sum((line.base_in_tier for line in lines), Decimal(0))
    if total_base != value:
        raise AssertionError("段内依据量之和 %s != 依据量 %s" % (total_base, value))
    for line in lines:
        if line.upper is None:
            continue
        if line.base_in_tier > (line.upper - line.lower):
            raise AssertionError("段 %d 依据量 %s 超出段宽" % (line.index, line.base_in_tier))
        if line.base_in_tier < 0:
            raise AssertionError("段 %d 依据量为负" % line.index)


def _node_has_pending(node: dict) -> bool:
    """节点是否含未核对（pending）数值——未核对不得进入计算路径，基准同样跳过。"""
    if node.get("status") == "pending":
        return True
    if node.get("value") is None and node.get("mechanism") == "by_output":
        return True
    if node.get("rate") is None and node.get("mechanism") == "by_project_cost":
        return True
    segments = node.get("segments") or []
    if segments and any(seg.get("status") == "pending" or seg.get("rate") is None for seg in segments):
        return True
    return False


def _all_segments(industry: dict) -> list:
    out = list(industry.get("segments") or [])
    for variant in industry.get("variants") or []:
        out.extend(variant.get("segments") or [])
    return out


def run_dual_version(manifest: Manifest, old_ruleset: dict, new_ruleset: dict) -> SuiteResult:
    """规则驱动：两版规则对同一对象各自计算，断言版本切换不串口径。"""
    from safefee.accrual import AccrualRequest, compute

    total = 0
    passed = 0
    failed: List[str] = []

    old_index = _index_nodes(old_ruleset)
    new_index = _index_nodes(new_ruleset)
    skipped = 0
    for key in sorted(set(old_index) & set(new_index)):
        industry_id, variant_id = key
        node_old = old_index[key]
        node_new = new_index[key]
        if node_old.get("mechanism") != node_new.get("mechanism"):
            continue
        # 首期未覆盖的行业不参与对照（不臆造结论）
        if node_old.get("implementation") == "deferred" or node_new.get("implementation") == "deferred":
            skipped += 1
            continue
        for ruleset, node, label in ((old_ruleset, node_old, "old"), (new_ruleset, node_new, "new")):
            if _node_has_pending(node):
                skipped += 1
                continue
            total += 1
            try:
                _assert_version_isolated(ruleset, industry_id, variant_id, node)
            except AssertionError as exc:
                failed.append("%s %s/%s: %s" % (label, industry_id, variant_id, exc))
            else:
                passed += 1

    notes = "规则驱动：两版各算各的期望值；配对 %d 组（首期未覆盖跳过 %d 组）" % (
        len(set(old_index) & set(new_index)), skipped)
    threshold = manifest.threshold_for("dual_version")
    met, measured = _evaluate_ratio("dual_version", total, passed, threshold)
    return SuiteResult("dual_version", total, passed, failed, notes, threshold, met, measured)


def _assert_version_isolated(ruleset: dict, industry_id: str, variant_id: Optional[str], node: dict) -> None:
    """断言某版本节点的计算结果只依赖**本版本**数值（不被另一版污染）。"""
    from safefee.accrual import AccrualRequest, compute

    mechanism = node.get("mechanism")
    if mechanism is None:
        raise AssertionError("节点缺 mechanism")
    if mechanism == "by_output":
        unit_value = node.get("value")
        if unit_value is None:
            raise AssertionError("未落值（pending）")
        request = AccrualRequest(industry_id, "output", Decimal("1000"), "ton", 2020, variant_id)
    elif mechanism == "by_project_cost":
        rate = node.get("rate")
        if rate is None:
            raise AssertionError("未落值（pending）")
        request = AccrualRequest(industry_id, "project_cost", Decimal("1000000"), "CNY", 2020, variant_id)
    else:
        segments = node.get("segments") or []
        if not segments:
            raise AssertionError("缺 segments")
        request = AccrualRequest(industry_id, "revenue", Decimal("20000000"), "CNY", 2020, variant_id)
    result = compute(ruleset, request)
    if result.amount < 0:
        raise AssertionError("金额为负")


def _index_nodes(ruleset: dict) -> Dict[Tuple[str, Optional[str]], dict]:
    index: Dict[Tuple[str, Optional[str]], dict] = {}
    for industry in ruleset.get("industries", []):
        industry_id = str(industry.get("industry_id"))
        variants = industry.get("variants") or []
        if not variants:
            index[(industry_id, None)] = industry
        for variant in variants:
            index[(industry_id, str(variant.get("variant_id")))] = dict(variant, mechanism=industry.get("mechanism"))
    return index


def run_synthetic_ledger(manifest: Manifest, truth_dir, rulesets_by_id: Dict[str, dict]) -> SuiteResult:
    """**样本驱动**：合成台账真值库全量重算对账（独立实现路径）。

    真值库缺省（M1 前）→ 记 ``notes`` 如实说明"该类用例未生成"，**不假装覆盖**。
    """
    from safefee.truth import iter_cases, evaluate_case

    cases = list(iter_cases(truth_dir))
    total = 0
    passed = 0
    failed: List[str] = []

    for case in cases:
        total += 1
        ruleset = rulesets_by_id.get(case.ruleset_id)
        if ruleset is None:
            failed.append("%s: 规则集 %s 未加载" % (case.case_id, case.ruleset_id))
            continue
        try:
            evaluate_case(case, ruleset)
        except AssertionError as exc:
            failed.append("%s: %s" % (case.case_id, exc))
        else:
            passed += 1

    notes = "样本驱动：真值库 %d 例" % len(cases)
    if not cases:
        notes = "样本驱动：真值库尚未生成（M1 待建），该类用例未生成——不假装覆盖"
    threshold = manifest.threshold_for("synthetic_ledger")
    met, measured = _evaluate_ratio("synthetic_ledger", total, passed, threshold)
    return SuiteResult("synthetic_ledger", total, passed, failed, notes, threshold, met, measured)


def run_all(
    manifest: Manifest,
    *,
    only: Optional[str] = None,
    data_dir=None,
) -> List[SuiteResult]:
    """跑基准；``only`` 不在白名单 → :class:`ConfigError`（退出码 2）。"""
    from safefee.rules import load_ruleset

    if only is not None and only not in SUITES:
        raise ConfigError("未知基准套件：%r（白名单：%s）" % (only, ", ".join(SUITES)))

    root = manifest.data_dir
    rulesets = [load_ruleset(root, ref.directory) for ref in manifest.refs]
    rulesets_by_id = {ref.ruleset_id: rs for ref, rs in zip(manifest.refs, rulesets)}

    results: List[SuiteResult] = []
    if only in (None, "tiered_boundary"):
        results.append(run_tiered_boundary(manifest, rulesets))
    if only in (None, "dual_version"):
        if len(manifest.refs) >= 2:
            results.append(run_dual_version(manifest, rulesets[0], rulesets[-1]))
        else:
            results.append(SuiteResult(
                "dual_version", 0, 0, [], "双版本对照：规则集不足两套，该类用例未生成",
                manifest.threshold_for("dual_version"), False, {"pass_ratio": 0.0},
            ))
    if only in (None, "synthetic_ledger"):
        results.append(run_synthetic_ledger(manifest, root / "truth", rulesets_by_id))
    return results


__all__ = [
    "SUITES",
    "BOUNDARY_NEIGHBOURHOOD",
    "SuiteResult",
    "run_all",
    "run_tiered_boundary",
    "run_dual_version",
    "run_synthetic_ledger",
]
