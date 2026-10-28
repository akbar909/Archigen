import os
import sys
import unittest
from unittest.mock import Mock, patch

from bson import ObjectId
from flask import Flask


BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from routes.chat import chat_bp
from utils.auth import generate_token
from utils.versioning import prepare_design_snapshot, summarize_design_changes


class VersioningHelperTests(unittest.TestCase):
    def test_snapshot_removes_stale_synthesis_fields_without_mutating_source(self):
        source = {
            "layout_approved": True,
            "approved_at": "2026-10-27T10:00:00",
            "glb_url": "https://example.com/old.glb",
            "rooms": [{"id": "living", "name": "Living"}],
        }

        snapshot = prepare_design_snapshot(source)

        self.assertTrue(source["layout_approved"])
        self.assertEqual("https://example.com/old.glb", source["glb_url"])
        self.assertFalse(snapshot["layout_approved"])
        self.assertNotIn("approved_at", snapshot)
        self.assertNotIn("glb_url", snapshot)

    def test_change_summary_counts_added_removed_and_modified_entities(self):
        previous = {
            "rooms": [
                {"id": "living", "name": "Living"},
                {"id": "store", "name": "Store"},
            ],
            "doors": [{"id": "front", "width": 0.9}],
        }
        current = {
            "rooms": [
                {"id": "living", "name": "Great Room"},
                {"id": "kitchen", "name": "Kitchen"},
            ],
            "doors": [{"id": "front", "width": 1.1}],
        }

        summary = summarize_design_changes(previous, current)

        self.assertEqual({"added": 1, "removed": 1, "modified": 1}, summary["rooms"])
        self.assertEqual(1, summary["doors"]["modified"])
        self.assertEqual(4, summary["total"])


class VersionSnapshotRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(chat_bp, url_prefix="/api")
        self.client = self.app.test_client()
        self.user_id = ObjectId()
        self.project_id = ObjectId()
        self.base_version_id = ObjectId()
        self.new_version_id = ObjectId()
        self.token = generate_token(self.user_id, "owner@example.com")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.base_design = {
            "style": "modern",
            "layout_approved": True,
            "glb_url": "https://example.com/stale.glb",
            "rooms": [{"id": "living", "name": "Living"}],
        }

    @patch("routes.chat_project_routes.ArchitecturalValidator")
    @patch("routes.chat_project_routes.validate_and_repair_design")
    @patch("routes.chat_project_routes.versions_collection")
    @patch("routes.chat_project_routes.projects_collection")
    def test_new_version_is_scoped_linked_and_keeps_3d_preview_base(
        self,
        projects_collection_mock,
        versions_collection_mock,
        preflight_mock,
        validator_mock,
    ):
        project_collection = Mock()
        project_collection.find_one.return_value = {
            "_id": self.project_id,
            "user_id": self.user_id,
            "style": "modern",
            "version_count": 2,
        }
        project_collection.find_one_and_update.return_value = {"version_count": 3}
        projects_collection_mock.return_value = project_collection

        version_collection = Mock()
        base_version = {
            "_id": self.base_version_id,
            "project_id": self.project_id,
            "user_id": self.user_id,
            "version_num": 2,
            "style": "modern",
            "design": self.base_design,
            "glb_url": "s3://models/base.glb",
        }

        def find_one(query, **kwargs):
            return base_version if "_id" in query else {"version_num": 2}

        version_collection.find_one.side_effect = find_one
        version_collection.insert_one.return_value = Mock(inserted_id=self.new_version_id)
        versions_collection_mock.return_value = version_collection

        edited_design = {
            **self.base_design,
            "rooms": [{"id": "living", "name": "Open Living"}],
        }
        repaired_design = {
            "style": "modern",
            "layout_approved": False,
            "rooms": edited_design["rooms"],
        }
        preflight_mock.return_value = (
            repaired_design,
            {"critical_errors": [], "repairs": [], "inventory": {}},
        )
        validator_mock.return_value.validate.return_value = (True, {"status": "valid", "errors": []})

        response = self.client.post(
            f"/api/projects/{self.project_id}/versions",
            headers=self.headers,
            json={
                "base_version_id": str(self.base_version_id),
                "design": edited_design,
                "note": "Opened the living space",
            },
        )

        self.assertEqual(201, response.status_code)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(3, payload["version"]["version_num"])
        self.assertEqual(str(self.base_version_id), payload["version"]["base_version_id"])

        inserted = version_collection.insert_one.call_args.args[0]
        self.assertEqual(self.user_id, inserted["user_id"])
        self.assertEqual(self.project_id, inserted["project_id"])
        self.assertEqual(self.base_version_id, inserted["base_version_id"])
        self.assertEqual("s3://models/base.glb", inserted["glb_url"])
        self.assertTrue(inserted["layout_approved"])
        self.assertTrue(inserted["design"]["layout_approved"])
        self.assertNotIn("glb_url", inserted["design"])
        self.assertEqual(1, inserted["change_summary"]["rooms"]["modified"])

        base_lookup = version_collection.find_one.call_args_list[0].args[0]
        self.assertEqual(self.user_id, base_lookup["user_id"])
        self.assertEqual(self.project_id, base_lookup["project_id"])

    def test_new_version_requires_authentication(self):
        response = self.client.post(
            f"/api/projects/{self.project_id}/versions",
            json={"base_version_id": str(self.base_version_id)},
        )
        self.assertEqual(401, response.status_code)


if __name__ == "__main__":
    unittest.main()
