"""异常与退出码契约。

退出码三语义（锁进 CLI 测试，重构不漂移）::

    0  成功（基准全达标；无检出不符合）
    1  门控拦截 / 基准未达标 / 检出不符合
    2  输入或用法错误（含年度无规则集、首期未覆盖行业、--only 未知名）
    3  可选依赖缺失（GUI、XLSX 台账读入）

纪律：批量扫描中**失败件 ≠ 违规**——失败件带原因码、单列、**不改退出码**。
"""

EXIT_OK = 0
EXIT_GATE = 1
EXIT_USAGE = 2
EXIT_DEP = 3

__all__ = [
    "EXIT_OK",
    "EXIT_GATE",
    "EXIT_USAGE",
    "EXIT_DEP",
    "SafeFeeError",
    "DataDirNotFound",
    "SchemaError",
    "IntegrityError",
    "NoRulesetForYear",
    "AmbiguousRuleset",
    "GateBlocked",
    "MissingInput",
    "NotCovered",
    "BenchmarkNotMet",
    "ConfigError",
    "OptionalDependencyMissing",
    "ScanItemError",
]


class SafeFeeError(Exception):
    """所有可预期错误的基类；``exit_code`` 决定 CLI 退出码。"""

    exit_code = EXIT_USAGE


class DataDirNotFound(SafeFeeError):
    """未找到含 ``rules/manifest.json`` 的数据目录。"""


class SchemaError(SafeFeeError):
    """规则包 schema 不符合预期（版本未知、字段缺失等）。"""


class IntegrityError(SafeFeeError):
    """规则包指纹与 manifest 登记值不一致（说明被手改）。"""


class NoRulesetForYear(SafeFeeError):
    """指定年度没有对应的规则集版本。"""


class AmbiguousRuleset(SafeFeeError):
    """同一时点匹配到多个规则集（配置错误）。"""


class GateBlocked(SafeFeeError):
    """门控拦截：该作用域引用了未核对（pending）条目。"""

    exit_code = EXIT_GATE


class MissingInput(SafeFeeError):
    """档案缺必填字段：**显式索取**，绝不静默取 0/1。"""


class NotCovered(SafeFeeError):
    """首期范围未覆盖（如 deferred 行业）：如实返回，不臆造结论。"""


class BenchmarkNotMet(SafeFeeError):
    """基准未达标。"""

    exit_code = EXIT_GATE


class ConfigError(SafeFeeError):
    """配置错误（如基准门槛缺失）：**不回落代码默认值**。"""


class OptionalDependencyMissing(SafeFeeError):
    """可选依赖缺失（GUI / XLSX 台账读入）。"""

    exit_code = EXIT_DEP


class ScanItemError(Exception):
    """批量扫描中的单件失败：带**原因码**，不中断整批、不改退出码。"""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(detail or reason_code)
        self.reason_code = reason_code
        self.detail = detail
