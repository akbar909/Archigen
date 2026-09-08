"""
worker_server.py
================
Lightweight HTTP worker microservice for Headless Blender 3D house generation.
Designed to run inside the Docker container on AWS EC2/ECS or locally.

Endpoints:
  GET  /health        - Health check and Blender CLI verification
  POST /generate      - Ingests layout JSON, runs procedural generation, uploads GLB to S3
  GET  /models/<file> - Serves local GLB files directly (fallback when S3 is not configured)
  POST /sync-assets   - Triggers S3 asset sync into container cache
"""

import os
import sys
import json
import time
import uuid
import subprocess
from typing import Optional

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    boto3 = None

# Root paths
BLENDER_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(BLENDER_DIR, "scripts")
INPUT_DIR = os.path.join(BLENDER_DIR, "input")
OUTPUT_DIR = os.path.join(BLENDER_DIR, "output")
GENERATE_SCRIPT = os.path.join(SCRIPTS_DIR, "generate_house.py")

os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Configuration from environment
PORT = int(os.getenv("PORT", 5001))
BLENDER_BIN = os.getenv("BLENDER_BIN", "blender")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_S3_PUBLIC_BASE_URL = os.getenv("AWS_S3_PUBLIC_BASE_URL", "")


def get_s3_client():
    """Returns an initialized S3 client if boto3 and credentials exist."""
    if boto3 is None:
        return None
    try:
        return boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=AWS_REGION
        )
    except Exception as e:
        print(f"[WARN] Failed to initialize S3 client: {e}")
        return None


def upload_glb_to_s3(local_path: str, s3_key: str, bucket: str) -> Optional[str]:
    """Uploads generated GLB to S3 and returns the public or presigned URL."""
    client = get_s3_client()
    if not client or not bucket:
        return None

    try:
        client.upload_file(
            local_path,
            bucket,
            s3_key,
            ExtraArgs={
                "ContentType": "model/gltf-binary"
            }
        )
        if AWS_S3_PUBLIC_BASE_URL:
            return f"{AWS_S3_PUBLIC_BASE_URL.rstrip('/')}/{s3_key}"
        return f"https://{bucket}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
    except (ClientError, NoCredentialsError) as err:
        print(f"[ERROR] S3 upload failed: {err}")
        return None


@app.route("/health", methods=["GET"])
def health_check():
    """Verifies that Blender can execute in background mode."""
    blender_version = "Unknown"
    try:
        res = subprocess.run([BLENDER_BIN, "--version"], capture_output=True, text=True, timeout=10)
        blender_version = res.stdout.split("\n")[0] if res.returncode == 0 else "Blender error"
    except Exception as e:
        blender_version = f"Unavailable: {str(e)}"

    return jsonify({
        "status": "healthy",
        "blender_bin": BLENDER_BIN,
        "blender_version": blender_version,
        "s3_bucket": AWS_S3_BUCKET or "none (local serving)",
        "worker_dir": BLENDER_DIR
    })


@app.route("/models/<path:filename>", methods=["GET"])
def serve_model(filename: str):
    """Serves locally generated GLB models when running without S3."""
    return send_from_directory(
        OUTPUT_DIR,
        filename,
        mimetype="model/gltf-binary",
        as_attachment=False
    )


@app.route("/generate", methods=["POST"])
def generate_house_endpoint():
    """
    Ingests layout JSON, invokes Blender Headless, and returns the GLB URL.
    """
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "Invalid or missing JSON payload"}), 400

    # Accommodate either wrapped {"layout": {...}} or direct layout dictionary
    layout_data = payload.get("layout", payload)

    house_id = layout_data.get("house_id") or f"house_{uuid.uuid4().hex[:8]}"
    input_file = os.path.join(INPUT_DIR, f"{house_id}.json")
    output_filename = f"{house_id}.glb"
    output_file = os.path.join(OUTPUT_DIR, output_filename)

    # Save incoming layout JSON
    with open(input_file, "w", encoding="utf-8") as f:
        json.dump(layout_data, f, indent=2)

    cmd = [
        BLENDER_BIN,
        "--background",
        "--python-exit-code", "1",
        "--python", GENERATE_SCRIPT,
        "--",
        "--input", input_file,
        "--output", output_file
    ]

    print(f"[WORKER] Starting Blender generation for {house_id}...")
    start_time = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        elapsed_ms = int((time.time() - start_time) * 1000)

        if proc.returncode != 0:
            print(f"[ERROR] Blender failed:\n{proc.stderr}")
            return jsonify({
                "error": "Blender generation process failed",
                "details": proc.stderr[-2000:],
                "stdout": proc.stdout[-1000:]
            }), 500

    except subprocess.TimeoutExpired:
        return jsonify({"error": "Blender generation timed out (limit: 180s)"}), 504
    except Exception as e:
        return jsonify({"error": f"Failed to execute Blender: {str(e)}"}), 500

    if not os.path.exists(output_file):
        return jsonify({
            "error": "Output GLB file was not created by Blender",
            "stdout": proc.stdout[-1500:],
            "stderr": proc.stderr[-1500:]
        }), 500

    file_size_bytes = os.path.getsize(output_file)

    # Upload to AWS S3 if bucket configured
    s3_key = f"outputs/houses/{output_filename}"
    glb_url = None
    if AWS_S3_BUCKET:
        glb_url = upload_glb_to_s3(output_file, s3_key, AWS_S3_BUCKET)

    # Fallback to local server URL
    if not glb_url:
        host_url = request.host_url.rstrip("/")
        glb_url = f"{host_url}/models/{output_filename}"

    return jsonify({
        "success": True,
        "house_id": house_id,
        "glb_url": glb_url,
        "file_size_bytes": file_size_bytes,
        "generation_time_ms": elapsed_ms,
        "s3_uploaded": bool(AWS_S3_BUCKET and "amazonaws.com" in glb_url)
    })


@app.route("/sync-assets", methods=["POST"])
def sync_assets_endpoint():
    """Calls S3 asset sync script to download models into local container."""
    data = request.get_json(silent=True) or {}
    direction = data.get("direction", "download")
    bucket = data.get("bucket") or AWS_S3_BUCKET

    if not bucket:
        return jsonify({"error": "No AWS_S3_BUCKET specified"}), 400

    sync_script = os.path.join(SCRIPTS_DIR, "sync_s3_assets.py")
    cmd = [sys.executable, sync_script, "--direction", direction, "--bucket", bucket]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return jsonify({
            "success": res.returncode == 0,
            "stdout": res.stdout,
            "stderr": res.stderr
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print(f"ArchGen Blender Worker starting on port {PORT}...")
    app.run(host="0.0.0.0", port=PORT, debug=False)
