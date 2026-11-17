"""Create and inspect a Blender rig for ArtWorkshop length validation."""
from hashlib import sha256
import json
from math import radians
from pathlib import Path
import sys

import bpy
from mathutils import Vector


folder = Path(sys.argv[-1]).resolve()
folder.mkdir(exist_ok=True)
scene = bpy.context.scene
for obj in list(scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

armature = bpy.data.armatures.new("Fixture limb rig")
rig = bpy.data.objects.new("Fixture", armature)
scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
rig.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
segments = {}
for side, x in (("left", -0.23), ("right", 0.23)):
    upper = None
    for index, name in enumerate(("upper", "lower")):
        segment = side + "-" + name
        bone = armature.edit_bones.new(segment)
        bone.head = (x, 0, 1.25 - index * 0.5)
        bone.tail = (x, 0, 0.75 - index * 0.5)
        if upper is not None:
            bone.parent = upper
            bone.use_connect = True
        upper = bone
        segments[segment] = {"bone": segment, "head": segment + "-head",
                             "tail": segment + "-tail", "bind-length-m": 0.5}
bpy.ops.object.mode_set(mode="OBJECT")

for frame, swing in ((1, -25), (3, 25), (5, -25)):
    for segment in segments:
        side, limb = segment.split("-")
        pose = rig.pose.bones[segment]
        pose.rotation_mode = "XYZ"
        angle = swing if limb == "upper" else 28 - swing / 2
        if side == "right":
            angle = -angle
        pose.rotation_euler = (radians(angle), 0, 0)
        pose.keyframe_insert(data_path="rotation_euler", frame=frame)
rig.animation_data.action.name = "Stride"
scene.frame_start, scene.frame_end = 1, 5
scene.render.fps = 30

markers = {}
limbs = {}
for segment, row in segments.items():
    for field, endpoint in (("head", 0), ("tail", 1)):
        marker = bpy.data.objects.new(row[field], None)
        scene.collection.objects.link(marker)
        location = marker.constraints.new("COPY_LOCATION")
        location.target = rig
        location.subtarget = segment
        location.head_tail = endpoint
        markers[row[field]] = marker
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=1)
    limb = bpy.context.object
    limb.name = "Visible " + segment
    limb.color = (0.13, 0.64, 0.85, 1) if segment.startswith("left") else (0.86, 0.42, 0.17, 1)
    limb.scale = (0.085, 0.085, 0.265)
    limbs[segment] = limb


def set_tick(tick):
    scene.frame_set(tick // 4, subframe=(tick % 4) / 4)
    return bpy.context.evaluated_depsgraph_get()


for tick in range(4, 21):
    graph = set_tick(tick)
    evaluated = rig.evaluated_get(graph)
    for segment, obj in limbs.items():
        pose = evaluated.pose.bones[segment]
        obj.location = (pose.head + pose.tail) / 2
        obj.rotation_euler = (pose.tail - pose.head).to_track_quat("Z", "Y").to_euler()
        obj.keyframe_insert(data_path="location", frame=tick / 4)
        obj.keyframe_insert(data_path="rotation_euler", frame=tick / 4)

bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1, location=(0, 0, 1.33))
body = bpy.context.object
body.name = "Fixture pelvis"
body.scale = (0.38, 0.27, 0.17)
body.color = (0.50, 0.54, 0.62, 1)
bpy.ops.object.camera_add(location=(3.5, -5, 2.5))
camera = bpy.context.object
camera.rotation_euler = (Vector((0, 0, 0.76)) - camera.location).to_track_quat("-Z", "Y").to_euler()
camera.data.type = "ORTHO"
camera.data.ortho_scale = 2.05
scene.camera = camera
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.color_type = "OBJECT"
scene.display.shading.show_cavity = True
scene.display.shading.background_type = "WORLD"
scene.world.color = (0.13, 0.15, 0.18)
scene.render.resolution_x, scene.render.resolution_y = 400, 400
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
set_tick(4)
blend = folder / "stride.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)

bpy.ops.wm.open_mainfile(filepath=str(blend))
scene = bpy.context.scene
rig = bpy.data.objects["Fixture"]
bpy.ops.object.select_all(action="DESELECT")
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
clip = folder / "stride.fbx"
bpy.ops.export_scene.fbx(filepath=str(clip), use_selection=True, object_types={"ARMATURE"},
                         bake_anim_use_nla_strips=False, bake_anim_use_all_actions=False, add_leaf_bones=False)


def pin(path):
    return {"path": path.name, "sha256": sha256(path.read_bytes()).hexdigest()}


samples = []
for tick in range(4, 21):
    graph = set_tick(tick)
    evaluated = rig.evaluated_get(graph)
    lengths = {}
    for name, row in segments.items():
        pose = evaluated.pose.bones[row["bone"]]
        ends = [bpy.data.objects[row[field]].evaluated_get(graph).matrix_world.translation
                for field in ("head", "tail")]
        lengths[name] = {"joint-m": (ends[0] - ends[1]).length,
                         "bone-m": ((evaluated.matrix_world @ pose.head) - (evaluated.matrix_world @ pose.tail)).length}
    samples.append({"tick": tick, "lengths": lengths})
measurements = {"schema": 1, "kind": "biological-segment-lengths", "scene": scene.name,
                "blend": pin(blend), "clip": pin(clip), "segments": segments,
                "clips": {"walk": {"action": rig.animation_data.action.name, "samples": samples}}}
(folder / "lengths.json").write_text(json.dumps(measurements, indent=2) + "\n")
visuals = {}
for frame in range(1, 6):
    scene.frame_set(frame)
    image = folder / f"stride-frame-{frame}.png"
    scene.render.filepath = str(image)
    bpy.ops.render.render(write_still=True)
    visuals[str(frame)] = pin(image)
(folder / "visuals.json").write_text(json.dumps({"schema": 1, "blend": pin(blend), "clip": pin(clip),
                                                "measurements": pin(folder / "lengths.json"),
                                                "shots": visuals}, indent=2) + "\n")
