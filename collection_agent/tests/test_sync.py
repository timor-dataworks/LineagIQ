import os
from unittest.mock import MagicMock
from collection_agent.src.sync.s3_sync import S3Uploader, S3Downloader


def test_s3_uploader_file(tmp_path):
    dummy_file = tmp_path / "data.parquet"
    dummy_file.write_text("parquet header data")

    mock_boto = MagicMock()
    uploader = S3Uploader(bucket="test-bucket", tenant_id="tenant_123", s3_client=mock_boto)

    success = uploader.upload_file(str(dummy_file), "graph/nodes/data.parquet")

    assert success is True
    mock_boto.upload_file.assert_called_once_with(
        str(dummy_file), "test-bucket", "tenants/tenant_123/graph/nodes/data.parquet"
    )


def test_s3_uploader_directory(tmp_path):
    sub_dir = tmp_path / "graph" / "nodes"
    sub_dir.mkdir(parents=True)
    file1 = sub_dir / "data.parquet"
    file1.write_text("data 1")

    mock_boto = MagicMock()
    uploader = S3Uploader(bucket="test-bucket", tenant_id="tenant_123", s3_client=mock_boto)

    uploaded_keys = uploader.sync_directory(str(tmp_path))

    assert len(uploaded_keys) == 1
    assert "s3://test-bucket/tenants/tenant_123/graph/nodes/data.parquet" in uploaded_keys[0]


def test_s3_downloader_file(tmp_path):
    dest_file = tmp_path / "downloaded.parquet"
    mock_boto = MagicMock()
    downloader = S3Downloader(bucket="test-bucket", tenant_id="tenant_123", s3_client=mock_boto)

    success = downloader.download_file("graph/nodes/data.parquet", str(dest_file))
    assert success is True
    mock_boto.download_file.assert_called_once_with(
        "test-bucket", "tenants/tenant_123/graph/nodes/data.parquet", str(dest_file)
    )


def test_s3_downloader_directory(tmp_path):
    mock_boto = MagicMock()
    paginator = MagicMock()
    paginator.paginate.return_value = [
        {"Contents": [{"Key": "tenants/tenant_123/graph/nodes/data.parquet"}]}
    ]
    mock_boto.get_paginator.return_value = paginator

    downloader = S3Downloader(bucket="test-bucket", tenant_id="tenant_123", s3_client=mock_boto)
    download_dir = tmp_path / "lake"
    downloaded = downloader.download_directory(str(download_dir))

    assert len(downloaded) == 1
    assert str(download_dir / "graph" / "nodes" / "data.parquet") in downloaded[0]
    mock_boto.download_file.assert_called_once()

