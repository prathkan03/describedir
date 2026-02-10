#!/usr/bin/env python
"""View directory descriptions from .describedir.json in a formatted terminal output."""

import json
import sys
from pathlib import Path
from typing import Optional


class DescriptionViewer:
    """Display directory descriptions in a formatted tree view."""

    def __init__(self, json_file: str = ".describedir.json"):
        """Initialize viewer with path to .describedir.json."""
        self.json_file = Path(json_file)
        self.data = None
        self.load_data()

    def load_data(self) -> None:
        """Load and parse the JSON file."""
        if not self.json_file.exists():
            print(f"Error: {self.json_file} not found.", file=sys.stderr)
            print(f"Run 'python -m describedir' first to generate descriptions.", file=sys.stderr)
            sys.exit(1)

        try:
            with open(self.json_file, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {self.json_file}: {e}", file=sys.stderr)
            sys.exit(1)

    def print_header(self) -> None:
        """Print header with metadata."""
        print("\n" + "=" * 80)
        print(f"📦 Project: {self.data['tree']['name']}")
        print(f"📍 Root: {self.data['root']}")
        print(f"🤖 Model: {self.data['model']}")
        print(f"⏰ Generated: {self.data['generated_at']}")
        print("=" * 80 + "\n")

    def print_tree(self, node: dict, depth: int = 0, is_last: bool = True) -> None:
        """Recursively print the directory tree with descriptions."""
        indent = "    " * (depth - 1)
        connector = "└── " if is_last and depth > 0 else "├── " if depth > 0 else ""

        # Print node name with icon
        if node["type"] == "directory":
            icon = "📁"
        else:
            icon = "📄"

        print(f"{indent}{connector}{icon} {node['name']}")

        # Print description
        if node.get("description"):
            desc_indent = "    " * depth
            desc = node["description"]
            # Wrap long descriptions
            if len(desc) > 70:
                words = desc.split()
                lines = []
                current_line = []
                for word in words:
                    if len(" ".join(current_line + [word])) <= 70:
                        current_line.append(word)
                    else:
                        if current_line:
                            lines.append(" ".join(current_line))
                        current_line = [word]
                if current_line:
                    lines.append(" ".join(current_line))
                for i, line in enumerate(lines):
                    print(f"{desc_indent}  {line}")
            else:
                print(f"{desc_indent}  {desc}")

        # Print file size for files
        if node["type"] == "file" and node.get("size_bytes"):
            size_indent = "    " * depth
            size_kb = node["size_bytes"] / 1024
            print(f"{size_indent}  ({size_kb:.1f} KB)")

        # Print skip reason if applicable
        if node.get("skipped"):
            skip_indent = "    " * depth
            reason = node.get("skip_reason", "unknown")
            print(f"{skip_indent}  [SKIPPED: {reason}]")

        # Recursively print children
        children = node.get("children", [])
        for i, child in enumerate(children):
            is_last_child = i == len(children) - 1
            self.print_tree(child, depth + 1, is_last_child)

    def find_node(self, path: str) -> Optional[dict]:
        """Find a node by path or name."""
        def search(node: dict, target: str) -> Optional[dict]:
            if node["path"] == target or node["name"] == target:
                return node
            for child in node.get("children", []):
                result = search(child, target)
                if result:
                    return result
            return None

        return search(self.data["tree"], path)

    def view_path(self, path: str) -> None:
        """View descriptions for a specific path."""
        node = self.find_node(path)
        if not node:
            print(f"Error: Path '{path}' not found.", file=sys.stderr)
            sys.exit(1)

        print("\n" + "=" * 80)
        print(f"📍 Path: {node['path']}")
        print("=" * 80 + "\n")
        self.print_tree(node)
        print()

    def view_all(self) -> None:
        """View the entire directory tree."""
        self.print_header()
        self.print_tree(self.data["tree"])
        print()

    def view_summary(self) -> None:
        """View a summary of the project."""
        self.print_header()
        print(f"📝 {self.data['tree']['description']}\n")


def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="View directory descriptions from .describedir.json"
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Specific path to view (e.g., 'src' or 'src/app.py')",
    )
    parser.add_argument(
        "-f",
        "--file",
        default=".describedir.json",
        help="Path to .describedir.json (default: .describedir.json)",
    )
    parser.add_argument(
        "-s",
        "--summary",
        action="store_true",
        help="Show only project summary",
    )

    args = parser.parse_args()

    viewer = DescriptionViewer(args.file)

    if args.summary:
        viewer.view_summary()
    elif args.path:
        viewer.view_path(args.path)
    else:
        viewer.view_all()


if __name__ == "__main__":
    main()