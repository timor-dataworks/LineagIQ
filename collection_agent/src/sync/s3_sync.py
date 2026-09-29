import os
from pathlib import Path
from typing import Any


class S3Uploader:
    """
    S3 Uploader for direct lake sync of columnar Parquet dataset files and vector index artifacts.

    Uploads local artifact files to S3 data lake paths:
    `s3://<bucket>/<prefix>/...`
    """

    def __init__(
        self,
        bucket: str | None = None,
        prefix: str = "",
        s3_client: Any | None = None,
    ):
        """
        Initializes S3Uploader.

        :param bucket: Optional target S3 bucket name (defaults to env `LINEAGIQ_S3_BUCKET`).
        :param prefix: Optional target S3 key prefix.
        :param s3_client: Optional boto3 S3 client instance.
        """
        self.bucket = bucket or os.getenv("LINEAGIQ_S3_BUCKET", "control-plane-lake")
        self.prefix = prefix
        self.s3_client = s3_client

        if not self.s3_client:
            try:
                import boto3

                self.s3_client = boto3.client("s3")
            except Exception:
                self.s3_client = None

    def upload_file(self, local_path: str, s3_key: str) -> bool:
        """
        Uploads a single local file to S3 under the prefix (`<prefix>/<s3_key>`).

        :param local_path: Absolute local file path.
        :param s3_key: Relative S3 key path.
        :return: True if upload succeeded, False if boto3 S3 client is unavailable.
        """
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Local artifact file not found: {local_path}")

        full_key = os.path.join(self.prefix, s3_key.lstrip("/")).lstrip("/")

        if self.s3_client:
            self.s3_client.upload_file(local_path, self.bucket, full_key)
            return True
        return False

    def sync_directory(self, local_dir: str, prefix: str = "") -> list[str]:
        """
        Recursively uploads all Parquet and vector artifact files from a local directory to S3.

        :param local_dir: Absolute path to local artifact directory.
        :param prefix: Optional prefix to prepend to S3 keys.
        :return: List of output S3 URIs (`s3://<bucket>/<prefix>/...`).
        """
        uploaded_keys = []
        base_path = Path(local_dir)

        if not base_path.exists():
            raise FileNotFoundError(f"Directory not found: {local_dir}")

        eff_prefix = os.path.join(self.prefix, prefix).lstrip("/") if prefix else self.prefix.lstrip("/")

        for file_path in base_path.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(base_path)
                s3_key = os.path.join(eff_prefix, str(rel_path)) if eff_prefix else str(rel_path)
                self.upload_file(str(file_path), s3_key)
                uploaded_keys.append(f"s3://{self.bucket}/{s3_key}")

        return uploaded_keys


class S3Downloader:
    """
    S3 Downloader for retrieving Delta Lake and Parquet datasets from S3.

    Downloads artifacts from S3 data lake paths:
    `s3://<bucket>/<prefix>/...` to local filesystem directories.
    """

    def __init__(
        self,
        bucket: str | None = None,
        prefix: str = "",
        s3_client: Any | None = None,
    ):
        """
        Initializes S3Downloader.

        :param bucket: Optional target S3 bucket name (defaults to env `LINEAGIQ_S3_BUCKET`).
        :param prefix: Optional S3 key prefix.
        :param s3_client: Optional boto3 S3 client instance.
        """
        self.bucket = bucket or os.getenv("LINEAGIQ_S3_BUCKET", "control-plane-lake")
        self.prefix = prefix
        self.s3_client = s3_client

        if not self.s3_client:
            try:
                import boto3

                self.s3_client = boto3.client("s3")
            except Exception:
                self.s3_client = None

    def download_file(self, s3_key: str, local_path: str) -> bool:
        """
        Downloads a single object from S3.

        :param s3_key: Relative S3 key path.
        :param local_path: Absolute destination local file path.
        :return: True if download succeeded, False if boto3 S3 client is unavailable.
        """
        full_key = os.path.join(self.prefix, s3_key.lstrip("/")).lstrip("/")
        if self.s3_client:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            self.s3_client.download_file(self.bucket, full_key, local_path)
            return True
        return False

    def download_directory(self, local_dir: str, prefix: str = "") -> list[str]:
        """
        Recursively downloads all artifact files (including Delta Lake logs and parquet files)
        from S3 into `local_dir`.

        :param local_dir: Absolute destination directory path.
        :param prefix: Optional subdirectory prefix under S3 prefix.
        :return: List of downloaded local absolute file paths.
        """
        if not self.s3_client:
            return []

        search_prefix = os.path.join(self.prefix, prefix).lstrip("/") if prefix else self.prefix.lstrip("/")
        if search_prefix and not search_prefix.endswith("/"):
            search_prefix += "/"

        downloaded_files = []
        paginator = self.s3_client.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=self.bucket, Prefix=search_prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                rel_path = key[len(search_prefix) :] if search_prefix else key
                dest_path = os.path.join(local_dir, rel_path)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                self.s3_client.download_file(self.bucket, key, dest_path)
                downloaded_files.append(dest_path)

        return downloaded_files
