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
    # pyrefly: ignore [missing-import]
    import bpy
except ImportError:
    bpy = None


def export_scene_to_glb(
    output_path: str,
    export_materials: bool = True,
    apply_modifiers: bool = True,
    use_draco: bool = True
) -> str:
    """
    Exports the active Blender scene to a web-optimized GLB file with Draco compression.

    Args:
        output_path: Target path for .glb file.
        export_materials: Include PBR materials and embedded textures.
        apply_modifiers: Bake modifiers (Booleans, Subdivisions, Bevels) into exported meshes.
        use_draco: Use Draco geometry compression (75-85% smaller file size).

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

    print(f"[EXPORT] Exporting scene to GLB (Draco={use_draco}): {output_path}")

    # glTF exporter parameters optimized for Three.js & fast web transmission
    export_kwargs = {
        "filepath": output_path,
        "export_format": "GLB",
        "export_apply": apply_modifiers,
        "export_materials": "EXPORT" if export_materials else "NONE",
        "export_colors": False,      # Materials use PBR shaders, vertex colors add redundant byte overhead
        "export_animations": False,  # Static architectural geometry has no skeletal/transform animations
        "export_cameras": False,
        "export_lights": True,       # Keep ambient/point lights if defined in scene
        "export_yup": True,          # glTF / Three.js standard Y-up coordinate orientation
        "export_draco_mesh_compression_enable": use_draco,
        "export_draco_mesh_compression_level": 7,
        "export_draco_position_quantization": 14,
        "export_draco_normal_quantization": 10,
        "export_draco_texcoord_quantization": 12,
    }

    # 1. Explicitly apply all modifiers (Boolean cuts) while target cutter objects still exist
    for obj in list(bpy.data.objects):
        if obj.type == 'MESH' and len(obj.modifiers) > 0:
            try:
                bpy.context.view_layer.objects.active = obj
                for mod in list(obj.modifiers):
                    bpy.ops.object.modifier_apply(modifier=mod.name)
            except Exception as e:
                print(f"[WARN] Modifier apply warning on {obj.name}: {e}")

    # 2. Clean up boolean cutters and temporary construction helpers before export
    objs_to_remove = [
        obj for obj in bpy.data.objects
        if obj.name.startswith(("_", "cutter", "baseboard", "cap"))
    ]
    for obj in objs_to_remove:
        try:
            bpy.data.objects.remove(obj, do_unlink=True)
        except Exception:
            pass

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
