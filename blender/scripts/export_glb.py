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
    use_draco: bool = False
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
        # Modifiers are baked explicitly below while their boolean cutters are
        # still present. glTF's export_apply also rebakes imported empty-root
        # hierarchies and shifts door/gate meshes away from their floor-level
        # origins, so it must remain disabled.
        "export_apply": False,
        "export_materials": "EXPORT" if export_materials else "NONE",
        "export_colors": False,      # Materials use PBR shaders, vertex colors add redundant byte overhead
        "export_animations": False,  # Static architectural geometry has no skeletal/transform animations
        "export_cameras": False,
        "export_lights": True,       # Keep ambient/point lights if defined in scene
        "export_yup": True,          # glTF / Three.js standard Y-up coordinate orientation
        "export_extras": True,       # Preserve custom object metadata for Three.js (room_id, floor_level)
        "export_draco_mesh_compression_enable": use_draco,
        "export_draco_mesh_compression_level": 5,
        "export_draco_position_quantization": 14,
        "export_draco_normal_quantization": 10,
        "export_draco_texcoord_quantization": 12,
    }

    # 1. Explicitly apply all modifiers (Boolean cuts) while target cutter objects still exist
    for obj in list(bpy.data.objects):
        if obj.type == 'MESH' and len(obj.modifiers) > 0:
            try:
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj
                for mod in list(obj.modifiers):
                    try:
                        bpy.ops.object.modifier_apply(modifier=mod.name)
                    except Exception as mod_err:
                        print(f"[WARN] Modifier {mod.name} apply failed on {obj.name}: {mod_err}")
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

    # 3. Downsample oversized 4K/2K textures to web-optimized 1024px resolution
    # Reduces GLB file size from 250MB+ down to ~15-20MB for fast 1-second web loading
    for img in list(bpy.data.images):
        try:
            w, h = img.size[0], img.size[1]
            if w > 1024 or h > 1024:
                scale = min(1024.0 / float(w), 1024.0 / float(h))
                new_w = max(int(w * scale), 64)
                new_h = max(int(h * scale), 64)
                print(f"[OPTIMIZE] Resizing texture '{img.name}' from {w}x{h} to {new_w}x{new_h}")
                img.scale(new_w, new_h)
        except Exception as img_err:
            print(f"[WARN] Failed to downsample image {img.name}: {img_err}")

    import gc
    gc.collect()

    try:
        # Blender's glTF operator options change between releases (for example
        # export_colors was removed in 5.x).  Filter optional flags against the
        # running operator schema so the worker remains version-compatible.
        supported = {
            prop.identifier for prop in bpy.ops.export_scene.gltf.get_rna_type().properties
        }
        compatible_kwargs = {key: value for key, value in export_kwargs.items() if key in supported}
        removed = sorted(set(export_kwargs) - set(compatible_kwargs))
        if removed:
            print(f"[EXPORT] Ignoring unsupported Blender options: {', '.join(removed)}")
        bpy.ops.export_scene.gltf(**compatible_kwargs)
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
