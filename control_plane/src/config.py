import os
from pathlib import Path
from typing import Optional

STATIC_DIR = Path(__file__).parent / "static"
STATIC_INDEX_FILE = STATIC_DIR / "index.html"


def resolve_data_path(tenant_id: str, custom_path: Optional[str] = None) -> str:
    """Resolves local or S3 tenant data path with environment fallback.

    Args:
        tenant_id: Unique tenant identifier.
        custom_path: Optional explicit data path passed in API request.

    Returns:
        Resolved file or directory path string for tenant Parquet datasets.
    """
    return custom_path or os.getenv("TENANT_DATA_DIR", f"/tmp/tenants/{tenant_id}")
