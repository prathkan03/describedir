"""CLI entry point and orchestration for describedir."""

import argparse
import os
import sys
from datetime import datetime, timezone

from .config import (
    DEFAULT_FILE_MAX_WORDS,
    DEFAULT_IGNORE_PATTERNS,
    DEFAULT_MODEL,
    OUTPUT_FILENAME,
)
from .llm import create_client, describe_directory, describe_files_batch
from .schema import DescriptionOutput
from .traversal import build_tree, walk_bottom_up


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="describedir",
        description="Generate LLM-powered hierarchical descriptions of a directory tree.",
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Root directory to describe (default: current directory)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help=f"Output JSON file path (default: <root>/{OUTPUT_FILENAME})",
    )
    parser.add_argument(
        "-m",
        "--model",
        default=DEFAULT_MODEL,
        help=f"OpenAI model to use (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--ignore",
        nargs="*",
        default=None,
        help="Additional ignore patterns (glob-style)",
    )
    parser.add_argument(
        "--no-default-ignore",
        action="store_true",
        help="Disable default ignore patterns",
    )
    parser.add_argument(
        "--max-file-size",
        type=int,
        default=None,
        help="Maximum file size in bytes to read (default: 100000)",
    )
    parser.add_argument(
        "--max-words",
        type=int,
        default=DEFAULT_FILE_MAX_WORDS,
        help=f"Maximum words per description (default: {DEFAULT_FILE_MAX_WORDS})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build the tree and show structure without calling the LLM",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print progress information to stderr",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root_path = os.path.abspath(args.root)

    if not os.path.isdir(root_path):
        print(f"Error: '{root_path}' is not a directory.", file=sys.stderr)
        return 1

    # Build ignore list
    ignore_patterns = [] if args.no_default_ignore else list(DEFAULT_IGNORE_PATTERNS)
    if args.ignore:
        ignore_patterns.extend(args.ignore)

    # Phase 1: Build tree
    if args.verbose:
        print("Building directory tree...", file=sys.stderr)
    tree = build_tree(root_path, ignore_patterns)

    if args.dry_run:
        output = DescriptionOutput(
            root=root_path,
            generated_at=datetime.now(timezone.utc).isoformat(),
            model=args.model,
            tree=tree,
        )
        print(output.to_json())
        return 0

    # Phase 2: Create LLM client
    try:
        client = create_client()
    except EnvironmentError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Phase 3: Bottom-up description generation
    dir_count = 0
    file_count = 0

    for dir_node in walk_bottom_up(tree):
        # Describe file children
        file_children = [c for c in (dir_node.children or []) if c.type == "file"]
        if file_children:
            if args.verbose:
                print(
                    f"  Describing {len(file_children)} file(s) in {dir_node.path}/",
                    file=sys.stderr,
                )
            describe_files_batch(
                client, file_children, root_path, model=args.model, max_words=args.max_words
            )
            file_count += len(file_children)

        # Describe the directory (subdirs already described from deeper levels)
        if args.verbose:
            print(f"  Describing directory: {dir_node.path}/", file=sys.stderr)
        describe_directory(client, dir_node, model=args.model, max_words=args.max_words)
        dir_count += 1

    # Phase 4: Write output
    output = DescriptionOutput(
        root=root_path,
        generated_at=datetime.now(timezone.utc).isoformat(),
        model=args.model,
        tree=tree,
    )

    output_path = args.output or os.path.join(root_path, OUTPUT_FILENAME)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(output.to_json())

    if args.verbose:
        print(
            f"\nDone. Described {file_count} files and {dir_count} directories.",
            file=sys.stderr,
        )
        print(f"Output written to: {output_path}", file=sys.stderr)

    return 0
