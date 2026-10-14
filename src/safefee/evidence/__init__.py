"""证据链与指纹（防篡改）。

每份台账/结果挂 ``content_sha256``；报告产物自身也挂 sha256 进 ``evidence.json``
——**报告被改动即可检出**。
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class Evidence:
    """证据链容器。"""

    entries: Dict[str, str] = field(default_factory=dict)

    def add(self, name: str, digest: str) -> None:
        self.entries[name] = digest

    def add_file(self, name: str, path: Path) -> str:
        digest = sha256_file(Path(path))
        self.entries[name] = digest
        return digest

    def add_bytes(self, name: str, payload: bytes) -> str:
        digest = sha256_bytes(payload)
        self.entries[name] = digest
        return digest

    def as_dict(self) -> dict:
        return {"entries": dict(sorted(self.entries.items()))}

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


__all__ = ["Evidence", "sha256_bytes", "sha256_text", "sha256_file"]
