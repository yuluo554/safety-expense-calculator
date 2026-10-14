"""manifest 加载、指纹校验、年度→版本锚定、基准门槛。

``manifest.json`` 是**规则包坐标与基准门槛的唯一来源**：

* ``rulesets[]`` 登记每个规则集目录、文号、生效年度区间、status 与 **sha256**；
* ``benchmark_thresholds`` 承载基准达标门槛——**门槛是数据不是代码**，基准层只读，
  缺失即报配置错误（退出码 2），**不得回落代码里的默认值**。

加载时逐份校验规则文件指纹：不一致说明规则包被手改（冻结纪律被破坏）→
:class:`IntegrityError`。
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from safefee.errors import (
    AmbiguousRuleset,
    ConfigError,
    IntegrityError,
    NoRulesetForYear,
    SchemaError,
)

SUPPORTED_SCHEMA_VERSION = 1


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class RulesetRef:
    """一个规则集的坐标。"""

    ruleset_id: str
    directory: str
    doc_no: str
    doc_title: str
    effective_from: date
    effective_to: Optional[date]
    status: str
    sha256: str

    def covers(self, day: date) -> bool:
        if day < self.effective_from:
            return False
        return self.effective_to is None or day <= self.effective_to

    def as_dict(self) -> Dict[str, object]:
        return {
            "ruleset_id": self.ruleset_id,
            "directory": self.directory,
            "doc_no": self.doc_no,
            "doc_title": self.doc_title,
            "effective_from": self.effective_from.isoformat(),
            "effective_to": self.effective_to.isoformat() if self.effective_to else None,
            "status": self.status,
            "sha256": self.sha256,
        }


class Manifest:
    """规则集索引 + 基准门槛。"""

    def __init__(self, data_dir: Path, payload: dict) -> None:
        self._data_dir = Path(data_dir)
        self._raw = payload
        self._thresholds = payload.get("benchmark_thresholds") or {}
        self._refs: List[RulesetRef] = []
        for item in payload.get("rulesets", []):
            try:
                from_day = _parse_day(item["effective_from"])
                to_day = _parse_day(item["effective_to"]) if item.get("effective_to") else None
                self._refs.append(
                    RulesetRef(
                        ruleset_id=item["ruleset_id"],
                        directory=item["dir"],
                        doc_no=item["doc_no"],
                        doc_title=item.get("doc_title", ""),
                        effective_from=from_day,
                        effective_to=to_day,
                        status=item.get("status", "pending"),
                        sha256=item.get("sha256", ""),
                    )
                )
            except KeyError as exc:
                raise SchemaError("manifest rulesets 条目缺字段：%s" % exc)

    @property
    def data_dir(self) -> Path:
        return self._data_dir

    @property
    def refs(self) -> Tuple[RulesetRef, ...]:
        return tuple(self._refs)

    @property
    def thresholds(self) -> dict:
        return self._thresholds

    def threshold_for(self, suite: str) -> dict:
        """取某基准套件的门槛；**缺失即配置错误（退出码 2）**，不回落默认值。"""
        if suite not in self._thresholds:
            raise ConfigError(
                "基准门槛缺失：manifest.benchmark_thresholds 未登记套件 %r（门槛是数据，不回落代码默认值）"
                % suite
            )
        return self._thresholds[suite]

    def resolve(self, day: date) -> RulesetRef:
        """按**日**锚定规则版本；无匹配 → 退出码 2，多匹配 → 配置错误。"""
        matched = [ref for ref in self._refs if ref.covers(day)]
        if not matched:
            raise NoRulesetForYear("年度 %s 没有适用的规则集版本" % day.isoformat())
        if len(matched) > 1:
            raise AmbiguousRuleset(
                "时点 %s 匹配到多个规则集：%s"
                % (day.isoformat(), ", ".join(ref.ruleset_id for ref in matched))
            )
        return matched[0]

    def resolve_year(self, year: int) -> RulesetRef:
        """按年度锚定：取该年度 **1 月 1 日** 为锚定日（口径见 plan/04 §2.1）。"""
        return self.resolve(date(int(year), 1, 1))

    def verify_integrity(self) -> None:
        """逐份校验规则文件 sha256 与 manifest 登记值一致（防手改）。"""
        for item in self._raw.get("rulesets", []):
            files = item.get("files") or {}
            base = self._data_dir / "rules" / item["dir"]
            for rel, expected in files.items():
                path = base / rel
                if not path.is_file():
                    raise IntegrityError("manifest 登记的规则文件缺失：%s" % path)
                actual = sha256_file(path)
                if actual != expected:
                    raise IntegrityError(
                        "规则文件指纹不符（规则包被手改？）：%s 期望 %s 实际 %s"
                        % (path, expected, actual)
                    )


def _parse_day(value) -> date:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise SchemaError("日期字段应为 ISO 字符串：%r" % (value,))
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise SchemaError("日期字段不是 ISO 格式（YYYY-MM-DD）：%r" % (value,))


def load_manifest(data_dir: Path, *, verify: bool = True) -> Manifest:
    """加载 ``<data_dir>/rules/manifest.json``；``verify`` 控制是否校验指纹。"""
    path = Path(data_dir) / "rules" / "manifest.json"
    if not path.is_file():
        raise SchemaError("缺少规则包清单：%s" % path)
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh, parse_float=Decimal)

    version = payload.get("schema_version")
    if version != SUPPORTED_SCHEMA_VERSION:
        raise SchemaError(
            "manifest schema_version 不支持：%r（本工具支持 %r）"
            % (version, SUPPORTED_SCHEMA_VERSION)
        )
    manifest = Manifest(Path(data_dir), payload)
    if verify:
        manifest.verify_integrity()
    return manifest


__all__ = [
    "Manifest",
    "RulesetRef",
    "load_manifest",
    "sha256_file",
    "SUPPORTED_SCHEMA_VERSION",
]
