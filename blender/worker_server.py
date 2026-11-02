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
import hashlib
import re
import signal
import datetime as dt
import subprocess
import tempfile
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
BLENDER_GENERATION_TIMEOUT_SECONDS = int(os.getenv("BLENDER_GENERATION_TIMEOUT_SECONDS", "600"))
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_S3_PUBLIC_BASE_URL = os.getenv("AWS_S3_PUBLIC_BASE_URL", "")


def file_sha256(path: str) -> Optional[str]:
    """Returns a file digest used to detect a downloaded worker update."""
    if not os.path.isfile(path):
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# Capture the running code, rather than claiming a newly downloaded file is active.
WORKER_SHA256 = file_sha256(__file__)


def _output_text(value) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value or "")


def blender_failure_reason(returncode, stdout="", stderr="") -> str:
    """Blender prints Python tracebacks to stdout on some supported versions."""
    lines = (_output_text(stderr) + "\n" + _output_text(stdout)).splitlines()
    for line in reversed(lines):
        message = line.strip()
        if re.match(r"^(?:[A-Za-z_]\w*(?:Error|Exception)|Exception)(?::|$)", message):
            return message[:400]
    if returncode in (-9, 137):
        return "Blender was killed (SIGKILL). Possible memory exhaustion; check the container and kernel logs."
    if returncode in (-11, 139):
        return "Blender crashed with a segmentation fault. Check the saved Blender log."
    if isinstance(returncode, int) and returncode < 0:
        try:
            name = signal.Signals(-returncode).name
        except ValueError:
            name = str(-returncode)
        return f"Blender was terminated by signal {name}. Check the saved Blender log."
    for line in reversed(lines):
        if re.search(r"(?:\[ERROR\]|^Error:|^FATAL|Segmentation fault|out of memory)", line, re.I):
            return line.strip()[:400]
    return f"Blender exited with code {returncode}. Check its saved stdout and stderr log."


def _write_generation_log(house_id, status, elapsed_ms, stdout="", stderr="", returncode=None, reason=None):
    """Keep diagnostic output on the worker volume without recording environment secrets."""
    filename = f"{house_id}_{uuid.uuid4().hex[:8]}.log"
    header = {"house_id": house_id, "status": status, "returncode": returncode,
              "elapsed_ms": elapsed_ms, "generation_timeout_seconds": BLENDER_GENERATION_TIMEOUT_SECONDS,
              "worker_sha256": WORKER_SHA256, "created_at": dt.datetime.utcnow().isoformat() + "Z",
              "reason": reason}
    try:
        with open(os.path.join(OUTPUT_DIR, filename), "w", encoding="utf-8") as handle:
            handle.write(json.dumps(header, ensure_ascii=False) + "\n\n--- STDOUT ---\n")
            handle.write(_output_text(stdout))
            handle.write("\n\n--- STDERR ---\n")
            handle.write(_output_text(stderr))
        print(f"[WORKER] Blender diagnostic log: {os.path.join(OUTPUT_DIR, filename)}", flush=True)
        return filename
    except OSError as exc:
        print(f"[WARN] Could not save Blender diagnostic log: {exc}", flush=True)
        return None


def _print_failure_output(reason, stdout="", stderr=""):
    # The complete streams are on disk; keep container logs useful and bounded.
    print(f"[ERROR] Blender generation failed: {reason}\n--- STDOUT (tail) ---\n{_output_text(stdout)[-12000:]}"
          f"\n--- STDERR (tail) ---\n{_output_text(stderr)[-12000:]}", flush=True)


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
        print(f"[WARN] Failed to initialize S3 client: {e}", flush=True)
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
                "ContentType": "model/gltf-binary",
                "CacheControl": "public, max-age=31536000, immutable"
            }
        )
        if AWS_S3_PUBLIC_BASE_URL:
            return f"{AWS_S3_PUBLIC_BASE_URL.rstrip('/')}/{s3_key}"
        return f"https://{bucket}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
    except (ClientError, NoCredentialsError) as err:
        print(f"[ERROR] S3 upload failed: {err}", flush=True)
        return None


@app.route("/health", methods=["GET"])
def health_check():
    """Verifies that Blender can execute in background mode."""
    blender_version = "Unknown"
    healthy = False
    try:
        res = subprocess.run([BLENDER_BIN, "--version"], capture_output=True, text=True, timeout=10)
        blender_version = res.stdout.split("\n")[0] if res.returncode == 0 else "Blender error"
        healthy = res.returncode == 0
    except Exception as e:
        blender_version = f"Unavailable: {str(e)}"

    return jsonify({
        "status": "healthy" if healthy else "unhealthy",
        "blender_bin": BLENDER_BIN,
        "blender_version": blender_version,
        "s3_bucket": AWS_S3_BUCKET or "none (local serving)",
        "worker_dir": BLENDER_DIR,
        "generation_timeout_seconds": BLENDER_GENERATION_TIMEOUT_SECONDS,
        "worker_sha256": WORKER_SHA256,
        "worker_file_sha256": file_sha256(__file__),
        "restart_required": WORKER_SHA256 != file_sha256(__file__),
    }), 200 if healthy else 503


@app.route("/models/<path:filename>", methods=["GET"])
def serve_model(filename: str):
    """Serves locally generated GLB models when running without S3."""
    if not filename.lower().endswith(".glb"):
        return jsonify({"error": "Model not found"}), 404
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
    if not isinstance(payload, dict) or not payload:
        return jsonify({"error": "Invalid or missing JSON payload"}), 400

    # Accommodate either wrapped {"layout": {...}} or direct layout dictionary
    layout_data = payload.get("layout", payload)
    if not isinstance(layout_data, dict):
        return jsonify({"error": "A layout JSON object is required"}), 400

    house_id = layout_data.get("house_id") or f"house_{uuid.uuid4().hex[:8]}"
    if not isinstance(house_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}", house_id):
        return jsonify({"error": "house_id must be a safe identifier of at most 160 characters"}), 400
    input_file = os.path.join(INPUT_DIR, f"{house_id}.json")
    output_filename = f"{house_id}.glb"
    output_file = os.path.join(OUTPUT_DIR, output_filename)

    # Save incoming layout JSON
    with open(input_file, "w", encoding="utf-8") as f:
        json.dump(layout_data, f, indent=2)

    cmd = [
        BLENDER_BIN,
        "--background",
        "--factory-startup",
        "--python-exit-code", "1",
        "--python", GENERATE_SCRIPT,
        "--",
        "--input", input_file,
        "--output", output_file
    ]

    print(f"[WORKER] Starting Blender generation for {house_id} (limit {BLENDER_GENERATION_TIMEOUT_SECONDS}s)...", flush=True)
    start_time = time.time()
    try:
        # Keep Blender's texture-export scratch files on the worker volume. On
        # Windows and hardened containers, the process-global temp directory can
        # be inaccessible during glTF cleanup and otherwise looks like a timeout.
        with tempfile.TemporaryDirectory(prefix=f"{house_id}_", dir=OUTPUT_DIR) as blender_temp:
            process_env = os.environ.copy()
            process_env["TEMP"] = blender_temp
            process_env["TMP"] = blender_temp
            process_env["TMPDIR"] = blender_temp
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=BLENDER_GENERATION_TIMEOUT_SECONDS,
                env=process_env,
            )
        elapsed_ms = int((time.time() - start_time) * 1000)
        reason = blender_failure_reason(proc.returncode, proc.stdout, proc.stderr) if proc.returncode else None
        if proc.returncode == 0 and not os.path.exists(output_file):
            reason = "Blender exited successfully without creating the requested GLB file."
        log_file = _write_generation_log(house_id, "failed" if reason else "completed", elapsed_ms,
                                          proc.stdout, proc.stderr, proc.returncode, reason)

        if proc.returncode != 0:
            _print_failure_output(reason, proc.stdout, proc.stderr)
            return jsonify({
                "error": "Blender generation process failed",
                "reason": reason,
                "returncode": proc.returncode,
                "log_file": log_file,
                "details": proc.stderr[-2000:],
                "stdout": proc.stdout[-1000:]
            }), 500

    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.time() - start_time) * 1000)
        reason = f"Blender generation timed out (limit: {BLENDER_GENERATION_TIMEOUT_SECONDS}s)"
        stdout, stderr = _output_text(exc.stdout), _output_text(exc.stderr)
        log_file = _write_generation_log(house_id, "timed_out", elapsed_ms, stdout, stderr, reason=reason)
        _print_failure_output(reason, stdout, stderr)
        return jsonify({
            "error": reason, "reason": reason, "log_file": log_file,
            "stdout": stdout[-1500:], "details": stderr[-2000:],
        }), 504
    except Exception as e:
        reason = f"{type(e).__name__}: {e}"
        elapsed_ms = int((time.time() - start_time) * 1000)
        log_file = _write_generation_log(house_id, "failed", elapsed_ms, reason=reason)
        _print_failure_output(reason)
        return jsonify({"error": "Failed to execute Blender", "reason": reason[:400], "log_file": log_file}), 500

    if not os.path.exists(output_file):
        return jsonify({
            "error": "Output GLB file was not created by Blender",
            "reason": "Blender exited successfully without creating the requested GLB file.",
            "log_file": log_file,
            "returncode": proc.returncode,
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
        "log_file": log_file,
        "s3_uploaded": bool(AWS_S3_BUCKET and "amazonaws.com" in glb_url)
    })


@app.route("/sync-assets", methods=["POST"])
def sync_assets_endpoint():
    """Downloads assets/scripts and reports when this worker needs a restart."""
    data = request.get_json(silent=True) or {}
    direction = data.get("direction", "download")
    bucket = data.get("bucket") or AWS_S3_BUCKET
    force = bool(data.get("force", False))

    if not bucket:
        return jsonify({"error": "No AWS_S3_BUCKET specified"}), 400

    sync_script = os.path.join(SCRIPTS_DIR, "sync_s3_assets.py")
    cmd = [sys.executable, sync_script, "--direction", direction, "--bucket", bucket]
    if force:
        cmd.append("--force")
    worker_path = os.path.abspath(__file__)
    worker_digest_before = file_sha256(worker_path)

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        worker_digest_after = file_sha256(worker_path)
        worker_updated = (
            direction == "download"
            and res.returncode == 0
            and worker_digest_before != worker_digest_after
        )
        return jsonify({
            "success": res.returncode == 0,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "worker_server_updated": worker_updated,
            "restart_required": worker_updated,
            "message": (
                "worker_server.py was updated; restart the worker container "
                "to activate it."
                if worker_updated
                else "Sync completed; the running worker server is unchanged."
            ),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print(f"ArchGen Blender Worker starting on port {PORT} (generation limit {BLENDER_GENERATION_TIMEOUT_SECONDS}s)...", flush=True)
    app.run(host="0.0.0.0", port=PORT, debug=False)
