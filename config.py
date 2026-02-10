"""Configuration constants for describedir."""

DEFAULT_IGNORE_PATTERNS: list[str] = [
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    ".nox",
    ".DS_Store",
    "Thumbs.db",
    ".env",
    "*.pyc",
    "*.pyo",
    "*.egg-info",
    ".describedir.json",
]

MAX_FILE_SIZE_BYTES: int = 100_000
TRUNCATED_READ_BYTES: int = 8_000

OPENAI_BASE_URL: str = "https://api.groq.com/openai/v1"
DEFAULT_MODEL: str = "openai/gpt-oss-20b"
DEFAULT_TEMPERATURE: float = 0.2
MAX_CHILDREN_PER_BATCH: int = 30

DEFAULT_FILE_MAX_WORDS: int = 30
DEFAULT_DIR_MAX_WORDS: int = 40

OUTPUT_FILENAME: str = ".describedir.json"
