"""规则集文件加载（``<ruleset_dir>/ruleset.json`` 等）。"""

import json
from decimal import Decimal
from pathlib import Path

from safefee.errors import SchemaError


def load_json(path: Path):
    """统一 JSON 读入：``parse_float=Decimal``（金额精度纪律）。"""
    path = Path(path)
    if not path.is_file():
        raise SchemaError("规则文件不存在：%s" % path)
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh, parse_float=Decimal)
    except ValueError as exc:  # JSONDecodeError 是 ValueError 子类
        raise SchemaError("规则文件不是合法 JSON：%s（%s）" % (path, exc))


def load_ruleset(data_dir: Path, ruleset_dir: str) -> dict:
    """加载某规则集的 ``ruleset.json``（计提标准）。"""
    return load_json(Path(data_dir) / "rules" / ruleset_dir / "ruleset.json")


def load_spending(data_dir: Path, ruleset_dir: str) -> dict:
    """加载某规则集的 ``spending.json``（支出范围条目）。"""
    return load_json(Path(data_dir) / "rules" / ruleset_dir / "spending.json")


def load_progress(data_dir: Path, ruleset_dir: str) -> dict:
    """加载某规则集的 ``progress.json``（使用进度门槛）。"""
    return load_json(Path(data_dir) / "rules" / ruleset_dir / "progress.json")


__all__ = ["load_json", "load_ruleset", "load_spending", "load_progress"]
