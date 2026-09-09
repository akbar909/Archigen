"""
sync_s3_assets.py
==================
Utility to synchronize 3D assets (GLB models, textures, and metadata)
between local disk and Amazon S3.

Usage:
  # Upload local assets to S3
  python sync_s3_assets.py --direction upload --bucket my-archigen-storage

  # Download remote assets from S3 to local folder
  python sync_s3_assets.py --direction download --bucket my-archigen-storage

  # Dry run (list files without transferring)
  python sync_s3_assets.py --dry-run
"""

import os
import sys
import argparse
from typing import Optional

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    boto3 = None


def _load_env():
    """Attempts to load AWS credentials from backend/gem_api.env if present."""
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


def get_s3_client(
    aws_access_key: Optional[str] = None,
    aws_secret_key: Optional[str] = None,
    region: Optional[str] = None
):
    """Initializes and returns a boto3 S3 client."""
    if boto3 is None:
        raise ImportError("boto3 is not installed. Please run 'pip install boto3'.")

    return boto3.client(
        "s3",
        aws_access_key_id=aws_access_key or os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=aws_secret_key or os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=region or os.getenv("AWS_REGION", "us-east-1")
    )


def upload_assets(
    blender_dir: str,
    bucket_name: str,
    s3_prefix: str = "assets/",
    dry_run: bool = False,
    s3_client=None
) -> int:
    """
    Uploads local furniture, doors, windows, textures, metadata, and scripts to S3.
    Target directories:
      - blender/assets/furniture/ -> s3://bucket/assets/furniture/
      - blender/assets/doors/     -> s3://bucket/assets/doors/
      - blender/assets/windows/   -> s3://bucket/assets/windows/
      - blender/assets/textures/  -> s3://bucket/assets/textures/
      - blender/metadata/         -> s3://bucket/assets/metadata/
      - blender/scripts/          -> s3://bucket/assets/scripts/
    """
    if s3_client is None:
        s3_client = get_s3_client()

    upload_count = 0
    folders_to_upload = [
        (os.path.join(blender_dir, "assets", "furniture"), f"{s3_prefix}furniture/"),
        (os.path.join(blender_dir, "assets", "doors"), f"{s3_prefix}doors/"),
        (os.path.join(blender_dir, "assets", "windows"), f"{s3_prefix}windows/"),
        (os.path.join(blender_dir, "assets", "textures"), f"{s3_prefix}textures/"),
        (os.path.join(blender_dir, "metadata"), f"{s3_prefix}metadata/"),
        (os.path.join(blender_dir, "scripts"), f"{s3_prefix}scripts/"),
    ]

    for local_folder, remote_prefix in folders_to_upload:
        if not os.path.exists(local_folder):
            print(f"[WARN] Local directory does not exist: {local_folder}")
            continue

        for root, _, files in os.walk(local_folder):
            for file in files:
                if file == ".gitkeep" or file.endswith(".tmp") or file.endswith(".pyc") or "__pycache__" in root:
                    continue

                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, local_folder).replace("\\", "/")
                s3_key = f"{remote_prefix}{rel_path}"

                content_type = (
                    "model/gltf-binary" if file.endswith(".glb") else
                    "model/gltf+json" if file.endswith(".gltf") else
                    "image/jpeg" if file.lower().endswith((".jpg", ".jpeg")) else
                    "image/png" if file.lower().endswith(".png") else
                    "application/json" if file.endswith(".json") else
                    "text/x-python" if file.endswith(".py") else
                    "application/octet-stream"
                )

                print(f"[UPLOAD] {abs_path} -> s3://{bucket_name}/{s3_key}")
                if not dry_run:
                    try:
                        s3_client.upload_file(
                            abs_path,
                            bucket_name,
                            s3_key,
                            ExtraArgs={"ContentType": content_type}
                        )
                        upload_count += 1
                    except (ClientError, NoCredentialsError) as err:
                        print(f"[ERROR] Failed to upload {file}: {err}")
                else:
                    upload_count += 1

    return upload_count


def download_assets(
    blender_dir: str,
    bucket_name: str,
    s3_prefix: str = "assets/",
    dry_run: bool = False,
    s3_client=None
) -> int:
    """
    Downloads remote assets from S3 to local blender directories.
    """
    if s3_client is None:
        s3_client = get_s3_client()

    download_count = 0
    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket_name, Prefix=s3_prefix)

        for page in pages:
            for obj in page.get("Contents", []):
                s3_key = obj["Key"]
                if s3_key.endswith("/"):
                    continue

                rel_key = s3_key[len(s3_prefix):]
                if rel_key.startswith("metadata/"):
                    local_path = os.path.join(blender_dir, rel_key)
                elif rel_key.startswith("furniture/"):
                    local_path = os.path.join(blender_dir, "assets", rel_key)
                elif rel_key.startswith("scripts/"):
                    local_path = os.path.join(blender_dir, rel_key)
                else:
                    local_path = os.path.join(blender_dir, "assets", rel_key)

                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                print(f"[DOWNLOAD] s3://{bucket_name}/{s3_key} -> {local_path}")

                if not dry_run:
                    s3_client.download_file(bucket_name, s3_key, local_path)
                download_count += 1

    except (ClientError, NoCredentialsError) as err:
        print(f"[ERROR] S3 operation failed: {err}")

    return download_count


def main():
    parser = argparse.ArgumentParser(description="Sync 3D assets with AWS S3.")
    parser.add_argument(
        "--direction",
        choices=["upload", "download"],
        default="upload",
        help="Transfer direction: upload local assets to S3, or download from S3."
    )
    parser.add_argument(
        "--bucket",
        default=os.getenv("AWS_S3_BUCKET", "archigen-storage"),
        help="Target AWS S3 bucket name."
    )
    parser.add_argument(
        "--prefix",
        default="assets/",
        help="S3 Key prefix (default: assets/)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform dry run without uploading or downloading files."
    )
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    blender_dir = os.path.dirname(script_dir)

    print(f"=== ArchGen S3 Asset Sync ===")
    print(f"Mode: {args.direction.upper()} {'(DRY RUN)' if args.dry_run else ''}")
    print(f"Bucket: {args.bucket}")
    print(f"Blender Directory: {blender_dir}")

    if boto3 is None:
        print("[ERROR] boto3 is required. Run: pip install boto3")
        sys.exit(1)

    try:
        s3 = get_s3_client()
    except Exception as err:
        print(f"[WARN] S3 Client initialization warning: {err}")
        s3 = None

    if args.direction == "upload":
        count = upload_assets(blender_dir, args.bucket, args.prefix, dry_run=args.dry_run, s3_client=s3)
        print(f"Finished. Total assets uploaded/processed: {count}")
    else:
        count = download_assets(blender_dir, args.bucket, args.prefix, dry_run=args.dry_run, s3_client=s3)
        print(f"Finished. Total assets downloaded/processed: {count}")


if __name__ == "__main__":
    main()
