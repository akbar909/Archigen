import datetime as dt
import mimetypes
import json
import logging
import threading
import uuid
import copy
from pathlib import Path

# pyrefly: ignore [missing-import]
from bson import ObjectId
# pyrefly: ignore [missing-import]
from routes.chat_project_routes import register_project_routes
from flask import Blueprint, Response, jsonify, request, send_from_directory, url_for

from utils.db import designs_collection, projects_collection, versions_collection
from utils.blender_service import generate_3d_house_model, BlenderGenerationError
from config import AWS_S3_BUCKET, BLENDER_TIMEOUT_SECONDS
from utils.s3_storage import get_s3_client, resolve_s3_url_to_presigned
from utils.gemini import (
    GeminiSchemaValidationError,
    GeminiTemporaryUnavailableError,
    build_generation_prompt,
    generate_home_design,
    validate_architectural_prompt,
)
from utils.gemini_layout import infer_layout_constraints
from utils.middleware import require_auth
from utils.architectural_validator import ArchitecturalValidator
from utils.architectural_preflight import validate_and_repair_design
from utils.architectural_refinement import apply_targeted_refinement, apply_layout_refinement, is_explicit_full_redesign
from utils.architectural_schema_v3 import validate_schema_v3
from utils.versioning import summarize_design_changes
from utils.asset_catalog import ASSET_ROOT, browser_url, list_uploaded_assets
from utils.wizard_constraints import build_prompt_layout_constraints, build_wizard_layout_constraints



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


def _serialize_version(doc, resolve_glb: bool = True):
    raw_glb = doc.get("glb_url") or (doc.get("design") or {}).get("glb_url")
    resolved_glb = resolve_s3_url_to_presigned(raw_glb) if resolve_glb else None
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
        "version_note": doc.get("version_note", ""),
        "change_summary": doc.get("change_summary") or {},
        "style":       doc.get("style", "modern"),
        "design":      design,
        "glb_url":     resolved_glb,
        "has_glb":     bool(raw_glb),
        "generation_3d": _generation_status(doc),
        "created_at":  doc["created_at"].isoformat() if doc.get("created_at") else None,
        "updated_at":  doc["updated_at"].isoformat() if doc.get("updated_at") else None,
    }


def _generation_status(version):
    job = dict(version.get('generation_3d') or {})
    if job.get('status') == 'running':
        try:
            started = dt.datetime.fromisoformat(job['started_at'])
            now = dt.datetime.now(started.tzinfo) if started.tzinfo else dt.datetime.utcnow()
            if (now - started).total_seconds() > job.get('timeout_seconds', BLENDER_TIMEOUT_SECONDS + 60):
                job.update(status='timed_out', error='The 3D worker did not return a model within the expected time. Check its logs and retry Build 3D.')
        except (ValueError, TypeError, KeyError):
            job.update(status='timed_out', error='This 3D build has no valid start time. Retry Build 3D.')
    return job or None


def _start_3d_generation(version, design, project_id):
    """Atomically claim one build; both approval and retries return immediately."""
    if (_generation_status(version) or {}).get('status') == 'running':
        return False
    collection = versions_collection()
    job = {'job_id': uuid.uuid4().hex, 'status': 'running',
           'started_at': dt.datetime.utcnow().isoformat(), 'completed_at': None,
           'timeout_seconds': BLENDER_TIMEOUT_SECONDS + 60, 'error': None}
    previous_id = (version.get('generation_3d') or {}).get('job_id')
    claim = collection.update_one(
        {'_id': version['_id'], 'generation_3d.job_id': previous_id},
        {'$set': {'design': design, 'layout_approved': bool(design.get('layout_approved')), 'generation_3d': job}})
    if claim.matched_count == 0:
        return False
    version['design'], version['generation_3d'] = design, job

    def build():
        query = {'_id': version['_id'], 'generation_3d.job_id': job['job_id']}
        try:
            url = generate_3d_house_model(copy.deepcopy(design), project_id=project_id,
                                          version_num=version.get('version_num', 1), raise_on_error=True)
            if not url:
                raise BlenderGenerationError('The Blender worker returned no model. Check its logs before retrying.')
            collection.update_one(query, {'$set': {
                'glb_url': url, 'design.glb_url': url, 'generation_3d.status': 'completed',
                'generation_3d.completed_at': dt.datetime.utcnow().isoformat(), 'generation_3d.error': None}})
        except Exception as exc:
            logging.exception('[BLENDER] Generation failed for version %s', version['_id'])
            reason = str(exc) if isinstance(exc, BlenderGenerationError) else 'The 3D build failed unexpectedly. Check the backend logs.'
            collection.update_one(query, {'$set': {
                'generation_3d.status': 'failed', 'generation_3d.error': reason,
                'generation_3d.completed_at': dt.datetime.utcnow().isoformat()}})

    try:
        threading.Thread(target=build, daemon=True).start()
    except Exception:
        collection.update_one({'_id':version['_id'], 'generation_3d.job_id':job['job_id']},
                              {'$set':{'generation_3d.status':'failed', 'generation_3d.error':'Could not start the 3D build. Retry Build 3D.'}})
        raise
    return True



# ─── PROJECTS ─────────────────────────────────────────────────────────────────

register_project_routes(chat_bp, _serialize_project, _serialize_version)


@chat_bp.get("/assets/catalog")
@require_auth
def uploaded_asset_catalog():
    """List only models and textures present in the synchronized S3 library."""
    entries, source = list_uploaded_assets()
    group = str(request.args.get("group") or "").strip().lower()
    category = str(request.args.get("category") or "").strip().lower()
    if group:
        entries = [entry for entry in entries if entry["group"] == group]
    if category:
        entries = [entry for entry in entries if entry["category"] == category]
    result = []
    for entry in entries:
        delivered_url = url_for(
            "chat.uploaded_asset_content" if entry["kind"] == "texture" else "chat.local_uploaded_asset",
            asset_path=entry["relative_path"],
            _external=True,
        )
        item = dict(entry)
        # Images are served through our stable asset endpoint. This avoids
        # cached/expired S3 signatures and gives TextureLoader a predictable
        # CORS response. GLBs continue using direct S3/CDN delivery.
        item["url"] = delivered_url if entry["kind"] == "texture" else browser_url(entry, delivered_url)
        item["model_path"] = item["url"] if item["kind"] == "model" else None
        item["thumbnail_url"] = item["url"] if item["kind"] == "texture" else None
        result.append(item)
    return jsonify({"assets": result, "source": source, "count": len(result)})


@chat_bp.get("/assets/local/<path:asset_path>")
def local_uploaded_asset(asset_path: str):
    """Development fallback for the exact files mirrored by the S3 sync job."""
    return send_from_directory(str(ASSET_ROOT), asset_path, conditional=True)


@chat_bp.get("/assets/content/<path:asset_path>")
def uploaded_asset_content(asset_path: str):
    """Stream an uploaded texture with a stable URL for browser materials."""
    normalized = str(asset_path or "").replace("\\", "/").lstrip("/")
    suffix = Path(normalized).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"} or ".." in Path(normalized).parts:
        return jsonify({"error": "Unsupported asset"}), 404

    s3 = get_s3_client()
    if s3 and AWS_S3_BUCKET:
        try:
            result = s3.get_object(Bucket=AWS_S3_BUCKET, Key=f"assets/{normalized}")
            body = result["Body"]
            response = Response(
                body.iter_chunks(chunk_size=64 * 1024),
                content_type=result.get("ContentType") or mimetypes.guess_type(normalized)[0] or "application/octet-stream",
                direct_passthrough=True,
            )
            response.headers["Cache-Control"] = "private, max-age=300"
            if result.get("ETag"):
                response.headers["ETag"] = result["ETag"]
            return response
        except Exception as exc:
            logging.warning("Texture asset delivery failed for %s: %s", normalized, exc)

    return send_from_directory(str(ASSET_ROOT), normalized, conditional=True, max_age=300)

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

    try:
        wizard_constraints = build_wizard_layout_constraints(data.get("wizard"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

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

    try:
        structured_prompt_constraints = (
            None if wizard_constraints else build_prompt_layout_constraints(prompt)
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    prompt_constraints = structured_prompt_constraints or infer_layout_constraints(prompt)
    effective_layout_constraints = wizard_constraints or structured_prompt_constraints
    replace_room_program = bool(
        wizard_constraints or prompt_constraints.get("replace_room_program")
    )

    design = None
    refinement_report = None
    if base_version and base_version.get("design") and not replace_room_program:
        design, refinement_report = apply_targeted_refinement(
            base_version["design"], prompt, requested_style=style
        )
        if refinement_report["handled"] and refinement_report["errors"]:
            return jsonify({
                "success": False,
                "error": "The requested layout refinement could not be applied safely.",
                "refinement": refinement_report,
            }), 422

        # A follow-up is an edit to the selected version, not an implicit request
        # for another floor plan.  Never let an unrecognized/ambiguous edit fall
        # through to whole-house generation; the user must explicitly authorize
        # a redesign.  This is the universal guardrail that protects plot size,
        # room geometry, openings, furniture, paths, and circulation.
        if design is None and not is_explicit_full_redesign(prompt):
            return jsonify({
                "success": False,
                "error": (
                    "This follow-up could not be applied as a safe edit, so the existing layout "
                    "was left unchanged. Describe the specific object and change, or explicitly "
                    "ask to 'redesign the entire layout' if a new floor plan is intended."
                ),
                "refinement": {
                    "handled": False,
                    "changes": [],
                    "errors": [],
                    "layout_preserved": True,
                    "requires_explicit_redesign": True,
                },
            }), 422

    # A recognized small edit is applied directly to the approved canonical
    # layout.  Only broader redesign prompts are delegated to Gemini.
    if design is None:
        if base_version and base_version.get("design") and not replace_room_program:
            base_design_json = json.dumps(base_version["design"], ensure_ascii=True)
            generation_prompt = build_generation_prompt(
                f"{prompt}\nCurrent design JSON:\n{base_design_json}",
                style=style,
                base_design=base_version.get("design"),
            )
        else:
            generation_prompt = build_generation_prompt(prompt, style=style)

        try:
            design = generate_home_design(
                generation_prompt,
                timeout=120,
                constraints_prompt=prompt,
                layout_constraints=effective_layout_constraints,
            )
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
    design_project = design.get("project") if isinstance(design.get("project"), dict) else {}
    design_house = design.get("house") if isinstance(design.get("house"), dict) else {}
    effective_style = (
        design.get("style") or design_project.get("style") or design_house.get("style") or style
    )

    ver_doc = {
        "project_id": proj_id,
        "user_id":    request.user["_id"],
        "base_version_id": base_version.get("_id") if base_version else None,
        "version_num": next_num,
        "prompt":     prompt,
        "style":      effective_style,
        "design":     design,
        "glb_url":     None,
        "layout_approved": False,
        "created_at": now,
    }
    design["layout_approved"] = False
    ver_result = versions_collection().insert_one(ver_doc)
    ver_id = ver_result.inserted_id
    ver_doc["_id"] = ver_id

    # Update project metadata
    projects_collection().update_one(
        {"_id": proj_id},
        {"$set": {
            "style":         effective_style,
            "version_count": next_num,
            "updated_at":    now,
        }}
    )

    # 3D synthesis is withheld until the user reviews 2D floor plan and approves
    return jsonify({
        "success": True,
        "version": _serialize_version(ver_doc),
        "refinement": refinement_report if refinement_report and refinement_report["handled"] else None,
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

    try:
        wizard_constraints = build_wizard_layout_constraints(data.get("wizard"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if not prompt:
        return jsonify({"error": "'prompt' is required and must be a non-empty string."}), 400

    if not isinstance(timeout, int) or timeout < 5 or timeout > 240:
        timeout = 120

    try:
        structured_prompt_constraints = (
            None if wizard_constraints else build_prompt_layout_constraints(prompt)
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    try:
        design = generate_home_design(
            build_generation_prompt(prompt, style=style),
            timeout=timeout,
            constraints_prompt=prompt,
            layout_constraints=wizard_constraints or structured_prompt_constraints,
        )
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

    # Auto-create a project from the prompt title (max 30 characters to match project name limit)
    project_name = (prompt[:27] + "…") if len(prompt) > 27 else prompt
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
        "layout_approved": False,
        "created_at":  now,
    }
    design["layout_approved"] = False
    ver_result = versions_collection().insert_one(ver_doc)
    ver_id = ver_result.inserted_id

    # Also write to legacy designs collection for any old consumers
    designs_collection().insert_one({
        "user_id":    request.user["_id"],
        "project_id": proj_id,
        "version_id": ver_id,
        "prompt":     prompt,
        "design":     design,
        "layout_approved": False,
        "created_at": now,
    })

    # 3D synthesis is withheld until the user reviews 2D floor plan and approves
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

    data = request.get_json(silent=True) or {}
    force_value = data.get("force", request.args.get("force", False))
    force = force_value is True or str(force_value).strip().lower() in {"1", "true", "yes", "on"}

    if (_generation_status(ver) or {}).get('status') == 'running':
        return jsonify({'success':True, 'pending':True, 'already_running':True,
                        'version':_serialize_version(ver)}), 202

    # Opening an existing version must not start Blender again. Return a fresh
    # signed URL for the saved object unless regeneration was explicit.
    existing_glb = ver.get("glb_url") or (ver.get("design") or {}).get("glb_url")
    if existing_glb and not force:
        serialized = _serialize_version(ver)
        return jsonify({
            "success": True,
            "reused": True,
            "glb_url": serialized.get("glb_url"),
            "version": serialized,
        })

    design, preflight = validate_and_repair_design(ver["design"], repair=True)
    if preflight["critical_errors"]:
        return jsonify({
            "success": False,
            "error": "3D generation blocked by architectural validation.",
            "validation": preflight,
        }), 422

    started = _start_3d_generation(ver, design, project_id)
    if not started:
        ver = versions_collection().find_one({'_id':ver_obj_id}) or ver
    return jsonify({'success':True, 'pending':True, 'reused':False,
                    'already_running':not started, 'version':_serialize_version(ver)}), 202


@chat_bp.post("/projects/<project_id>/versions/<version_id>/approve-layout")
@require_auth
def approve_layout_for_version(project_id: str, version_id: str):
    """User approval gate: marks floor plan layout approved and triggers 3D Blender synthesis."""
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

    if (_generation_status(ver) or {}).get('status') == 'running':
        return jsonify({'success':True, 'pending':True, 'already_running':True,
                        'version':_serialize_version(ver)}), 202

    # Repair safe transform issues before approval and refuse to represent an
    # invalid scene as complete.  Required objects are never silently deleted.
    design, preflight = validate_and_repair_design(ver["design"], repair=True)
    if preflight["critical_errors"]:
        return jsonify({
            "success": False,
            "error": "Layout cannot be approved until critical conflicts are resolved.",
            "validation": preflight,
        }), 422

    # Update design state to approved
    design["layout_approved"] = True
    design["approved_at"] = dt.datetime.utcnow().isoformat()

    started = _start_3d_generation(ver, design, project_id)
    if not started:
        ver = versions_collection().find_one({'_id':ver_obj_id}) or ver
    return jsonify({
        "success": True,
        "pending": True,
        "already_running": not started,
        "message": "Floor plan approved! 3D house synthesis initiated.",
        "version": _serialize_version(ver),
    }), 202


@chat_bp.post("/projects/<project_id>/versions/<version_id>/layout/refine")
@require_auth
def refine_layout_draft(project_id: str, version_id: str):
    """Return a validated local edit; persistence remains an explicit save."""
    try:
        project_oid, version_oid = ObjectId(project_id), ObjectId(version_id)
    except Exception:
        return jsonify({"error": "Invalid project or version id"}), 400
    version = versions_collection().find_one({
        "_id": version_oid, "project_id": project_oid, "user_id": request.user["_id"],
    })
    if not version:
        return jsonify({"error": "Version not found"}), 404
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required"}), 400
    prompt = data.get("prompt")
    design = data.get("design", version.get("design"))
    if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 1500:
        return jsonify({"error": "Enter an edit of 1–1500 characters"}), 400
    if not isinstance(design, dict) or not isinstance(design.get("floors"), list):
        return jsonify({"error": "A design with floors is required"}), 400
    if design.get("schema_version") in ("3.0", "3.0.0"):
        valid, errors = validate_schema_v3(design)
        if not valid:
            return jsonify({"error": "The draft does not match the architectural schema", "details": errors}), 400
    try:
        refined, report = apply_layout_refinement(design, prompt.strip(), data.get('selection'))
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        logging.warning("Invalid local layout refinement: %s", exc)
        return jsonify({"error": "This draft could not be refined. Check its geometry and target identifiers."}), 422
    if refined is None:
        return jsonify({"error": "; ".join(report.get("errors") or ["The requested edit is not supported"]), "report": report}), 422
    if refined.get('schema_version') in ('3.0','3.0.0'):
        valid, errors = validate_schema_v3(refined)
        if not valid:
            return jsonify({'error':'This edit would create invalid dimensions. Try a smaller adjustment.','details':errors}),422
    # Retain the saved preview while the edited JSON is reviewed and saved.
    for name in ("glb_url", "model_url", "layout_approved", "approved_at"):
        if name in design:
            refined[name] = design[name]
    return jsonify({"success": True, "design": refined, "report": report})


@chat_bp.patch("/projects/<project_id>/versions/<version_id>/layout")
@require_auth
def update_layout_for_version(project_id: str, version_id: str):
    """Allows user to tweak rooms or materials in the architectural JSON, re-running validation."""
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
    if not ver:
        return jsonify({"error": "Version not found"}), 404

    # Keep the last Blender export available as the visual base while the
    # edited version is rebuilt. The frontend applies saved furniture
    # transforms to this base immediately; force-generation replaces it with
    # the new canonical GLB as soon as Blender finishes.
    preview_glb_url = ver.get("glb_url") or (ver.get("design") or {}).get("glb_url")
    keep_3d_view = bool(preview_glb_url)

    data = request.get_json(silent=True) or {}
    updated_design = data.get("design") or data.get("layout")
    if not isinstance(updated_design, dict):
        return jsonify({"error": "design or layout object is required"}), 400

    if updated_design.get("schema_version") in ("3.0", "3.0.0"):
        schema_valid, schema_errors = validate_schema_v3(updated_design)
        if not schema_valid:
            return jsonify({"error": "Invalid architectural layout", "details": schema_errors}), 400

    updated_design, preflight = validate_and_repair_design(updated_design, repair=True)
    version_note = str(data.get("note") or "").strip()
    if len(version_note) > 500:
        return jsonify({"error": "Version note cannot exceed 500 characters"}), 400
    change_summary = summarize_design_changes(ver.get("design"), updated_design)
    # The JSON is the source of truth. Its prior GLB remains only as a preview
    # base until the automatic force-generation completes.
    updated_design["layout_approved"] = keep_3d_view
    updated_design.pop("approved_at", None)
    updated_design.pop("glb_url", None)
    updated_design.pop("model_url", None)
    # Run architectural validation after deterministic repairs.
    validator = ArchitecturalValidator(updated_design)
    is_valid, val_report = validator.validate()
    val_report["critical_errors"] = preflight["critical_errors"]
    val_report["repairs"] = preflight["repairs"]
    val_report["inventory"] = preflight["inventory"]
    if preflight["critical_errors"]:
        is_valid = False
        val_report["status"] = "invalid"
        val_report["errors"] = preflight["critical_errors"] + val_report.get("errors", [])

    now = dt.datetime.utcnow()
    versions_collection().update_one(
        {"_id": ver_obj_id},
        {"$set": {
            "design": updated_design,
            "layout_approved": keep_3d_view,
            "glb_url": preview_glb_url,
            "version_note": version_note,
            "change_summary": change_summary,
            "updated_at": now,
        }}
    )
    ver["design"] = updated_design
    ver["layout_approved"] = keep_3d_view
    ver["glb_url"] = preview_glb_url
    ver["version_note"] = version_note
    ver["change_summary"] = change_summary
    ver["updated_at"] = now

    projects_collection().update_one(
        {"_id": proj_obj_id, "user_id": request.user["_id"]},
        {"$set": {"updated_at": now}},
    )

    return jsonify({
        "success": True,
        "design": updated_design,
        "validation": val_report,
        "version": _serialize_version(ver),
    })


@chat_bp.get("/projects/<project_id>/versions/<version_id>/validation")
@require_auth
def get_layout_validation(project_id: str, version_id: str):
    """Returns the 20-point architectural validation report for a specific version."""
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
        return jsonify({"error": "Version or design not found"}), 404

    canonical, preflight = validate_and_repair_design(ver["design"], repair=True)
    validator = ArchitecturalValidator(canonical)
    is_valid, report = validator.validate()
    report["critical_errors"] = preflight["critical_errors"]
    report["repairs"] = preflight["repairs"]
    report["inventory"] = preflight["inventory"]
    if preflight["critical_errors"]:
        is_valid = False
        report["status"] = "invalid"
        report["errors"] = preflight["critical_errors"] + report.get("errors", [])

    return jsonify({
        "success": True,
        "is_valid": is_valid,
        "report": report,
    })
