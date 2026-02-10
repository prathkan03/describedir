"""OpenAI API interaction, prompt construction, and batching."""

import json
import os
import time

from openai import APIError, APITimeoutError, OpenAI, RateLimitError

from .config import (
    DEFAULT_FILE_MAX_WORDS,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    MAX_CHILDREN_PER_BATCH,
    MAX_FILE_SIZE_BYTES,
    TRUNCATED_READ_BYTES,
    OPENAI_BASE_URL,
)
from dotenv import load_dotenv
from .fileio import is_binary_file, read_file_content
from .schema import FileNode

import mimetypes


def create_client() -> OpenAI:
    """Create OpenAI client from OPENAI_API_KEY env var."""
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY environment variable is not set. "
            "Set it with: export OPENAI_API_KEY='sk-...'"
        )
    return OpenAI(api_key=api_key, base_url=OPENAI_BASE_URL)


def _call_llm(
    client: OpenAI,
    system_prompt: str,
    user_prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    max_retries: int = 3,
) -> str:
    """Call OpenAI Chat Completions API with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response.choices[0].message.content.strip()
        except RateLimitError:
            wait = 2**attempt * 5
            time.sleep(wait)
        except (APIError, APITimeoutError) as e:
            if attempt == max_retries - 1:
                raise RuntimeError(
                    f"OpenAI API error after {max_retries} attempts: {e}"
                )
            time.sleep(2**attempt)
    raise RuntimeError("Max retries exceeded for LLM call")


def _describe_single_file(
    client: OpenAI,
    node: FileNode,
    root_path: str,
    model: str = DEFAULT_MODEL,
    max_words: int = DEFAULT_FILE_MAX_WORDS,
) -> None:
    """Describe a single file via individual LLM call. Mutates node in place."""
    full_path = os.path.join(root_path, node.path.replace("/", os.sep))

    if is_binary_file(full_path):
        mime, _ = mimetypes.guess_type(full_path)
        node.description = f"Binary file ({mime or 'unknown type'})."
        node.skipped = True
        node.skip_reason = "binary_file"
        return

    try:
        content, was_truncated = read_file_content(full_path)
    except (UnicodeDecodeError, OSError) as e:
        node.description = f"Could not read file: {type(e).__name__}."
        node.skipped = True
        node.skip_reason = "encoding_error"
        return

    truncation_note = ""
    if was_truncated:
        truncation_note = (
            f"\n\n[NOTE: This file was truncated. "
            f"Original size: {node.size_bytes} bytes. "
            f"Only the first portion is shown.]"
        )

    system_prompt = (
        "You are a technical documentation assistant. "
        f"Given a file's path and contents, produce a single concise sentence "
        f"(max {max_words} words) describing what this file does or contains. "
        "Be specific and technical. Do not start with 'This file'."
    )

    user_prompt = f"File: {node.path}\n\n```\n{content}\n```{truncation_note}"

    node.description = _call_llm(client, system_prompt, user_prompt, model=model)
    node.skipped = False


def describe_files_batch(
    client: OpenAI,
    file_nodes: list[FileNode],
    root_path: str,
    model: str = DEFAULT_MODEL,
    max_words: int = DEFAULT_FILE_MAX_WORDS,
) -> None:
    """Describe multiple files, batching readable ones into single LLM calls."""
    batchable: list[tuple[FileNode, str, bool]] = []

    for node in file_nodes:
        full_path = os.path.join(root_path, node.path.replace("/", os.sep))

        if is_binary_file(full_path):
            mime, _ = mimetypes.guess_type(full_path)
            node.description = f"Binary file ({mime or 'unknown type'})."
            node.skipped = True
            node.skip_reason = "binary_file"
            continue

        try:
            content, was_truncated = read_file_content(full_path)
        except (UnicodeDecodeError, OSError):
            node.description = "Could not read file."
            node.skipped = True
            node.skip_reason = "encoding_error"
            continue

        batchable.append((node, content, was_truncated))

    if not batchable:
        return

    for i in range(0, len(batchable), MAX_CHILDREN_PER_BATCH):
        chunk = batchable[i : i + MAX_CHILDREN_PER_BATCH]
        _describe_batch_chunk(client, chunk, root_path, model, max_words)


def _describe_batch_chunk(
    client: OpenAI,
    chunk: list[tuple[FileNode, str, bool]],
    root_path: str,
    model: str,
    max_words: int,
) -> None:
    """Send a batch of files to the LLM and parse JSON response."""
    # If only one file, just use single-file path
    if len(chunk) == 1:
        node, _, _ = chunk[0]
        _describe_single_file(client, node, root_path, model, max_words)
        return

    system_prompt = (
        "You are a technical documentation assistant. "
        "You will be given multiple files with their paths and contents. "
        f"For each file, produce a concise description (max {max_words} words). "
        "Be specific and technical. Do not start descriptions with 'This file'. "
        "Return your answer as a JSON object mapping file paths to descriptions. "
        'Example: {"src/app.py": "Flask application entry point...", ...}'
    )

    parts = []
    for node, content, was_truncated in chunk:
        trunc_note = " [TRUNCATED]" if was_truncated else ""
        parts.append(f"=== File: {node.path}{trunc_note} ===\n{content}\n")

    user_prompt = "\n".join(parts)

    raw_response = _call_llm(client, system_prompt, user_prompt, model=model)

    # Parse JSON response
    try:
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
        descriptions = json.loads(cleaned)
    except (json.JSONDecodeError, IndexError):
        # Fallback: describe each file individually
        for node, _, _ in chunk:
            _describe_single_file(client, node, root_path, model, max_words)
        return

    for node, _, _ in chunk:
        if node.path in descriptions:
            node.description = descriptions[node.path]
            node.skipped = False
        else:
            # File not in response -- fall back to individual call
            _describe_single_file(client, node, root_path, model, max_words)


def describe_directory(
    client: OpenAI,
    dir_node: FileNode,
    model: str = DEFAULT_MODEL,
    max_words: int = DEFAULT_FILE_MAX_WORDS,
) -> None:
    """Generate a directory description from its children's descriptions."""
    dir_max_words = max_words + 10

    if not dir_node.children:
        dir_node.description = "Empty directory."
        return

    children_info = []
    for child in dir_node.children:
        prefix = "[dir]" if child.type == "directory" else "[file]"
        children_info.append(f"  {prefix} {child.name}: {child.description}")

    children_text = "\n".join(children_info)

    system_prompt = (
        "You are a technical documentation assistant. "
        "Given a directory name and descriptions of its immediate children, "
        f"produce a single concise sentence (max {dir_max_words} words) summarizing "
        "the purpose and contents of this directory. "
        "Be specific. Do not start with 'This directory'."
    )

    user_prompt = f"Directory: {dir_node.path}/\n\nContents:\n{children_text}"

    dir_node.description = _call_llm(client, system_prompt, user_prompt, model=model)
