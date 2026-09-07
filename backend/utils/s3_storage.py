"""
s3_storage.py
=============
AWS S3 storage utility for uploading and generating URLs for 3D models.
"""

import os
from typing import Optional

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    boto3 = None

from config import (
    AWS_ACCESS_KEY_ID,
    AWS_REGION,
    AWS_S3_BUCKET,
    AWS_S3_PUBLIC_BASE_URL,
    AWS_SECRET_ACCESS_KEY,
)


def get_s3_client():
    """Initializes and returns a boto3 S3 client if credentials and library exist."""
    if boto3 is None:
        return None
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        return None

    try:
        return boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION,
        )
    except Exception as e:
        print(f"[WARN] S3 client creation failed: {e}")
        return None


def get_public_s3_url(s3_key: str, bucket: Optional[str] = None) -> str:
    """Constructs the public HTTPS URL for an S3 object."""
    target_bucket = bucket or AWS_S3_BUCKET
    if AWS_S3_PUBLIC_BASE_URL:
        return f"{AWS_S3_PUBLIC_BASE_URL.rstrip('/')}/{s3_key.lstrip('/')}"
    return f"https://{target_bucket}.s3.{AWS_REGION}.amazonaws.com/{s3_key.lstrip('/')}"


def upload_file_to_s3(
    local_path: str,
    s3_key: str,
    content_type: str = "model/gltf-binary",
    bucket: Optional[str] = None
) -> Optional[str]:
    """
    Uploads a local file to S3 and returns the public URL.
    Returns None if upload fails or credentials are missing.
    """
    client = get_s3_client()
    target_bucket = bucket or AWS_S3_BUCKET

    if not client or not target_bucket:
        return None

    try:
        client.upload_file(
            local_path,
            target_bucket,
            s3_key,
            ExtraArgs={"ContentType": content_type}
        )
        return get_public_s3_url(s3_key, target_bucket)
    except (ClientError, NoCredentialsError) as err:
        print(f"[ERROR] Failed to upload {local_path} to S3: {err}")
        return None


def generate_presigned_url(s3_key: str, expires_in: int = 3600, bucket: Optional[str] = None) -> Optional[str]:
    """Generates a temporary presigned URL for private S3 objects."""
    client = get_s3_client()
    target_bucket = bucket or AWS_S3_BUCKET

    if not client or not target_bucket:
        return None

    try:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": target_bucket, "Key": s3_key},
            ExpiresIn=expires_in
        )
    except Exception as e:
        print(f"[ERROR] Presigned URL generation failed: {e}")
        return None
