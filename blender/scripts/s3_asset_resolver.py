"""
s3_asset_resolver.py
====================
Resolves and downloads 3D furniture models and textures from Amazon S3 on-demand.
Used during Headless Blender procedural generation when assets are not cached locally.
"""

import os
import sys
import json
import re
import tempfile
from urllib.parse import unquote, urlsplit
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
    base_dir = os.path.realpath(base_blender_dir or os.path.join(os.path.dirname(__file__), ".."))
    try:
        local_path = _contained_path(base_dir, str(rel_model_path).replace("\\", "/"))
        return ensure_model_ready(local_path, base_blender_dir=base_dir, bucket_name=bucket_name)
    except (AssetDependencyError, OSError, ValueError) as exc:
        print(f"[S3Resolver] {exc}", flush=True)
        return None


class AssetDependencyError(RuntimeError):
    """A referenced asset cannot be imported completely from the local/S3 bundle."""


def _contained_path(root, relative):
    if not relative or os.path.isabs(relative) or re.match(r"^[A-Za-z]:", relative):
        raise AssetDependencyError("Asset paths must be relative to the Blender asset workspace.")
    path = os.path.realpath(os.path.join(root, *relative.split("/")))
    if os.path.commonpath([root, path]) != root:
        raise AssetDependencyError("Asset dependency path leaves the Blender asset workspace.")
    return path


def _usable_file(path, minimum_size=1):
    return os.path.isfile(path) and os.path.getsize(path) >= minimum_size


def _workspace_for_model(path):
    parent = os.path.dirname(os.path.realpath(path))
    current = parent
    while os.path.dirname(current) != current:
        if os.path.basename(current).lower() == "assets":
            return os.path.dirname(current)
        current = os.path.dirname(current)
    return parent


def _source_glb(path):
    """Find the same authored model, including resolution-only exported variants."""
    directory = os.path.dirname(path)
    if not os.path.isdir(directory):
        return None
    stem = os.path.splitext(os.path.basename(path))[0].casefold()
    source_stem = re.sub(r"_(?:1k|2k|4k|8k|16k)$", "", stem)
    for desired in dict.fromkeys([stem, source_stem]):
        for name in sorted(os.listdir(directory)):
            candidate_stem, extension = os.path.splitext(name)
            candidate = os.path.join(directory, name)
            if extension.lower() == ".glb" and candidate_stem.casefold() == desired and _usable_file(candidate):
                return candidate
    return None


def _download_file(path, workspace, bucket, minimum_size=1):
    if _usable_file(path, minimum_size):
        return True
    client = get_s3_client()
    if client is None:
        return False
    relative = os.path.relpath(path, workspace).replace("\\", "/")
    keys = [relative, relative[7:] if relative.startswith("assets/") else f"assets/{relative}"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for key in dict.fromkeys(keys):
        # Never let a failed or interrupted transfer turn into a valid cache hit.
        temporary = None
        try:
            handle = tempfile.NamedTemporaryFile(prefix=".asset-", suffix=".tmp", dir=os.path.dirname(path), delete=False)
            temporary = handle.name
            handle.close()
            print(f"[S3Resolver] Downloading s3://{bucket}/{key}", flush=True)
            client.download_file(bucket, key, temporary)
            if _usable_file(temporary, minimum_size):
                os.replace(temporary, path)
                return True
        except Exception as exc:
            response = getattr(exc, "response", {})
            if str(response.get("Error", {}).get("Code")) not in ("404", "NoSuchKey", "NotFound"):
                print(f"[S3Resolver] Failed to download {key}: {exc}", flush=True)
        finally:
            if temporary and os.path.isfile(temporary):
                os.unlink(temporary)
    return False


def _gltf_dependencies(path, workspace):
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            document = json.load(handle)
    except (OSError, ValueError) as exc:
        raise AssetDependencyError(f"Invalid glTF model '{os.path.basename(path)}': {exc}") from exc
    if not isinstance(document, dict):
        raise AssetDependencyError(f"Invalid glTF model '{os.path.basename(path)}': expected a JSON object.")
    dependencies = {}
    asset_root = os.path.join(workspace, "assets")
    boundary = asset_root if os.path.isdir(asset_root) and os.path.commonpath([asset_root, path]) == asset_root else workspace
    for kind in ("buffers", "images"):
        entries = document.get(kind, [])
        if not isinstance(entries, list):
            raise AssetDependencyError(f"Invalid glTF '{os.path.basename(path)}': {kind} must be an array.")
        for item in entries:
            uri = item.get("uri") if isinstance(item, dict) else None
            if not uri:
                continue
            if not isinstance(uri, str):
                raise AssetDependencyError(f"Invalid glTF {kind} URI in '{os.path.basename(path)}'.")
            parts = urlsplit(uri)
            if parts.scheme.lower() == "data":
                continue
            if parts.scheme or parts.netloc:
                raise AssetDependencyError(f"glTF dependency '{uri}' must use an embedded or relative URI.")
            decoded = unquote(parts.path).replace("\\", "/")
            relative = os.path.relpath(os.path.dirname(path), boundary).replace("\\", "/") + "/" + decoded
            if decoded.startswith("/") or re.match(r"^[A-Za-z]:", decoded):
                raise AssetDependencyError("glTF dependencies must remain inside the asset workspace.")
            dependency = _contained_path(boundary, relative)
            try:
                minimum_size = max(1, int(item.get("byteLength", 1))) if kind == "buffers" else 1
            except (ValueError, TypeError) as exc:
                raise AssetDependencyError(f"Invalid buffer byteLength in glTF '{os.path.basename(path)}'.") from exc
            dependencies[dependency] = max(minimum_size, dependencies.get(dependency, 1))
    return dependencies


def ensure_model_ready(file_path, base_blender_dir=None, bucket_name=None):
    """Resolve external glTF buffers/images even when its JSON file is cached."""
    path = os.path.realpath(file_path)
    workspace = os.path.realpath(base_blender_dir or _workspace_for_model(path))
    if os.path.commonpath([workspace, path]) != workspace:
        raise AssetDependencyError("The model is outside the Blender asset workspace.")
    bucket = bucket_name or DEFAULT_BUCKET
    gltf = os.path.splitext(path)[1].lower() == ".gltf"
    fallback = _source_glb(path) if gltf else None
    if fallback and not _usable_file(path):
        return fallback
    if not _usable_file(path) and not _download_file(path, workspace, bucket):
        if fallback:
            return fallback
        raise AssetDependencyError(f"Model file is unavailable locally or in S3: {path}")
    if not gltf:
        return path
    try:
        dependencies = _gltf_dependencies(path, workspace)
    except AssetDependencyError:
        if fallback:
            return fallback
        raise
    missing = [dependency for dependency, size in dependencies.items() if not _usable_file(dependency, size)]
    if missing and fallback:
        print(f"[S3Resolver] Incomplete glTF '{os.path.basename(path)}'; using its source GLB '{os.path.basename(fallback)}'.", flush=True)
        return fallback
    for dependency in missing:
        _download_file(dependency, workspace, bucket, dependencies[dependency])
    missing = [os.path.relpath(dependency, os.path.dirname(path)).replace("\\", "/")
               for dependency, size in dependencies.items() if not _usable_file(dependency, size)]
    if missing:
        raise AssetDependencyError(f"Incomplete glTF '{os.path.basename(path)}': missing external dependencies {', '.join(missing)}. Sync the complete asset folder or provide its source GLB.")
    return path
