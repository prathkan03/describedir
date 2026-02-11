
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional


@dataclass
class FileNode:
    name: str
    type: str  # "file" or "directory"
    path: str  # relative to root, forward slashes
    description: str
    size_bytes: Optional[int] = None
    skipped: Optional[bool] = None
    skip_reason: Optional[str] = None
    children: Optional[list[FileNode]] = None

    def to_dict(self) -> dict:
        d: dict = {}
        for k, v in self.__dict__.items():
            if v is None:
                continue
            if k == "children":
                d[k] = [child.to_dict() for child in v]
            else:
                d[k] = v
        return d


@dataclass
class DescriptionOutput:
    schema_version: str = "describedir-v1"
    root: str = ""
    generated_at: str = ""
    model: str = ""
    tree: Optional[FileNode] = None

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(
            {
                "$schema": self.schema_version,
                "root": self.root,
                "generated_at": self.generated_at,
                "model": self.model,
                "tree": self.tree.to_dict() if self.tree else None,
            },
            indent=indent,
        )
