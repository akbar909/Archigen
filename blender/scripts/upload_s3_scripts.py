"""Upload the current Blender Python scripts to Amazon S3.

The worker's asset-sync endpoint downloads Python files from
``s3://<bucket>/assets/scripts/``, so that is the default destination.

Examples (run from the repository root):

    # Preview files whose content differs from S3
    python blender/scripts/upload_s3_scripts.py --dry-run

    # Upload only new or changed files
    python blender/scripts/upload_s3_scripts.py

    # Upload selected files, even if their content is unchanged
    python blender/scripts/upload_s3_scripts.py --force --files generate_house.py import_asset.py

AWS settings are read from the process environment first, then from
``backend/gem_api.env`` for values that are not already set.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path
from typing import Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent


def load_project_env() -> None:
    """Load missing values from backend/gem_api.env without exposing secrets."""
    env_path = PROJECT_ROOT / "backend" / "gem_api.env"
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value:
            os.environ.setdefault(key, value)


load_project_env()

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
except ImportError:  # pragma: no cover - handled with a useful CLI error
    boto3 = None
    Config = None
    BotoCoreError = Exception
    ClientError = Exception
    NoCredentialsError = Exception


def normalize_prefix(prefix: str) -> str:
    """Return an S3 prefix with forward slashes and one trailing slash."""
    normalized = prefix.strip().strip("/").replace("\\", "/")
    return f"{normalized}/" if normalized else ""


def file_digest(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_scripts(requested_files: Iterable[str] | None) -> list[Path]:
    """Find Python files and keep explicitly requested paths inside SCRIPT_DIR."""
    if not requested_files:
        return sorted(
            path
            for path in SCRIPT_DIR.rglob("*.py")
            if "__pycache__" not in path.parts
        )

    scripts: list[Path] = []
    for requested in requested_files:
        candidate = (SCRIPT_DIR / requested).resolve()
        try:
            candidate.relative_to(SCRIPT_DIR)
        except ValueError as err:
            raise ValueError(f"File must be inside {SCRIPT_DIR}: {requested}") from err

        if not candidate.is_file():
            raise FileNotFoundError(f"Script does not exist: {candidate}")
        if candidate.suffix.lower() != ".py":
            raise ValueError(f"Only .py files can be uploaded: {candidate}")
        scripts.append(candidate)

    return sorted(set(scripts))


def remote_matches(s3_client, bucket: str, key: str, local_path: Path) -> bool:
    """Compare hashes, falling back to the ETag used by older uploads."""
    try:
        response = s3_client.head_object(Bucket=bucket, Key=key)
    except ClientError as err:
        code = str(err.response.get("Error", {}).get("Code", ""))
        if code in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise

    remote_sha256 = response.get("Metadata", {}).get("sha256")
    if remote_sha256:
        return remote_sha256 == file_digest(local_path, "sha256")

    # Python files use a single-part upload, whose ETag is the content MD5.
    etag = str(response.get("ETag", "")).strip('"')
    return bool(etag and "-" not in etag and etag == file_digest(local_path, "md5"))


def build_s3_client(region: str | None):
    if boto3 is None:
        raise RuntimeError("boto3 is required. Install it with: pip install boto3")

    return boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=region or os.getenv("AWS_REGION", "us-east-1"),
        config=Config(
            connect_timeout=10,
            read_timeout=30,
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upload new or changed blender/scripts Python files to S3."
    )
    parser.add_argument(
        "--bucket",
        default=os.getenv("AWS_S3_BUCKET", "archigen-storage"),
        help="Destination S3 bucket (default: AWS_S3_BUCKET or archigen-storage).",
    )
    parser.add_argument(
        "--prefix",
        default="assets/scripts/",
        help="Destination key prefix (default: assets/scripts/).",
    )
    parser.add_argument(
        "--region",
        default=os.getenv("AWS_REGION"),
        help="AWS region (default: AWS_REGION or us-east-1).",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        metavar="FILE",
        help="Upload only these paths relative to blender/scripts.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Upload every selected file without comparing it with S3.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be uploaded without changing S3.",
    )
    args = parser.parse_args()

    try:
        scripts = discover_scripts(args.files)
    except (FileNotFoundError, ValueError) as err:
        print(f"[ERROR] {err}", file=sys.stderr)
        return 2

    if not scripts:
        print("[ERROR] No Python scripts were found.", file=sys.stderr)
        return 2

    prefix = normalize_prefix(args.prefix)
    print("=== ArchGen S3 Script Upload ===")
    print(f"Bucket: s3://{args.bucket}/{prefix}")
    print(f"Selected: {len(scripts)} Python file(s)")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'UPLOAD'}")

    try:
        s3_client = build_s3_client(args.region)
    except Exception as err:
        print(f"[ERROR] Could not initialize S3 client: {err}", file=sys.stderr)
        return 1

    uploaded = 0
    unchanged = 0
    failed = 0

    for local_path in scripts:
        relative_path = local_path.relative_to(SCRIPT_DIR).as_posix()
        s3_key = f"{prefix}{relative_path}"
        destination = f"s3://{args.bucket}/{s3_key}"

        try:
            if not args.force and remote_matches(s3_client, args.bucket, s3_key, local_path):
                unchanged += 1
                print(f"[SKIP] unchanged: {relative_path}")
                continue

            if args.dry_run:
                uploaded += 1
                print(f"[WOULD UPLOAD] {relative_path} -> {destination}")
                continue

            sha256 = file_digest(local_path, "sha256")
            s3_client.upload_file(
                str(local_path),
                args.bucket,
                s3_key,
                ExtraArgs={
                    "ContentType": "text/x-python; charset=utf-8",
                    "CacheControl": "no-cache",
                    "Metadata": {"sha256": sha256},
                },
            )
            uploaded += 1
            print(f"[UPLOADED] {relative_path} -> {destination}")
        except (BotoCoreError, ClientError, NoCredentialsError, OSError) as err:
            failed += 1
            print(f"[ERROR] {relative_path}: {err}", file=sys.stderr)

    action = "Would upload" if args.dry_run else "Uploaded"
    print(f"Finished. {action}: {uploaded}; unchanged: {unchanged}; failed: {failed}.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
