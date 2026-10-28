import os
import sys
import unittest
from unittest.mock import patch
from bson import ObjectId
from flask import Flask


BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from utils.asset_catalog import _entry, list_uploaded_assets, browser_url
from routes.chat import chat_bp
from utils.auth import generate_token
from utils.blender_service import _canonical_blender_layout


class UploadedAssetCatalogTests(unittest.TestCase):
    @patch("routes.chat.get_s3_client")
    def test_stable_texture_endpoint_streams_uploaded_s3_image(self, get_client_mock):
        class Body:
            def iter_chunks(self, chunk_size):
                self.chunk_size = chunk_size
                yield b"\xff\xd8texture\xff\xd9"

        get_client_mock.return_value.get_object.return_value = {
            "Body": Body(), "ContentType": "image/jpeg", "ETag": '"texture-etag"'
        }
        app = Flask(__name__)
        app.register_blueprint(chat_bp, url_prefix="/api")
        response = app.test_client().get('/api/assets/content/textures/walls/brick_wall_diff_2k.jpg')
        self.assertEqual(200, response.status_code)
        self.assertEqual('image/jpeg', response.content_type)
        self.assertEqual(b"\xff\xd8texture\xff\xd9", response.data)
        get_client_mock.return_value.get_object.assert_called_once_with(
            Bucket='archigen-storage', Key='assets/textures/walls/brick_wall_diff_2k.jpg'
        )

    def test_texture_endpoint_rejects_non_image_and_parent_traversal(self):
        app = Flask(__name__)
        app.register_blueprint(chat_bp, url_prefix="/api")
        client = app.test_client()
        self.assertEqual(404, client.get('/api/assets/content/furniture/chair.glb').status_code)
        self.assertEqual(404, client.get('/api/assets/content/..%2F.env.jpg').status_code)

    def test_export_of_table_assembly_omits_separate_chairs(self):
        design = {'floors': [{'rooms': [{'id': 'dining', 'dimensions': {'width': 5, 'depth': 4}}],
            'furniture': [
                {'id': 'table', 'room_id': 'dining', 'suppressed_furniture_ids': ['chair']},
                {'id': 'chair', 'room_id': 'dining'},
            ]}]}
        result = _canonical_blender_layout(design, 'test', 'modern')
        self.assertEqual(['table'], result['expected_inventory']['furniture_ids'])

    def test_nightstands_are_not_sized_as_beds(self):
        entry = _entry('assets/furniture/bedroom/nightstands/nightstand_01.glb', 's3')
        self.assertEqual('nightstand', entry['category'])
        self.assertLess(entry['dimensions']['width'], 0.8)
        self.assertLess(entry['dimensions']['height'], 0.9)

    def test_curtain_and_ceiling_assets_are_available(self):
        self.assertEqual('curtain', _entry('assets/decorations/curtains_blinds/curtains_01.glb', 's3')['group'])
        self.assertEqual('ceiling_asset', _entry('assets/architecture/ceilings/fans/ceiling_fan_01.glb', 's3')['group'])

    def test_legacy_table_with_different_category_is_still_deduplicated(self):
        with patch('utils.asset_catalog._s3_keys', return_value=[
            'assets/furniture/dining_room/dining_table_001.glb',
            'assets/furniture/dining_room/dining_tables/dining_table_001.glb',
        ]):
            assets, _ = list_uploaded_assets()
        self.assertEqual(1, len(assets))
        self.assertEqual('dining_table', assets[0]['category'])

    def test_texture_delivery_uses_signed_s3_when_cdn_is_configured(self):
        entry = _entry('assets/textures/grounds/leafy_grass_diff_1k.jpg', 's3')
        with patch('utils.asset_catalog.AWS_S3_PUBLIC_BASE_URL', 'https://cdn.example'), patch(
            'utils.asset_catalog.generate_presigned_url', return_value='https://s3.example/grass.jpg?signature=fresh'
        ):
            self.assertEqual('https://s3.example/grass.jpg?signature=fresh', browser_url(entry, ''))

    def test_uploaded_chair_is_classified_for_dining_chair_swap(self):
        entry = _entry(
            "assets/furniture/dining_room/dining_chairs/dining_chair_002.glb",
            "s3",
        )

        self.assertEqual("furniture", entry["group"])
        self.assertEqual("dining_chair", entry["category"])
        self.assertEqual("dining_chair_002", entry["asset_id"])

    def test_wall_and_ground_textures_are_surface_assets(self):
        wall = _entry("assets/textures/walls/brick_wall_diff_2k.jpg", "s3")
        ground = _entry("assets/textures/grounds/leafy_grass_diff_1k.jpg", "s3")

        self.assertEqual(("wall_finish", "texture"), (wall["group"], wall["kind"]))
        self.assertEqual(("ground_finish", "texture"), (ground["group"], ground["kind"]))

    def test_catalog_uses_s3_inventory_instead_of_frontend_placeholders(self):
        keys = [
            "assets/furniture/bedroom/beds/bed_03.glb",
            "assets/furniture/dining_room/dining_chairs/dining_chair_002.glb",
        ]
        with patch("utils.asset_catalog._s3_keys", return_value=keys):
            assets, source = list_uploaded_assets()

        self.assertEqual("s3", source)
        self.assertEqual({"bed_03", "dining_chair_002"}, {item["id"] for item in assets})

    def test_legacy_s3_copy_does_not_duplicate_same_uploaded_asset(self):
        keys = [
            "assets/furniture/dining_room/dining_chair_001.glb",
            "assets/furniture/dining_room/dining_chairs/dining_chair_001.glb",
            "assets/furniture/dining_room/dining_chairs/dining_chair_002.glb",
        ]
        with patch("utils.asset_catalog._s3_keys", return_value=keys):
            assets, _ = list_uploaded_assets()

        self.assertEqual(["dining_chair_001", "dining_chair_002"], [item["id"] for item in assets])
        chair_one = next(item for item in assets if item["id"] == "dining_chair_001")
        self.assertIn("/dining_chairs/", chair_one["s3_key"])

    @patch("routes.chat.browser_url", return_value="https://assets.example/chair.glb")
    @patch("routes.chat.list_uploaded_assets")
    def test_authenticated_catalog_route_returns_browser_ready_uploaded_asset(
        self, list_assets_mock, _browser_url_mock
    ):
        entry = _entry(
            "assets/furniture/dining_room/dining_chairs/dining_chair_002.glb",
            "s3",
        )
        list_assets_mock.return_value = ([entry], "s3")
        app = Flask(__name__)
        app.register_blueprint(chat_bp, url_prefix="/api")
        client = app.test_client()
        token = generate_token(ObjectId(), "catalog@example.com")

        response = client.get(
            "/api/assets/catalog",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertEqual("s3", payload["source"])
        self.assertEqual("dining_chair_002", payload["assets"][0]["id"])
        self.assertEqual("https://assets.example/chair.glb", payload["assets"][0]["model_path"])


if __name__ == "__main__":
    unittest.main()

