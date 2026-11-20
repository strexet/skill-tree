"""Capture immutable Blender geometry for a static asset texture task."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

import bpy


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_hash(path):
    result = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def inspect_scene():
    scenes = list(bpy.data.scenes)
    if len(scenes) != 1 or bpy.data.libraries or bpy.data.actions or bpy.data.armatures:
        raise ValueError("Static capture requires one local scene. Use the appropriate rigged asset lock for animation.")
    scene = scenes[0]
    objects = sorted(scene.objects, key=lambda obj: obj.name)
    if not any(obj.type == "MESH" for obj in objects):
        raise ValueError("Static capture needs at least one mesh")
    sections = {key: {} for key in ("geometry", "uv", "weights", "rig", "pose", "animation", "material_assignments")}
    for obj in objects:
        if obj.type not in {"MESH", "EMPTY", "CAMERA", "LIGHT"} or (
                obj.animation_data or obj.constraints or obj.modifiers or obj.instance_type != "NONE"):
            raise ValueError(f"Unsupported static lock object or deformation: {obj.name}")
        sections["pose"][obj.name] = {
            "type": obj.type, "world": [list(row) for row in obj.matrix_world],
            "parent": obj.parent.name if obj.parent else None,
        }
        if obj.type != "MESH":
            continue
        mesh = obj.data
        if mesh.shape_keys or mesh.animation_data:
            raise ValueError(f"Unsupported mesh deformation: {obj.name}")
        sections["geometry"][obj.name] = {
            "vertices": [list(vertex.co) for vertex in mesh.vertices],
            "edges": [[*edge.vertices, edge.use_edge_sharp] for edge in mesh.edges],
            "faces": [[*face.vertices, face.use_smooth] for face in mesh.polygons],
            "normals": [list(normal.vector) for normal in mesh.corner_normals],
        }
        sections["uv"][obj.name] = {
            layer.name: [list(value.vector) for value in layer.uv] for layer in mesh.uv_layers
        }
        sections["weights"][obj.name] = {
            "groups": [group.name for group in obj.vertex_groups],
            "vertices": [[(group.group, group.weight) for group in vertex.groups] for vertex in mesh.vertices],
        }
        sections["material_assignments"][obj.name] = {
            "slots": [(slot.link, slot.material.name if slot.material else None) for slot in obj.material_slots],
            "faces": [face.material_index for face in mesh.polygons],
        }
    return {key: digest(value) for key, value in sections.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    path = args.source.resolve(strict=True)
    before = file_hash(path)
    bpy.ops.wm.open_mainfile(filepath=str(path), use_scripts=False, load_ui=False)
    bpy.context.view_layer.update()
    sections = inspect_scene()
    if before != file_hash(path):
        raise ValueError("Blender source changed while capturing geometry")
    report = {"schema": 1, "kind": "texture-lock-capture", "scope": "art-workshop-static",
              "status": "passed", "source": {"name": path.name, "sha256": before},
              "blender_version": bpy.app.version_string, "blender_build": bpy.app.build_hash.decode("ascii"),
              "fingerprints": sections}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    main()
