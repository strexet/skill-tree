"""Capture anatomical bind lengths in the isolated approved detail fixture."""
from hashlib import sha256
import json
from pathlib import Path
import sys

import bpy


folder = Path(sys.argv[-1]).resolve()
rest = folder / "stride-rest.blend"
rig = bpy.data.objects["Fixture"]
rig.animation_data_clear()
for pose in rig.pose.bones:
    pose.rotation_euler = (0, 0, 0)
bpy.ops.wm.save_as_mainfile(filepath=str(rest), compress=True)
bpy.ops.wm.open_mainfile(filepath=str(rest))
rig = bpy.data.objects["Fixture"]
lengths = {bone.name: ((rig.matrix_world @ bone.head_local) - (rig.matrix_world @ bone.tail_local)).length
           for bone in rig.data.bones if bone.use_deform}
report = {"schema": 1, "kind": "biological-bind-lengths",
          "source": {"path": rest.name, "sha256": sha256(rest.read_bytes()).hexdigest()},
          "rest-lengths-m": lengths}
(folder / "bind-lengths.json").write_text(json.dumps(report, indent=2) + "\n")
