import os
from pathlib import Path
from typing import Dict, Any, List, Optional


class S3Uploader:
    """
    S3 Uploader for direct lake sync of columnar Parquet dataset files and vector index artifacts.

    Uploads local artifact files to multi-tenant S3 data lake paths:
    `s3://<bucket>/tenants/<tenant_id>/...`
    """

    def __init__(
        self,
        bucket: Optional[str] = None,
        tenant_id: Optional[str] = None,
        s3_client: Optional[Any] = None,
    ):
        """
        Initializes S3Uploader.

        :param bucket: Optional target S3 bucket name (defaults to env `LINEAGIQ_S3_BUCKET`).
        :param tenant_id: Optional LineagIQ tenant ID (defaults to env `LINEAGIQ_TENANT_ID`).
        :param s3_client: Optional boto3 S3 client instance.
        """
        self.bucket = bucket or os.getenv("LINEAGIQ_S3_BUCKET", "control-plane-lake")
        self.tenant_id = tenant_id or os.getenv("LINEAGIQ_TENANT_ID", "default_tenant")
        self.s3_client = s3_client

        if not self.s3_client:
            try:
                import boto3
                self.s3_client = boto3.client("s3")
            except Exception:
                self.s3_client = None

    def upload_file(self, local_path: str, s3_key: str) -> bool:
        """
        Uploads a single local file to S3 under the tenant prefix (`tenants/<tenant_id>/<s3_key>`).

        :param local_path: Absolute local file path.
        :param s3_key: Relative S3 key path.
        :return: True if upload succeeded, False if boto3 S3 client is unavailable.
        """
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Local artifact file not found: {local_path}")

        full_key = f"tenants/{self.tenant_id}/{s3_key.lstrip('/')}"

        if self.s3_client:
            self.s3_client.upload_file(local_path, self.bucket, full_key)
            return True
        return False

    def sync_directory(self, local_dir: str, prefix: str = "") -> List[str]:
        """
        Recursively uploads all Parquet and vector artifact files from a local directory to S3.

        :param local_dir: Absolute path to local artifact directory.
        :param prefix: Optional prefix to prepend to S3 keys.
        :return: List of output S3 URIs (`s3://<bucket>/tenants/<tenant_id>/...`).
        """
        uploaded_keys = []
        base_path = Path(local_dir)

        if not base_path.exists():
            raise FileNotFoundError(f"Directory not found: {local_dir}")

        for file_path in base_path.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(base_path)
                s3_key = os.path.join(prefix, str(rel_path)) if prefix else str(rel_path)
                self.upload_file(str(file_path), s3_key)
                uploaded_keys.append(f"s3://{self.bucket}/tenants/{self.tenant_id}/{s3_key}")

        return uploaded_keys
