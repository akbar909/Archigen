"""
export_glb.py
=============
Module to export the generated 3D architectural scene to an optimized
GLB / glTF 2.0 binary file for consumption in React / Three.js frontends.

Designed for Headless Blender execution (bpy).
"""

import os
import sys
from typing import Optional

try:
    import bpy
except ImportError:
    bpy = None


def export_scene_to_glb(
    output_path: str,
    export_materials: bool = True,
    apply_modifiers: bool = True,
    use_draco: bool = False
) -> str:
    """
    Exports the active Blender scene to a web-optimized GLB file.

    Args:
        output_path: Target path for .glb file.
        export_materials: Include PBR materials and embedded textures.
        apply_modifiers: Bake modifiers (Booleans, Subdivisions, Bevels) into exported meshes.
        use_draco: Use Draco geometry compression (requires Draco decoder in Three.js).

    Returns:
        Absolute path to exported GLB file.
    """
    if bpy is None:
        raise RuntimeError("Blender environment (bpy) is required to run export_glb.")

    # Ensure output directory exists
    output_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(output_dir, exist_ok=True)

    if not output_path.lower().endswith(".glb"):
        output_path += ".glb"

    print(f"[EXPORT] Exporting scene to GLB: {output_path}")

    # glTF exporter parameters optimized for Three.js
    export_kwargs = {
        "filepath": output_path,
        "export_format": "GLB",
        "export_apply": apply_modifiers,
        "export_materials": "EXPORT" if export_materials else "NONE",
        "export_colors": True,
        "export_cameras": False,
        "export_lights": True,  # Keep ambient/point lights if defined in scene
        "export_yup": True,     # glTF / Three.js standard Y-up coordinate orientation
        "export_draco_mesh_compression_enable": use_draco,
    }

    try:
        bpy.ops.export_scene.gltf(**export_kwargs)
        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"[EXPORT] Successfully generated GLB ({file_size_mb:.2f} MB): {output_path}")
        return output_path
    except Exception as e:
        print(f"[ERROR] Failed to export GLB: {e}")
        raise


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = sys.argv[-1]
        if target.endswith(".glb"):
            export_scene_to_glb(target)
    else:
        print("ArchGen GLB Export utility loaded.")
