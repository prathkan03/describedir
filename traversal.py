"""Directory tree building and bottom-up traversal ordering."""

import fnmatch
import os
from collections import defaultdict
from typing import Generator

from .config import DEFAULT_IGNORE_PATTERNS
from .schema import FileNode


def should_ignore(name: str, ignore_patterns: list[str]) -> bool:
    """Check if a file/folder name matches any ignore pattern."""
    return any(fnmatch.fnmatch(name, pat) for pat in ignore_patterns)


def build_tree(
    root_path: str,
    ignore_patterns: list[str] = DEFAULT_IGNORE_PATTERNS,
    _rel_prefix: str = "",
) -> FileNode:
    """Recursively build a FileNode tree from the filesystem.

    Populates structure only -- descriptions are left empty.
    """
    root_name = os.path.basename(os.path.abspath(root_path))
    entries = sorted(os.listdir(root_path))
    children: list[FileNode] = []

    for entry in entries:
        if should_ignore(entry, ignore_patterns):
            continue

        full_path = os.path.join(root_path, entry)
        rel_path = f"{_rel_prefix}{entry}" if _rel_prefix else entry

        if os.path.isdir(full_path):
            child = build_tree(full_path, ignore_patterns, _rel_prefix=rel_path + "/")
            child.name = entry
            child.path = rel_path
            children.append(child)
        elif os.path.isfile(full_path):
            children.append(
                FileNode(
                    name=entry,
                    type="file",
                    path=rel_path,
                    description="",
                    size_bytes=os.path.getsize(full_path),
                )
            )

    return FileNode(
        name=root_name,
        type="directory",
        path=_rel_prefix.rstrip("/") or ".",
        description="",
        children=children,
    )


def get_levels_bottom_up(root_node: FileNode) -> list[list[FileNode]]:
    """Return directory nodes grouped by depth, deepest first.

    File nodes are not included -- they are processed as children of their parent.
    """
    levels: dict[int, list[FileNode]] = defaultdict(list)

    def _collect(node: FileNode, depth: int) -> None:
        if node.type == "directory":
            levels[depth].append(node)
            if node.children:
                for child in node.children:
                    _collect(child, depth + 1)

    _collect(root_node, 0)

    if not levels:
        return []

    max_depth = max(levels.keys())
    return [levels[d] for d in range(max_depth, -1, -1)]


def walk_bottom_up(root_node: FileNode) -> Generator[FileNode, None, None]:
    """Yield directory FileNode objects from deepest to shallowest."""
    for level in get_levels_bottom_up(root_node):
        yield from level
