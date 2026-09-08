import datetime as dt
import json
import logging
import threading

# pyrefly: ignore [missing-import]
from bson import ObjectId
from flask import Blueprint, jsonify, request

from utils.db import designs_collection, projects_collection, versions_collection
from utils.blender_service import generate_3d_house_model
from utils.s3_storage import resolve_s3_url_to_presigned
from utils.gemini import (
    GeminiSchemaValidationError,
    GeminiTemporaryUnavailableError,
    build_generation_prompt,
    generate_home_design,
    validate_architectural_prompt,
)
from utils.middleware import require_auth



chat_bp = Blueprint("chat", __name__)


# ─── helpers ─────────────────────────────────────────────────────────────────

def _serialize_project(doc, latest_version=None):
    return {
        "id":         str(doc["_id"]),
        "name":       doc.get("name", "Untitled Project"),
        "style":      doc.get("style", "modern"),
        "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
        "updated_at": doc["updated_at"].isoformat() if doc.get("updated_at") else None,
        "version_count": doc.get("version_count", 0),
        "latest_version": latest_version,
    }


def _serialize_version(doc):
    raw_glb = doc.get("glb_url") or (doc.get("design") or {}).get("glb_url")
    resolved_glb = resolve_s3_url_to_presigned(raw_glb)
    design = doc.get("design")
    if isinstance(design, dict) and resolved_glb:
        design = dict(design)
        design["glb_url"] = resolved_glb

    return {
        "id":          str(doc["_id"]),
        "project_id":  str(doc.get("project_id", "")),
        "base_version_id": str(doc.get("base_version_id")) if doc.get("base_version_id") else None,
        "version_num": doc.get("version_num", 1),
        "prompt":      doc.get("prompt", ""),
        "style":       doc.get("style", "modern"),
        "design":      design,
        "glb_url":     resolved_glb,
        "created_at":  doc["created_at"].isoformat() if doc.get("created_at") else None,
    }



# ─── PROJECTS ─────────────────────────────────────────────────────────────────

@chat_bp.get("/projects")
@require_auth
def list_projects():
    """Return all projects for the current user, newest first."""
    try:
        cursor = projects_collection().find(
            {"user_id": request.user["_id"]}
        ).sort("updated_at", -1)

        result = []
        for doc in cursor:
            # Fetch the latest version summary (prompt only, not full design)
            latest = versions_collection().find_one(
                {"project_id": doc["_id"]},
                sort=[("version_num", -1)],
                projection={"prompt": 1, "version_num": 1, "style": 1, "created_at": 1}
            )
            latest_summary = None
            if latest:
                latest_summary = {
                    "id":          str(latest["_id"]),
                    "version_num": latest.get("version_num", 1),
                    "prompt":      latest.get("prompt", ""),
                    "style":       latest.get("style", "modern"),
                    "created_at":  latest["created_at"].isoformat() if latest.get("created_at") else None,
                }
            result.append(_serialize_project(doc, latest_summary))

        return jsonify({"projects": result})
    except Exception as e:
        return jsonify({"error": "Failed to load projects"}), 500


@chat_bp.post("/projects")
@require_auth
def create_project():
    """Create a new empty project."""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "Untitled Project").strip()

    now = dt.datetime.utcnow()
    doc = {
        "user_id":       request.user["_id"],
        "name":          name,
        "style":         data.get("style", "modern"),
        "version_count": 0,
        "created_at":    now,
        "updated_at":    now,
    }
    result = projects_collection().insert_one(doc)
    doc["_id"] = result.inserted_id
    return jsonify({"success": True, "project": _serialize_project(doc)}), 201


@chat_bp.patch("/projects/<project_id>")
@require_auth
def rename_project(project_id: str):
    """Rename a project."""
    try:
        obj_id = ObjectId(project_id)
    except Exception:
        return jsonify({"error": "Invalid project id"}), 400

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    projects_collection().update_one(
        {"_id": obj_id, "user_id": request.user["_id"]},
        {"$set": {"name": name, "updated_at": dt.datetime.utcnow()}}
    )
    return jsonify({"success": True})


@chat_bp.delete("/projects/<project_id>")
@require_auth
def delete_project(project_id: str):
    """Delete a project and all its versions."""
    try:
        obj_id = ObjectId(project_id)
    except Exception:
        return jsonify({"error": "Invalid project id"}), 400

    projects_collection().delete_one({"_id": obj_id, "user_id": request.user["_id"]})
    versions_collection().delete_many({"project_id": obj_id, "user_id": request.user["_id"]})
    return jsonify({"success": True})


# ─── VERSIONS ─────────────────────────────────────────────────────────────────

@chat_bp.get("/projects/<project_id>/versions")
@require_auth
def list_versions(project_id: str):
    """List all versions for a project (no design data, just metadata)."""
    try:
        obj_id = ObjectId(project_id)
    except Exception:
        return jsonify({"error": "Invalid project id"}), 400

    cursor = versions_collection().find(
        {"project_id": obj_id, "user_id": request.user["_id"]},
        projection={"design": 0}   # exclude heavy design JSON
    ).sort("version_num", -1)

    items = [_serialize_version(doc) for doc in cursor]
    return jsonify({"versions": items})


@chat_bp.get("/versions/<version_id>")
@require_auth
def get_version(version_id: str):
    """Load a single version with full design data."""
    try:
        obj_id = ObjectId(version_id)
    except Exception:
        return jsonify({"error": "Invalid version id"}), 400

    doc = versions_collection().find_one(
        {"_id": obj_id, "user_id": request.user["_id"]}
    )
    if not doc:
        return jsonify({"error": "Version not found"}), 404

    return jsonify({"version": _serialize_version(doc)})


@chat_bp.post("/projects/<project_id>/generate")
@require_auth
def generate_version(project_id: str):
    """Generate a new version inside an existing project."""
    try:
        proj_id = ObjectId(project_id)
    except Exception:
        return jsonify({"error": "Invalid project id"}), 400

    project = projects_collection().find_one(
        {"_id": proj_id, "user_id": request.user["_id"]}
    )
    if not project:
        return jsonify({"error": "Project not found"}), 404

    data = request.get_json(silent=True) or {}
    prompt = data.get("prompt", "").strip()
    style  = data.get("style", project.get("style", "modern"))
    base_version_id = data.get("base_version_id")

    if not prompt:
        return jsonify({"error": "'prompt' is required"}), 400

    # Validate that prompt is about architecture/design
    is_valid_prompt, validation_error = validate_architectural_prompt(prompt)
    if not is_valid_prompt:
        return jsonify({"error": validation_error}), 400

    base_version = None
    if base_version_id:
        try:
            base_obj_id = ObjectId(base_version_id)
        except Exception:
            return jsonify({"error": "Invalid base_version_id"}), 400

        base_version = versions_collection().find_one({
            "_id": base_obj_id,
            "project_id": proj_id,
            "user_id": request.user["_id"],
        })
        if not base_version:
            return jsonify({"error": "Base version not found"}), 404
    else:
        # When refining without explicitly selecting a version, use latest version of the same project.
        base_version = versions_collection().find_one(
            {"project_id": proj_id, "user_id": request.user["_id"]},
            sort=[("version_num", -1)]
        )

    if base_version and base_version.get("design"):
        base_design_json = json.dumps(base_version["design"], ensure_ascii=True)
        generation_prompt = build_generation_prompt(
            f"{prompt}\nCurrent design JSON:\n{base_design_json}",
            style=style,
            base_design=base_version.get("design"),
        )
    else:
        generation_prompt = build_generation_prompt(prompt, style=style)

    try:
        design = generate_home_design(generation_prompt, timeout=120)
    except GeminiTemporaryUnavailableError as exc:
        return jsonify({"success": False, "error": str(exc)}), 503
    except GeminiSchemaValidationError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422
    except (ValueError, EnvironmentError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 502
    except Exception:
        return jsonify({"success": False, "error": "Internal server error."}), 500

    # Determine next version number
    last = versions_collection().find_one(
        {"project_id": proj_id},
        sort=[("version_num", -1)],
        projection={"version_num": 1}
    )
    next_num = (last["version_num"] + 1) if last else 1
    now = dt.datetime.utcnow()

    ver_doc = {
        "project_id": proj_id,
        "user_id":    request.user["_id"],
        "base_version_id": base_version.get("_id") if base_version else None,
        "version_num": next_num,
        "prompt":     prompt,
        "style":      style,
        "design":     design,
        "glb_url":     None,
        "created_at": now,
    }
    ver_result = versions_collection().insert_one(ver_doc)
    ver_id = ver_result.inserted_id
    ver_doc["_id"] = ver_id

    # Update project metadata
    projects_collection().update_one(
        {"_id": proj_id},
        {"$set": {
            "style":         style,
            "version_count": next_num,
            "updated_at":    now,
        }}
    )

    # Launch Blender 3D procedural generation in background thread
    def _bg_generate_blender(d_copy, p_id_str, v_obj_id, v_num):
        try:
            g_url = generate_3d_house_model(d_copy, project_id=p_id_str, version_num=v_num)
            if g_url:
                versions_collection().update_one(
                    {"_id": v_obj_id},
                    {"$set": {"glb_url": g_url, "design.glb_url": g_url}}
                )
        except Exception as e:
            logging.error(f"[BLENDER] Background generation error: {e}")

    threading.Thread(
        target=_bg_generate_blender,
        args=(design, str(proj_id), ver_id, next_num),
        daemon=True,
    ).start()

    return jsonify({
        "success": True,
        "version": _serialize_version(ver_doc),
    }), 200


# ─── LEGACY flat-design routes (kept for backward compatibility) ──────────────

@chat_bp.post("/chat")
@require_auth
def generate_design_legacy():
    """
    Legacy endpoint — creates a new project automatically from the prompt
    and saves the design as Version 1 of that project.
    This keeps the old frontend working while we migrate.
    """
    data = request.get_json(silent=True) or {}
    prompt = data.get("prompt", "").strip()
    style  = data.get("style", "modern")
    timeout = data.get("timeout", 120)

    if not prompt:
        return jsonify({"error": "'prompt' is required and must be a non-empty string."}), 400

    if not isinstance(timeout, int) or timeout < 5 or timeout > 240:
        timeout = 120

    try:
        design = generate_home_design(build_generation_prompt(prompt, style=style), timeout=timeout)
    except GeminiTemporaryUnavailableError as exc:
        return jsonify({"success": False, "error": str(exc)}), 503
    except GeminiSchemaValidationError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422
    except (ValueError, EnvironmentError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 502
    except Exception:
        return jsonify({"success": False, "error": "Internal server error."}), 500

    now = dt.datetime.utcnow()

    # Auto-create a project from the prompt title
    project_name = (prompt[:48] + "…") if len(prompt) > 48 else prompt
    proj_doc = {
        "user_id":       request.user["_id"],
        "name":          project_name,
        "style":         style,
        "version_count": 1,
        "created_at":    now,
        "updated_at":    now,
    }
    proj_result = projects_collection().insert_one(proj_doc)
    proj_id = proj_result.inserted_id

    ver_doc = {
        "project_id":  proj_id,
        "user_id":     request.user["_id"],
        "version_num": 1,
        "prompt":      prompt,
        "style":       style,
        "design":      design,
        "glb_url":     None,
        "created_at":  now,
    }
    ver_result = versions_collection().insert_one(ver_doc)
    ver_id = ver_result.inserted_id

    # Also write to legacy designs collection for any old consumers
    designs_collection().insert_one({
        "user_id":    request.user["_id"],
        "project_id": proj_id,
        "version_id": ver_id,
        "prompt":     prompt,
        "design":     design,
        "created_at": now,
    })

    # Launch Blender 3D procedural generation in background thread
    def _bg_generate_blender_legacy(d_copy, p_id_str, v_obj_id):
        try:
            g_url = generate_3d_house_model(d_copy, project_id=p_id_str, version_num=1)
            if g_url:
                versions_collection().update_one(
                    {"_id": v_obj_id},
                    {"$set": {"glb_url": g_url, "design.glb_url": g_url}}
                )
                designs_collection().update_one(
                    {"version_id": v_obj_id},
                    {"$set": {"glb_url": g_url, "design.glb_url": g_url}}
                )
        except Exception as e:
            logging.error(f"[BLENDER] Legacy background generation error: {e}")

    threading.Thread(
        target=_bg_generate_blender_legacy,
        args=(design, str(proj_id), ver_id),
        daemon=True,
    ).start()

    return jsonify({
        "success":    True,
        "design":     design,
        "design_id":  str(ver_id),
        "project_id": str(proj_id),
        "version_num": 1,
        "glb_url":    None,
    }), 200


@chat_bp.get("/history")
@require_auth
def history_legacy():
    """
    Legacy history endpoint — now returns projects list with latest version info.
    Keeps old frontend shape: items[].id, .prompt, .style, .created_at
    """
    try:
        cursor = projects_collection().find(
            {"user_id": request.user["_id"]}
        ).sort("updated_at", -1)

        items = []
        for doc in cursor:
            latest = versions_collection().find_one(
                {"project_id": doc["_id"]},
                sort=[("version_num", -1)],
                projection={"prompt": 1, "style": 1, "version_num": 1, "created_at": 1}
            )
            items.append({
                "id":            str(doc["_id"]),
                "project_id":    str(doc["_id"]),
                "name":          doc.get("name", "Untitled"),
                "prompt":        latest.get("prompt", "") if latest else doc.get("name", ""),
                "style":         (latest or doc).get("style", "modern"),
                "version_count": doc.get("version_count", 1),
                "created_at":    doc["created_at"].isoformat() if doc.get("created_at") else None,
            })

        return jsonify({"items": items})
    except Exception:
        return jsonify({"error": "Failed to load history"}), 500


@chat_bp.get("/design/<design_id>")
@require_auth
def get_design_legacy(design_id: str):
    """
    Legacy single-design fetch — now fetches the latest version of a project.
    design_id is treated as a project_id.
    """
    try:
        obj_id = ObjectId(design_id)
    except Exception:
        return jsonify({"error": "Invalid design id"}), 400

    try:
        # Try as project_id first (new path)
        doc = versions_collection().find_one(
            {"project_id": obj_id, "user_id": request.user["_id"]},
            sort=[("version_num", -1)]
        )
        if doc:
            design = doc.get("design")
            resolved_glb = resolve_s3_url_to_presigned(doc.get("glb_url") or (design or {}).get("glb_url"))
            if isinstance(design, dict) and resolved_glb:
                design = dict(design)
                design["glb_url"] = resolved_glb
            return jsonify({
                "design":      design,
                "prompt":      doc.get("prompt"),
                "version_num": doc.get("version_num", 1),
                "glb_url":     resolved_glb,
                "created_at":  doc["created_at"].isoformat() if doc.get("created_at") else None,
            })

        # Fallback: try legacy designs collection
        doc = designs_collection().find_one(
            {"_id": obj_id, "user_id": request.user["_id"]}
        )
        if not doc:
            return jsonify({"error": "Design not found"}), 404

        design = doc.get("design")
        resolved_glb = resolve_s3_url_to_presigned(doc.get("glb_url") or (design or {}).get("glb_url"))
        if isinstance(design, dict) and resolved_glb:
            design = dict(design)
            design["glb_url"] = resolved_glb

        created = doc.get("created_at")
        return jsonify({
            "design":     design,
            "prompt":     doc.get("prompt"),
            "glb_url":    resolved_glb,
            "created_at": created.isoformat() if created else None,
        })
    except Exception:
        return jsonify({"error": "Failed to load design"}), 500


@chat_bp.post("/projects/<project_id>/versions/<version_id>/generate-3d")
@require_auth
def generate_3d_for_version(project_id: str, version_id: str):
    """Triggers or retries Headless Blender 3D generation for a specific version."""
    try:
        ver_obj_id = ObjectId(version_id)
        proj_obj_id = ObjectId(project_id)
    except Exception:
        return jsonify({"error": "Invalid project or version id"}), 400

    ver = versions_collection().find_one({
        "_id": ver_obj_id,
        "project_id": proj_obj_id,
        "user_id": request.user["_id"],
    })
    if not ver or not ver.get("design"):
        return jsonify({"error": "Version or architectural design not found"}), 404

    glb_url = generate_3d_house_model(
        ver["design"],
        project_id=project_id,
        version_num=ver.get("version_num", 1)
    )

    if not glb_url:
        return jsonify({"success": False, "error": "Blender 3D generation failed or timed out"}), 502

    versions_collection().update_one(
        {"_id": ver_obj_id},
        {"$set": {"glb_url": glb_url, "design.glb_url": glb_url}}
    )
    ver["glb_url"] = glb_url
    if "design" in ver and isinstance(ver["design"], dict):
        ver["design"]["glb_url"] = glb_url

    return jsonify({
        "success": True,
        "glb_url": glb_url,
        "version": _serialize_version(ver),
    })

