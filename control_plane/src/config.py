import os
from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"
STATIC_INDEX_FILE = STATIC_DIR / "index.html"


def resolve_data_path() -> str:
    """Resolves data path strictly from the DATA_PATH environment variable.

    DATA_PATH must be set in the environment. Client requests, CLI flags,
    web GUI inputs, and hardcoded default fallbacks are strictly prohibited.

    Returns:
        Configured directory or S3 path string for datasets.

    Raises:
        ValueError: If DATA_PATH environment variable is missing.
    """
    env_dir = os.getenv("DATA_PATH")
    if not env_dir:
        raise ValueError("DATA_PATH environment variable must be set.")

    return env_dir
