"""Project and version retrieval routes for the chat blueprint."""

import datetime as dt

from bson import ObjectId
from flask import jsonify, request

from utils.db import projects_collection, versions_collection
from utils.middleware import require_auth


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
    
    

