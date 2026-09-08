"""
s3_asset_resolver.py
====================
Resolves and downloads 3D furniture models and textures from Amazon S3 on-demand.
Used during Headless Blender procedural generation when assets are not cached locally.
"""

import os
import sys
from typing import Optional

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    boto3 = None


def _load_env():
    """Loads environment variables from gem_api.env if present."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    possible_paths = [
        os.path.join(script_dir, "..", "..", "backend", "gem_api.env"),
        os.path.join(script_dir, "..", "gem_api.env"),
    ]
    for p in possible_paths:
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip().strip('"').strip("'")
                        if k and v and k not in os.environ:
                            os.environ[k] = v
            break


_load_env()

DEFAULT_BUCKET = os.getenv("AWS_S3_BUCKET", "archigen-storage")
_s3_client = None


def get_s3_client():
    """Lazily initializes and caches a boto3 S3 client."""
    global _s3_client
    if _s3_client is not None:
        return _s3_client

    if boto3 is None:
        return None

    try:
        _s3_client = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
        return _s3_client
    except Exception as e:
        print(f"[S3Resolver] Failed to create S3 client: {e}")
        return None


def download_asset_if_missing(
    rel_model_path: str,
    base_blender_dir: Optional[str] = None,
    bucket_name: Optional[str] = None
) -> Optional[str]:
    """
    Checks if a model file exists locally. If not, attempts to download it from S3.

    Args:
        rel_model_path: Relative path to model (e.g. 'assets/furniture/bedroom/bed_02.glb').
        base_blender_dir: Base directory for blender workspace.
        bucket_name: S3 bucket name (defaults to AWS_S3_BUCKET env var).

    Returns:
        Absolute local path to file if available/downloaded, or None if failed.
    """
    if not rel_model_path:
        return None

    norm_rel = rel_model_path.replace("\\", "/").lstrip("/")
    base_dir = base_blender_dir or os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    local_abs_path = os.path.join(base_dir, norm_rel)

    # 1. Already exists on local disk
    if os.path.isfile(local_abs_path) and os.path.getsize(local_abs_path) > 0:
        return local_abs_path

    # 2. Attempt download from S3
    client = get_s3_client()
    if client is None:
        print(f"[S3Resolver] boto3 client unavailable, cannot download {norm_rel} from S3.")
        return None

    bucket = bucket_name or DEFAULT_BUCKET

    # Try candidate S3 keys (with or without 'assets/' prefix)
    candidate_keys = [
        norm_rel,
        f"assets/{norm_rel}" if not norm_rel.startswith("assets/") else norm_rel[7:],
    ]

    os.makedirs(os.path.dirname(local_abs_path), exist_ok=True)

    for s3_key in candidate_keys:
        try:
            print(f"[S3Resolver] Downloading s3://{bucket}/{s3_key} -> {local_abs_path}...")
            client.download_file(bucket, s3_key, local_abs_path)
            if os.path.isfile(local_abs_path) and os.path.getsize(local_abs_path) > 0:
                print(f"[S3Resolver] Successfully downloaded {s3_key} ({os.path.getsize(local_abs_path)} bytes)")
                return local_abs_path
        except ClientError as e:
            err_code = e.response.get("Error", {}).get("Code")
            if err_code == "404" or err_code == "NoSuchKey":
                continue
            print(f"[S3Resolver] S3 ClientError downloading {s3_key}: {e}")
        except Exception as e:
            print(f"[S3Resolver] Unexpected error downloading {s3_key}: {e}")

    print(f"[S3Resolver] Could not find {norm_rel} in S3 bucket '{bucket}'.")
    return None
