"""
s3_storage.py
=============
AWS S3 storage utility for uploading and generating URLs for 3D models.
"""

import os
from functools import lru_cache
from typing import Optional
from urllib.parse import urlparse

try:
    import boto3
    from botocore.config import Config
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


@lru_cache(maxsize=2)
def get_s3_client(*, catalog: bool = False):
    """Initializes and returns a boto3 S3 client if credentials and library exist."""
    if boto3 is None:
        return None
    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        return None

    try:
        options = {}
        if catalog:
            # Catalog requests have a local fallback; avoid long SDK retries.
            # Leave upload/download client behavior unchanged.
            options["config"] = Config(
                connect_timeout=3,
                read_timeout=5,
                retries={"total_max_attempts": 1},
            )
        return boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION,
            **options,
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
            ExtraArgs={
                "ContentType": content_type,
                "CacheControl": "public, max-age=31536000, immutable",
            }
        )
        return get_public_s3_url(s3_key, target_bucket)
    except (ClientError, NoCredentialsError) as err:
        print(f"[ERROR] Failed to upload {local_path} to S3: {err}")
        return None


def generate_presigned_url(s3_key: str, expires_in: int = 86400, bucket: Optional[str] = None) -> Optional[str]:
    """Generates a temporary presigned URL for private S3 objects (default 24h)."""
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


def resolve_s3_url_to_presigned(url_or_key: Optional[str], expires_in: int = 86400) -> Optional[str]:
    """
    Takes an S3 URL or object key and returns a valid presigned URL.
    This resolves HTTP 403 Forbidden errors when fetching models from private S3 buckets.
    """
    if not url_or_key:
        return None

    s = str(url_or_key).strip()
    if not s:
        return None

    # CloudFront (and any other explicit non-S3 HTTPS URL) is already a
    # browser-ready delivery URL. Previously the generic ``endswith('.glb')``
    # branch treated the complete CDN URL as an S3 object key and generated an
    # invalid presigned URL for it.
    parsed_url = urlparse(s)
    if parsed_url.scheme in {"http", "https"} and "amazonaws.com" not in parsed_url.netloc:
        return s

    s3_key = None
    target_bucket = AWS_S3_BUCKET

    if "amazonaws.com" in s:
        parsed = urlparse(s)
        path = parsed.path.lstrip("/")
        host = parsed.netloc

        if host.startswith(f"{AWS_S3_BUCKET}.s3"):
            s3_key = path
        elif host.startswith("s3."):
            parts = path.split("/", 1)
            if len(parts) == 2:
                target_bucket = parts[0]
                s3_key = parts[1]
            else:
                s3_key = path
        else:
            parts = path.split("/", 1)
            if len(parts) == 2 and parts[0] == AWS_S3_BUCKET:
                s3_key = parts[1]
            else:
                s3_key = path
    elif s.startswith("outputs/") or s.endswith(".glb"):
        s3_key = s.lstrip("/")

    if s3_key:
        # Strip any query parameters (like previous expired signatures)
        s3_key = s3_key.split("?")[0]
        # When a CDN is configured, also migrate previously stored S3 URLs and
        # plain object keys to CloudFront at response time.
        if AWS_S3_PUBLIC_BASE_URL:
            return f"{AWS_S3_PUBLIC_BASE_URL.rstrip('/')}/{s3_key.lstrip('/')}"
        presigned = generate_presigned_url(s3_key, expires_in=expires_in, bucket=target_bucket)
        if presigned:
            return presigned
    return s


def configure_bucket_cors(bucket: Optional[str] = None) -> bool:
    """Ensures S3 bucket has CORS enabled so web browsers can fetch GLB models without CORS errors."""
    client = get_s3_client()
    target_bucket = bucket or AWS_S3_BUCKET
    if not client or not target_bucket:
        return False
    try:
        client.put_bucket_cors(
            Bucket=target_bucket,
            CORSConfiguration={
                'CORSRules': [
                    {
                        'AllowedHeaders': ['*'],
                        'AllowedMethods': ['GET', 'HEAD'],
                        'AllowedOrigins': ['*'],
                        'ExposeHeaders': ['ETag', 'Content-Range'],
                        'MaxAgeSeconds': 3000,
                    }
                ]
            }
        )
        print(f"[S3] Successfully applied CORS rules to S3 bucket '{target_bucket}'.")
        return True
    except Exception as e:
        print(f"[WARN] S3 put_bucket_cors failed: {e}")
        return False
