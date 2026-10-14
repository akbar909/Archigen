"""Print world-space bounds for named objects in an exported GLB."""

import argparse
import sys

import bpy
import mathutils


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--filter", default="")
    options = parser.parse_args(args)

    bpy.ops.import_scene.gltf(filepath=options.input)
    bpy.context.view_layer.update()
    query = options.filter.lower()
    for obj in bpy.context.scene.objects:
        if query and query not in obj.name.lower():
            continue
        meshes = [item for item in [obj] + list(obj.children_recursive) if item.type == "MESH"]
        points = [
            item.matrix_world @ mathutils.Vector(corner)
            for item in meshes
            for corner in item.bound_box
        ]
        if not points:
            continue
        bounds = (
            min(point.x for point in points),
            min(point.y for point in points),
            min(point.z for point in points),
            max(point.x for point in points),
            max(point.y for point in points),
            max(point.z for point in points),
        )
        print(
            "AUDIT",
            obj.name,
            "location",
            tuple(round(value, 3) for value in obj.location),
            "bounds",
            tuple(round(value, 3) for value in bounds),
        )


if __name__ == "__main__":
    main()
