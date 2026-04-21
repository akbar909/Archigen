import datetime as dt

from bson import ObjectId
from flask import Blueprint, jsonify, request

from utils.db import designs_collection, projects_collection, versions_collection
from utils.gemini import GeminiTemporaryUnavailableError, generate_home_design
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
    return {
        "id":          str(doc["_id"]),
        "project_id":  str(doc.get("project_id", "")),
        "version_num": doc.get("version_num", 1),
        "prompt":      doc.get("prompt", ""),
        "style":       doc.get("style", "modern"),
        "design":      doc.get("design"),
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

    if not prompt:
        return jsonify({"error": "'prompt' is required"}), 400

    try:
        design = generate_home_design(
            f"{prompt} Style: {style}.".strip(), timeout=60
        )
    except GeminiTemporaryUnavailableError as exc:
        return jsonify({"success": False, "error": str(exc)}), 503
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
        "version_num": next_num,
        "prompt":     prompt,
        "style":      style,
        "design":     design,
        "created_at": now,
    }
    ver_result = versions_collection().insert_one(ver_doc)

    # Update project metadata
    projects_collection().update_one(
        {"_id": proj_id},
        {"$set": {
            "style":         style,
            "version_count": next_num,
            "updated_at":    now,
        }}
    )

    ver_doc["_id"] = ver_result.inserted_id
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
    timeout = data.get("timeout", 60)

    if not prompt:
        return jsonify({"error": "'prompt' is required and must be a non-empty string."}), 400

    if not isinstance(timeout, int) or timeout < 5 or timeout > 180:
        timeout = 60

    try:
        design = generate_home_design(
            f"{prompt} Style: {style}.".strip(), timeout=timeout
        )
    except GeminiTemporaryUnavailableError as exc:
        return jsonify({"success": False, "error": str(exc)}), 503
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
        "created_at":  now,
    }
    ver_result = versions_collection().insert_one(ver_doc)

    # Also write to legacy designs collection for any old consumers
    designs_collection().insert_one({
        "user_id":    request.user["_id"],
        "project_id": proj_id,
        "version_id": ver_result.inserted_id,
        "prompt":     prompt,
        "design":     design,
        "created_at": now,
    })

    return jsonify({
        "success":    True,
        "design":     design,
        "design_id":  str(ver_result.inserted_id),
        "project_id": str(proj_id),
        "version_num": 1,
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
            return jsonify({
                "design":      doc.get("design"),
                "prompt":      doc.get("prompt"),
                "version_num": doc.get("version_num", 1),
                "created_at":  doc["created_at"].isoformat() if doc.get("created_at") else None,
            })

        # Fallback: try legacy designs collection
        doc = designs_collection().find_one(
            {"_id": obj_id, "user_id": request.user["_id"]}
        )
        if not doc:
            return jsonify({"error": "Design not found"}), 404

        created = doc.get("created_at")
        return jsonify({
            "design":     doc.get("design"),
            "prompt":     doc.get("prompt"),
            "created_at": created.isoformat() if created else None,
        })
    except Exception:
        return jsonify({"error": "Failed to load design"}), 500
