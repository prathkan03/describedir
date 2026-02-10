"""File reading utilities with binary detection and truncation."""

import mimetypes
import os

from .config import MAX_FILE_SIZE_BYTES, TRUNCATED_READ_BYTES

# MIME prefixes that indicate binary content
_BINARY_MIME_PREFIXES = ("image/", "audio/", "video/", "application/octet-stream")


def is_binary_file(filepath: str) -> bool:
    """Check if a file is binary by reading a sample and checking for null bytes."""
    mime, _ = mimetypes.guess_type(filepath)
    if mime and any(mime.startswith(p) for p in _BINARY_MIME_PREFIXES):
        return True

    try:
        with open(filepath, "rb") as f:
            chunk = f.read(8192)
    except OSError:
        return True  # if we can't read it, treat as binary

    return b"\x00" in chunk


def read_file_content(
    filepath: str,
    max_bytes: int = MAX_FILE_SIZE_BYTES,
    truncate_to: int = TRUNCATED_READ_BYTES,
) -> tuple[str, bool]:
    """Read file contents as text.

    Returns (content_string, was_truncated).
    Raises ValueError for binary files.
    Raises UnicodeDecodeError for undecodable files.
    """
    size = os.path.getsize(filepath)
    was_truncated = size > max_bytes

    read_size = truncate_to if was_truncated else size

    with open(filepath, "r", encoding="utf-8", errors="strict") as f:
        content = f.read(read_size)

    return content, was_truncated


def get_file_size(filepath: str) -> int:
    """Return file size in bytes."""
    return os.path.getsize(filepath)
