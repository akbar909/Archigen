import os
import sys
import unittest
from unittest.mock import Mock, patch

from bson import ObjectId
from flask import Flask, request


BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from routes.chat import generate_3d_for_version


class SavedModelReuseTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.project_id = ObjectId()
        self.version_id = ObjectId()
        self.user_id = ObjectId()
        self.design = {
            "layout_approved": True,
            "glb_url": "https://example-bucket.s3.amazonaws.com/outputs/existing.glb",
        }
        self.version = {
            "_id": self.version_id,
            "project_id": self.project_id,
            "user_id": self.user_id,
            "version_num": 1,
            "design": dict(self.design),
            "glb_url": self.design["glb_url"],
        }

    def call_view(self, payload):
        with self.app.test_request_context("/generate-3d", method="POST", json=payload):
            request.user = {"_id": self.user_id, "email": "test@example.com"}
            return generate_3d_for_version.__wrapped__(
                str(self.project_id),
                str(self.version_id),
            )

    @patch("routes.chat.resolve_s3_url_to_presigned", return_value="https://signed.example/existing.glb")
    @patch("routes.chat.generate_3d_house_model")
    @patch("routes.chat.versions_collection")
    def test_existing_model_is_reused_without_running_blender(
        self,
        versions_collection_mock,
        generate_mock,
        _resolve_mock,
    ):
        collection = Mock()
        collection.find_one.return_value = dict(self.version)
        versions_collection_mock.return_value = collection

        response = self.call_view({"force": False})
        payload = response.get_json()

        self.assertTrue(payload["success"])
        self.assertTrue(payload["reused"])
        self.assertEqual("https://signed.example/existing.glb", payload["glb_url"])
        generate_mock.assert_not_called()
        collection.update_one.assert_not_called()

    @patch("routes.chat.resolve_s3_url_to_presigned", side_effect=lambda value: value)
    @patch("routes.chat.validate_and_repair_design")
    @patch("routes.chat.generate_3d_house_model", return_value="https://example-bucket.s3.amazonaws.com/outputs/new.glb")
    @patch("routes.chat.versions_collection")
    def test_force_true_regenerates_and_replaces_saved_model(
        self,
        versions_collection_mock,
        generate_mock,
        preflight_mock,
        _resolve_mock,
    ):
        collection = Mock()
        collection.find_one.return_value = dict(self.version)
        versions_collection_mock.return_value = collection
        preflight_mock.return_value = (dict(self.design), {"critical_errors": []})

        response = self.call_view({"force": True})
        payload = response.get_json()

        self.assertTrue(payload["success"])
        self.assertFalse(payload["reused"])
        generate_mock.assert_called_once()
        collection.update_one.assert_called_once()


if __name__ == "__main__":
    unittest.main()
