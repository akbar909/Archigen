import os
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BLENDER_SCRIPTS = os.path.join(PROJECT_ROOT, "blender", "scripts")
if BLENDER_SCRIPTS not in sys.path:
    sys.path.insert(0, BLENDER_SCRIPTS)

from generate_house import (  # noqa: E402
    _select_door_model_path,
    _select_house_wall_config,
    _wall_specific_override,
)


class BlenderStyleDefaultsTests(unittest.TestCase):
    def test_one_dominant_wall_style_is_used_for_the_house(self):
        rooms = [
            {"walls": {"pattern": "brick", "color": [0.4, 0.2, 0.1]}},
            {"walls": {"pattern": "plain", "color": [1.0, 1.0, 1.0]}},
            {"walls": {"pattern": "brick", "color": [0.5, 0.3, 0.2]}},
        ]
        self.assertEqual(
            {"pattern": "brick", "color": [0.4, 0.2, 0.1]},
            _select_house_wall_config(rooms),
        )

    def test_building_wall_style_and_per_wall_override_are_explicit(self):
        configured = {"pattern": "painted", "color": "#123456"}
        selected = _select_house_wall_config([], configured)
        self.assertEqual("painted", selected["pattern"])
        self.assertEqual("brick", _select_house_wall_config([], "brick")["pattern"])
        self.assertEqual({}, _wall_specific_override({"connected_rooms": ["living_01"]}))
        self.assertEqual(
            "wood_panel",
            _wall_specific_override({"material_override": {"pattern": "wood_panel"}})["pattern"],
        )

    def test_one_default_door_is_used_unless_opening_requests_another(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("door_standard.glb", "door_standard_02.glb", "door_standard_03.glb"):
                Path(directory, name).touch()

            self.assertEqual(
                "door_standard.glb",
                os.path.basename(_select_door_model_path(directory)),
            )
            self.assertEqual(
                "door_standard_03.glb",
                os.path.basename(_select_door_model_path(directory, "door_standard_03")),
            )
            self.assertEqual(
                "door_standard.glb",
                os.path.basename(_select_door_model_path(directory, "missing_door")),
            )


if __name__ == "__main__":
    unittest.main()
