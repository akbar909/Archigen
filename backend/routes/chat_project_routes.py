"""Project and version retrieval routes for the chat blueprint."""

import datetime as dt

from bson import ObjectId
from flask import jsonify, request
from pymongo import ReturnDocument

from utils.db import projects_collection, versions_collection
from utils.middleware import require_auth
from utils.architectural_preflight import validate_and_repair_design
from utils.architectural_validator import ArchitecturalValidator
from utils.versioning import prepare_design_snapshot, summarize_design_changes


def register_project_routes(chat_bp, serialize_project, serialize_version):
    """Attach project CRUD and version-read endpoints to the supplied blueprint."""
    _serialize_project = serialize_project
    _serialize_version = serialize_version

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
        if not name:
            name = "Untitled Project"
        if len(name) < 2:
            return jsonify({"error": "Project name must be at least 2 characters"}), 400
        if len(name) > 30:
            return jsonify({"error": "Project name cannot exceed 30 characters"}), 400
    
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
    
    
    @chat_bp.get("/projects/<project_id>")
    @require_auth
    def get_project(project_id: str):
        """Return a single project and its versions list."""
        try:
            obj_id = ObjectId(project_id)
        except Exception:
            return jsonify({"error": "Invalid project id"}), 400
    
        doc = projects_collection().find_one(
            {"_id": obj_id, "user_id": request.user["_id"]}
        )
        if not doc:
            return jsonify({"error": "Project not found"}), 404
    
        cursor = versions_collection().find(
            {"project_id": obj_id, "user_id": request.user["_id"]},
            projection={"design": 0}
        ).sort("version_num", -1)
        # Sidebar summaries need availability, not a freshly signed URL for every
        # model. Signing here slows initial project loading and changes cache keys.
        versions = [_serialize_version(v, resolve_glb=False) for v in cursor]
    
        return jsonify({
            "project": _serialize_project(doc),
            "versions": versions
        })
    
    
    @chat_bp.route("/projects/<project_id>", methods=["PATCH", "PUT"])
    @require_auth
    def rename_project(project_id: str):
        """Rename a project."""
        try:
            obj_id = ObjectId(project_id)
        except Exception:
            return jsonify({"error": "Invalid project id"}), 400
    
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        if not name or len(name) < 2:
            return jsonify({"error": "Project name must be at least 2 characters"}), 400
        if len(name) > 30:
            return jsonify({"error": "Project name cannot exceed 30 characters"}), 400
    
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
    
        items = [_serialize_version(doc, resolve_glb=False) for doc in cursor]
        return jsonify({"versions": items})


    @chat_bp.post("/projects/<project_id>/versions")
    @require_auth
    def create_version_snapshot(project_id: str):
        """Save the current draft as a new immutable project version."""
        try:
            proj_obj_id = ObjectId(project_id)
        except Exception:
            return jsonify({"error": "Invalid project id"}), 400

        project = projects_collection().find_one({
            "_id": proj_obj_id,
            "user_id": request.user["_id"],
        })
        if not project:
            return jsonify({"error": "Project not found"}), 404

        data = request.get_json(silent=True) or {}
        base_version_id = data.get("base_version_id")
        if not base_version_id:
            return jsonify({"error": "base_version_id is required"}), 400
        try:
            base_obj_id = ObjectId(base_version_id)
        except Exception:
            return jsonify({"error": "Invalid base_version_id"}), 400

        base_version = versions_collection().find_one({
            "_id": base_obj_id,
            "project_id": proj_obj_id,
            "user_id": request.user["_id"],
        })
        if not base_version or not isinstance(base_version.get("design"), dict):
            return jsonify({"error": "Base version not found"}), 404

        supplied_design = data.get("design")
        if supplied_design is not None and not isinstance(supplied_design, dict):
            return jsonify({"error": "design must be an object"}), 400

        note = str(data.get("note") or "").strip()
        if len(note) > 500:
            return jsonify({"error": "Version note cannot exceed 500 characters"}), 400

        draft = supplied_design if supplied_design is not None else base_version["design"]
        draft = prepare_design_snapshot(draft)
        saved_design, preflight = validate_and_repair_design(draft, repair=True)
        preview_glb_url = base_version.get("glb_url") or base_version["design"].get("glb_url")
        keep_3d_view = bool(preview_glb_url)
        saved_design["layout_approved"] = keep_3d_view

        validator = ArchitecturalValidator(saved_design)
        is_valid, validation = validator.validate()
        validation["critical_errors"] = preflight["critical_errors"]
        validation["repairs"] = preflight["repairs"]
        validation["inventory"] = preflight["inventory"]
        if preflight["critical_errors"]:
            is_valid = False
            validation["status"] = "invalid"
            validation["errors"] = preflight["critical_errors"] + validation.get("errors", [])

        latest = versions_collection().find_one(
            {"project_id": proj_obj_id, "user_id": request.user["_id"]},
            sort=[("version_num", -1)],
            projection={"version_num": 1},
        )
        now = dt.datetime.utcnow()
        design_project = saved_design.get("project")
        if not isinstance(design_project, dict):
            design_project = {}
        style = (
            saved_design.get("style")
            or design_project.get("style")
            or base_version.get("style")
            or project.get("style")
            or "modern"
        )
        project_filter = {"_id": proj_obj_id, "user_id": request.user["_id"]}
        # Bring older counters forward, then reserve the next number atomically.
        # Concurrent saves therefore receive different version numbers.
        projects_collection().update_one(
            project_filter,
            {"$max": {"version_count": int((latest or {}).get("version_num") or 0)}},
        )
        reserved_project = projects_collection().find_one_and_update(
            project_filter,
            {
                "$inc": {"version_count": 1},
                "$set": {"style": style, "updated_at": now},
            },
            projection={"version_count": 1},
            return_document=ReturnDocument.AFTER,
        )
        if not reserved_project:
            return jsonify({"error": "Project no longer exists"}), 409
        next_num = int(reserved_project.get("version_count") or 1)
        change_summary = summarize_design_changes(base_version["design"], saved_design)
        version_doc = {
            "project_id": proj_obj_id,
            "user_id": request.user["_id"],
            "base_version_id": base_obj_id,
            "version_num": next_num,
            "prompt": note or f"Manual edits from Version {base_version.get('version_num', 1)}",
            "version_note": note,
            "change_summary": change_summary,
            "style": style,
            "design": saved_design,
            "glb_url": preview_glb_url,
            "layout_approved": keep_3d_view,
            "created_at": now,
            "updated_at": now,
        }
        result = versions_collection().insert_one(version_doc)
        version_doc["_id"] = result.inserted_id

        return jsonify({
            "success": True,
            "version": _serialize_version(version_doc),
            "validation": validation,
            "is_valid": is_valid,
        }), 201
    
    
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
    
    
