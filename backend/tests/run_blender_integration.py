"""Headless Blender integration matrix for the canonical ArchiGen pipeline."""

import argparse
import copy
import json
import os
import subprocess
import sys
import tempfile


BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(BACKEND_ROOT)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from utils.architectural_preflight import validate_and_repair_design
from utils.architectural_refinement import apply_targeted_refinement
from utils.blender_service import adapt_gemini_to_blender_layout
from utils.layout_engine import ArchitecturalLayoutEngine


SCENARIOS = [
    ("reported_11x12_single_floor", ["living_room", "kitchen", "bedroom", "bathroom"], (11, 12), 1),
    ("multi_bed_bath", ["living_room", "kitchen", "bedroom", "bedroom", "bedroom", "bathroom", "bathroom"], (18, 22), 1),
    ("narrow_corridor", ["foyer", "corridor", "living_room", "kitchen", "bedroom", "bathroom"], (12, 22), 1),
    ("same_wall_openings", ["bedroom", "bathroom"], (12, 14), 1),
    ("multi_floor_stairs", ["living_room", "kitchen", "bedroom", "bedroom", "master_bedroom", "bathroom", "master_bathroom"], (16, 20), 2),
    ("varied_furniture", ["living_room", "dining_room", "kitchen", "home_office", "bedroom", "bathroom"], (17, 20), 1),
    ("three_floor_vertical_core", ["living_room", "kitchen", "bedroom", "bedroom", "bedroom", "bathroom", "bathroom", "home_office"], (18, 24), 3),
    ("four_floor_vertical_core", ["living_room", "kitchen", "bedroom", "bedroom", "bedroom", "bathroom", "bathroom", "home_office"], (18, 24), 4),
    ("wide_plot_variant", ["garage", "living_room", "dining_room", "kitchen", "bedroom", "bathroom"], (22, 16), 1),
    ("deterministic_repeat", ["living_room", "kitchen", "bedroom", "bathroom"], (14, 18), 1),
]


def make_layout(name, room_types, plot, floors):
    requirements = {
        "project_name": name,
        "plot": {"width": plot[0], "depth": plot[1]},
        "floors": floors,
        "rooms": [{"id": f"{name}_room_{index}", "type": room_type} for index, room_type in enumerate(room_types, 1)],
    }
    design = ArchitecturalLayoutEngine(unit="meters").generate_layout(requirements)
    if name == "same_wall_openings":
        floor = design["floors"][0]
        source = floor["doors"][0]
        window = copy.deepcopy(source)
        window.update({"id": "same_wall_window", "type": "window", "width": 1.0, "height": 1.1, "sill_height": 0.9})
        floor["windows"].append(window)
    canonical, report = validate_and_repair_design(design, repair=True)
    if report["critical_errors"]:
        raise AssertionError(f"{name}: preflight failed: {report['critical_errors']}")
    if name == "reported_11x12_single_floor":
        canonical, refinement = apply_targeted_refinement(
            canonical,
            "room one window from bedroom which is back side of bed",
        )
        if not canonical or refinement["errors"]:
            raise AssertionError(f"{name}: refinement failed: {refinement}")
    layout = adapt_gemini_to_blender_layout(canonical, project_id=f"integration_{name}", version_num=1)
    layout["house_id"] = f"integration_{name}"
    return layout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender", required=True)
    parser.add_argument("--limit", type=int, default=len(SCENARIOS))
    parser.add_argument("--start", type=int, default=1)
    args = parser.parse_args()
    generate_script = os.path.join(REPO_ROOT, "blender", "scripts", "generate_house.py")
    end = max(1, min(args.limit, len(SCENARIOS)))
    start = max(0, min(args.start - 1, end - 1))
    scenarios = SCENARIOS[start:end]

    with tempfile.TemporaryDirectory(prefix="archigen_blender_test_") as temp_dir:
        for index, (name, rooms, plot, floors) in enumerate(scenarios, start + 1):
            layout = make_layout(name, rooms, plot, floors)
            input_path = os.path.join(temp_dir, f"{name}.json")
            output_path = os.path.join(temp_dir, f"{name}.glb")
            with open(input_path, "w", encoding="utf-8") as handle:
                json.dump(layout, handle)
            print(f"[{index}/{end}] {name}: Blender generation started", flush=True)
            process = subprocess.run(
                [args.blender, "--background", "--factory-startup", "--python-exit-code", "1", "--python", generate_script,
                 "--", "--input", input_path, "--output", output_path],
                capture_output=True,
                text=True,
                timeout=240,
            )
            if process.returncode != 0:
                raise RuntimeError(f"{name}: Blender failed\n{process.stdout[-3000:]}\n{process.stderr[-3000:]}")
            if not os.path.isfile(output_path) or os.path.getsize(output_path) < 1000:
                raise RuntimeError(f"{name}: GLB was not produced")
            expected = layout["expected_inventory"]["furniture_count"]
            marker = f"Verified furniture inventory: {expected}/{expected}"
            if marker not in process.stdout:
                raise RuntimeError(f"{name}: scene inventory was not verified\n{process.stdout[-3000:]}")
            print(f"[{index}/{end}] {name}: PASS ({os.path.getsize(output_path)} bytes, {expected} furniture)", flush=True)
    print(f"All {len(scenarios)} selected Blender integration scenarios passed.", flush=True)


if __name__ == "__main__":
    main()
