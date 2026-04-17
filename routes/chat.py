import datetime as dt

from bson import ObjectId
from flask import Blueprint, jsonify, request

from utils.db import designs_collection
from utils.gemini import generate_home_design
from utils.middleware import require_auth


chat_bp = Blueprint("chat", __name__)


@chat_bp.post("/chat")
@require_auth
def generate_design():
	data = request.get_json(silent=True) or {}
	prompt = data.get("prompt")
	timeout = data.get("timeout", 45)
	style = data.get("style")  # optional style override

	if not isinstance(prompt, str) or not prompt.strip():
		return jsonify({"error": "'prompt' is required and must be a non-empty string."}), 400

	if not isinstance(timeout, int) or timeout < 5 or timeout > 180:
		return jsonify({"error": "'timeout' must be an integer between 5 and 180."}), 400

	style_text = f" Style: {style}." if style else ""
	try:
		design = generate_home_design(f"{prompt.strip()} {style_text}".strip(), timeout=timeout)

		doc = {
			"user_id": request.user["_id"],
			"prompt": prompt.strip(),
			"design": design,
			"created_at": dt.datetime.utcnow(),
		}
		result = designs_collection().insert_one(doc)

		return jsonify({"success": True, "design": design, "design_id": str(result.inserted_id)}), 200
	except (ValueError, EnvironmentError) as exc:
		return jsonify({"success": False, "error": str(exc)}), 400
	except RuntimeError as exc:
		return jsonify({"success": False, "error": str(exc)}), 502
	except Exception:
		return jsonify({"success": False, "error": "Internal server error."}), 500


@chat_bp.get("/history")
@require_auth
def history():
	try:
		cursor = designs_collection().find({"user_id": request.user["_id"]}).sort("created_at", -1)
		history_items = []
		for doc in cursor:
			created = doc.get("created_at")
			history_items.append(
				{
					"id": str(doc.get("_id")),
					"prompt": doc.get("prompt"),
					"created_at": created.isoformat() if created else None,
					"style": doc.get("design", {}).get("style"),
				}
			)
		return jsonify({"items": history_items})
	except Exception:
		return jsonify({"error": "Failed to load history"}), 500


@chat_bp.get("/design/<design_id>")
@require_auth
def get_design(design_id: str):
	try:
		obj_id = ObjectId(design_id)
	except Exception:
		return jsonify({"error": "Invalid design id"}), 400

	try:
		doc = designs_collection().find_one({"_id": obj_id, "user_id": request.user["_id"]})
		if not doc:
			return jsonify({"error": "Design not found"}), 404

		created = doc.get("created_at")
		return jsonify({
			"design": doc.get("design"),
			"prompt": doc.get("prompt"),
			"created_at": created.isoformat() if created else None,
		})
	except Exception:
		return jsonify({"error": "Failed to load design"}), 500

