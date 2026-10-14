"""批量台账扫描（失败件隔离）。

**两条退出码纪律**：

* **失败件 ≠ 违规**——"坏 JSON / 不可解析 / 读盘失败"是**未判定**（记
  ``scan_error`` / ``parse_error`` / ``missing_field`` / ``unknown_industry`` /
  ``unsupported_container`` / ``too_large``），**不改变退出码**（退出码仍由"是否检出
  不符合 / 门控"决定）；失败件在结果与报告中**单列**，绝不静默吞掉；
* **失败隔离**——单件异常**不中断整批**。

判别口诀：**"没判定"与"判出违规"是两种不同的退出码语义**。
"""

from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

#: 单件读取的安全阀（超过则记 ``too_large``，不整体读入内存）
DEFAULT_MAX_BYTES = 32 * 1024 * 1024

REASON_PARSE_ERROR = "parse_error"
REASON_MISSING_FIELD = "missing_field"
REASON_UNKNOWN_INDUSTRY = "unknown_industry"
REASON_UNSUPPORTED_CONTAINER = "unsupported_container"
REASON_TOO_LARGE = "too_large"


@dataclass(frozen=True)
class ScanFailure:
    """失败件（单列，不改退出码）。"""

    source: str
    reason_code: str
    detail: str = ""

    def as_dict(self) -> dict:
        return {"source": self.source, "reason_code": self.reason_code, "detail": self.detail}


@dataclass
class ScanOutcome:
    """批量扫描结果。"""

    processed: List[object] = field(default_factory=list)
    failures: List[ScanFailure] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "processed_count": len(self.processed),
            "failure_count": len(self.failures),
            "failures": [f.as_dict() for f in self.failures],
        }


def scan_sources(
    sources: Iterable[str],
    handler: Callable[[str], object],
    *,
    on_error: Optional[Callable[[str, Exception], ScanFailure]] = None,
) -> ScanOutcome:
    """对每个来源调用 ``handler``；**单件异常不中断整批**。

    ``handler`` 抛 :class:`~safefee.errors.ScanItemError` → 按原因码记失败件；
    抛其他异常 → 归入 ``scan_error``（仍不中断）。
    """
    from safefee.errors import ScanItemError

    outcome = ScanOutcome()
    for source in sources:
        try:
            outcome.processed.append(handler(source))
        except ScanItemError as exc:
            outcome.failures.append(ScanFailure(source, exc.reason_code, exc.detail))
        except Exception as exc:  # noqa: BLE001 —— 失败隔离是刻意的
            if on_error is not None:
                outcome.failures.append(on_error(source, exc))
            else:
                outcome.failures.append(ScanFailure(source, "scan_error", str(exc)))
    return outcome


__all__ = [
    "DEFAULT_MAX_BYTES",
    "REASON_PARSE_ERROR",
    "REASON_MISSING_FIELD",
    "REASON_UNKNOWN_INDUSTRY",
    "REASON_UNSUPPORTED_CONTAINER",
    "REASON_TOO_LARGE",
    "ScanFailure",
    "ScanOutcome",
    "scan_sources",
]
